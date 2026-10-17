"""Entry lanes in one backtest account (TAA-507): every setup trading together, as the live engine runs them."""

from __future__ import annotations

import json
from datetime import timedelta
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from app.backtest.engine import BacktestEngine, BacktestLane, BacktestResult, SymbolData
from app.backtest.runner import load_history, run_backtest
from app.cli.__main__ import main
from app.config import AppConfig, StrategiesConfig, StrategyEntry
from app.core.enums import ExitReason, Timeframe
from app.execution.simulated_broker import AccountCurrencyOnly
from app.market_data.history_store import ParquetHistoryStore
from app.strategy.catalog import default_registry
from app.strategy.example_strategy import TrendPullback
from app.strategy.registry import StrategyRegistry, StrategySet
from tests.backtest.test_runner_cli import full_columns
from tests.strategy_data import EURUSD_SPEC, candles_from_closes, resample, sawtooth_m15

MAIN_NAME = "example_trend_pullback"
FAST_NAME = "trend_pullback_fast"


class FastPullback(TrendPullback):
    """The example strategy under a lane's own name (lane strategy names are unique across the engine)."""

    name = FAST_NAME


def thirds(m15: pd.DataFrame) -> pd.DataFrame:
    """Each M15 bar as three noisy M5 bars walking from its open to its close."""
    rng = np.random.default_rng(5)
    o, c = m15["open"].to_numpy(), m15["close"].to_numpy()
    closes = np.column_stack([o + (c - o) * k / 3 for k in (1, 2, 3)]).ravel()
    closes += rng.normal(0.0, 0.0002, len(closes))
    return candles_from_closes(closes, Timeframe.M5, wick=np.abs(rng.normal(0.0, 0.0003, len(closes))))


@pytest.fixture(scope="module")
def data() -> dict[str, SymbolData]:
    m15 = sawtooth_m15(1800)  # the uptrend tests/backtest/test_engine.py trades
    frames = {Timeframe.M5: thirds(m15), Timeframe.M15: m15, Timeframe.H1: resample(m15, Timeframe.H1)}
    return {"EURUSD": SymbolData(EURUSD_SPEC, frames)}


def config(time_stop: int | None = None) -> AppConfig:
    management = {} if time_stop is None else {MAIN_NAME: {"time_stop_bars": time_stop}}
    return AppConfig.model_validate(
        {
            "symbols": {"allowed": ["EURUSD"]},
            "backtest": {"slippage_model": "none"},
            "risk": {"correlation_groups": {}},
            "strategies": {"items": [{"name": MAIN_NAME}]},
            "position_management": {"by_strategy": management},
            "lanes": [
                {
                    "name": "fast",
                    "timeframes": {"higher": "H1", "entry": "M5"},
                    "symbols": ["EURUSD"],
                    "strategies": {"items": [{"name": FAST_NAME}], "cooldown_bars": 12},
                }
            ],
        }
    )


def main_set(cfg: AppConfig, on: bool = True) -> StrategySet:
    items = [StrategyEntry(name=MAIN_NAME)] if on else []
    return default_registry().from_config(StrategiesConfig(items=items), cfg.timeframes)


def fast_lane(cfg: AppConfig, on: bool = True) -> BacktestLane:
    view = cfg.for_lane(cfg.lane("fast"))
    items = [StrategyEntry(name=FAST_NAME)] if on else []
    sset = StrategyRegistry((FastPullback,)).from_config(StrategiesConfig(items=items), view.timeframes)
    return BacktestLane("fast", view, sset, frozenset({"EURUSD"}))


def window(data: dict[str, SymbolData]) -> tuple[pd.Timestamp, pd.Timestamp]:
    m15 = data["EURUSD"].frames[Timeframe.M15]
    return m15["close_time"].iloc[1000], m15["close_time"].iloc[1450]


def run(
    cfg: AppConfig,
    data: dict[str, SymbolData],
    strategies: StrategySet,
    lanes: list[BacktestLane] | None = None,
) -> BacktestResult:
    start, end = window(data)
    engine = BacktestEngine(
        cfg,
        data,
        strategies,
        AccountCurrencyOnly("USD"),
        start=start.to_pydatetime(),
        end=end.to_pydatetime(),
        lanes=lanes or [],
    )
    return engine.run()


def fills(result: BacktestResult) -> list[tuple[object, ...]]:
    return [
        (t.strategy, t.entry_time, t.side, t.exit_time, t.exit_price, round(t.net, 6)) for t in result.trades
    ]


