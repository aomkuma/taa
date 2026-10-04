"""Cloud worker: job queue, leases and retries, schedules, retention, the loop, health and settings (TAA-808)."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from app.config import load_worker_settings
from app.core.clock import ManualClock, SystemClock
from app.core.errors import ConfigError
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    DecisionRecordRow,
    EngineCommandRow,
    LoginThrottleRow,
    SessionRow,
    UserRow,
    WorkerHeartbeatRow,
    WorkerJobRow,
    WorkerScheduleRow,
)
from app.sync.command_queue import CommandQueue
from app.worker.__main__ import main as worker_main
from app.worker.jobs import JobError, JobFailed, JobQueue, RetryLater, backoff
from app.worker.retention import run_retention
from app.worker.schedule import Schedule, ScheduledTask
from app.worker.service import JobContext, Worker, worker_health
from tests.sync_data import sample_rows

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(NOW)


@pytest.fixture
def queue(db: Database, clock: ManualClock) -> JobQueue:
    return JobQueue(db, clock)


def status(queue: JobQueue, job_id: str) -> dict[str, Any]:
    job = queue.get(job_id)
    assert job is not None
    return job


class TestQueue:
    def test_jobs_run_by_priority_then_due_time(self, queue: JobQueue, clock: ManualClock) -> None:
        late = queue.enqueue("a", delay=timedelta(minutes=5))
        normal = queue.enqueue("a")
        urgent = queue.enqueue("a", priority=0)
        other = queue.enqueue("b")
        claimed = [queue.claim("w1", kinds=("a",)) for _ in range(3)]
        assert [j.job_id if j else None for j in claimed] == [urgent, normal, None]
        clock.advance(300)
        job = queue.claim("w1", kinds=("a",))
        assert job is not None and job.job_id == late and job.attempts == 1
        assert status(queue, other)["status"] == "QUEUED"  # another kind: not this worker's

    def test_a_job_has_one_owner(self, queue: JobQueue) -> None:
        job_id = queue.enqueue("a", {"x": 1})
        job = queue.claim("w1")
        assert job is not None and job.payload == {"x": 1}
        assert queue.claim("w2") is None
        assert not queue.finish(job_id, "w2", {"stolen": True})
        assert queue.finish(job_id, "w1", {"ok": True})
        done = status(queue, job_id)
        assert done["status"] == "DONE" and done["result"] == {"ok": True} and done["finished_at"]

    def test_retries_back_off_then_fail(self, queue: JobQueue, clock: ManualClock) -> None:
        job_id = queue.enqueue("push.send", max_attempts=2)
        job = queue.claim("w1")
        assert job is not None and queue.retry(job, "w1", "503 from the push service")
        queued = status(queue, job_id)
        assert queued["status"] == "QUEUED" and queued["last_error"] == "503 from the push service"
        assert queued["run_after"] == (NOW + timedelta(seconds=30)).isoformat()
        assert queue.claim("w1") is None
        clock.advance(30)
        job = queue.claim("w1")
        assert job is not None and job.attempts == 2
        assert not queue.retry(job, "w1", "still 503")
        failed = status(queue, job_id)
        assert failed["status"] == "FAILED" and failed["last_error"].startswith("gave up after 2 attempts")

    def test_backoff(self) -> None:
        assert [backoff(n).total_seconds() for n in (1, 2, 3, 8, 20)] == [30, 60, 120, 3600, 3600]

    def test_a_lost_lease_goes_back_to_the_queue(self, queue: JobQueue, clock: ManualClock) -> None:
        job_id = queue.enqueue("a", max_attempts=2)
        assert queue.claim("w1", lease=timedelta(seconds=60)) is not None
        clock.advance(30)
        assert queue.extend(job_id, "w1", timedelta(seconds=60))
        clock.advance(61)
        assert queue.requeue_stale() == 1
        assert not queue.finish(job_id, "w1")  # the dead worker's late result is dropped
        assert queue.claim("w2", lease=timedelta(seconds=60)) is not None
        clock.advance(61)
        assert queue.requeue_stale() == 1
        assert status(queue, job_id)["status"] == "FAILED"  # attempts used up

    def test_dedupe_key_while_open(self, queue: JobQueue) -> None:
        first = queue.enqueue("a", dedupe_key="k")
        assert queue.enqueue("a", dedupe_key="k") == first
        job = queue.claim("w1")
        assert job is not None and queue.enqueue("a", dedupe_key="k") == first
        queue.finish(first, "w1")
        assert queue.enqueue("a", dedupe_key="k") != first

    def test_attempt_bounds(self, queue: JobQueue) -> None:
        with pytest.raises(JobError):
            queue.enqueue("a", max_attempts=0)


class TestSchedule:
    def test_each_occurrence_runs_once_across_workers(self, db: Database, clock: ManualClock) -> None:
        runs: list[str] = []
        task = ScheduledTask("tick", timedelta(seconds=30), lambda: runs.append("tick") or None)
        a, b = Schedule(db, clock, [task]), Schedule(db, clock, [task])
        assert a.run_due("w1") == ["tick"] and b.run_due("w2") == []
        clock.advance(29)
        assert a.run_due("w1") == [] and b.run_due("w2") == []
        clock.advance(1)
        assert b.run_due("w2") == ["tick"] and a.run_due("w1") == []
        assert runs == ["tick", "tick"]

    def test_a_failing_task_is_recorded_and_the_others_run(self, db: Database, clock: ManualClock) -> None:
        def boom() -> str:
            raise RuntimeError("database gone")

        ran: list[str] = []
        schedule = Schedule(
            db,
            clock,
            [
                ScheduledTask("bad", timedelta(minutes=1), boom),
                ScheduledTask("good", timedelta(minutes=1), lambda: ran.append("x") or "fine"),
            ],
        )
        assert schedule.run_due("w1") == ["bad", "good"] and ran == ["x"]
        with db.session() as sess:
            bad, good = sess.get(WorkerScheduleRow, "bad"), sess.get(WorkerScheduleRow, "good")
            assert bad is not None and bad.last_status == "FAILED" and "database gone" in bad.last_error
            assert good is not None and good.last_status == "OK"

    def test_names_are_unique(self, db: Database, clock: ManualClock) -> None:
        task = ScheduledTask("x", timedelta(seconds=1), lambda: None)
        with pytest.raises(ValueError, match="unique"):
            Schedule(db, clock, [task, task])


class TestWorker:
    def make(self, db: Database, clock: ManualClock, handlers: Mapping[str, Any], **kw: Any) -> Worker:
        return Worker(db, clock, handlers=handlers, tasks=kw.pop("tasks", []), worker_id="w1", **kw)

    def test_handlers_run_jobs_and_outcomes_are_recorded(self, db: Database, clock: ManualClock) -> None:
        def ok(ctx: JobContext) -> dict[str, Any]:
            assert ctx.extend()
            return {"echo": ctx.job.payload["n"]}

        def later(ctx: JobContext) -> None:
            raise RetryLater("push service busy", seconds=5)

        def hopeless(ctx: JobContext) -> None:
            raise JobFailed("subscription gone (410)")

        def broken(ctx: JobContext) -> None:
            raise ZeroDivisionError("bug")

        worker = self.make(db, clock, {"ok": ok, "later": later, "hopeless": hopeless, "broken": broken})
        ids = {kind: worker.queue.enqueue(kind, {"n": 1}) for kind in ("ok", "later", "hopeless", "broken")}
        unknown = worker.queue.enqueue("from_a_newer_release")
        while worker.step():
            pass
        got = {kind: status(worker.queue, i) for kind, i in ids.items()}
        assert got["ok"]["status"] == "DONE" and got["ok"]["result"] == {"echo": 1}
        assert (
            got["later"]["status"] == "QUEUED"
            and got["later"]["run_after"] == (NOW + timedelta(seconds=5)).isoformat()
        )
        assert (
            got["hopeless"]["status"] == "FAILED"
            and got["hopeless"]["last_error"] == "subscription gone (410)"
        )
        assert got["broken"]["status"] == "QUEUED" and "ZeroDivisionError" in got["broken"]["last_error"]
        assert status(worker.queue, unknown)["status"] == "QUEUED"  # left for a worker that knows it
        assert (worker.counters.done, worker.counters.failed) == (1, 1)
        with db.session() as sess:
            beat = sess.get(WorkerHeartbeatRow, "w1")
            assert beat is not None and beat.status == "RUNNING"

    def test_without_handlers_no_job_is_claimed(self, db: Database, clock: ManualClock) -> None:
        worker = self.make(db, clock, {})
        job_id = worker.queue.enqueue("anything")
        assert worker.step() is False and status(worker.queue, job_id)["status"] == "QUEUED"

    def test_run_until_stopped(self, db: Database, clock: ManualClock) -> None:
        stop = threading.Event()

        def last(ctx: JobContext) -> None:
            stop.set()

        worker = self.make(db, clock, {"last": last}, poll_seconds=0.01)
        worker.queue.enqueue("last")
        worker.run(stop)
        assert worker.counters.done == 1
        health = worker_health(db, clock)
        assert health["status"] == "stale" and health["workers"][0]["status"] == "STOPPED"

    def test_a_failing_pass_does_not_end_the_loop(
        self, db: Database, clock: ManualClock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stop = threading.Event()
        worker = self.make(db, clock, {}, poll_seconds=0.01)
        calls = iter([RuntimeError("db down"), None])

        def flaky() -> int:
            exc = next(calls)
            if exc is not None:
                raise exc
            stop.set()
            return 0

        monkeypatch.setattr(worker.queue, "requeue_stale", flaky)
        worker.run(stop)
        assert worker.counters.last_error == "RuntimeError: db down"

    def test_default_tasks_expire_commands_and_apply_retention(
        self, db: Database, clock: ManualClock
    ) -> None:
        commands = CommandQueue(db, clock)
        cmd = commands.enqueue("eng-1", "RESYNC", created_by="alice")
        worker = Worker(db, clock, worker_id="w1")
        assert {t.name for t in worker.schedule.tasks} == {
            "retention",
            "expire_commands",
            "engine_watchdog",
            "opportunity_alerts",
        }
        clock.advance(121)
        worker.step()
        row = commands.get(cmd["id"])
        assert row is not None and row.status == "EXPIRED"
        with db.session() as sess:
            assert {r.name for r in sess.scalars(select(WorkerScheduleRow))} == {
                "retention",
                "expire_commands",
                "engine_watchdog",
                "opportunity_alerts",
            }

    def test_health(self, db: Database, clock: ManualClock) -> None:
        assert worker_health(db, clock)["status"] == "none"
        worker = self.make(db, clock, {})
        worker.step()
        assert worker_health(db, clock)["status"] == "ok"
        clock.advance(61)
        assert worker_health(db, clock)["status"] == "stale"


class TestRetention:
    def test_only_housekeeping_rows_are_removed(self, db: Database, clock: ManualClock) -> None:
        old, recent = NOW - timedelta(days=100), NOW - timedelta(hours=1)
        with db.session() as sess:
            sess.add(
                UserRow(
                    id="u1",
                    username="alice",
                    password_hash="x",
                    totp_secret_enc="x",
                    role="OWNER",
                    created_at=old,
                )
            )
        with db.session() as sess:
            for sid, expires, revoked in (
                ("s-old", old, None),
                ("s-revoked", NOW + timedelta(hours=1), old),
                ("s-live", NOW + timedelta(hours=1), None),
            ):
                sess.add(
                    SessionRow(
                        id=sid,
                        token_hash=sid,
                        user_id="u1",
                        created_at=old,
                        last_seen_at=recent,
                        expires_at=expires,
                        revoked_at=revoked,
                    )
                )
            sess.add(LoginThrottleRow(key="user:old", failures=3, locked_until=None, updated_at=old))
            sess.add(
                LoginThrottleRow(
                    key="user:locked", failures=9, locked_until=NOW + timedelta(hours=1), updated_at=old
                )
            )
            for i, (state, created) in enumerate((("EXECUTED", old), ("QUEUED", old), ("EXECUTED", recent))):
                sess.add(
                    EngineCommandRow(
                        command_id=f"c{i}",
                        engine_id="e",
                        type="RESYNC",
                        params={},
                        created_by="a",
                        created_at=created,
                        expires_at=created,
                        status=state,
                        result={},
                    )
                )
            for i, (state, finished) in enumerate((("DONE", old), ("FAILED", recent), ("RUNNING", None))):
                sess.add(
                    WorkerJobRow(
                        job_id=f"j{i}",
                        kind="k",
                        payload={},
                        status=state,
                        run_after=old,
                        created_at=old,
                        finished_at=finished,
                        last_error="",
                        result={},
                    )
                )
            sess.add(WorkerHeartbeatRow(worker_id="gone", status="STOPPED", started_at=old, beat_at=old))
            sess.add_all(r for r in sample_rows() if isinstance(r, DecisionRecordRow))
        AuditLog(db, "web", ManualClock(old)).append("OLD", "x", {})

        removed = run_retention(db, clock)
        assert removed == {
            "sessions": 2,
            "login_throttle": 1,
            "ingest_nonces": 0,
            "engine_commands": 1,
            "worker_jobs": 1,
            "worker_heartbeats": 1,
        }
        with db.session() as sess:
            assert sess.scalars(select(SessionRow.id)).all() == ["s-live"]
            assert sess.scalars(select(LoginThrottleRow.key)).all() == ["user:locked"]
            assert sorted(sess.scalars(select(EngineCommandRow.command_id))) == ["c1", "c2"]
            assert sorted(sess.scalars(select(WorkerJobRow.job_id))) == ["j1", "j2"]
            for model in (AuditEvent, DecisionRecordRow):  # records are kept forever
                assert sess.scalar(select(func.count()).select_from(model)) == 1


class TestEntryPoint:
    def test_settings(self) -> None:
        settings = load_worker_settings(environ={"WORKER_ENV": "development", "WORKER_POLL_SECONDS": "5"})
        assert (
            settings.WORKER_POLL_SECONDS == 5.0 and not settings.is_production and settings.WORKER_ID is None
        )
        assert load_worker_settings(environ={}).is_production
        for bad in ({"WORKER_POLL_SECONDS": "0"}, {"WORKER_ID": "has space"}, {"WORKER_ENV": "staging"}):
            with pytest.raises(ConfigError):
                load_worker_settings(environ=bad)

    def test_check_reports_health(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite:///{(tmp_path / 'cloud.db').as_posix()}"
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setattr(
            "app.worker.__main__.configure_logging", lambda *_a, **_k: None
        )  # global handlers
        args = ["check", "--env-file", str(tmp_path / "none.env")]
        assert worker_main([*args, "--migrate"]) == 1
        assert '"status": "none"' in capsys.readouterr().out
        db = Database(url)
        Worker(db, SystemClock(), tasks=[], worker_id="w1").beat()
        db.dispose()
        assert worker_main(args) == 0
