"""Cloud backtest jobs: presets, queueing, worker execution on uploaded history, results (TAA-807)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.backtest.presets import BacktestRequest, apply_preset
from app.core.clock import ManualClock
from app.core.enums import Timeframe
from app.core.errors import ConfigError
from app.market_data.history_store import SqlHistoryStore
from app.storage.database import Database
from app.storage.models import BacktestRunRow, NotificationRow, SymbolCatalogRow, WorkerJobRow
from app.worker.backtests import BACKTEST_RUN, BacktestLimit, BacktestService, downsample
from app.worker.backtests import handlers as backtest_handlers
from app.worker.jobs import JobQueue
from app.worker.service import Worker
from tests.backtest.test_runner_cli import CONFIG, GOLDEN, SERVER, full_columns
from tests.strategy_data import EURUSD_SPEC, resample, sawtooth_m15

ENGINE = "eng-1"
NOW = datetime(2027, 1, 1, tzinfo=UTC)  # after the synthetic history


def upload(db: Database, spec: Any = EURUSD_SPEC, engine: str = ENGINE) -> pd.DataFrame:
    """What the engine's history upload and catalog replication leave in the cloud database."""
    m15 = sawtooth_m15(1800)
    store = SqlHistoryStore(db, engine)
    store.save(SERVER, spec.name, Timeframe.M15, full_columns(m15))
    store.save(SERVER, spec.name, Timeframe.H1, full_columns(resample(m15, Timeframe.H1)))
    with db.session() as sess:
        sess.add(
            SymbolCatalogRow(
                engine_id=engine,
                server=SERVER,
                symbol=spec.name,
                asset_class="FOREX_MAJOR",
                enabled=True,
                reason="",
                path="Forex",
                description="",
                spec=dataclasses.asdict(spec),
                first_seen_at=NOW,
                refreshed_at=NOW,
                present=True,
            )
        )
    return m15


def period(m15: pd.DataFrame) -> tuple[datetime, datetime]:
    close = m15["open_time"] + pd.Timedelta(minutes=15)
    return pd.Timestamp(close.iloc[1000]).to_pydatetime(), pd.Timestamp(close.iloc[1450]).to_pydatetime()


class Rig:
    def __init__(self, db: Database, **kw: Any) -> None:
        self.db, self.clock = db, ManualClock(NOW)
        self.service = BacktestService(db, self.clock, JobQueue(db, self.clock), config=lambda: CONFIG, **kw)
        self.worker = Worker(
            db, self.clock, handlers=backtest_handlers(self.service), tasks=[], worker_id="w1"
        )

    def request(self, m15: pd.DataFrame, **over: Any) -> BacktestRequest:
        start, end = period(m15)
        return BacktestRequest.model_validate({"symbols": ["EURUSD"], "start": start, "end": end} | over)

    def run(self) -> None:
        while self.worker.step():
            pass

    def row(self, run_id: str) -> BacktestRunRow:
        with self.db.session() as sess:
            row = sess.get(BacktestRunRow, run_id)
            assert row is not None
            return row


@pytest.fixture
def rig(db: Database) -> Rig:
    return Rig(db)


