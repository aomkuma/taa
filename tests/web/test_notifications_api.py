"""Push subscriptions, test push and the notification centre over the API (TAA-806)."""

from __future__ import annotations

import base64
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.clock import ManualClock
from app.storage.database import Database
from app.storage.models import NotificationRow, PushSubscriptionRow
from app.sync.notifications import NotificationType, Severity, notify
from app.sync.stream import StreamLog
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, login, make_app, mutation_headers
from tests.web.test_auth import next_step

PUBLIC_KEY = "B" + "A" * 86
FCM = "https://fcm.googleapis.com/fcm/send/device-1"
P256DH = base64.urlsafe_b64encode(b"\x04" + b"\x01" * 64).decode().rstrip("=")
AUTH = base64.urlsafe_b64encode(b"\x02" * 16).decode().rstrip("=")


def sub_body(endpoint: str = FCM, **over: Any) -> dict[str, Any]:
    return {"endpoint": endpoint, "keys": {"p256dh": P256DH, "auth": AUTH}, "expirationTime": None} | over


@pytest.fixture
def app(db: Database, clock: ManualClock, static_dir: Path) -> FastAPI:
    app = make_app(db, clock, static_dir, DEV_ENV | {"VAPID_PUBLIC_KEY": PUBLIC_KEY})
    for name, role in (("alice", "OWNER"), ("bob", "SUBSCRIBER")):
        app.state.ctx.auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
    return app


@pytest.fixture
def client(app: FastAPI, clock: ManualClock) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver") as c:
        assert login(c, clock, username="alice").status_code == 200
        yield c


def post(client: TestClient, path: str, body: Any = None) -> Any:
    return client.post(f"/api/v1{path}", json=body, headers=mutation_headers(client))


def user_id(app: FastAPI, name: str) -> str:
    return next(u.id for u in app.state.ctx.auth.list_users() if u.username == name)


class TestPush:
    def test_key_subscribe_list_unsubscribe(self, client: TestClient, db: Database) -> None:
        assert client.get("/api/v1/push/key").json() == {"public_key": PUBLIC_KEY}
        resp = post(client, "/push/subscribe", sub_body(label="  my   phone "))
        assert resp.status_code == 201
        again = post(client, "/push/subscribe", sub_body())  # the browser re-subscribes: same row
        assert again.json()["subscription_id"] == resp.json()["subscription_id"]
        [item] = client.get("/api/v1/push/subscriptions").json()["items"]
        assert item["service"] == "fcm.googleapis.com" and item["active"] is True
        assert "endpoint" not in item and FCM not in str(item)
        assert post(client, "/push/unsubscribe", {"endpoint": FCM}).status_code == 204
        assert post(client, "/push/unsubscribe", {"endpoint": FCM}).status_code == 204  # idempotent
        with db.session() as sess:
            assert sess.scalars(select(PushSubscriptionRow)).all() == []

    @pytest.mark.parametrize(
        ("body", "status", "code"),
        [
            (sub_body("https://evil.example/collect"), 400, "push_endpoint_not_allowed"),
            (sub_body("http://fcm.googleapis.com/fcm/send/x"), 400, "push_endpoint_not_allowed"),
            (sub_body(keys={"p256dh": "A" * 87, "auth": AUTH}), 400, "invalid_push_keys"),
            (sub_body(keys={"p256dh": P256DH, "auth": "A" * 30}), 400, "invalid_push_keys"),
            (sub_body(keys={"p256dh": P256DH}), 422, "invalid_request"),
        ],
    )
    def test_bad_subscriptions(
        self, client: TestClient, body: dict[str, Any], status: int, code: str
    ) -> None:
        resp = post(client, "/push/subscribe", body)
        assert resp.status_code == status and resp.json()["error"]["code"] == code

    def test_csrf_and_sign_in_are_required(self, client: TestClient) -> None:
        assert client.post("/api/v1/push/subscribe", json=sub_body()).status_code == 403
        client.cookies.clear()
        assert client.get("/api/v1/push/key").status_code == 401

    def test_device_limit(self, client: TestClient) -> None:
        for i in range(10):
            assert post(client, "/push/subscribe", sub_body(f"{FCM}-{i}")).status_code == 201
        resp = post(client, "/push/subscribe", sub_body(f"{FCM}-x"))
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "push_subscription_limit"

    def test_an_endpoint_moves_to_the_user_who_subscribes_it(
        self, app: FastAPI, client: TestClient, clock: ManualClock, db: Database
    ) -> None:
        post(client, "/push/subscribe", sub_body())
        client.cookies.clear()
        next_step(clock)
        assert login(client, clock, username="bob").status_code == 200
        post(client, "/push/subscribe", sub_body())
        with db.session() as sess:
            [row] = sess.scalars(select(PushSubscriptionRow)).all()
            assert row.user_id == user_id(app, "bob")

    def test_a_test_push_is_queued_for_the_user(self, app: FastAPI, client: TestClient, db: Database) -> None:
        resp = post(client, "/push/test")
        assert resp.status_code == 202
        with db.session() as sess:
            row = sess.get(NotificationRow, resp.json()["notification_id"])
            assert row is not None and row.type == "TEST" and row.push_status == "PENDING"
            assert row.user_id == user_id(app, "alice")

    def test_push_off_without_a_key(self, db: Database, clock: ManualClock, static_dir: Path) -> None:
        app = make_app(db, clock, static_dir)
        app.state.ctx.auth.create_user("carol", PASSWORD, TOTP_SECRET)
        with TestClient(app, base_url="https://testserver") as c:
            login(c, clock, username="carol")
            assert c.get("/api/v1/push/key").json()["error"]["code"] == "push_not_configured"
            assert post(c, "/push/test").status_code == 404


