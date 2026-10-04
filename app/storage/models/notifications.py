"""User notifications (PLAN §A14 "Web Push", §A15 notification centre; TAA-705, TAA-806).

Cloud only. One row per event a user should hear about (engine offline/back now; breaker trips, trades and the
rest with Web Push). ``push_status`` is the delivery state the Web Push sender (TAA-806) works through; the
row itself is the notification centre's record. Payloads are minimal: never balances or full logins.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base
from app.storage.types import JSONType, UTCDateTime


class NotificationRow(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUIDv7
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    engine_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))  # INFO / WARNING / CRITICAL
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    push_status: Mapped[str] = mapped_column(String(12), default="PENDING", index=True)


class PushSubscriptionRow(Base):
    """A browser's Web Push subscription (one per device and browser profile; TAA-806).

    ``endpoint`` is the push service URL the worker posts to; only known push services are accepted
    (``app.sync.notifications.push_endpoint_allowed``). A 404/410 from the push service disables the row."""

    __tablename__ = "push_subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    endpoint: Mapped[str] = mapped_column(String(2048), unique=True)
    p256dh: Mapped[str] = mapped_column(String(128))
    auth: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    disabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class NotificationPrefsRow(Base):
    """A user's push preferences: the notification types they do not want pushed (all others are)."""

    __tablename__ = "notification_prefs"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    disabled_types: Mapped[list[str]] = mapped_column(JSONType)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
