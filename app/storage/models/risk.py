"""Risk bookkeeping: loss baselines, HWM, streaks, processed deals (TAA-403); circuit breakers (TAA-404).

Accounts are identified by ``account_key`` (a hash of login and server), so these rows can be replicated to
the cloud without exposing the login.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, EngineKeyed, EngineTagged, utcnow
from app.storage.types import JSONType, UTCDateTime


class RiskBaseline(EngineKeyed, Base):
    """Equity at the start of a broker day or week, plus the cash flows booked during it."""

    __tablename__ = "risk_baselines"

    account_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    period: Mapped[str] = mapped_column(String(8), primary_key=True)  # DAY | WEEK
    period_key: Mapped[str] = mapped_column(String(16), primary_key=True)  # 2026-09-30 | 2026-W40
    start_equity: Mapped[float] = mapped_column(Float)
    cash_flow: Mapped[float] = mapped_column(Float, default=0.0)  # deposits (+) / withdrawals (-) since start
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class RiskState(EngineKeyed, Base):
    __tablename__ = "risk_state"

    account_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    hwm: Mapped[float] = mapped_column(Float)  # peak of equity net of cumulative cash flows
    cumulative_cash_flow: Mapped[float] = mapped_column(Float, default=0.0)
    consecutive_losses: Mapped[int] = mapped_column(Integer, default=0)
    last_loss_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class RiskDeal(EngineKeyed, Base):
    """A deal already applied to the risk state (cash flow or closed bot trade), so it is applied once."""

    __tablename__ = "risk_deals"

    account_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    ticket: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # CASH_FLOW | CLOSE
    amount: Mapped[float] = mapped_column(Float)
    time_utc: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class BreakerStateRow(EngineKeyed, Base):
    """Current state of one circuit breaker in one scope (``scope_key`` is "" for global breakers)."""

    __tablename__ = "breaker_states"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(16))  # CLOSED | OPEN | HALF_OPEN
    latched: Mapped[bool] = mapped_column(Boolean, default=False)  # manual reset required
    reason: Mapped[str] = mapped_column(Text, default="")
    opened_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    opened_day_key: Mapped[str] = mapped_column(String(16), default="")
    opened_week_key: Mapped[str] = mapped_column(String(16), default="")
    trips_day_key: Mapped[str] = mapped_column(String(16), default="")
    trips_today: Mapped[int] = mapped_column(Integer, default=0)
    healthy_count: Mapped[int] = mapped_column(Integer, default=0)
    healthy_since: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class BreakerEventRow(EngineTagged, Base):
    """Every trip, half-open probe and reset, with who and why (also appended to the audit chain)."""

    __tablename__ = "breaker_events"
    __table_args__ = (UniqueConstraint("engine_id", "source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # the engine's own id of this row (the cloud's ``id`` is its own; TAA-709)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ts_utc: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    name: Mapped[str] = mapped_column(String(32), index=True)
    scope_key: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(16))  # TRIP | HALF_OPEN | RESET
    severity: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
