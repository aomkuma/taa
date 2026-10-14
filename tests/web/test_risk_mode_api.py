"""The aggressive preset from the PWA (PLAN §A36): raising needs a step-up and an own engine that reports the
preset available; lowering needs only CSRF; the plain preferences PUT can never raise it."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.clock import ManualClock
from app.storage.database import Database
from app.storage.models import AuditEvent, EngineHeartbeatRow
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, current_code, login, make_app, mutation_headers
from tests.web.test_auth import next_step

T = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
RAISE = {"risk_mode": "AGGRESSIVE", "aggressive_risk_percent": 7.5}


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

    def put_mode(self, body: dict[str, Any]) -> Any:
        return self.client.put(
            "/api/v1/advisory/preferences/risk-mode", json=body, headers=mutation_headers(self.client)
        )

    def prefs(self) -> dict[str, Any]:
        data: dict[str, Any] = self.client.get("/api/v1/advisory/preferences").json()
        return data

    def put_prefs(self, prefs: dict[str, Any]) -> Any:
        return self.client.put(
            "/api/v1/advisory/preferences", json=prefs, headers=mutation_headers(self.client)
        )


def beat(db: Database, engine_id: str, available: bool) -> None:
    high_risk = {"available": available, "reason": None if available else "HIGH_RISK_NOT_ENABLED"}
    payload = {"account": {"risk_limits": {"high_risk": high_risk}}}
    with db.session() as sess:
        sess.add(
            EngineHeartbeatRow(
                engine_id=engine_id,
                received_at=T,
                sent_at=T,
                run_id="r1",
                mode="PAPER",
                state="running",
                connected=True,
                market_open=True,
                watch_status="ONLINE",
                offline_reason="",
                payload=payload,
            )
        )


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
        yield Rig(app, client, clock, ids[0], ids[1])


def audit(db: Database) -> list[AuditEvent]:
    with db.session() as sess:
        return list(sess.scalars(select(AuditEvent).where(AuditEvent.event_type == "RISK_MODE_CHANGED")))


class TestRaise:
    def test_needs_a_step_up(self, rig: Rig, db: Database) -> None:
        beat(db, rig.mine, True)
        resp = rig.put_mode(RAISE | {"engine_id": rig.mine})
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "step_up_required"
        assert rig.prefs()["trading_profile"]["risk_mode"] == "STANDARD"

    def test_needs_an_engine_that_reports_the_preset(self, rig: Rig, db: Database) -> None:
        rig.step_up()
        assert rig.put_mode(RAISE).json()["error"]["code"] == "engine_required"
        beat(db, rig.mine, False)
        resp = rig.put_mode(RAISE | {"engine_id": rig.mine})
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "high_risk_unavailable"

    def test_someone_elses_engine_is_not_found(self, rig: Rig, db: Database) -> None:
        beat(db, rig.theirs, True)
        rig.step_up()
        resp = rig.put_mode(RAISE | {"engine_id": rig.theirs})
        assert resp.status_code == 404 and resp.json()["error"]["code"] == "engine_not_found"

    def test_with_step_up_and_an_available_engine(self, rig: Rig, db: Database) -> None:
        beat(db, rig.mine, True)
        rig.step_up()
        resp = rig.put_mode({"risk_mode": "AGGRESSIVE", "aggressive_risk_percent": 8, "engine_id": rig.mine})
        assert resp.status_code == 200, resp.json()
        profile = resp.json()["trading_profile"]
        assert profile["risk_mode"] == "AGGRESSIVE" and profile["aggressive_risk_percent"] == 8
        events = audit(db)
        assert len(events) == 1 and events[0].payload["raised"] is True

    def test_out_of_bounds_risk_is_refused(self, rig: Rig) -> None:
        rig.step_up()
        for pct in (4.9, 10.5):
            resp = rig.put_mode(
                {"risk_mode": "AGGRESSIVE", "aggressive_risk_percent": pct, "engine_id": rig.mine}
            )
            assert resp.status_code == 422


class TestLower:
    def test_lowering_needs_no_step_up(self, rig: Rig, db: Database) -> None:
        beat(db, rig.mine, True)
        rig.step_up()
        assert rig.put_mode(RAISE | {"engine_id": rig.mine}).status_code == 200
        rig.clock.advance(900)  # the step-up has expired
        lower = rig.put_mode({"risk_mode": "AGGRESSIVE", "aggressive_risk_percent": 5})
        assert lower.status_code == 200 and lower.json()["trading_profile"]["aggressive_risk_percent"] == 5
        back = rig.put_mode({"risk_mode": "STANDARD"})
        assert back.status_code == 200 and back.json()["trading_profile"]["risk_mode"] == "STANDARD"
        assert [e.payload["raised"] for e in audit(db)] == [True, False, False]


class TestPlainPut:
    def test_cannot_raise(self, rig: Rig) -> None:
        prefs = rig.prefs()
        prefs["trading_profile"]["risk_mode"] = "AGGRESSIVE"
        resp = rig.put_prefs(prefs)
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "risk_mode_locked"

    def test_keeps_and_lowers(self, rig: Rig, db: Database) -> None:
        beat(db, rig.mine, True)
        rig.step_up()
        assert rig.put_mode(RAISE | {"engine_id": rig.mine}).status_code == 200
        prefs = rig.prefs()
        prefs["trading_profile"]["style"] = 30
        assert rig.put_prefs(prefs).status_code == 200  # unchanged mode: fine
        prefs["trading_profile"]["aggressive_risk_percent"] = 9
        assert rig.put_prefs(prefs).json()["error"]["code"] == "risk_mode_locked"  # higher risk
        prefs["trading_profile"]["risk_mode"] = "STANDARD"
        assert rig.put_prefs(prefs).status_code == 200  # lower
