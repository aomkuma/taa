"""User notifications (PLAN §A14 "Web Push", §A15 notification centre; TAA-705, TAA-806).

Cloud only. One row per event a user should hear about (engine offline/back now; breaker trips, trades and the
rest with Web Push). ``push_status`` is the delivery state the Web Push sender (TAA-806) works through; the
row itself is the notification centre's record. Payloads are minimal: never balances or full logins.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String
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
