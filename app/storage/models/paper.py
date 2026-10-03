"""PAPER-mode account, order intents and positions (TAA-602): the simulated book survives restarts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, utcnow
from app.storage.types import UTCDateTime


class PaperAccountRow(Base):
    __tablename__ = "paper_accounts"

    account_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    currency: Mapped[str] = mapped_column(String(8))
    initial_balance: Mapped[float] = mapped_column(Float)
    balance: Mapped[float] = mapped_column(Float)
    next_id: Mapped[int] = mapped_column(BigInteger, default=1)  # simulated order/ticket/deal ids
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PaperIntentRow(Base):
    """One order the engine decided to place. ``idempotency_key`` is unique: a decision is executed once."""

    __tablename__ = "paper_intents"

    intent_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_key: Mapped[str] = mapped_column(String(32), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    decision_id: Mapped[str] = mapped_column(String(36))
    signal_id: Mapped[str] = mapped_column(String(36))
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(4))
    volume: Mapped[float] = mapped_column(Float)
    entry_type: Mapped[str] = mapped_column(String(8))
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    magic: Mapped[int] = mapped_column(BigInteger)
    risk_money: Mapped[float] = mapped_column(Float)
    order_id: Mapped[int] = mapped_column(BigInteger)
    ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # PENDING | FILLED | REJECTED | EXPIRED
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class PaperPositionRow(Base):
    __tablename__ = "paper_positions"

    ticket: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_key: Mapped[str] = mapped_column(String(32), index=True)
    intent_id: Mapped[str] = mapped_column(String(36))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(4))
    volume: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[datetime] = mapped_column(UTCDateTime())
    entry_price: Mapped[float] = mapped_column(Float)
    sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_kind: Mapped[str] = mapped_column(String(8))
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    swap: Mapped[float] = mapped_column(Float, default=0.0)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    mfe: Mapped[float] = mapped_column(Float, default=0.0)
    price_current: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(8), index=True)  # OPEN | CLOSED
    exit_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    net: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    bars_held: Mapped[int] = mapped_column(Integer, default=0)
