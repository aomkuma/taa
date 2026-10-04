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


class CommandLogRow(Base):
    """Engine side: every remote command received, once (idempotency, audit, used TOTP steps; TAA-704)."""

    __tablename__ = "command_log"

    command_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(48))
    created_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    outcome: Mapped[str] = mapped_column(String(16))  # EXECUTED / REJECTED / FAILED
    reason: Mapped[str] = mapped_column(String(32), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    totp_step: Mapped[int | None] = mapped_column(Integer, nullable=True)  # a consumed code's time step
    params: Mapped[dict[str, Any]] = mapped_column(JSONType)


class EngineCommandRow(Base):
    """Cloud side: the command queue an engine long-polls (TAA-704).

    A TOTP code is kept only until the command is answered or expires (≤ 120 s)."""

    __tablename__ = "engine_commands"

    command_id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUIDv7: the poll cursor
    engine_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(48))
    params: Mapped[dict[str, Any]] = mapped_column(JSONType)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    totp: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), index=True
    )  # QUEUED/DELIVERED/EXECUTED/REJECTED/FAILED/EXPIRED
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSONType)
