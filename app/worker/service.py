"""The cloud worker process (PLAN §A14 "Worker"; TAA-808): ``python -m app.worker`` / Railway ``worker``.

One loop, single-threaded, each pass:

1. heartbeat (``worker_heartbeats``, every ``heartbeat_seconds``)
2. leases that expired go back to the queue (:meth:`JobQueue.requeue_stale`)
3. due periodic tasks (:class:`app.worker.schedule.Schedule`)
4. at most one job: claim, run its handler, record DONE / retry / FAILED

and sleeps ``poll_seconds`` when there was no job. Handlers are registered by kind (Web Push sends, backtests
and analytics register theirs in their tickets). A handler raises :class:`RetryLater` for a transient problem
(push retries back off this way), :class:`JobFailed` for a permanent one; any other exception is logged with
its traceback and retried with backoff. Nothing a handler or task does can stop the loop.

Health: the heartbeat row; :func:`worker_health` (used by ``python -m app.worker check``) reports whether a
worker beat recently.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app import __version__
from app.core.clock import Clock, ensure_utc
from app.storage.database import Database
from app.storage.models.worker import WorkerHeartbeatRow
from app.sync.command_queue import CommandQueue
from app.worker.jobs import DEFAULT_LEASE, Job, JobFailed, JobQueue, RetryLater
from app.worker.retention import run_retention
from app.worker.schedule import Schedule, ScheduledTask

log = logging.getLogger(__name__)

HEALTHY_WITHIN = timedelta(seconds=60)


@dataclass
class JobContext:
    """What a handler gets: the job, and a way to keep a long job's lease."""

    job: Job
    queue: JobQueue
    worker_id: str
    clock: Clock

    def extend(self, lease: timedelta = DEFAULT_LEASE) -> bool:
        return self.queue.extend(self.job.job_id, self.worker_id, lease)


Handler = Callable[[JobContext], Mapping[str, Any] | None]


def default_worker_id() -> str:
    return f"{socket.gethostname()[:48]}-{os.getpid()}"


def default_tasks(db: Database, clock: Clock) -> list[ScheduledTask]:
    commands = CommandQueue(db, clock)

    def retention() -> str:
        removed = run_retention(db, clock)
        return ", ".join(f"{t}={n}" for t, n in removed.items() if n) or "nothing to remove"

    def expire_commands() -> str | None:
        n = commands.expire()
        return f"{n} commands expired" if n else None

    return [
        ScheduledTask("retention", timedelta(hours=1), retention),
        ScheduledTask("expire_commands", timedelta(seconds=30), expire_commands),
    ]


@dataclass
class Counters:
    done: int = 0
    failed: int = 0
    last_error: str = ""


