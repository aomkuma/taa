"""Creating user notifications in the cloud (TAA-705; Web Push delivery is TAA-806).

:func:`notify` writes a :class:`NotificationRow` and, for an engine's notification, a live-stream event (topic
``notifications``) in the caller's transaction. Delivery by Web Push works from ``push_status`` (PENDING) and
is added with TAA-806; until then notifications are visible in the stream and the notification centre.
Payloads carry identifiers and reasons only, never balances or logins.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.storage.models import NotificationRow
from app.sync.events import json_safe
from app.sync.stream import StreamEntry, StreamLog


class NotificationType(StrEnum):
    ENGINE_OFFLINE = "ENGINE_OFFLINE"
    ENGINE_BACK = "ENGINE_BACK"


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
