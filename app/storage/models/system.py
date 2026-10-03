"""System tables: runs, configuration snapshots, audit chain, kill switch history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, utcnow
from app.storage.types import JSONType, UTCDateTime


class Run(Base):
    """One process lifetime of the engine (or a backtest run)."""

    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    process: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16))
    version: Mapped[str] = mapped_column(String(32))
    config_hash: Mapped[str] = mapped_column(String(32))
    host: Mapped[str] = mapped_column(String(128), default="")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")
    detail: Mapped[str] = mapped_column(Text, default="")


class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"

    config_hash: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)


class AuditChainHead(Base):
    """Latest sequence number and hash per chain; updated in the same transaction as the append."""

    __tablename__ = "audit_chain_heads"

    chain: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
    last_hash: Mapped[str] = mapped_column(String(64))


class AuditEvent(Base):
    """Append-only, hash-chained audit record: hash = sha256(prev_hash || canonical(event))."""

    __tablename__ = "audit_events"
    __table_args__ = (UniqueConstraint("chain", "seq", name="uq_audit_events_chain_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True)
    chain: Mapped[str] = mapped_column(String(64), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    ts_utc: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


class KillSwitchEvent(Base):
    __tablename__ = "kill_switch_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts_utc: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(16))  # ACTIVATE | RELEASE
    mode: Mapped[str] = mapped_column(String(16))  # HALT | FLATTEN
    source: Mapped[str] = mapped_column(String(16))  # file | cli | remote | engine
    actor: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)


class EngineState(Base):
    """Small persisted engine state (arbiter cooldowns, last entry per symbol) restored at startup."""

    __tablename__ = "engine_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONType)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
