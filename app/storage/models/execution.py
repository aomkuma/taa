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
