"""Engine management API: register, list, rotate, revoke; ownership, limits, rate limit, secrets once (TAA-811)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.clock import ManualClock
from app.storage.database import Database
from app.storage.models import AuditEvent
from app.web.engines import ISSUE_LIMIT, ISSUE_WINDOW, EngineRegistry
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, current_code, login, make_app, mutation_headers
from tests.web.test_auth import next_step

MULTI = DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"}


class Rig:
    def __init__(self, app: FastAPI, client: TestClient, clock: ManualClock) -> None:
        self.app, self.client, self.clock = app, client, clock

    @property
    def registry(self) -> EngineRegistry:
        registry: EngineRegistry = self.app.state.ctx.engine.registry
        return registry

    def login(self, username: str) -> None:
        self.client.cookies.clear()
        next_step(self.clock)
        assert login(self.client, self.clock, username=username).status_code == 200
        next_step(self.clock)
        resp = self.client.post(
            "/api/v1/auth/step-up",
            json={"code": current_code(self.clock)},
            headers=mutation_headers(self.client),
        )
        assert resp.status_code == 200

    def post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.client.post(
            f"/api/v1/engines{path}", json=body or {}, headers=mutation_headers(self.client)
        )

    def register(self, label: str = "home pc") -> Any:
        return self.post("", {"label": label})

    def engine_of(self, username: str, label: str = "pc") -> str:
        user = self.registry.user(username)
        return self.registry.register(user, label, actor="pytest").engine_id


def make_rig(db: Database, clock: ManualClock, static_dir: Path, env: dict[str, str]) -> Iterator[Rig]:
    app = make_app(db, clock, static_dir, env)
    for name, role in (("alice", "OWNER"), ("bob", "SUBSCRIBER")):
        app.state.ctx.auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
    with TestClient(app, base_url="https://testserver") as client:
        rig = Rig(app, client, clock)
        rig.login("alice")
        yield rig


@pytest.fixture
def rig(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[Rig]:
    yield from make_rig(db, clock, static_dir, MULTI)


@pytest.fixture
def rig_with(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[Callable[[dict[str, str]], Rig]]:
    """A rig with other settings (closed at teardown)."""
    with ExitStack() as stack:
        yield lambda env: stack.enter_context(contextmanager(make_rig)(db, clock, static_dir, env))


def audit(db: Database) -> list[AuditEvent]:
    with db.session() as sess:
        return list(sess.scalars(select(AuditEvent).where(AuditEvent.chain == "web")))


class TestRegister:
    def test_the_secret_is_issued_once(self, rig: Rig, db: Database) -> None:
        resp = rig.register("  home   pc ")
        assert resp.status_code == 201
        assert resp.headers["cache-control"] == "no-store" and resp.headers["pragma"] == "no-cache"
        body = resp.json()
        engine_id, secret = body["engine_id"], body["secret"]
        assert engine_id.startswith("eng_") and len(secret) >= 32
        assert body["cloud_base_url"] == "https://testserver"
        assert rig.registry.keys(engine_id) == (secret.encode(),)
        listed = rig.client.get("/api/v1/engines")
        [item] = listed.json()["items"]
        assert item["engine_id"] == engine_id and item["label"] == "home pc" and item["status"] == "ACTIVE"
        assert item["first_seen_at"] is None and item["rotation_pending"] is False and "owner" not in item
        texts = [listed.text, rig.client.get(f"/api/v1/engines/{engine_id}/status").text]
        texts += [str(e.payload) for e in audit(db)]
        assert all(secret not in t for t in texts)
        assert [e.event_type for e in audit(db) if e.event_type.startswith("ENGINE_")] == [
            "ENGINE_REGISTERED"
        ]

    def test_production_hands_out_the_public_origin(
        self, db: Database, clock: ManualClock, static_dir: Path
    ) -> None:
        env = MULTI | {"WEB_ENV": "production", "WEB_PUBLIC_ORIGIN": "https://taa.example.com"}
        app = make_app(db, clock, static_dir, env)
        app.state.ctx.auth.create_user("alice", PASSWORD, TOTP_SECRET, role="OWNER")
        with TestClient(app, base_url="https://testserver") as client:
            rig = Rig(app, client, clock)
            client.cookies.clear()
            next_step(clock)
            origin = "https://taa.example.com"
            assert login(client, clock, username="alice", origin=origin).status_code == 200
            next_step(clock)
            headers = mutation_headers(client, origin)
            client.post("/api/v1/auth/step-up", json={"code": current_code(clock)}, headers=headers)
            resp = client.post("/api/v1/engines", json={"label": "vps"}, headers=headers)
            assert resp.status_code == 201 and resp.json()["cloud_base_url"] == origin
            assert rig.registry.list_engines()[0].label == "vps"

    def test_a_step_up_is_required(self, rig: Rig) -> None:
        rig.clock.advance(5 * 60)
        resp = rig.register()
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "step_up_required"
        assert rig.registry.list_engines() == []

    @pytest.mark.parametrize(
        ("label", "status", "code"), [("   ", 400, "invalid_label"), ("x" * 201, 422, "invalid_request")]
    )
    def test_labels(self, rig: Rig, label: str, status: int, code: str) -> None:
        resp = rig.register(label)
        assert resp.status_code == status and resp.json()["error"]["code"] == code

    def test_the_per_user_limit(self, rig: Rig) -> None:
        assert rig.register().status_code == 201
        resp = rig.register("second")
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "engine_limit_reached"

    def test_only_the_owner_links_engines_while_multi_engine_is_off(
        self, rig_with: Callable[[dict[str, str]], Rig]
    ) -> None:
        rig = rig_with(DEV_ENV)
        assert rig.register().status_code == 201
        rig.login("bob")
        resp = rig.register()
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "engine_linking_disabled"


class TestRotateAndRevoke:
    def test_rotation_hands_over_and_never_repeats_a_secret(self, rig: Rig) -> None:
        first = rig.register().json()
        resp = rig.post(f"/{first['engine_id']}/rotate")
        assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
        second = resp.json()
        assert second["engine_id"] == first["engine_id"] and second["secret"] != first["secret"]
        assert rig.registry.keys(first["engine_id"]) == (second["secret"].encode(), first["secret"].encode())
        listed = rig.client.get("/api/v1/engines")
        assert (
            listed.json()["items"][0]["rotation_pending"] is True and listed.json()["items"][0]["rotated_at"]
        )
        assert first["secret"] not in listed.text and second["secret"] not in listed.text

    def test_revocation_needs_the_typed_id(self, rig: Rig) -> None:
        engine_id = rig.register().json()["engine_id"]
        resp = rig.post(f"/{engine_id}/revoke", {"confirm": "eng_wrong"})
        assert resp.status_code == 400 and resp.json()["error"]["code"] == "confirmation_mismatch"
        assert rig.post(f"/{engine_id}/revoke", {"confirm": engine_id}).status_code == 204
        assert rig.registry.keys(engine_id) is None
        [item] = rig.client.get("/api/v1/engines").json()["items"]
        assert item["status"] == "REVOKED" and item["revoked_at"]
        for resp in (
            rig.post(f"/{engine_id}/revoke", {"confirm": engine_id}),
            rig.post(f"/{engine_id}/rotate"),
        ):
            assert resp.status_code == 409 and resp.json()["error"]["code"] == "engine_revoked"
        assert rig.register("next").status_code == 201  # the slot is free again

    def test_another_users_engine(self, rig: Rig) -> None:
        bobs = rig.engine_of("bob")
        rig.login("bob")
        alices = rig.engine_of("alice")
        for resp in (rig.post(f"/{alices}/rotate"), rig.post(f"/{alices}/revoke", {"confirm": alices})):
            assert resp.status_code == 404 and resp.json()["error"]["code"] == "engine_not_found"
        assert [i["engine_id"] for i in rig.client.get("/api/v1/engines").json()["items"]] == [bobs]
        resp = rig.client.get("/api/v1/engines?scope=all")
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "owner_only"
        rig.login("alice")  # the OWNER role lists and revokes every engine, but rotates only its own
        listed = rig.client.get("/api/v1/engines?scope=all").json()["items"]
        assert {(i["engine_id"], i["owner"]) for i in listed} == {(bobs, "bob"), (alices, "alice")}
        assert rig.post(f"/{bobs}/rotate").status_code == 404
        assert rig.post(f"/{bobs}/revoke", {"confirm": bobs}).status_code == 204
        assert rig.registry.keys(bobs) is None

    def test_unknown_ids(self, rig: Rig) -> None:
        for bogus in ("eng_doesnotexist", "x" * 65, "-leading-dash"):
            resp = rig.post(f"/{bogus}/revoke", {"confirm": bogus})
            assert resp.status_code == 404, bogus


class TestRateLimit:
    def test_new_secrets_per_user_per_hour(
        self, rig_with: Callable[[dict[str, str]], Rig], clock: ManualClock
    ) -> None:
        rig = rig_with(MULTI | {"WEB_MAX_ENGINES_PER_USER": "3"})
        engine_id = rig.register().json()["engine_id"]
        for _ in range(ISSUE_LIMIT - 1):
            assert rig.post(f"/{engine_id}/rotate").status_code == 200
        for resp in (rig.post(f"/{engine_id}/rotate"), rig.register("more")):
            assert resp.status_code == 429 and resp.json()["error"]["code"] == "engine_rate_limited"
            assert 0 < int(resp.headers["retry-after"]) <= ISSUE_WINDOW.total_seconds() + 1
        rig.login("bob")  # the limit is per user
        assert rig.register().status_code == 201
        clock.advance(ISSUE_WINDOW.total_seconds())
        rig.login("alice")
        assert rig.post(f"/{engine_id}/rotate").status_code == 200
