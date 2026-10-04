"""Backtest jobs in the cloud worker (PLAN §A14 "Worker", §A17; TAA-807).

- :meth:`BacktestService.create` (called by the web API) validates a :class:`BacktestRequest` against
  ``config.yaml`` and its preset, enforces ``MAX_OPEN_RUNS`` per user, stores a QUEUED ``backtest_runs`` row
  and queues a ``backtest.run`` job in the same transaction.
- :meth:`BacktestService.handle` runs it: the engine's uploaded history (``SqlHistoryStore``, specs from its
  replicated symbol catalog, warm-up bars before ``start`` included), the same backtest code as the CLI
  (:func:`app.backtest.runner.run_backtest`), progress and lease renewal on every engine progress step, and a
  wall-clock limit of ``MAX_SECONDS``. The worker runs one job at a time, so backtests never overlap.
- Results: the CLI's summary (metrics, provenance with seed, config hash, data hash and code version), an
  equity curve downsampled to ``MAX_EQUITY_POINTS`` and the first ``MAX_STORED_TRADES`` trades. Missing
  history or specs fail the run with the loader's message (fail closed, never a partial run).
- The owner gets a BACKTEST_FINISHED notification either way.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select

from app.backtest.engine import Progress
from app.backtest.presets import BacktestRequest, apply_preset
from app.backtest.report import summary, trade_row
from app.backtest.runner import load_history, run_backtest
from app.config import AppConfig, config_hash, load_app_config
from app.core.clock import Clock
from app.core.errors import ConfigError, TaaError
from app.core.ids import new_id
from app.market_data.history_store import SqlHistoryStore
from app.storage.database import Database
from app.storage.models import BacktestRunRow
from app.sync.events import json_safe
from app.sync.notifications import NotificationType, Severity, notify
from app.sync.stream import StreamLog
from app.worker.jobs import JobFailed, JobQueue

log = logging.getLogger(__name__)

BACKTEST_RUN = "backtest.run"
MAX_OPEN_RUNS = 2
MAX_SECONDS = 30 * 60.0
MAX_EQUITY_POINTS = 1000
MAX_STORED_TRADES = 2000
OPEN = ("QUEUED", "RUNNING")


class BacktestLimit(TaaError):
    """The user already has ``MAX_OPEN_RUNS`` queued or running backtests."""


class _TimeLimit(TaaError):
    pass


def run_dict(row: BacktestRunRow, *, full: bool = False) -> dict[str, Any]:
    out = {
        "run_id": row.run_id,
        "engine_id": row.engine_id,
        "preset": row.preset,
        "request": dict(row.request),
        "status": row.status,
        "progress": round(row.progress, 4),
        "created_at": json_safe(row.created_at),
        "started_at": json_safe(row.started_at),
        "finished_at": json_safe(row.finished_at),
        "error": row.error,
        "metrics": dict(row.summary).get("metrics"),
        "trades_total": row.trades_total,
    }
    if full:
        out |= {"summary": dict(row.summary), "equity": list(row.equity)}
    return out


def downsample(points: list[Any], limit: int) -> list[Any]:
    """At most *limit* points, evenly spaced, always keeping the last one."""
    if len(points) <= limit:
        return points
    step = len(points) / limit
    picked = [points[int(i * step)] for i in range(limit - 1)]
    return [*picked, points[-1]]


class BacktestService:
    def __init__(
        self,
        db: Database,
        clock: Clock,
        queue: JobQueue,
        *,
        config: Callable[[], AppConfig] | None = None,  # default: config.yaml, read for every run
        max_seconds: float = MAX_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.db = db
        self.clock = clock
        self.queue = queue
        self._config = config
        self.max_seconds = max_seconds
        self.monotonic = monotonic

    def config(self) -> AppConfig:
        return self._config() if self._config is not None else load_app_config()

    # --- creation (web API) -------------------------------------------------------------------------------

    def create(
        self, owner_user_id: str, engine_id: str, request: BacktestRequest, *, created_by: str
    ) -> dict[str, Any]:
        """Validate and queue; raises ``ConfigError`` (bad strategies) or :class:`BacktestLimit`."""
        apply_preset(self.config(), request)  # refuse now what the run would refuse later
        now = self.clock.now_utc()
        if request.end > now:
            raise ConfigError("the period must have ended")
        with self.db.session() as sess:
            open_runs = sess.scalar(
                select(func.count())
                .select_from(BacktestRunRow)
                .where(BacktestRunRow.owner_user_id == owner_user_id, BacktestRunRow.status.in_(OPEN))
            )
            if int(open_runs or 0) >= MAX_OPEN_RUNS:
                raise BacktestLimit(f"at most {MAX_OPEN_RUNS} backtests queued or running per user")
            row = BacktestRunRow(
                run_id=new_id(),
                owner_user_id=owner_user_id,
                engine_id=engine_id,
                preset=request.preset,
                request=request.model_dump(mode="json"),
                status="QUEUED",
                progress=0.0,
                created_at=now,
                error="",
                summary={},
                equity=[],
                trades=[],
                trades_total=0,
            )
            sess.add(row)
            row.job_id = self.queue.enqueue(
                BACKTEST_RUN, {"run_id": row.run_id}, created_by=created_by[:64], max_attempts=2, sess=sess
            )
            return run_dict(row)

    # --- execution (worker job) ---------------------------------------------------------------------------

    def handle(self, ctx: Any) -> dict[str, Any]:
        run_id = str(ctx.job.payload.get("run_id", ""))
        with self.db.session() as sess:
            row = sess.get(BacktestRunRow, run_id)
            if row is None:
                raise JobFailed(f"no backtest run {run_id}")
            if row.status not in OPEN:
                return {"skipped": row.status}  # a redelivered job of a finished run
            row.status, row.started_at, row.progress = "RUNNING", self.clock.now_utc(), 0.0
            engine_id = row.engine_id
            request = BacktestRequest.model_validate(row.request)
        try:
            result = self._run(ctx, run_id, engine_id, request)
        except (TaaError, ValueError) as exc:
            message = (
                str(exc) if not isinstance(exc, _TimeLimit) else f"stopped after {self.max_seconds:.0f} s"
            )
            self._finish(run_id, "FAILED", error=message[:2000])
            raise JobFailed(message) from exc
        self._finish(run_id, "DONE", **result)
        return {"trades": result["trades_total"]}

    def _run(self, ctx: Any, run_id: str, engine_id: str, request: BacktestRequest) -> dict[str, Any]:
        config = apply_preset(self.config(), request)
        store = SqlHistoryStore(self.db, engine_id)
        server = self._server(store, request.symbols[0])
        loaded = load_history(
            store,
            server,
            request.symbols,
            config.timeframes.enabled,
            account_currency=config.backtest.account_currency,
            start=None,  # warm-up bars before the period; the engine trades only inside it
            end=request.end,
        )
        deadline = self.monotonic() + self.max_seconds
        last = [0.0]

        def progress(p: Progress) -> None:
            if self.monotonic() > deadline:
                raise _TimeLimit("time limit")
            if p.fraction - last[0] >= 0.02:
                last[0] = p.fraction
                ctx.extend()
                with self.db.session() as sess:
                    row = sess.get(BacktestRunRow, run_id)
                    if row is not None:
                        row.progress = p.fraction

        result, provenance = run_backtest(
            config,
            loaded,
            config_hash=config_hash(config),
            strategy_names=request.strategies,
            start=request.start,
            end=request.end,
            on_progress=progress,
        )
        report = json_safe(summary(result, provenance) | {"server": server, "preset": request.preset})
        equity = [
            [json_safe(p.at), round(p.balance, 2), round(p.equity, 2)]
            for p in downsample(list(result.equity_curve), MAX_EQUITY_POINTS)
        ]
        return {
            "summary": report,
            "equity": equity,
            "trades": [json_safe(trade_row(t)) for t in result.trades[:MAX_STORED_TRADES]],
            "trades_total": len(result.trades),
        }

    @staticmethod
    def _server(store: SqlHistoryStore, symbol: str) -> str:
        servers = sorted({srv for srv, sym, _ in store.available() if sym == symbol})
        if not servers:
            raise JobFailed(f"{symbol}: the engine has not uploaded history for it")
        if len(servers) > 1:  # a user who moved brokers: the history must not be mixed
            raise JobFailed(f"{symbol}: history from several servers ({', '.join(servers)})")
        return servers[0]

    def _finish(self, run_id: str, status: str, *, error: str = "", **result: Any) -> None:
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = sess.get(BacktestRunRow, run_id)
            if row is None:
                return
            row.status, row.finished_at, row.error = status, now, error
            if status == "DONE":
                row.progress = 1.0
                row.summary, row.equity, row.trades = result["summary"], result["equity"], result["trades"]
                row.trades_total = result["trades_total"]
            notify(
                sess,
                StreamLog(self.db, self.clock),
                user_id=row.owner_user_id,
                engine_id=row.engine_id,
                type_=NotificationType.BACKTEST_FINISHED,
                severity=Severity.INFO,
                payload={"run_id": run_id, "status": status, "preset": row.preset},
                now=now,
            )


def handlers(service: BacktestService) -> dict[str, Callable[[Any], dict[str, Any]]]:
    return {BACKTEST_RUN: service.handle}