@dataclass
class Worker:
    db: Database
    clock: Clock
    handlers: Mapping[str, Handler] = field(default_factory=dict)
    tasks: list[ScheduledTask] | None = None
    worker_id: str = field(default_factory=default_worker_id)
    poll_seconds: float = 2.0
    heartbeat_seconds: float = 10.0
    lease: timedelta = DEFAULT_LEASE

    def __post_init__(self) -> None:
        self.queue = JobQueue(self.db, self.clock)
        self.schedule = Schedule(
            self.db, self.clock, default_tasks(self.db, self.clock) if self.tasks is None else self.tasks
        )
        self.counters = Counters()
        self._started = self.clock.now_utc()
        self._next_beat = float("-inf")
        self._current: str | None = None

    # --- loop ---------------------------------------------------------------------------------------------

    def step(self) -> bool:
        """One pass of the loop; True when a job ran (the caller then skips the idle sleep)."""
        self._beat_if_due()
        moved = self.queue.requeue_stale()
        if moved:
            log.warning("%d jobs lost their worker's lease and were requeued", moved)
        self.schedule.run_due(self.worker_id)
        if not self.handlers:  # claim() with no kinds would take any job; take none instead
            return False
        job = self.queue.claim(self.worker_id, lease=self.lease, kinds=tuple(self.handlers))
        if job is None:
            return False
        self.run_job(job)
        return True

    def run(self, stop: threading.Event) -> None:
        log.info("worker %s started (%d job kinds)", self.worker_id, len(self.handlers))
        try:
            while not stop.is_set():
                try:
                    busy = self.step()
                except Exception as exc:  # loop boundary: a database hiccup must not end the worker
                    log.exception("worker pass failed")
                    self.counters.last_error = f"{type(exc).__name__}: {exc}"
                    busy = False
                if not busy:
                    stop.wait(self.poll_seconds)
        finally:
            self.beat("STOPPED")
            log.info("worker %s stopped", self.worker_id)

    def run_job(self, job: Job) -> None:
        handler = self.handlers.get(job.kind)
        self._current = job.job_id
        try:
            if handler is None:  # claim() only takes known kinds; this guards a handler map changed meanwhile
                self.queue.fail(job.job_id, self.worker_id, f"no handler for {job.kind}")
                self.counters.failed += 1
                return
            try:
                result = handler(JobContext(job, self.queue, self.worker_id, self.clock))
            except RetryLater as exc:
                delay = None if exc.seconds is None else timedelta(seconds=exc.seconds)
                if not self.queue.retry(job, self.worker_id, str(exc), delay):
                    self.counters.failed += 1
                return
            except JobFailed as exc:
                self.queue.fail(job.job_id, self.worker_id, str(exc))
                self.counters.failed += 1
                return
            except Exception as exc:  # job boundary: retried with backoff, never fatal
                log.exception("job %s (%s) failed on attempt %d", job.job_id, job.kind, job.attempts)
                self.counters.last_error = f"{type(exc).__name__}: {exc}"
                if not self.queue.retry(job, self.worker_id, self.counters.last_error):
                    self.counters.failed += 1
                return
            if self.queue.finish(job.job_id, self.worker_id, dict(result or {})):
                self.counters.done += 1
            else:
                log.warning("job %s finished after its lease was lost; the result was dropped", job.job_id)
        finally:
            self._current = None

    # --- heartbeat ----------------------------------------------------------------------------------------

    def _beat_if_due(self) -> None:
        now = self.clock.monotonic()
        if now >= self._next_beat:
            self.beat()
            self._next_beat = now + self.heartbeat_seconds

    def beat(self, status: str = "RUNNING") -> None:
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = sess.get(WorkerHeartbeatRow, self.worker_id)
            if row is None:
                row = WorkerHeartbeatRow(
                    worker_id=self.worker_id,
                    host=socket.gethostname()[:128],
                    version=__version__,
                    started_at=self._started,
                    status=status,
                    beat_at=now,
                )
                sess.add(row)
            row.status = status
            row.beat_at = now
            row.jobs_done = self.counters.done
            row.jobs_failed = self.counters.failed
            row.current_job = self._current
            row.last_error = self.counters.last_error[:2000]


def worker_health(db: Database, clock: Clock, within: timedelta = HEALTHY_WITHIN) -> dict[str, Any]:
    """``ok`` when some worker is RUNNING and beat within *within*; else ``stale`` (or ``none``)."""
    now = clock.now_utc()
    with db.session() as sess:
        rows = list(
            sess.execute(select(WorkerHeartbeatRow).order_by(WorkerHeartbeatRow.beat_at.desc())).scalars()
        )
    workers = [
        {
            "worker_id": r.worker_id,
            "status": r.status,
            "beat_at": ensure_utc(r.beat_at).isoformat(),
            "jobs_done": r.jobs_done,
            "jobs_failed": r.jobs_failed,
        }
        for r in rows
    ]
    alive = any(r.status == "RUNNING" and now - ensure_utc(r.beat_at) <= within for r in rows)
    return {"status": "ok" if alive else ("stale" if rows else "none"), "workers": workers}
