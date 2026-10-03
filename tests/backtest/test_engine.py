from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from app.backtest.engine import BacktestEngine, BacktestResult, Progress, SymbolData
from app.config import AppConfig, PositionManagementConfig, StrategiesConfig, StrategyEntry
from app.core.enums import ExitReason, Side, Timeframe
from app.execution.management import PositionView, manage
from app.execution.simulated_broker import AccountCurrencyOnly
from app.strategy.catalog import default_registry
from tests.strategy_data import EURUSD_SPEC, resample, sawtooth_m15
from tests.unit.test_exposure_manager import GBPUSD_SPEC

PM = PositionManagementConfig()
POINT = 0.00001


class TestManagementRules:
    def view(self, side: Side = Side.BUY, sl: float = 1.0980, bars: int = 0) -> PositionView:
        entry = 1.1000
        initial = entry - side.sign * 0.0020
        return PositionView(side, entry, initial, sl if side is Side.BUY else 2.2 - sl, bars)

    def test_nothing_below_one_r(self) -> None:
        assert manage(self.view(), mark=1.1019, atr=0.001, point=POINT, cfg=PM).new_sl is None

    def test_break_even_at_one_r(self) -> None:
        adj = manage(self.view(), mark=1.1020, atr=0.001, point=POINT, cfg=PM)
        assert adj.new_sl == pytest.approx(1.1000 + 2 * POINT)
        assert adj.stop_kind is ExitReason.BREAK_EVEN

    def test_trailing_after_one_and_a_half_r(self) -> None:
        adj = manage(self.view(), mark=1.1060, atr=0.001, point=POINT, cfg=PM)
        assert adj.new_sl == pytest.approx(1.1060 - 0.002)
        assert adj.stop_kind is ExitReason.TRAILING_STOP

    def test_stop_never_moves_back_or_by_less_than_a_step(self) -> None:
        trailed = self.view(sl=1.1045)
        assert (
            manage(trailed, mark=1.1060, atr=0.001, point=POINT, cfg=PM).new_sl is None
        )  # trail 1.1040 < 1.1045
        assert (
            manage(self.view(sl=1.10398), mark=1.1060, atr=0.001, point=POINT, cfg=PM).new_sl is None
        )  # 2-pt step

    def test_sell_mirrors(self) -> None:
        adj = manage(self.view(Side.SELL), mark=1.0980, atr=0.001, point=POINT, cfg=PM)
        assert adj.new_sl == pytest.approx(1.1000 - 2 * POINT)

    def test_time_stop(self) -> None:
        cfg = PositionManagementConfig(time_stop_bars=10)
        assert (
            manage(self.view(bars=10), mark=1.1, atr=0.001, point=POINT, cfg=cfg).close
            is ExitReason.TIME_STOP
        )


def symbol_data(spec, sign: int, n: int = 1800, seed: int = 5) -> SymbolData:  # type: ignore[no-untyped-def]
    m15 = sawtooth_m15(n, sign=sign, seed=seed)
    return SymbolData(spec, {Timeframe.M15: m15, Timeframe.H1: resample(m15, Timeframe.H1)})


def run(data: dict[str, SymbolData], progress: list[Progress] | None = None) -> BacktestResult:
    config = AppConfig.model_validate(
        {
            "symbols": {"allowed": list(data)},
            "backtest": {"slippage_model": "none"},
            "risk": {"correlation_groups": {}},
        }
    )
    strategies = default_registry().from_config(
        StrategiesConfig(items=[StrategyEntry(name="example_trend_pullback")]), config.timeframes
    )
    first = next(iter(data.values())).frames[Timeframe.M15]
    # the window of tests/unit/test_strategy_example.py's scenario: setups exist in both trends there
    start = pd.Timestamp(first["close_time"].iloc[1000]).to_pydatetime()
    end = pd.Timestamp(first["close_time"].iloc[1450]).to_pydatetime()
    engine = BacktestEngine(
        config,
        data,
        strategies,
        AccountCurrencyOnly("USD"),
        start=start,
        end=end,
        on_progress=None if progress is None else progress.append,
        progress_every=100,
    )
    return engine.run()


@pytest.fixture(scope="module")
def uptrend() -> BacktestResult:
    return run({"EURUSD": symbol_data(EURUSD_SPEC, 1)})


class TestEngine:
    def test_trades_follow_the_trend(self, uptrend: BacktestResult) -> None:
        assert uptrend.trades, (uptrend.decisions, uptrend.rejections)
        assert {t.side for t in uptrend.trades} == {Side.BUY}
        assert uptrend.decisions["ACCEPT"] >= len(uptrend.trades)

    def test_fills_at_bar_opens_after_the_decision(self, uptrend: BacktestResult) -> None:
        for t in uptrend.trades:
            assert t.entry_time.minute % 15 == 0 and t.entry_time.second == 0
            assert t.exit_time >= t.entry_time
            assert t.risk_money > 0
            assert t.r_multiple is not None and t.r_multiple >= -1.5  # a stop-out costs about 1R

    def test_equity_curve_and_accounting(self, uptrend: BacktestResult) -> None:
        curve = uptrend.equity_curve
        assert curve[0].at == uptrend.start
        assert curve[-1].open_positions == 0
        assert uptrend.final_equity == pytest.approx(10_000 + sum(t.net for t in uptrend.trades))

    def test_deterministic(self, uptrend: BacktestResult) -> None:
        again = run({"EURUSD": symbol_data(EURUSD_SPEC, 1)})
        assert [(t.entry_time, t.exit_price, t.net) for t in again.trades] == [
            (t.entry_time, t.exit_price, t.net) for t in uptrend.trades
        ]

    def test_multi_symbol_and_progress(self) -> None:
        events: list[Progress] = []
        result = run({"EURUSD": symbol_data(EURUSD_SPEC, 1), "GBPUSD": symbol_data(GBPUSD_SPEC, -1)}, events)
        sides = {(t.symbol, t.side) for t in result.trades}
        assert ("GBPUSD", Side.SELL) in sides
        assert ("GBPUSD", Side.BUY) not in sides
        assert ("EURUSD", Side.SELL) not in sides
        assert [e.step for e in events] == sorted(e.step for e in events)
        assert events[-1].fraction == 1.0

    def test_no_trades_outside_the_session_window(self, uptrend: BacktestResult) -> None:
        for t in uptrend.trades:
            decided = t.entry_time  # the decision bar closed at this open
            assert decided.weekday() < 5
            assert 7 <= decided.hour <= 20 or (decided - timedelta(minutes=15)).hour <= 20
