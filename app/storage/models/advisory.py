"""Advisory tables (PLAN §A25-A27): the symbol catalog (TAA-6A1) and suitability snapshots (TAA-6A5)."""

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
