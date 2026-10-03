"""Advisory tables (PLAN §A25-A27): symbol catalog, suitability snapshots and market opportunities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base
from app.storage.types import JSONType, UTCDateTime


class SymbolCatalogRow(Base):
    """Every symbol the broker offers, classified; refreshed daily from ``symbols_get``."""

    __tablename__ = "symbol_catalog"

    server: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    asset_class: Mapped[str] = mapped_column(String(16), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text, default="")
    path: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(String(128), default="")
    spec: Mapped[dict[str, Any]] = mapped_column(JSONType)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    refreshed_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    present: Mapped[bool] = mapped_column(Boolean, default=True)  # still offered by the broker


class SuitabilitySnapshotRow(Base):
    """The ranking per symbol: one row per symbol and UTC hour, rewritten by every run within that hour.

    The rows of the newest ``computed_at`` are the latest ranking; older hours are the history (90-day
    retention).
    """

    __tablename__ = "suitability_snapshots"
    __table_args__ = (UniqueConstraint("server", "symbol", "hour", name="uq_suitability_symbol_hour"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32))
    hour: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    asset_class: Mapped[str] = mapped_column(String(16))
    rank: Mapped[int] = mapped_column(Integer)
    eligible: Mapped[bool] = mapped_column(Boolean)
    overall: Mapped[float] = mapped_column(Float)
    now_score: Mapped[float] = mapped_column(Float)
    failed_gates: Mapped[list[str]] = mapped_column(JSONType)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)  # scores, gates, metrics, session


class OpportunityRow(Base):
    """A market opportunity: one strategy's entry signal on one symbol and bar that passed the ADVISORY hard
    checks. Idempotent per strategy/symbol/bar/side (the signal's idempotency key). Never an alert by itself:
    the personalizer decides who is alerted (§A30)."""

    __tablename__ = "opportunities"

    opportunity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    server: Mapped[str] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_class: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(8))
    side: Mapped[str] = mapped_column(String(4))
    bar_close_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    signal_expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    setup_strength: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    # lifecycle (TAA-6B4)
    status: Mapped[str] = mapped_column(String(16), index=True, default="CANDIDATE")
    status_reason: Mapped[str] = mapped_column(Text, default="")
    status_at: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    valid_reason: Mapped[str] = mapped_column(String(64), default="")
    # the owner account at signal time
    decision_id: Mapped[str] = mapped_column(String(64))
    warnings: Mapped[list[str]] = mapped_column(JSONType)
    lot: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    # market facts and model inputs
    session: Mapped[str] = mapped_column(String(24))
    regime: Mapped[str] = mapped_column(String(16))
    atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    requirements_version: Mapped[str] = mapped_column(String(16))
    features: Mapped[dict[str, float]] = mapped_column(JSONType)
    signal: Mapped[dict[str, Any]] = mapped_column(JSONType)  # conditions, evidence, confluence
