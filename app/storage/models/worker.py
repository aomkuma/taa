"""Cloud worker tables (PLAN §A14 "Worker"; TAA-808): the job queue, periodic schedules and worker heartbeats.

Cloud only: the engine database carries them empty (one model set serves both databases).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base
from app.storage.types import JSONType, UTCDateTime


class WorkerJobRow(Base):
    """One unit of background work. QUEUED → RUNNING → DONE, or back to QUEUED for a retry, or FAILED after
    ``max_attempts``. A RUNNING job holds a lease (``lease_until``); a worker that died loses it."""

    __tablename__ = "worker_jobs"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUIDv7
    kind: Mapped[str] = mapped_column(String(48), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(12), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)  # lower runs first
    dedupe_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    run_after: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict[str, Any]] = mapped_column(JSONType)


class WorkerScheduleRow(Base):
    """A periodic task's next due time. A worker claims a run by moving ``next_run_at`` forward in one
    conditional UPDATE, so several workers never run the same occurrence twice."""

    __tablename__ = "worker_schedules"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_run_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_status: Mapped[str] = mapped_column(String(8), default="")  # OK / FAILED
    last_error: Mapped[str] = mapped_column(Text, default="")
    locked_by: Mapped[str] = mapped_column(String(64), default="")


class WorkerHeartbeatRow(Base):
    """A worker process's liveness and counters, written every few seconds (health and the System page)."""

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    host: Mapped[str] = mapped_column(String(128), default="")
    version: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(12))  # RUNNING / STOPPED
    started_at: Mapped[datetime] = mapped_column(UTCDateTime())
    beat_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    jobs_done: Mapped[int] = mapped_column(Integer, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    current_job: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
