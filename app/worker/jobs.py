"""Database-backed job queue of the cloud worker (PLAN §A14 "Worker"; TAA-808).

Producers (the web service, schedules, later Web Push and backtests) call :meth:`JobQueue.enqueue`; a worker
claims one job at a time with :meth:`JobQueue.claim` and reports :meth:`finish`, :meth:`retry` or
:meth:`fail`. Every state change is a conditional UPDATE, so the queue works the same on SQLite and
PostgreSQL and with several workers:

- **Claim:** ``UPDATE ... SET status=RUNNING WHERE job_id=? AND status=QUEUED``; only the worker whose UPDATE
  changed the row owns the job. Order: ``priority``, then ``run_after``, then age.
- **Lease:** a RUNNING job belongs to its worker until ``lease_until``; long jobs extend it with
  :meth:`extend`. :meth:`requeue_stale` gives an expired lease's job back to the queue (or fails it after
  ``max_attempts``), so a worker that died never strands work.
- **Results** are accepted only from the worker holding the lease, so a worker that lost its lease cannot
  overwrite the next attempt.
- **Retries** (push sends, transient failures) back off exponentially, :func:`backoff`, up to
  ``max_attempts``; then the job is FAILED and kept for inspection.
- ``dedupe_key``: enqueueing while an open job (QUEUED or RUNNING) has the same key returns that job instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import select, update

from app.core.clock import Clock, ensure_utc
from app.core.errors import TaaError
from app.core.ids import new_id
from app.storage.database import Database
from app.storage.models.worker import WorkerJobRow

DEFAULT_LEASE = timedelta(minutes=10)
BACKOFF_BASE_SECONDS = 30.0
BACKOFF_MAX_SECONDS = 3600.0
MAX_ERROR_CHARS = 2000


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


OPEN = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)
CLOSED = (JobStatus.DONE.value, JobStatus.FAILED.value)


class JobError(TaaError):
    pass


class RetryLater(JobError):
    """Raised by a handler: try again after *seconds* (counts as an attempt)."""

    def __init__(self, reason: str, seconds: float | None = None) -> None:
        super().__init__(reason)
        self.seconds = seconds


class JobFailed(JobError):
    """Raised by a handler: the job cannot succeed; do not retry."""


def backoff(attempt: int) -> timedelta:
    """30 s, 60 s, 120 s, ... capped at one hour (attempt counts from 1)."""
    return timedelta(seconds=min(BACKOFF_BASE_SECONDS * 2 ** max(0, attempt - 1), BACKOFF_MAX_SECONDS))


@dataclass(frozen=True)
class Job:
    job_id: str
    kind: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    created_by: str

    @classmethod
    def of(cls, row: WorkerJobRow) -> Job:
        return cls(row.job_id, row.kind, dict(row.payload), row.attempts, row.max_attempts, row.created_by)


def job_dict(row: WorkerJobRow) -> dict[str, Any]:
    def iso(value: datetime | None) -> str | None:
        return None if value is None else ensure_utc(value).isoformat()

    return {
        "job_id": row.job_id,
        "kind": row.kind,
        "status": row.status,
        "attempts": row.attempts,
        "max_attempts": row.max_attempts,
        "run_after": iso(row.run_after),
        "created_at": iso(row.created_at),
        "started_at": iso(row.started_at),
        "finished_at": iso(row.finished_at),
        "last_error": row.last_error,
        "result": dict(row.result),
    }


class JobQueue:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def enqueue(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        created_by: str = "",
        priority: int = 1,
        max_attempts: int = 5,
        delay: timedelta = timedelta(0),
        dedupe_key: str | None = None,
    ) -> str:
        """Queue a job; returns its id (or the id of the open job with the same *dedupe_key*)."""
        if not 1 <= max_attempts <= 100:
            raise JobError("max_attempts: 1-100")
        now = self.clock.now_utc()
        with self.db.session() as sess:
            if dedupe_key is not None:
                existing = sess.execute(
                    select(WorkerJobRow.job_id)
                    .where(WorkerJobRow.dedupe_key == dedupe_key, WorkerJobRow.status.in_(OPEN))
                    .limit(1)
                ).scalar_one_or_none()
                if existing is not None:
                    return existing
            row = WorkerJobRow(
                job_id=new_id(),
                kind=kind,
                payload=dict(payload or {}),
                status=JobStatus.QUEUED.value,
                priority=priority,
                dedupe_key=dedupe_key,
                run_after=now + delay,
                attempts=0,
                max_attempts=max_attempts,
                created_by=created_by[:64],
                created_at=now,
                last_error="",
                result={},
            )
            sess.add(row)
            return row.job_id

    def claim(
        self, worker_id: str, *, lease: timedelta = DEFAULT_LEASE, kinds: tuple[str, ...] = ()
    ) -> Job | None:
        """The next due job, now RUNNING under *worker_id*'s lease; None when nothing is due."""
        now = self.clock.now_utc()
        with self.db.session() as sess:
            query = select(WorkerJobRow.job_id).where(
                WorkerJobRow.status == JobStatus.QUEUED.value, WorkerJobRow.run_after <= now
            )
            if kinds:
                query = query.where(WorkerJobRow.kind.in_(kinds))
            candidates = (
                sess.execute(
                    query.order_by(WorkerJobRow.priority, WorkerJobRow.run_after, WorkerJobRow.job_id).limit(
                        5
                    )
                )
                .scalars()
                .all()
            )
        for job_id in candidates:
            with self.db.session() as sess:
                result = sess.execute(
                    update(WorkerJobRow)
                    .where(WorkerJobRow.job_id == job_id, WorkerJobRow.status == JobStatus.QUEUED.value)
                    .values(
                        status=JobStatus.RUNNING.value,
                        locked_by=worker_id,
                        lease_until=now + lease,
                        attempts=WorkerJobRow.attempts + 1,
                        started_at=now,
                    )
                    .execution_options(synchronize_session=False)
                )
                if getattr(result, "rowcount", 0) == 1:
                    row = sess.get(WorkerJobRow, job_id)
                    if row is not None:
                        sess.refresh(row)
                        return Job.of(row)
        return None

    def _owned(self, job_id: str, worker_id: str, **values: Any) -> bool:
        with self.db.session() as sess:
            result = sess.execute(
                update(WorkerJobRow)
                .where(
                    WorkerJobRow.job_id == job_id,
                    WorkerJobRow.status == JobStatus.RUNNING.value,
                    WorkerJobRow.locked_by == worker_id,
                )
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            return getattr(result, "rowcount", 0) == 1

    def extend(self, job_id: str, worker_id: str, lease: timedelta = DEFAULT_LEASE) -> bool:
        """Keep a long job's lease; False when the lease was already lost."""
        return self._owned(job_id, worker_id, lease_until=self.clock.now_utc() + lease)

    def finish(self, job_id: str, worker_id: str, result: Mapping[str, Any] | None = None) -> bool:
        return self._owned(
            job_id,
            worker_id,
            status=JobStatus.DONE.value,
            result=dict(result or {}),
            finished_at=self.clock.now_utc(),
            locked_by=None,
            lease_until=None,
        )

    def fail(self, job_id: str, worker_id: str, error: str) -> bool:
        return self._owned(
            job_id,
            worker_id,
            status=JobStatus.FAILED.value,
            last_error=error[:MAX_ERROR_CHARS],
            finished_at=self.clock.now_utc(),
            locked_by=None,
            lease_until=None,
        )

    def retry(self, job: Job, worker_id: str, error: str, delay: timedelta | None = None) -> bool:
        """Back to the queue after *delay* (default :func:`backoff`), or FAILED when attempts are used up.
        Returns True when the job will run again."""
        if job.attempts >= job.max_attempts:
            self.fail(job.job_id, worker_id, f"gave up after {job.attempts} attempts: {error}")
            return False
        wait = delay if delay is not None else backoff(job.attempts)
        self._owned(
            job.job_id,
            worker_id,
            status=JobStatus.QUEUED.value,
            run_after=self.clock.now_utc() + wait,
            last_error=error[:MAX_ERROR_CHARS],
            locked_by=None,
            lease_until=None,
        )
        return True

    def requeue_stale(self) -> int:
        """Jobs whose worker lost its lease: back to the queue, or FAILED when attempts are used up. Two
        conditional UPDATEs, so a worker that finishes at the same moment keeps its result."""
        now = self.clock.now_utc()
        expired = (WorkerJobRow.status == JobStatus.RUNNING.value, WorkerJobRow.lease_until < now)
        released = {"locked_by": None, "lease_until": None, "last_error": "the worker's lease expired"}
        with self.db.session() as sess:
            failed = sess.execute(
                update(WorkerJobRow)
                .where(*expired, WorkerJobRow.attempts >= WorkerJobRow.max_attempts)
                .values(status=JobStatus.FAILED.value, finished_at=now, **released)
                .execution_options(synchronize_session=False)
            )
            requeued = sess.execute(
                update(WorkerJobRow)
                .where(*expired)
                .values(status=JobStatus.QUEUED.value, run_after=now, **released)
                .execution_options(synchronize_session=False)
            )
        return int(getattr(failed, "rowcount", 0) or 0) + int(getattr(requeued, "rowcount", 0) or 0)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.db.session() as sess:
            row = sess.get(WorkerJobRow, job_id)
            return None if row is None else job_dict(row)