class TestCentre:
    def add(self, app: FastAPI, name: str, n: int = 1) -> list[str]:
        ctx = app.state.ctx
        ids = []
        for i in range(n):
            with ctx.db.session() as sess:
                row = notify(
                    sess,
                    StreamLog(ctx.db, ctx.clock),
                    user_id=user_id(app, name),
                    engine_id=None,
                    type_=NotificationType.ENGINE_OFFLINE,
                    severity=Severity.WARNING,
                    payload={"label": f"pc{i}", "reason": "SILENT"},
                    now=ctx.clock.now_utc(),
                )
                ids.append(row.notification_id)
            ctx.clock.advance(1)
        return ids

    def test_list_read_and_ownership(self, app: FastAPI, client: TestClient) -> None:
        mine = self.add(app, "alice", 3)
        [theirs] = self.add(app, "bob")
        page = client.get("/api/v1/notifications?limit=2").json()
        assert [n["notification_id"] for n in page["items"]] == mine[:0:-1] and page["next_cursor"]
        assert page["items"][0]["payload"] == {"label": "pc2", "reason": "SILENT"}
        assert post(client, f"/notifications/{mine[0]}/read").status_code == 204
        unread = client.get("/api/v1/notifications?unread=true").json()["items"]
        assert [n["notification_id"] for n in unread] == mine[:0:-1]
        resp = post(client, f"/notifications/{theirs}/read")
        assert resp.status_code == 404 and resp.json()["error"]["code"] == "notification_not_found"
        assert post(client, "/notifications/read-all").json() == {"updated": 2}
        assert client.get("/api/v1/notifications?unread=true").json()["items"] == []
        assert theirs not in client.get("/api/v1/notifications").text

    def test_preferences(self, client: TestClient) -> None:
        body = client.get("/api/v1/notifications/preferences").json()
        assert body == {"types": ["ENGINE_OFFLINE", "ENGINE_BACK", "TEST"], "disabled": []}
        resp = client.put(
            "/api/v1/notifications/preferences",
            json={"disabled": ["ENGINE_BACK", "ENGINE_BACK"]},
            headers=mutation_headers(client),
        )
        assert resp.json()["disabled"] == ["ENGINE_BACK"]
        assert client.get("/api/v1/notifications/preferences").json()["disabled"] == ["ENGINE_BACK"]
        bad = client.put(
            "/api/v1/notifications/preferences", json={"disabled": ["NOPE"]}, headers=mutation_headers(client)
        )
        assert bad.status_code == 422
