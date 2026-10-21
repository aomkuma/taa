"""The backtest's quote path (app/backtest/engine.py "Quotes"): a quote-driven strategy (PLAN-1's NY straddle)
gets every stored tick of its window, its entry fills at the next tick, and the open position is stepped on
ticks - the stop at the crossing tick, the time exit at the first tick after the close request. Every price
and time below is worked by hand."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from app.backtest.engine import BacktestEngine, BacktestResult, SymbolData
from app.config import AppConfig, StrategiesConfig, StrategyEntry
from app.core.enums import ExitReason, Side, Timeframe
from app.execution.simulated_broker import AccountCurrencyOnly
from app.strategy.catalog import default_registry
from tests.risk_data import XAUUSD_SPEC

SPEC = dataclasses.replace(XAUUSD_SPEC, currency_margin="USD", currency_base="USD")


def m1(start: str, last_open: str) -> pd.DataFrame:
    """Flat M1 bars: 4000 +- 0.5, spread 30 points (0.30)."""
    opens = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(last_open, tz="UTC"), freq="1min")
    n = len(opens)
    return pd.DataFrame(
        {
            "open_time": opens,
            "close_time": opens + pd.Timedelta(minutes=1),
            "open": np.full(n, 4000.0),
            "high": np.full(n, 4000.5),
            "low": np.full(n, 3999.5),
            "close": np.full(n, 4000.0),
            "tick_volume": np.full(n, 100),
            "spread": np.full(n, 30),
        }
    )


def h1(df: pd.DataFrame) -> pd.DataFrame:
    key = df.open_time.dt.floor("h")
    g = df.groupby(key)
    out = pd.DataFrame(
        {
            "open": g.open.first(),
            "high": g.high.max(),
            "low": g.low.min(),
            "close": g.close.last(),
            "tick_volume": g.tick_volume.sum(),
            "spread": g.spread.max(),
        }
    )
    out.insert(0, "open_time", out.index)
    out.insert(1, "close_time", out.index + pd.Timedelta(hours=1))
    return out.reset_index(drop=True)


class Ticks:
    def __init__(self, rows: list[tuple[str, float, float]]) -> None:
        self.t = np.array([pd.Timestamp(r[0], tz="UTC").value for r in rows], dtype=np.int64)
        self.bid = np.array([r[1] for r in rows])
        self.ask = np.array([r[2] for r in rows])
        self.asked: list[datetime] = []

    def between(
        self, symbol: str, start: datetime, end: datetime
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self.asked.append(start)
        k = (self.t >= pd.Timestamp(start).value) & (self.t < pd.Timestamp(end).value)
        return self.t[k], self.bid[k], self.ask[k]


ARM = [
    ("2026-09-30 12:29:50", 4000.0, 4000.4),  # the reference: the buy stop 4002.4, the sell stop 3998.0
    ("2026-09-30 12:30:00.5", 4001.0, 4001.4),  # inside
    ("2026-09-30 12:30:01", 4002.1, 4002.5),  # ask 4002.5 >= 4002.4: the BUY; decided at this tick
    ("2026-09-30 12:30:01.5", 4002.6, 4003.0),  # the market order fills here, at the ask 4003.0
]


def run(ticks: Ticks) -> BacktestResult:
    config = AppConfig.model_validate(
        {
            "symbols": {"allowed": ["XAUUSD"]},
            "timeframes": {"higher": "H1", "entry": "M1", "warmup_bars": 3000},
            "backtest": {"slippage_model": "none"},
            "risk": {"correlation_groups": {}, "max_spread_points": 100},
            "position_management": {"break_even_trigger_r": 50.0, "trailing_start_r": 50.0},
        }
    )
    strategies = default_registry().from_config(
        StrategiesConfig(items=[StrategyEntry(name="setup_plan1_ny")]), config.timeframes
    )
    bars = m1("2026-09-27 00:00", "2026-09-30 13:30")
    engine = BacktestEngine(
        config,
        {"XAUUSD": SymbolData(SPEC, {Timeframe.M1: bars, Timeframe.H1: h1(bars)})},
        strategies,
        AccountCurrencyOnly("USD"),
        start=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
        end=datetime(2026, 9, 30, 13, 30, tzinfo=UTC),
        quotes=ticks,
    )
    return engine.run()


def test_entry_on_the_trigger_tick_fill_on_the_next_and_time_exit_on_ticks() -> None:
    ticks = Ticks(
        [
            *ARM,
            ("2026-09-30 12:45:00", 4005.0, 4005.4),
            ("2026-09-30 12:59:59", 4006.5, 4006.9),  # before 09:00 New York: still open
            ("2026-09-30 13:00:00.2", 4006.0, 4006.4),  # the first tick after the close request at 13:00
            ("2026-09-30 13:00:30", 4010.0, 4010.4),
        ]
    )
    result = run(ticks)
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.side is Side.BUY and t.entry_price == pytest.approx(4003.0)
    assert t.entry_time == datetime(2026, 9, 30, 12, 30, 1, 500_000, tzinfo=UTC)
    # 8 USD from the trigger tick's ask (the research's fill price)
    assert t.sl_initial == pytest.approx(4002.5 - 8.0)
    assert t.exit_reason is ExitReason.TIME_STOP and t.exit_price == pytest.approx(4006.0)
    assert t.exit_time == datetime(2026, 9, 30, 13, 0, 0, 200_000, tzinfo=UTC)
    record = result.journal[t.signal_id]
    assert record["strategy"] == "setup_plan1_ny" and "release" in record["conditions"]
    # the broker stepped on ticks only where some were stored while arming or holding: 12:29, 12:30, 12:45,
    # 12:59, 13:00
    assert result.tick_minutes == 5


def test_the_stop_at_the_crossing_tick_gap_included() -> None:
    ticks = Ticks([*ARM, ("2026-09-30 12:40:10", 3994.4, 3994.8), ("2026-09-30 12:40:20", 4001.0, 4001.4)])
    t = run(ticks).trades[0]
    # the bid 3994.4 is past the stop 3994.5: out at that tick's bid (gap included)
    assert t.exit_reason is ExitReason.STOP_LOSS and t.exit_price == pytest.approx(3994.4)
    assert t.exit_time == datetime(2026, 9, 30, 12, 40, 10, tzinfo=UTC)


def test_without_ticks_the_straddle_cannot_trade() -> None:
    assert run(Ticks([("2026-09-29 00:00:01", 4000.0, 4000.4)])).trades == []


def test_a_bar_close_decision_reads_the_bars_last_tick() -> None:
    """With stored ticks the quote of a bar-close decision is the bar's last tick (its age to the close), as
    live; without one the bar's close and spread."""
    ticks = Ticks([("2026-09-30 10:00:10", 4001.0, 4001.3), ("2026-09-30 10:00:50", 4002.0, 4002.45)])
    config = AppConfig.model_validate(
        {"symbols": {"allowed": ["XAUUSD"]}, "timeframes": {"higher": "H1", "entry": "M1"}}
    )
    bars = m1("2026-09-30 09:00", "2026-09-30 10:05")
    engine = BacktestEngine(
        config,
        {"XAUUSD": SymbolData(SPEC, {Timeframe.M1: bars, Timeframe.H1: h1(bars)})},
        default_registry().from_config(StrategiesConfig(items=[]), config.timeframes),
        AccountCurrencyOnly("USD"),
        quotes=ticks,
    )
    close = datetime(2026, 9, 30, 10, 1, tzinfo=UTC)
    bar = engine._bar("XAUUSD", bars.iloc[60], close)
    q = engine._decision_quote("XAUUSD", bar, close)
    assert (q.bid, q.ask, q.age_seconds) == (4002.0, 4002.45, pytest.approx(10.0))
    assert q.spread_points == pytest.approx(45.0)
    later = datetime(2026, 9, 30, 10, 2, tzinfo=UTC)
    q2 = engine._decision_quote("XAUUSD", engine._bar("XAUUSD", bars.iloc[61], later), later)
    assert (q2.bid, q2.ask) == (4000.0, pytest.approx(4000.3))  # no tick in 10:01: the bar close + 30 points
