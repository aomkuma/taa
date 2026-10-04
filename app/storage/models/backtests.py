"""Cloud backtest runs (PLAN §A17, §A18; TAA-807).

One row per run a user asked for on one of their engines' uploaded history: the validated request, the job
state and progress, and the results the PWA renders (summary with metrics and provenance, a downsampled
equity curve and the first ``MAX_STORED_TRADES`` trades; ``trades_total`` counts all).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base
from app.storage.types import JSONType, UTCDateTime


class BacktestRunRow(Base):
    __tablename__ = "backtest_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUIDv7
    owner_user_id: Mapped[str] = mapped_column(String(36), index=True)
    engine_id: Mapped[str] = mapped_column(String(64), index=True)
    preset: Mapped[str] = mapped_column(String(32))
    request: Mapped[dict[str, Any]] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(12), index=True)  # QUEUED / RUNNING / DONE / FAILED
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[dict[str, Any]] = mapped_column(JSONType)
    equity: Mapped[list[Any]] = mapped_column(JSONType)
    trades: Mapped[list[Any]] = mapped_column(JSONType)
    trades_total: Mapped[int] = mapped_column(Integer, default=0)