class TestPortfolio:
    def test_the_main_timeframe_alone_is_the_plain_run(self, data: dict[str, SymbolData]) -> None:
        cfg = config()
        plain = run(cfg.model_copy(update={"lanes": []}), data, main_set(cfg))
        with_idle_lane = run(cfg, data, main_set(cfg), [fast_lane(cfg, on=False)])
        assert plain.trades
        assert fills(with_idle_lane) == fills(plain)

    def test_a_lane_alone_is_its_own_run(self, data: dict[str, SymbolData]) -> None:
        cfg = config()
        lane = fast_lane(cfg)
        alone = run(lane.config, data, lane.strategies)
        in_portfolio = run(cfg, data, main_set(cfg, on=False), [lane])
        assert alone.trades
        assert fills(in_portfolio) == fills(alone)

    def test_lanes_share_the_account_and_the_symbol_limit(self, data: dict[str, SymbolData]) -> None:
        cfg = config()
        both = run(cfg, data, main_set(cfg), [fast_lane(cfg)])
        assert {t.strategy for t in both.trades} == {MAIN_NAME, FAST_NAME}
        ordered = sorted(both.trades, key=lambda t: t.entry_time)
        for a, b in pairwise(ordered):
            assert b.entry_time >= a.exit_time  # max_positions_per_symbol 1: never two at once
        assert both.rejections["MAX_POSITIONS_PER_SYMBOL"] > 0
        start, _ = window(data)
        assert both.equity_curve[1].at - both.equity_curve[0].at == timedelta(minutes=5)  # the M5 clock
        assert both.equity_curve[0].at >= start

    def test_bars_held_count_on_the_strategy_s_own_timeframe(self, data: dict[str, SymbolData]) -> None:
        cfg = config(time_stop=3)
        both = run(cfg, data, main_set(cfg), [fast_lane(cfg)])
        timed = [t for t in both.trades if t.strategy == MAIN_NAME and t.exit_reason is ExitReason.TIME_STOP]
        assert timed
        # three M15 bars, although the broker steps EURUSD on M5 for the fast lane
        assert {t.exit_time - t.entry_time for t in timed} == {timedelta(minutes=45)}


SERVER = "FBS-Demo"
LANE_ONLY = {
    "symbols": {"allowed": ["EURUSD"]},
    "backtest": {"slippage_model": "none"},
    "risk": {"correlation_groups": {}},
    "strategies": {"items": []},
    "lanes": [
        {
            "name": "fast",
            "timeframes": {"higher": "H1", "entry": "M5"},
            "symbols": ["EURUSD"],
            "strategies": {"items": [{"name": MAIN_NAME}], "cooldown_bars": 12},
        }
    ],
}


@pytest.fixture
def store(tmp_path: Path, data: dict[str, SymbolData]) -> ParquetHistoryStore:
    s = ParquetHistoryStore(tmp_path / "history")
    for tf, frame in data["EURUSD"].frames.items():
        s.save(SERVER, "EURUSD", tf, full_columns(frame), EURUSD_SPEC)
    return s


class TestRunner:
    def test_the_runner_builds_the_lanes_from_the_config(
        self, store: ParquetHistoryStore, data: dict[str, SymbolData]
    ) -> None:
        cfg = AppConfig.model_validate(LANE_ONLY)
        tfs = {"EURUSD": [Timeframe.M15, Timeframe.H1, Timeframe.M5]}
        loaded = load_history(store, SERVER, ["EURUSD"], tfs, account_currency="USD")
        start, end = (x.to_pydatetime() for x in window(data))
        both, prov = run_backtest(cfg, loaded, config_hash="h", start=start, end=end, portfolio=True)
        lane, _ = run_backtest(cfg.for_lane(cfg.lane("fast")), loaded, config_hash="h", start=start, end=end)
        assert lane.trades and fills(both) == fills(lane)
        assert prov.extra["lanes"] == ["fast"] and prov.extra["strategies"] == [MAIN_NAME]

    def test_cli_portfolio(
        self,
        store: ParquetHistoryStore,
        data: dict[str, SymbolData],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        env, conf, out = tmp_path / ".env", tmp_path / "config.yaml", tmp_path / "report"
        env.write_text("TRADING_MODE=BACKTEST\n", encoding="utf-8")
        conf.write_text(yaml.safe_dump(LANE_ONLY), encoding="utf-8")
        start, end = window(data)
        args = ["--env-file", str(env), "--config", str(conf), "backtest", "--server", SERVER, "--data"]
        args += [str(store.root), "--start", start.isoformat(), "--end", end.isoformat(), "--out", str(out)]
        assert main([*args, "--portfolio"]) == 0, capsys.readouterr().err
        printed = capsys.readouterr().out
        assert f"  {MAIN_NAME}: " in printed and " R/trade, net " in printed
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        assert summary["provenance"]["lanes"] == ["fast"]
        assert main([*args, "--portfolio", "--lane", "fast"]) == 1
