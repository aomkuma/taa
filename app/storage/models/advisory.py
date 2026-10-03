"""Advisory tables (PLAN §A25-A27): the symbol catalog (TAA-6A1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, String, Text
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
