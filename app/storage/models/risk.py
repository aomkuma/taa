"""Risk bookkeeping: loss baselines, high-water mark, consecutive losses, processed deals (TAA-403).

Accounts are identified by ``account_key`` (a hash of login and server), so these rows can be replicated to
the cloud without exposing the login.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, utcnow
from app.storage.types import UTCDateTime


class RiskBaseline(Base):
    """Equity at the start of a broker day or week, plus the cash flows booked during it."""

    __tablename__ = "risk_baselines"

    account_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    period: Mapped[str] = mapped_column(String(8), primary_key=True)  # DAY | WEEK
    period_key: Mapped[str] = mapped_column(String(16), primary_key=True)  # 2026-09-30 | 2026-W40
    start_equity: Mapped[float] = mapped_column(Float)
    cash_flow: Mapped[float] = mapped_column(Float, default=0.0)  # deposits (+) / withdrawals (-) since start
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class RiskState(Base):
    __tablename__ = "risk_state"

    account_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    hwm: Mapped[float] = mapped_column(Float)  # peak of equity net of cumulative cash flows
    cumulative_cash_flow: Mapped[float] = mapped_column(Float, default=0.0)
    consecutive_losses: Mapped[int] = mapped_column(Integer, default=0)
    last_loss_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class RiskDeal(Base):
    """A deal already applied to the risk state (cash flow or closed bot trade), so it is applied once."""

    __tablename__ = "risk_deals"

    account_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    ticket: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # CASH_FLOW | CLOSE
    amount: Mapped[float] = mapped_column(Float)
    time_utc: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