class TestPresets:
    def test_requests_are_bounded(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        ok = {"symbols": ["EURUSD"], "start": start, "end": start + timedelta(days=30)}
        BacktestRequest.model_validate(ok)
        for bad in (
            {"symbols": []},
            {"symbols": ["A", "B", "C", "D", "E", "F"]},
            {"symbols": ["EURUSD", "EURUSD"]},
            {"symbols": ["EUR/USD"]},
            {"end": start},
            {"end": start + timedelta(days=367)},
            {"start": "2026-01-01T00:00:00"},
            {"risk_percent": 50},
            {"preset": "aggressive"},
            {"config": {"risk": {}}},
        ):
            with pytest.raises(ValidationError):
                BacktestRequest.model_validate(ok | bad)

    def test_presets_change_only_what_they_say(self) -> None:
        req = BacktestRequest.model_validate(
            {"symbols": ["EURUSD"], "start": NOW - timedelta(days=9), "end": NOW, "preset": "conservative"}
        )
        conservative = apply_preset(CONFIG, req)
        assert conservative.risk.max_risk_per_trade_percent == CONFIG.risk.max_risk_per_trade_percent / 2
        assert conservative.backtest == CONFIG.backtest
        costly = apply_preset(CONFIG, req.model_copy(update={"preset": "high_costs", "seed": 7}))
        assert costly.backtest.slippage_points == max(CONFIG.backtest.slippage_points, 1.0) * 3
        assert costly.backtest.seed == 7 and costly.risk == CONFIG.risk
        with pytest.raises(ConfigError, match="strategies"):
            apply_preset(CONFIG, req.model_copy(update={"strategies": ["nope"]}))


class TestJobs:
    def test_a_cloud_run_matches_the_cli_on_the_same_data(self, rig: Rig, db: Database) -> None:
        m15 = upload(db)
        run = rig.service.create("u1", ENGINE, rig.request(m15), created_by="alice")
        assert run["status"] == "QUEUED"
        with db.session() as sess:
            [job] = sess.scalars(select(WorkerJobRow)).all()
            assert job.kind == BACKTEST_RUN and job.payload == {"run_id": run["run_id"]}
        rig.run()
        row = rig.row(run["run_id"])
        assert row.status == "DONE" and row.progress == 1.0 and row.error == ""
        trades, net, exits = GOLDEN
        assert row.trades_total == trades and [t["exit_reason"] for t in row.trades] == exits
        assert row.summary["metrics"]["net_profit"] == pytest.approx(
            net - CONFIG.backtest.initial_balance, abs=0.01
        )
        assert row.summary["server"] == SERVER and row.summary["provenance"]["data_hash"]
        assert row.summary["limitations"] and row.equity and len(row.equity[0]) == 3
        with db.session() as sess:
            [note] = sess.scalars(select(NotificationRow)).all()
            assert note.type == "BACKTEST_FINISHED" and note.payload["status"] == "DONE"

    def test_missing_history_fails_closed(self, rig: Rig, db: Database) -> None:
        m15 = upload(db)
        run = rig.service.create("u1", ENGINE, rig.request(m15, symbols=["GBPUSD"]), created_by="a")
        rig.run()
        row = rig.row(run["run_id"])
        assert row.status == "FAILED" and "GBPUSD" in row.error and row.trades == []
        other = rig.service.create("u1", "eng-2", rig.request(m15), created_by="a")  # another engine's data
        rig.run()
        assert rig.row(other["run_id"]).status == "FAILED"

    def test_the_time_limit_stops_a_run(self, db: Database) -> None:
        ticks = iter(range(0, 10**9, 1000))  # every progress check is 1000 s later
        rig = Rig(db, max_seconds=150, monotonic=lambda: float(next(ticks)))
        m15 = upload(db)
        run = rig.service.create("u1", ENGINE, rig.request(m15), created_by="a")
        rig.run()
        row = rig.row(run["run_id"])
        assert row.status == "FAILED" and "stopped after 150 s" in row.error

    def test_limits_on_creation(self, rig: Rig, db: Database) -> None:
        m15 = upload(db)
        for _ in range(2):
            rig.service.create("u1", ENGINE, rig.request(m15), created_by="a")
        with pytest.raises(BacktestLimit):
            rig.service.create("u1", ENGINE, rig.request(m15), created_by="a")
        rig.service.create("u2", ENGINE, rig.request(m15), created_by="b")  # per user
        rig.clock.set(datetime(2026, 1, 1, tzinfo=UTC))
        with pytest.raises(ConfigError, match="ended"):
            rig.service.create("u3", ENGINE, rig.request(m15), created_by="c")


def test_downsample_keeps_the_ends() -> None:
    points = list(range(10_000))
    out = downsample(points, 1000)
    assert len(out) == 1000 and out[0] == 0 and out[-1] == 9999
    assert downsample([1, 2], 1000) == [1, 2]
