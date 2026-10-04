"""Roles, tenancy and personal data: ADMIN without trading controls, one role guard, PDPA export/erasure,
cross-tenant isolation of user-owned rows (TAA-8A1)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.clock import ManualClock
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    NotificationRow,
    PushSubscriptionRow,
    SessionRow,
    UserAdvisoryPrefsRow,
    UserRow,
)
from app.sync.notifications import NotificationType, Severity, notify
from app.sync.stream import StreamLog
from app.web.engines import EngineError
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, current_code, login, make_app, mutation_headers
from tests.web.test_auth import next_step

FCM = "https://fcm.googleapis.com/fcm/send/device-1"


class Rig:
    def __init__(self, app: FastAPI, client: TestClient, clock: ManualClock) -> None:
        self.app, self.client, self.clock = app, client, clock
        self.ids = {u.username: u.id for u in app.state.ctx.auth.list_users()}

    def login(self, name: str, *, step_up: bool = True) -> None:
        self.client.cookies.clear()
        next_step(self.clock)
        assert login(self.client, self.clock, username=name).status_code == 200
        if step_up:
            next_step(self.clock)
            code = current_code(self.clock)
            assert self.post("/auth/step-up", {"code": code}).status_code == 200

    def post(self, path: str, body: Any = None) -> Any:
        return self.client.post(f"/api/v1{path}", json=body, headers=mutation_headers(self.client))

    def note(self, name: str, label: str) -> None:
        ctx = self.app.state.ctx
        with ctx.db.session() as sess:
            notify(
                sess,
                StreamLog(ctx.db, ctx.clock),
                user_id=self.ids[name],
                engine_id=None,
                type_=NotificationType.TEST,
                severity=Severity.INFO,
                payload={"label": label},
                now=ctx.clock.now_utc(),
            )


@pytest.fixture
def rig(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[Rig]:
    app = make_app(
        db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true", "VAPID_PUBLIC_KEY": "B" + "A" * 86}
    )
    auth = app.state.ctx.auth
    for name, role in (("alice", "OWNER"), ("ada", "ADMIN"), ("bob", "SUBSCRIBER"), ("cid", "SUBSCRIBER")):
        auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
    with TestClient(app, base_url="https://testserver") as client:
        yield Rig(app, client, clock)


class TestRoles:
    def test_admin_is_support_only(self, rig: Rig) -> None:
        rig.login("ada")
        users = rig.client.get("/api/v1/admin/users").json()["items"]
        assert {u["username"] for u in users} == {"alice", "ada", "bob", "cid"}
        assert set(users[0]) == {"id", "username", "role", "disabled", "created_at"}
        resp = rig.post("/engines", {"label": "x"})
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "role_forbidden"
        ada = rig.app.state.ctx.engine.registry.user("ada")
        with pytest.raises(EngineError, match="support"):  # the CLI path refuses as well
            rig.app.state.ctx.engine.registry.register(ada, "x", actor="cli")
        erase = rig.post(f"/admin/users/{rig.ids['bob']}/erase", {"confirm": "bob"})
        assert erase.status_code == 403  # erasing other users is the owner's

    def test_subscribers_see_no_user_list(self, rig: Rig) -> None:
        rig.login("bob", step_up=False)
        resp = rig.client.get("/api/v1/admin/users")
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "role_forbidden"

    def test_a_subscriber_controls_only_the_engine_it_owns(self, rig: Rig) -> None:
        rig.login("bob")
        mine = rig.post("/engines", {"label": "bob pc"}).json()["engine_id"]
        assert rig.post(f"/engines/{mine}/commands", {"type": "RESYNC"}).status_code == 202
        alice = rig.app.state.ctx.engine.registry.user("alice")
        theirs = rig.app.state.ctx.engine.registry.register(alice, "alice pc", actor="t").engine_id
        assert rig.post(f"/engines/{theirs}/commands", {"type": "RESYNC"}).status_code == 404


class TestIsolation:
    def test_user_owned_rows_never_cross_users(self, rig: Rig) -> None:
        rig.note("alice", "alice-secret-label")
        rig.login("alice", step_up=False)
        rig.post("/push/subscribe", {"endpoint": FCM, "keys": {"p256dh": "BA" + "Q" * 85, "auth": "A" * 22}})
        rig.post("/advisory/favourites/XAUUSD")
        rig.login("bob", step_up=False)
        assert rig.client.get("/api/v1/notifications").json()["items"] == []
        assert rig.client.get("/api/v1/push/subscriptions").json()["items"] == []
        prefs = rig.client.get("/api/v1/advisory/preferences").json()
        assert all("XAUUSD" not in w["symbols"] for w in prefs["watchlists"])
        assert rig.client.get("/api/v1/engines").json()["items"] == []
        export = rig.client.get("/api/v1/me/export").text
        assert "alice-secret-label" not in export and "XAUUSD" not in export


class TestPersonalData:
    def test_export_holds_the_users_data_and_no_secrets(self, rig: Rig) -> None:
        rig.note("bob", "home pc")
        rig.login("bob", step_up=False)
        rig.post(
            "/push/subscribe",
            {"endpoint": FCM, "keys": {"p256dh": "BA" + "Q" * 85, "auth": "A" * 22}, "label": "phone"},
        )
        rig.post("/advisory/favourites/EURUSD")
        resp = rig.client.get("/api/v1/me/export")
        assert resp.headers["content-disposition"] == 'attachment; filename="taa-bob.json"'
        data = json.loads(resp.text)
        assert data["user"]["username"] == "bob" and data["notifications"][0]["payload"] == {
            "label": "home pc"
        }
        assert data["push_devices"] == [
            {
                "label": "phone",
                "service": "fcm.googleapis.com",
                "created_at": data["push_devices"][0]["created_at"],
                "active": True,
            }
        ]
        assert "EURUSD" in json.dumps(data["advisory_preferences"])
        for secret in ("password_hash", "totp_secret", "$argon2", TOTP_SECRET, FCM, "token_hash", "p256dh"):
            assert secret not in resp.text

    def test_erasure_removes_personal_data_and_keeps_the_record(self, rig: Rig, db: Database) -> None:
        rig.note("bob", "home pc")
        rig.note("cid", "cid pc")
        rig.login("bob")
        rig.post("/push/subscribe", {"endpoint": FCM, "keys": {"p256dh": "BA" + "Q" * 85, "auth": "A" * 22}})
        rig.post("/advisory/favourites/EURUSD")
        engine = rig.post("/engines", {"label": "bob pc"}).json()["engine_id"]
        assert rig.post("/me/erase", {"confirm": "bobby"}).json()["error"]["code"] == "confirmation_mismatch"
        busy = rig.post("/me/erase", {"confirm": "bob"})
        assert busy.status_code == 409 and busy.json()["error"]["code"] == "engines_active"
        rig.post(f"/engines/{engine}/revoke", {"confirm": engine})
        assert rig.post("/me/erase", {"confirm": "bob"}).status_code == 204
        bob = rig.ids["bob"]
        with db.session() as sess:
            user = sess.get(UserRow, bob)
            assert user is not None and user.username == f"deleted-{bob[:8]}" and user.disabled
            assert user.password_hash == "!" and user.totp_secret_enc == ""
            for model, col in (
                (NotificationRow, NotificationRow.user_id),
                (PushSubscriptionRow, PushSubscriptionRow.user_id),
                (UserAdvisoryPrefsRow, UserAdvisoryPrefsRow.user_id),
                (SessionRow, SessionRow.user_id),
            ):
                assert sess.scalar(select(func.count()).select_from(model).where(col == bob)) == 0, model
            assert sess.scalar(select(func.count()).select_from(NotificationRow)) == 1  # cid's stays
            erased = sess.scalars(select(AuditEvent).where(AuditEvent.event_type == "user.erased")).all()
            assert [e.payload["pseudonym"] for e in erased] == [f"deleted-{bob[:8]}"]
        assert rig.client.get("/api/v1/notifications").status_code == 401  # the session is gone
        next_step(rig.clock)
        assert login(rig.client, rig.clock, username="bob").status_code == 401

    def test_the_owner_cannot_be_erased_but_can_erase_others(self, rig: Rig) -> None:
        rig.login("alice")
        resp = rig.post("/me/erase", {"confirm": "alice"})
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "owner_cannot_be_erased"
        assert rig.post(f"/admin/users/{rig.ids['cid']}/erase", {"confirm": "cid"}).status_code == 204
        names = {u["username"] for u in rig.client.get("/api/v1/admin/users").json()["items"]}
        assert "cid" not in names and f"deleted-{rig.ids['cid'][:8]}" in names


class TestAccountProfile:
    def test_manual_and_linked_profiles(self, rig: Rig) -> None:
        rig.login("bob")
        assert rig.client.get("/api/v1/me/account-profile").json() == {"source": None}
        manual = {
            "source": "MANUAL",
            "equity": 2500,
            "currency": "EUR",
            "leverage": 100,
            "risk_percent": 0.25,
        }
        saved = rig.client.put(
            "/api/v1/me/account-profile", json=manual, headers=mutation_headers(rig.client)
        )
        assert saved.status_code == 200 and saved.json()["balance"] == 2500  # balance defaults to equity
        for bad in (
            manual | {"equity": None},
            manual | {"currency": "euro"},
            manual | {"risk_percent": 50},
            manual | {"engine_id": "eng-x"},
            {"source": "LINKED_ENGINE"},
        ):
            resp = rig.client.put(
                "/api/v1/me/account-profile", json=bad, headers=mutation_headers(rig.client)
            )
            assert resp.status_code == 422, bad
        alice = rig.app.state.ctx.engine.registry.user("alice")
        theirs = rig.app.state.ctx.engine.registry.register(alice, "pc", actor="t").engine_id
        linked = {"source": "LINKED_ENGINE", "engine_id": theirs}
        resp = rig.client.put("/api/v1/me/account-profile", json=linked, headers=mutation_headers(rig.client))
        assert resp.status_code == 404 and resp.json()["error"]["code"] == "engine_not_found"
        mine = rig.post("/engines", {"label": "bob pc"}).json()["engine_id"]
        ok = rig.client.put(
            "/api/v1/me/account-profile",
            json={"source": "LINKED_ENGINE", "engine_id": mine},
            headers=mutation_headers(rig.client),
        )
        assert ok.status_code == 200 and ok.json()["engine_id"] == mine
        assert json.loads(rig.client.get("/api/v1/me/export").text)["account_profile"]["engine_id"] == mine
