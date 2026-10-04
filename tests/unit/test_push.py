"""Web Push from the worker: dispatch rules, sending, retries, unsubscribes, the endpoint allowlist (TAA-806)."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from app.config import REPO_ROOT, load_worker_settings
from app.core.clock import ManualClock
from app.core.errors import ConfigError
from app.core.ids import new_id
from app.storage.database import Database
from app.storage.models import (
    NotificationPrefsRow,
    NotificationRow,
    PushSubscriptionRow,
    UserRow,
    WorkerJobRow,
)
from app.sync.notifications import NotificationType, Severity, notify, push_endpoint_allowed
from app.sync.stream import StreamLog
from app.worker.jobs import JobQueue
from app.worker.push import PUSH_SEND, RATE_LIMIT_PER_HOUR, PushDispatcher, SendResult, push_message
from app.worker.push import handlers as push_handlers
from app.worker.service import Worker

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
FCM = "https://fcm.googleapis.com/fcm/send/abc"


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any], int]] = []
        self.answers: list[SendResult] = []

    def __call__(self, subscription: Mapping[str, Any], data: str, ttl: int) -> SendResult:
        self.sent.append((subscription["endpoint"], json.loads(data), ttl))
        return self.answers.pop(0) if self.answers else SendResult(201)


class Rig:
    def __init__(self, db: Database) -> None:
        self.db, self.clock = db, ManualClock(NOW)
        self.sender = FakeSender()
        self.queue = JobQueue(db, self.clock)
        self.push = PushDispatcher(db, self.clock, self.queue, self.sender)
        self.worker = Worker(
            db, self.clock, handlers=push_handlers(self.push), tasks=[], worker_id="w1", poll_seconds=0.01
        )
        with db.session() as sess:
            for uid, locale in (("u1", "th"), ("u2", "en")):
                sess.add(UserRow(id=uid, username=uid, password_hash="x", totp_secret_enc="x", locale=locale))

    def subscribe(self, user: str, endpoint: str = FCM) -> str:
        sid = new_id()
        with self.db.session() as sess:
            sess.add(
                PushSubscriptionRow(
                    subscription_id=sid,
                    user_id=user,
                    endpoint=endpoint,
                    p256dh="B" * 87,
                    auth="a" * 22,
                    created_at=NOW,
                )
            )
        return sid

    def note(
        self,
        user: str = "u1",
        type_: NotificationType = NotificationType.ENGINE_OFFLINE,
        severity: Severity = Severity.WARNING,
        engine: str | None = "eng-1",
        **payload: Any,
    ) -> str:
        with self.db.session() as sess:
            row = notify(
                sess,
                StreamLog(self.db, self.clock),
                user_id=user,
                engine_id=engine,
                type_=type_,
                severity=severity,
                payload=payload or {"label": "home pc", "reason": "SILENT"},
                now=self.clock.now_utc(),
            )
            return row.notification_id

    def status(self, nid: str) -> str:
        with self.db.session() as sess:
            row = sess.get(NotificationRow, nid)
            assert row is not None
            return row.push_status

    def drain(self) -> None:
        while self.worker.step():
            pass


@pytest.fixture
def rig(db: Database) -> Rig:
    return Rig(db)


class TestDispatch:
    def test_a_notification_reaches_every_device_in_the_users_language(self, rig: Rig) -> None:
        rig.subscribe("u1")
        rig.subscribe("u1", "https://updates.push.services.mozilla.com/wpush/v2/x")
        nid = rig.note()
        assert rig.push.dispatch() == "QUEUED=1"
        assert rig.status(nid) == "QUEUED"
        rig.drain()
        assert rig.status(nid) == "SENT" and len(rig.sender.sent) == 2
        _, message, ttl = rig.sender.sent[0]
        assert message["title"] == "Engine ออฟไลน์" and "home pc" in message["body"] and ttl == 3600
        assert message["tag"] == "ENGINE_OFFLINE:eng-1" and message["url"] == "/notifications"
        assert "ไม่ได้รับสัญญาณ" in message["body"]  # the reason, translated

    def test_preferences_dedup_rate_limit_and_targets(self, rig: Rig, db: Database) -> None:
        rig.subscribe("u1")
        with db.session() as sess:
            sess.add(NotificationPrefsRow(user_id="u2", disabled_types=["ENGINE_BACK"], updated_at=NOW))
        rig.subscribe("u2", "https://web.push.apple.com/abc")
        first, dup = rig.note(), rig.note()
        other_engine = rig.note(engine="eng-2")
        critical = rig.note(severity=Severity.CRITICAL)
        skipped = rig.note(user="u2", type_=NotificationType.ENGINE_BACK, label="x")
        no_device = rig.note(user="u3")
        rig.push.dispatch()
        assert [rig.status(n) for n in (first, dup, other_engine, critical, skipped, no_device)] == [
            "QUEUED",
            "SUPPRESSED",
            "QUEUED",
            "QUEUED",
            "SKIPPED",
            "NO_TARGET",
        ]
        rig.clock.advance(601)  # after the 10-minute window the same alert goes out again
        again = rig.note()
        rig.push.dispatch()
        assert rig.status(again) == "QUEUED"

    def test_the_hourly_limit_spares_critical_alerts(self, rig: Rig) -> None:
        rig.subscribe("u1")
        for i in range(RATE_LIMIT_PER_HOUR):
            rig.note(engine=f"e{i}")
        rig.push.dispatch()
        over, critical = rig.note(engine="late"), rig.note(engine="late2", severity=Severity.CRITICAL)
        rig.push.dispatch()
        assert (rig.status(over), rig.status(critical)) == ("RATE_LIMITED", "QUEUED")

    def test_stale_notifications_expire(self, rig: Rig) -> None:
        rig.subscribe("u1")
        nid = rig.note()
        rig.clock.advance(3601)
        rig.push.dispatch()
        assert rig.status(nid) == "EXPIRED"

    def test_test_pushes_are_not_deduplicated(self, rig: Rig) -> None:
        rig.subscribe("u1")
        a = rig.note(type_=NotificationType.TEST, severity=Severity.INFO, engine=None, x=1)
        b = rig.note(type_=NotificationType.TEST, severity=Severity.INFO, engine=None, x=1)
        rig.push.dispatch()
        assert (rig.status(a), rig.status(b)) == ("QUEUED", "QUEUED")


class TestSending:
    def jobs(self, db: Database) -> list[WorkerJobRow]:
        with db.session() as sess:
            return list(sess.scalars(select(WorkerJobRow).where(WorkerJobRow.kind == PUSH_SEND)))

    def test_a_gone_browser_disables_its_subscription(self, rig: Rig, db: Database) -> None:
        sid = rig.subscribe("u1")
        rig.sender.answers = [SendResult(410)]
        nid = rig.note()
        rig.push.dispatch()
        rig.drain()
        [job] = self.jobs(db)
        assert job.status == "FAILED" and "unsubscribed" in job.last_error
        with db.session() as sess:
            sub = sess.get(PushSubscriptionRow, sid)
            assert sub is not None and sub.disabled_at is not None
        assert rig.status(nid) == "QUEUED"  # attempted; nothing was delivered
        later = rig.note(engine="eng-9")
        rig.push.dispatch()
        assert rig.status(later) == "NO_TARGET"  # the only device is gone

    def test_busy_push_services_are_retried(self, rig: Rig, db: Database) -> None:
        rig.subscribe("u1")
        rig.sender.answers = [SendResult(503), SendResult(429, retry_after=120), SendResult(201)]
        nid = rig.note()
        rig.push.dispatch()
        rig.drain()
        [job] = self.jobs(db)
        assert job.status == "QUEUED" and job.attempts == 1  # backoff 30 s
        rig.clock.advance(30)
        rig.drain()
        assert self.jobs(db)[0].attempts == 2
        rig.clock.advance(119)
        rig.drain()
        assert len(rig.sender.sent) == 2  # Retry-After honoured
        rig.clock.advance(1)
        rig.drain()
        assert rig.status(nid) == "SENT" and self.jobs(db)[0].status == "DONE"

    def test_an_endpoint_outside_the_allowlist_is_never_contacted(self, rig: Rig, db: Database) -> None:
        sid = rig.subscribe("u1", "https://evil.example/collect")
        rig.note()
        rig.push.dispatch()
        rig.drain()
        assert rig.sender.sent == []
        with db.session() as sess:
            sub = sess.get(PushSubscriptionRow, sid)
            assert sub is not None and sub.disabled_at is not None

    def test_messages_hold_no_balances(self, rig: Rig) -> None:
        with rig.db.session() as sess:
            row = sess.get(NotificationRow, rig.note())
            assert row is not None
            message = push_message(row, "en")
        assert set(message) == {"notification_id", "type", "severity", "title", "body", "tag", "url"}
        assert message["body"] == "home pc: no heartbeat for over a minute while its market is open"


@pytest.mark.parametrize(
    ("endpoint", "allowed"),
    [
        (FCM, True),
        ("https://updates.push.services.mozilla.com/wpush/v2/x", True),
        ("https://web.push.apple.com/QGx", True),
        ("https://db5p.notify.windows.com/w/?token=x", True),
        ("http://fcm.googleapis.com/fcm/send/abc", False),
        ("https://fcm.googleapis.com.evil.example/x", False),
        ("https://evilfcm.googleapis.com.example/x", False),
        ("https://user:pw@fcm.googleapis.com/x", False),
        ("https://fcm.googleapis.com:8443/x", False),
        ("https://127.0.0.1/x", False),
        ("https://[::1]/x", False),
        ("not a url", False),
        ("https://fcm.googleapis.com/" + "x" * 2100, False),
    ],
)
def test_push_endpoint_allowlist(endpoint: str, allowed: bool) -> None:
    assert push_endpoint_allowed(endpoint) is allowed


def test_the_key_script_makes_a_usable_pair(capsys: pytest.CaptureFixture[str]) -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import generate_vapid_keys
    finally:
        sys.path.pop(0)
    assert generate_vapid_keys.main(["--subject", "mailto:me@example.com"]) == 0
    lines = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    settings = load_worker_settings(
        environ={"VAPID_PRIVATE_KEY": lines["VAPID_PRIVATE_KEY"], "VAPID_SUBJECT": lines["VAPID_SUBJECT"]}
    )
    assert settings.push_enabled and len(lines["VAPID_PUBLIC_KEY"]) == 87
    from py_vapid import Vapid02

    assert Vapid02.from_string(lines["VAPID_PRIVATE_KEY"]).sign(
        {"sub": "mailto:me@example.com", "aud": "https://fcm.googleapis.com"}
    )
    with pytest.raises(ConfigError, match="together"):
        load_worker_settings(environ={"VAPID_PRIVATE_KEY": lines["VAPID_PRIVATE_KEY"]})


class TestWebPushSender:
    def test_status_codes_and_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pywebpush
        import requests

        from app.worker.push import WebPushSender

        calls: list[dict[str, Any]] = []

        def ok(sub: Any, data: str, **kw: Any) -> Any:
            calls.append({"sub": sub, "data": data} | kw)
            return type("R", (), {"status_code": 201})()

        monkeypatch.setattr(pywebpush, "webpush", ok)
        sender = WebPushSender("key", "mailto:me@example.com")
        target = {"endpoint": FCM, "keys": {"p256dh": "p", "auth": "a"}}
        assert sender(target, "{}", 60) == SendResult(201)
        assert calls[0]["vapid_claims"] == {"sub": "mailto:me@example.com"} and calls[0]["ttl"] == 60
        assert sender.claims == {"sub": "mailto:me@example.com"}  # pywebpush's aud never leaks into ours

        gone = requests.Response()
        gone.status_code, gone.headers["Retry-After"] = 429, "30"

        def busy(*_a: Any, **_k: Any) -> Any:
            raise pywebpush.WebPushException("busy", response=gone)

        monkeypatch.setattr(pywebpush, "webpush", busy)
        assert sender(target, "{}", 60) == SendResult(429, 30.0)

        def down(*_a: Any, **_k: Any) -> Any:
            raise requests.ConnectionError("no route")

        monkeypatch.setattr(pywebpush, "webpush", down)
        assert sender(target, "{}", 60) == SendResult(0)
