"""Web Push delivery from the worker (PLAN §A14 "Web Push"; TAA-806).

**Dispatch** (scheduled task ``push_dispatch``, every 5 s) takes PENDING notifications, oldest first, and
decides each one's ``push_status``:

| Status | When |
|---|---|
| EXPIRED | older than ``MAX_AGE`` (1 h): a late alert is worse than none |
| SKIPPED | the user switched this type off (``notification_prefs``) |
| SUPPRESSED | the same type for the same subject (symbol, else engine) was pushed in the last 10 min |
| RATE_LIMITED | the user already got ``RATE_LIMIT_PER_HOUR`` pushes in the last hour |
| NO_TARGET | the user has no active subscription |
| QUEUED | one ``push.send`` job per active subscription was queued |

CRITICAL notifications skip deduplication and the rate limit; TEST notifications skip deduplication.

**Sending** (job ``push.send``): the TH/EN text in the user's language (:data:`TEXTS`), encrypted and signed
with VAPID by pywebpush. 2xx marks the notification SENT. 404/410 means the browser unsubscribed: the
subscription is disabled and the job fails. 429, 5xx and network errors retry through the job queue with
backoff (honouring ``Retry-After``); other 4xx fail. The endpoint is checked against the push-service
allowlist again before every send. Payloads hold a title, a short text, a tag and a link: never balances or
logins.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock, ensure_utc
from app.storage.database import Database
from app.storage.models import NotificationPrefsRow, NotificationRow, PushSubscriptionRow, UserRow
from app.sync.notifications import NotificationType, Severity, push_endpoint_allowed
from app.worker.jobs import JobFailed, JobQueue, RetryLater

log = logging.getLogger(__name__)

PUSH_SEND = "push.send"
DEDUP_WINDOW = timedelta(minutes=10)
RATE_LIMIT_PER_HOUR = 20
MAX_AGE = timedelta(hours=1)
BATCH = 100
SEND_ATTEMPTS = 5
TTL_SECONDS = 3600
CRITICAL_TTL_SECONDS = 24 * 3600


class PushStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    SENT = "SENT"
    EXPIRED = "EXPIRED"
    SKIPPED = "SKIPPED"
    SUPPRESSED = "SUPPRESSED"
    RATE_LIMITED = "RATE_LIMITED"
    NO_TARGET = "NO_TARGET"


PUSHED = (PushStatus.QUEUED.value, PushStatus.SENT.value)

# Server-side texts (PLAN §A28): (title, body) per type and language; {placeholders} come from the payload.
TEXTS: dict[str, dict[str, tuple[str, str]]] = {
    NotificationType.ENGINE_OFFLINE: {
        "th": ("Engine ออฟไลน์", "{label}: {reason}"),
        "en": ("Engine offline", "{label}: {reason}"),
    },
    NotificationType.ENGINE_BACK: {
        "th": ("Engine กลับมาออนไลน์", "{label} กลับมาทำงานแล้ว"),
        "en": ("Engine back online", "{label} is running again"),
    },
    NotificationType.TEST: {
        "th": ("ทดสอบการแจ้งเตือน", "การแจ้งเตือนบนอุปกรณ์นี้ใช้งานได้"),
        "en": ("Test notification", "Notifications work on this device"),
    },
}
REASONS: dict[str, dict[str, str]] = {
    "SILENT": {
        "th": "ไม่ได้รับสัญญาณเกิน 1 นาทีขณะตลาดเปิด",
        "en": "no heartbeat for over a minute while its market is open",
    },
    "STOPPED": {"th": "ถูกหยุดการทำงาน", "en": "was stopped"},
}


def push_message(row: NotificationRow, language: str) -> dict[str, Any]:
    lang = language if language in ("th", "en") else "th"
    title, body = TEXTS.get(row.type, {}).get(lang, (row.type, ""))
    params = {k: str(v) for k, v in dict(row.payload).items()}
    if "reason" in params:
        params["reason"] = REASONS.get(params["reason"], {}).get(lang, params["reason"])
    try:
        text = body.format_map(params)
    except (KeyError, ValueError):  # a missing placeholder never blocks the alert
        text = body
    return {
        "notification_id": row.notification_id,
        "type": row.type,
        "severity": row.severity,
        "title": title,
        "body": text,
        "tag": f"{row.type}:{row.engine_id or ''}",  # a newer push of the same kind replaces the older one
        "url": "/notifications",
    }


@dataclass(frozen=True)
class SendResult:
    status: int  # HTTP status from the push service; 0 for a network error
    retry_after: float | None = None


class PushSender(Protocol):
    def __call__(self, subscription: Mapping[str, Any], data: str, ttl: int) -> SendResult: ...


class WebPushSender:
    """pywebpush with the worker's VAPID key; never raises, returns the push service's status."""

    def __init__(self, private_key: str, subject: str, timeout: float = 10.0) -> None:
        self.private_key = private_key
        self.claims = {"sub": subject}
        self.timeout = timeout

    def __call__(self, subscription: Mapping[str, Any], data: str, ttl: int) -> SendResult:
        from pywebpush import WebPushException, webpush  # cloud-only dependency, imported where used

        try:
            response: Any = webpush(
                dict(subscription),
                data,
                vapid_private_key=self.private_key,
                vapid_claims=dict(self.claims),  # pywebpush adds aud/exp to the dict it is given
                ttl=ttl,
                timeout=self.timeout,
            )
            return SendResult(int(getattr(response, "status_code", 201)))
        except WebPushException as exc:
            resp = exc.response
            if resp is None:
                return SendResult(0)
            retry = resp.headers.get("Retry-After")
            return SendResult(resp.status_code, float(retry) if retry and retry.isdigit() else None)
        except Exception as exc:  # network errors and the like: retried by the job queue
            log.warning("push send failed: %s", type(exc).__name__)
            return SendResult(0)


def _subject(row: NotificationRow) -> str:
    payload = dict(row.payload)
    return str(payload.get("symbol") or row.engine_id or "")


class PushDispatcher:
    def __init__(self, db: Database, clock: Clock, queue: JobQueue, sender: PushSender) -> None:
        self.db = db
        self.clock = clock
        self.queue = queue
        self.sender = sender

    # --- dispatch (scheduled) -----------------------------------------------------------------------------

    def dispatch(self) -> str | None:
        """Decide every PENDING notification; returns a summary for the log, or None when idle."""
        now = self.clock.now_utc()
        counts: dict[str, int] = {}
        with self.db.session() as sess:
            pending = list(
                sess.scalars(
                    select(NotificationRow)
                    .where(NotificationRow.push_status == PushStatus.PENDING.value)
                    .order_by(NotificationRow.created_at, NotificationRow.notification_id)
                    .limit(BATCH)
                )
            )
            for row in pending:
                status = self._decide(sess, row, now)
                row.push_status = status.value
                sess.flush()  # later rows of this batch see this one in dedup and rate counts
                counts[status.value] = counts.get(status.value, 0) + 1
        return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or None

    def _decide(self, sess: Session, row: NotificationRow, now: datetime) -> PushStatus:
        created = ensure_utc(row.created_at)
        if now - created > MAX_AGE:
            return PushStatus.EXPIRED
        prefs = sess.get(NotificationPrefsRow, row.user_id)
        if prefs is not None and row.type in (prefs.disabled_types or []):
            return PushStatus.SKIPPED
        critical = row.severity == Severity.CRITICAL.value
        if not critical and row.type != NotificationType.TEST.value:
            recent = sess.scalars(
                select(NotificationRow).where(
                    NotificationRow.user_id == row.user_id,
                    NotificationRow.type == row.type,
                    NotificationRow.push_status.in_(PUSHED),
                    NotificationRow.created_at >= created - DEDUP_WINDOW,
                    NotificationRow.notification_id != row.notification_id,
                )
            ).all()
            if any(_subject(r) == _subject(row) for r in recent):
                return PushStatus.SUPPRESSED
        if not critical:
            sent = sess.scalar(
                select(func.count())
                .select_from(NotificationRow)
                .where(
                    NotificationRow.user_id == row.user_id,
                    NotificationRow.push_status.in_(PUSHED),
                    NotificationRow.created_at >= now - timedelta(hours=1),
                )
            )
            if int(sent or 0) >= RATE_LIMIT_PER_HOUR:
                return PushStatus.RATE_LIMITED
        subs = sess.scalars(
            select(PushSubscriptionRow.subscription_id).where(
                PushSubscriptionRow.user_id == row.user_id, PushSubscriptionRow.disabled_at.is_(None)
            )
        ).all()
        if not subs:
            return PushStatus.NO_TARGET
        for sub_id in subs:
            self.queue.enqueue(
                PUSH_SEND,
                {"notification_id": row.notification_id, "subscription_id": sub_id},
                created_by="push_dispatch",
                priority=0 if critical else 1,
                max_attempts=SEND_ATTEMPTS,
                dedupe_key=f"push:{row.notification_id}:{sub_id}",
                sess=sess,  # the jobs commit together with the QUEUED status
            )
        return PushStatus.QUEUED

    # --- sending (job handler) ----------------------------------------------------------------------------

    def handle(self, ctx: Any) -> dict[str, Any]:
        """The ``push.send`` job: one notification to one subscription."""
        nid, sid = ctx.job.payload.get("notification_id"), ctx.job.payload.get("subscription_id")
        with self.db.session() as sess:
            note = sess.get(NotificationRow, nid)
            sub = sess.get(PushSubscriptionRow, sid)
            if note is None:
                raise JobFailed("the notification no longer exists")
            if sub is None or sub.disabled_at is not None:
                raise JobFailed("the subscription is gone or disabled")
            allowed = push_endpoint_allowed(sub.endpoint)
            if not allowed:  # committed before the job fails (raising here would roll it back)
                sub.disabled_at = self.clock.now_utc()
            user = sess.get(UserRow, note.user_id)
            message = push_message(note, user.locale if user is not None else "th")
            target = {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
            critical = note.severity == Severity.CRITICAL.value
        if not allowed:
            raise JobFailed("the endpoint is not a known push service; subscription disabled")
        result = self.sender(
            target, json.dumps(message, ensure_ascii=False), CRITICAL_TTL_SECONDS if critical else TTL_SECONDS
        )
        return self._record(nid, sid, result)

    def _record(self, nid: str, sid: str, result: SendResult) -> dict[str, Any]:
        now = self.clock.now_utc()
        with self.db.session() as sess:
            sub = sess.get(PushSubscriptionRow, sid)
            note = sess.get(NotificationRow, nid)
            if 200 <= result.status < 300:
                if sub is not None:
                    sub.last_success_at, sub.failures = now, 0
                if note is not None:
                    note.push_status = PushStatus.SENT.value
                return {"status": result.status}
            if sub is not None:
                sub.last_failure_at, sub.failures = now, sub.failures + 1
                if result.status in (404, 410):
                    sub.disabled_at = now
        if result.status in (404, 410):
            raise JobFailed(f"the browser unsubscribed ({result.status}); subscription disabled")
        if result.status == 0 or result.status == 429 or result.status >= 500:
            raise RetryLater(f"push service unavailable ({result.status or 'network'})", result.retry_after)
        raise JobFailed(f"the push service refused the message ({result.status})")


def handlers(dispatcher: PushDispatcher) -> dict[str, Callable[[Any], Mapping[str, Any] | None]]:
    return {PUSH_SEND: dispatcher.handle}
