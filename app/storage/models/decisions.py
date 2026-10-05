"""Decision records and their checks (PLAN §A8; TAA-405). Every check is stored with value and threshold."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, EngineKeyed, EngineTagged
from app.storage.types import JSONType, UTCDateTime


class DecisionRecordRow(EngineKeyed, Base):
    __tablename__ = "decision_records"

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    signal_id: Mapped[str] = mapped_column(String(36), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    action: Mapped[str] = mapped_column(String(8))
    profile: Mapped[str] = mapped_column(String(16))  # EXECUTION | ADVISORY
    decision: Mapped[str] = mapped_column(String(16), index=True)  # ACCEPT | REJECT | HOLD
    reason_codes: Mapped[list[str]] = mapped_column(JSONType, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONType, default=list)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    bar_times: Mapped[dict[str, str]] = mapped_column(JSONType, default=dict)
    signal: Mapped[dict[str, Any]] = mapped_column(JSONType)
    market: Mapped[dict[str, Any]] = mapped_column(JSONType)
    config_hash: Mapped[str] = mapped_column(String(32))
    code_version: Mapped[str] = mapped_column(String(32))
    # the limits the decision was measured against (PLAN §A33, TAA-710): cloud:<v> | cache:<v> | local:<v>
    risk_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    risk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)  # effective per-trade risk


class DecisionCheckRow(EngineTagged, Base):
    __tablename__ = "decision_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(36), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(64), index=True)
    passed: Mapped[bool] = mapped_column(Boolean)
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[Any] = mapped_column(JSONType, nullable=True)
    threshold: Mapped[Any] = mapped_column(JSONType, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
