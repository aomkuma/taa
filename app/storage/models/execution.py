"""Broker order intents (PLAN §A12; TAA-1202): written before every send, the record of what happened."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, EngineKeyed
from app.storage.types import UTCDateTime


class OrderIntentRow(EngineKeyed, Base):
    __tablename__ = "order_intents"
    __table_args__ = (UniqueConstraint("engine_id", "idempotency_key"),)

    intent_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    decision_id: Mapped[str] = mapped_column(String(36))
    signal_id: Mapped[str] = mapped_column(String(36))
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(4))
    volume: Mapped[float] = mapped_column(Float)
    price_requested: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    magic: Mapped[int] = mapped_column(BigInteger)
    comment: Mapped[str] = mapped_column(String(32))
    risk_money: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(20), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retcode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retcode_desc: Mapped[str] = mapped_column(String(48), default="")
    order_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deal_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    position_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fill_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    slippage_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    detail: Mapped[str] = mapped_column(Text, default="")
    # entry plans (TAA-1207): the parts of one signal share plan_key; a LIMIT part rests until cancel_after
    plan_key: Mapped[str] = mapped_column(String(80), default="", server_default="", index=True)
    part_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    order_type: Mapped[str] = mapped_column(String(8), default="MARKET", server_default="MARKET")
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    cancel_after: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class MagicRegistryRow(Base):
    """Stable magic numbers (PLAN_LEARNING §L21.8; TAA-L901): ``(bot_id, strategy)`` → its slots, assigned
    once and never reused. Magic = ``MAGIC_NUMBER_BASE + bot_slot × 100 + strategy_slot``. Engine-local."""

    __tablename__ = "magic_registry"
    __table_args__ = (UniqueConstraint("bot_slot", "strategy_slot"),)

    bot_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    strategy: Mapped[str] = mapped_column(String(64), primary_key=True)
    bot_slot: Mapped[int] = mapped_column(Integer)
    strategy_slot: Mapped[int] = mapped_column(Integer)
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime())


class BrokerTradeRow(EngineKeyed, Base):
    """A closed bot position on the broker account (DEMO/LIVE; TAA-1208), booked once from the MT5 deals.

    One row per MT5 position, so a split entry's parts are separate rows like in the terminal. ``net`` is
    profit + swap + commission + fee (the balance change); ``r_multiple`` is measured from the intent's stop.
    """

    __tablename__ = "broker_trades"

    position_ticket: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_key: Mapped[str] = mapped_column(String(32), index=True)
    mode: Mapped[str] = mapped_column(String(8))  # DEMO | LIVE
    intent_id: Mapped[str] = mapped_column(String(36))
    decision_id: Mapped[str] = mapped_column(String(36))
    strategy: Mapped[str] = mapped_column(String(64))
    magic: Mapped[int] = mapped_column(BigInteger)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(4))
    volume: Mapped[float] = mapped_column(Float)
    plan_key: Mapped[str] = mapped_column(String(80), default="")
    part_index: Mapped[int] = mapped_column(Integer, default=0)
    entry_time: Mapped[datetime] = mapped_column(UTCDateTime())
    entry_price: Mapped[float] = mapped_column(Float)
    sl_initial: Mapped[float] = mapped_column(Float)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    exit_price: Mapped[float] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    profit: Mapped[float] = mapped_column(Float)
    swap: Mapped[float] = mapped_column(Float)
    commission: Mapped[float] = mapped_column(Float)  # commission + fee
    net: Mapped[float] = mapped_column(Float)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    booked_at: Mapped[datetime] = mapped_column(UTCDateTime())
