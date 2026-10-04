"""Market-data bookkeeping tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, EngineKeyed, utcnow
from app.storage.types import UTCDateTime


class ProcessedCandle(Base):
    """Watermark: the newest closed bar already evaluated per symbol/timeframe (survives restarts)."""

    __tablename__ = "processed_candles"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    last_open_time_utc: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class HistoryCandle(EngineKeyed, Base):
    """Historical closed bars (UTC open time) used by cloud backtests and PWA charts.

    Per engine (TAA-706): the cloud keeps each engine's own bars (uploaded or streamed), so one engine's data
    can never change another user's charts or backtests."""

    __tablename__ = "history_candles"

    server: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(UTCDateTime(), primary_key=True)
    time_server: Mapped[int] = mapped_column(BigInteger)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    tick_volume: Mapped[int] = mapped_column(BigInteger, default=0)
    spread: Mapped[int] = mapped_column(Integer, default=0)
