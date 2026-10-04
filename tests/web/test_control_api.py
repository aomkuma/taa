"""Control API: commands for the user's own engines only, step-up, field rules, audit, results (TAA-805)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.clock import ManualClock
from app.core.ids import new_id
from app.storage.database import Database
from app.storage.models import AuditEvent, EngineCommandRow
from app.sync.stream import TOPICS, StreamLog
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, current_code, login, make_app, mutation_headers
from tests.web.test_auth import next_step

CONTROL_CODE = "246810"  # the engine's control TOTP: the cloud only carries it


class Rig:
    def __init__(self, app: FastAPI, client: TestClient, clock: ManualClock, mine: str, theirs: str) -> None:
        self.app, self.client, self.clock, self.mine, self.theirs = app, client, clock, mine, theirs

    def step_up(self) -> None:
        next_step(self.clock)
        resp = self.client.post(
            "/api/v1/auth/step-up",
            json={"code": current_code(self.clock)},
            headers=mutation_headers(self.client),
        )
        assert resp.status_code == 200

    def send(self, body: dict[str, Any], engine_id: str | None = None) -> Any:
        return self.client.post(
            f"/api/v1/engines/{engine_id or self.mine}/commands",
            json=body,
            headers=mutation_headers(self.client),
        )

    def get(self, route: str, engine_id: str | None = None) -> Any:
        return self.client.get(f"/api/v1/engines/{engine_id or self.mine}/{route}")


@pytest.fixture
def rig(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[Rig]:
    app = make_app(db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"})
    auth, registry = app.state.ctx.auth, app.state.ctx.engine.registry
    ids = []
    for name, role in (("alice", "OWNER"), ("bob", "SUBSCRIBER")):
        user = auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
        ids.append(registry.register(user, f"{name} pc", actor=name).engine_id)
    with TestClient(app, base_url="https://testserver") as client:
        assert login(client, clock, username="alice").status_code == 200
        r = Rig(app, client, clock, ids[0], ids[1])
        r.step_up()
        yield r


def audit(db: Database, event_type: str) -> list[AuditEvent]:
    with db.session() as sess:
        return list(sess.scalars(select(AuditEvent).where(AuditEvent.event_type == event_type)))


def stored(db: Database, engine_id: str) -> list[EngineCommandRow]:
    with db.session() as sess:
        return list(sess.scalars(select(EngineCommandRow).where(EngineCommandRow.engine_id == engine_id)))


class TestQueue:
    def test_the_kill_switch_is_queued_audited_and_streamed(self, rig: Rig, db: Database) -> None:
        resp = rig.send({"type": "KILL_SWITCH_ACTIVATE", "reason": " news spike "})
        assert resp.status_code == 202
        body = resp.json()
        assert body["type"] == "KILL_SWITCH_ACTIVATE" and body["status"] == "QUEUED"
        assert body["params"] == {"reason": "news spike"} and body["created_by"] == "alice"
        assert body["result"] == {} and body["completed_at"] is None and "totp" not in body
        [event] = audit(db, "COMMAND_QUEUED")
        assert event.actor == "alice" and event.payload["command_id"] == body["id"]
        assert event.payload["engine_id"] == rig.mine and event.payload["params"] == {"reason": "news spike"}
        [streamed] = StreamLog(db, rig.clock).read(rig.mine, 0, TOPICS, 10)[0]
        assert (streamed.topic, streamed.type, streamed.key) == ("status", "command", body["id"])

    @pytest.mark.parametrize(
        "body",
        [
            {"type": "STRATEGY_DISABLE", "strategy": "example_trend_pullback"},
            {"type": "STRATEGY_DISABLE", "strategy": "example_trend_pullback", "reason": "drawdown"},
            {"type": "RESYNC"},
            {"type": "RESCAN_SUITABILITY"},
            {"type": "POSITION_CLOSE", "ticket": 7, "code": CONTROL_CODE},
            {"type": "FLATTEN_ALL", "reason": "leaving", "code": CONTROL_CODE},
        ],
    )
    def test_every_allowed_command(self, rig: Rig, body: dict[str, Any]) -> None:
        resp = rig.send(body)
        assert resp.status_code == 202 and resp.json()["type"] == body["type"]
        assert "code" not in resp.json()["params"]

    def test_the_engine_code_is_carried_but_never_shown(self, rig: Rig, db: Database) -> None:
        sent = rig.send({"type": "POSITION_CLOSE", "ticket": 7, "code": CONTROL_CODE}).json()
        assert sent["params"] == {"ticket": 7}
        [row] = stored(db, rig.mine)
        assert row.totp == CONTROL_CODE  # the engine needs it (and clears it on the answer)
        [delivered] = rig.app.state.ctx.engine.commands.pending(rig.mine)
        assert delivered["totp"] == CONTROL_CODE
        for text in (
            rig.get("commands").text,
            rig.get(f"commands/{sent['id']}").text,
            str(audit(db, "COMMAND_QUEUED")[0].payload),
            str(StreamLog(db, rig.clock).read(rig.mine, 0, TOPICS, 10)[0][0].item),
        ):
            assert CONTROL_CODE not in text

    @pytest.mark.parametrize(
        ("body", "status", "code"),
        [
            ({"type": "KILL_SWITCH_ACTIVATE"}, 400, "invalid_command"),
            ({"type": "KILL_SWITCH_ACTIVATE", "reason": "   "}, 400, "invalid_command"),
            ({"type": "KILL_SWITCH_ACTIVATE", "reason": "x", "code": CONTROL_CODE}, 400, "invalid_command"),
            ({"type": "RESYNC", "ticket": 1}, 400, "invalid_command"),
            ({"type": "POSITION_CLOSE", "ticket": 7}, 400, "invalid_command"),
            ({"type": "FLATTEN_ALL", "code": CONTROL_CODE}, 400, "invalid_command"),
            ({"type": "POSITION_CLOSE", "ticket": 7, "code": "12345"}, 422, "invalid_request"),
            ({"type": "POSITION_CLOSE", "ticket": 0, "code": CONTROL_CODE}, 422, "invalid_request"),
            ({"type": "KILL_SWITCH_RELEASE"}, 422, "invalid_request"),
            ({"type": "BREAKER_RESET"}, 422, "invalid_request"),
            ({"type": "RESYNC", "limits": {"risk": 5}}, 422, "invalid_request"),
        ],
    )
    def test_unusable_bodies_queue_nothing(
        self, rig: Rig, db: Database, body: dict[str, Any], status: int, code: str
    ) -> None:
        resp = rig.send(body)
        assert resp.status_code == status and resp.json()["error"]["code"] == code
        assert stored(db, rig.mine) == []

    def test_a_step_up_and_csrf_are_required(self, rig: Rig, db: Database) -> None:
        url = f"/api/v1/engines/{rig.mine}/commands"
        body = {"type": "KILL_SWITCH_ACTIVATE", "reason": "x"}
        resp = rig.client.post(url, json=body)
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "origin_not_allowed"
        rig.clock.advance(5 * 60)  # the step-up window ends
        assert rig.send(body).json()["error"]["code"] == "step_up_required"
        assert stored(db, rig.mine) == []

    def test_a_revoked_engine_takes_no_commands(self, rig: Rig, db: Database) -> None:
        rig.app.state.ctx.engine.registry.revoke(rig.mine, actor="alice")
        resp = rig.send({"type": "RESYNC"})
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "engine_revoked"
        assert rig.get("commands").status_code == 200  # its history stays readable


class TestOwnership:
    def test_another_users_engine_is_not_found(self, rig: Rig, db: Database) -> None:
        theirs = rig.app.state.ctx.engine.commands.enqueue(rig.theirs, "RESYNC", created_by="bob")
        for resp in (
            rig.send({"type": "KILL_SWITCH_ACTIVATE", "reason": "x"}, rig.theirs),
            rig.get("commands", rig.theirs),
            rig.get(f"commands/{theirs['id']}", rig.theirs),
        ):
            assert resp.status_code == 404 and resp.json()["error"]["code"] == "engine_not_found"
        resp = rig.get(f"commands/{theirs['id']}")  # through my engine's path
        assert resp.status_code == 404 and resp.json()["error"]["code"] == "command_not_found"
        assert len(stored(db, rig.theirs)) == 1 and audit(db, "COMMAND_QUEUED") == []

    def test_a_subscriber_controls_the_engine_they_own(self, rig: Rig) -> None:
        rig.client.cookies.clear()
        rig.clock.advance(30)
        assert login(rig.client, rig.clock, username="bob").status_code == 200
        rig.step_up()
        assert rig.send({"type": "KILL_SWITCH_ACTIVATE", "reason": "x"}, rig.theirs).status_code == 202
        assert rig.send({"type": "KILL_SWITCH_ACTIVATE", "reason": "x"}, rig.mine).status_code == 404


class TestHistory:
    def test_results_reach_the_command_audit_and_stream(self, rig: Rig, db: Database) -> None:
        sent = rig.send({"type": "FLATTEN_ALL", "reason": "leaving", "code": CONTROL_CODE}).json()
        ctx = rig.app.state.ctx
        ctx.engine.commands.pending(rig.mine)  # the engine's long poll
        assert rig.get(f"commands/{sent['id']}").json()["status"] == "DELIVERED"
        now = rig.clock.now_utc().isoformat()
        doc = {
            "schema": 1,
            "engine_id": rig.mine,
            "sent_at_utc": now,
            "events": [
                {
                    "event_id": new_id(),
                    "type": "command_result",
                    "occurred_at_utc": now,
                    "payload": {
                        "command_id": sent["id"],
                        "type": "FLATTEN_ALL",
                        "outcome": "EXECUTED",
                        "reason": "",
                        "detail": "kill switch active (FLATTEN)",
                        "at": now,
                    },
                }
            ],
        }
        assert ctx.engine.ingest.ingest(rig.mine, doc).accepted == 1
        detail = rig.get(f"commands/{sent['id']}").json()
        assert detail["status"] == "EXECUTED" and detail["result"]["detail"] == "kill switch active (FLATTEN)"
        assert detail["completed_at"] == now
        [event] = audit(db, "COMMAND_RESULT")
        assert event.payload["command_id"] == sent["id"] and event.payload["result"]["outcome"] == "EXECUTED"
        streamed = StreamLog(db, rig.clock).read(rig.mine, 0, TOPICS, 10)[0]
        assert [(e.key, e.item["status"]) for e in streamed] == [
            (sent["id"], "QUEUED"),
            (sent["id"], "EXECUTED"),
        ]
        [row] = stored(db, rig.mine)
        assert row.totp is None

    def test_the_list_pages_filters_and_shows_expiry(self, rig: Rig) -> None:
        ids = []
        for _ in range(3):
            ids.append(rig.send({"type": "RESYNC"}).json()["id"])
            rig.clock.advance(1)
        page = rig.get("commands?limit=2").json()
        assert [c["id"] for c in page["items"]] == ids[:0:-1] and page["next_cursor"]
        rest = rig.get(f"commands?limit=2&cursor={page['next_cursor']}").json()
        assert [c["id"] for c in rest["items"]] == ids[:1] and rest["next_cursor"] is None
        rig.clock.advance(121)
        assert [c["status"] for c in rig.get("commands").json()["items"]] == ["EXPIRED"] * 3
        assert rig.get("commands?status=QUEUED").json()["items"] == []
        assert rig.get("commands?status=NOPE").status_code == 422
        assert rig.get("commands?cursor=garbage").json()["error"]["code"] == "invalid_query"
