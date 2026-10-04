"""Creating user notifications in the cloud (TAA-705; Web Push delivery is TAA-806).

:func:`notify` writes a :class:`NotificationRow` and, for an engine's notification, a live-stream event (topic
``notifications``) in the caller's transaction. Web Push delivery works from ``push_status`` (PENDING) in the
worker (TAA-806, ``app/worker/push.py``), with the user's preferences, deduplication and rate limits.
Payloads carry identifiers and reasons only, never balances or logins.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.storage.models import NotificationRow
from app.sync.events import json_safe
from app.sync.stream import StreamEntry, StreamLog


class NotificationType(StrEnum):
    ENGINE_OFFLINE = "ENGINE_OFFLINE"
    ENGINE_BACK = "ENGINE_BACK"
    BACKTEST_FINISHED = "BACKTEST_FINISHED"
    TEST = "TEST"  # the PWA's "send a test push" button


# Push services browsers subscribe with (Chrome/Edge via FCM, Firefox, Safari/Apple, Windows). The worker
# posts to a subscription's endpoint, so anything else is refused: a stored endpoint must never turn the
# worker into a request forwarder (SSRF). Matched on the host name, exactly or as a subdomain.
PUSH_HOST_SUFFIXES = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.apple.com",
    "notify.windows.com",
)
MAX_ENDPOINT_LENGTH = 2048


def push_endpoint_allowed(endpoint: str) -> bool:
    """An https URL on a known push service, without credentials or an explicit port."""
    if len(endpoint) > MAX_ENDPOINT_LENGTH:
        return False
    try:
        url = urlsplit(endpoint)
        port = url.port
    except ValueError:
        return False
    host = (url.hostname or "").lower()
    if url.scheme != "https" or url.username or url.password or port not in (None, 443) or not host:
        return False
    return any(host == s or host.endswith("." + s) for s in PUSH_HOST_SUFFIXES)


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


def notification_dict(row: NotificationRow) -> dict[str, Any]:
    return {
        "notification_id": row.notification_id,
        "engine_id": row.engine_id,
        "type": row.type,
        "severity": row.severity,
        "payload": dict(row.payload),
        "created_at": json_safe(row.created_at),
        "read_at": json_safe(row.read_at),
    }


def notify(
    sess: Session,
    stream: StreamLog,
    *,
    user_id: str,
    engine_id: str | None,
    type_: NotificationType,
    severity: Severity,
    payload: Mapping[str, Any],
    now: datetime,
) -> NotificationRow:
    row = NotificationRow(
        notification_id=new_id(),
        user_id=user_id,
        engine_id=engine_id,
        type=type_.value,
        severity=severity.value,
        payload=json_safe(dict(payload)),
        created_at=now,
        read_at=None,
        push_status="PENDING",
    )
    sess.add(row)
    if engine_id is not None:
        stream.append(
            sess,
            engine_id,
            [StreamEntry("notifications", "notification", row.notification_id, notification_dict(row))],
        )
    return row
