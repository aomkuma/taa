"""Cloud-sync tables (PLAN §A13): the cloud's ingest nonce store and, on the engine, the event outbox."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base
from app.storage.types import JSONType, UTCDateTime


class IngestNonceRow(Base):
    """A request nonce seen by the cloud, kept until it expires (replay protection, TAA-702)."""

    __tablename__ = "ingest_nonces"

    engine_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class OutboxEventRow(Base):
    """An engine event waiting to be replicated to the cloud (TAA-701). Status: PENDING → SENT, or DEAD after
    ``sync.max_attempts`` rejections."""

    __tablename__ = "outbox_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUIDv7: time-ordered
    type: Mapped[str] = mapped_column(String(48), index=True)
    priority: Mapped[int] = mapped_column(
        Integer, index=True
    )  # 0 audit/trades/decisions/breakers ... 2 quotes
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    coalesce_key: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(8), index=True, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
