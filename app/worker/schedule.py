"""Periodic tasks of the cloud worker (TAA-808): retention, command expiry and, later, the engine watchdog.

Each task has a row in ``worker_schedules``. A worker runs an occurrence only after moving ``next_run_at``
forward with one conditional UPDATE (``WHERE next_run_at <= now``), so with several workers each occurrence
runs once; a worker that dies mid-task simply leaves the next occurrence to whoever is alive. Times come from
the injected clock (``ManualClock`` in tests).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.core.clock import Clock, ensure_utc
from app.storage.database import Database
from app.storage.models.worker import WorkerScheduleRow

log = logging.getLogger(__name__)

TaskFn = Callable[[], str | None]  # returns a short summary for the log


@dataclass(frozen=True)
class ScheduledTask:
    name: str
    every: timedelta
    fn: TaskFn


class Schedule:
    def __init__(self, db: Database, clock: Clock, tasks: list[ScheduledTask]) -> None:
        names = [t.name for t in tasks]
        if len(set(names)) != len(names):
            raise ValueError("scheduled task names must be unique")
        self.db = db
        self.clock = clock
        self.tasks = tasks
        # The next due time last seen per task: no database round trip until it has come.
        self._next: dict[str, datetime] = {}

    def _ensure(self, task: ScheduledTask) -> None:
        with self.db.session() as sess:
            row = sess.get(WorkerScheduleRow, task.name)
            if row is not None:
                self._next[task.name] = ensure_utc(row.next_run_at)
                return
        try:
            with self.db.session() as sess:  # first run right away
                sess.add(WorkerScheduleRow(name=task.name, next_run_at=self.clock.now_utc()))
        except IntegrityError:  # another worker created it first
            pass
        self._next[task.name] = self.clock.now_utc()

    def _claim(self, task: ScheduledTask, worker_id: str) -> bool:
        now = self.clock.now_utc()
        with self.db.session() as sess:
            result = sess.execute(
                update(WorkerScheduleRow)
                .where(WorkerScheduleRow.name == task.name, WorkerScheduleRow.next_run_at <= now)
                .values(next_run_at=now + task.every, locked_by=worker_id)
                .execution_options(synchronize_session=False)
            )
            if getattr(result, "rowcount", 0) == 1:
                self._next[task.name] = now + task.every
                return True
            row = sess.get(WorkerScheduleRow, task.name)  # another worker ran it: remember its next time
            self._next[task.name] = now + task.every if row is None else ensure_utc(row.next_run_at)
            return False

    def _record(self, task: ScheduledTask, status: str, error: str = "") -> None:
        with self.db.session() as sess:
            row = sess.get(WorkerScheduleRow, task.name)
            if row is not None:
                row.last_run_at = self.clock.now_utc()
                row.last_status = status
                row.last_error = error[:2000]

    def run_due(self, worker_id: str) -> list[str]:
        """Run every task that is due and this worker claimed; returns their names. A failing task is logged
        and recorded and never stops the others."""
        ran: list[str] = []
        now = self.clock.now_utc()
        for task in self.tasks:
            if task.name not in self._next:
                self._ensure(task)
            if now < self._next[task.name] or not self._claim(task, worker_id):
                continue
            ran.append(task.name)
            try:
                summary = task.fn()
            except Exception as exc:  # task boundary: one broken task never stops the worker
                log.exception("scheduled task %s failed", task.name)
                self._record(task, "FAILED", f"{type(exc).__name__}: {exc}")
                continue
            self._record(task, "OK")
            if summary:
                log.info("scheduled task %s: %s", task.name, summary)
        return ran
