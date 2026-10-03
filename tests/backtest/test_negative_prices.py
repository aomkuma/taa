"""Negative or zero prices (WTI front-month futures settled at -37.63 USD on 2020-04-20).

The system must not trade on such data, must keep valuing open positions correctly through it, and must
report the loss of a stop gapped through honestly (far more than 1R).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.backtest.engine import BacktestEngine, SymbolData
from app.config import AppConfig, BacktestConfig, StrategiesConfig, StrategyEntry
from app.core.enums import ExitReason, Side, Timeframe
from app.engine.decision_engine import Decision
from app.execution.fill_model import Bar
from app.execution.simulated_broker import AccountCurrencyOnly, OrderRequest, SimulatedBroker
from app.strategy.catalog import default_registry
from app.strategy.context_builder import analyze_frame, context_at
from tests.strategy_data import EURUSD_SPEC, candles_from_closes, resample, sawtooth_m15
from tests.unit.test_decision_engine import engine, request
from tests.unit.test_strategy_models import make_context

CFG = AppConfig()
T = datetime(2020, 4, 20, 12, 0, tzinfo=UTC)
H = timedelta(hours=1)
WTI = dataclasses.replace(
    EURUSD_SPEC,
    name="XTIUSD",
    description="WTI crude oil CFD",
    digits=2,
    point=0.01,
    tick_size=0.01,
    tick_value=10.0,
    tick_value_profit=10.0,
    tick_value_loss=10.0,
    contract_size=1000,
    currency_base="USD",
    currency_profit="USD",
    currency_margin="USD",
)


class TestNoTradingOnBadPrints:
    def test_the_window_holding_a_negative_print_is_flagged_until_it_rolls_off(self) -> None:
        closes = [20.0] * 120 + [-37.6] + [20.0] * 120
        m15 = candles_from_closes(closes, wick=0.05)
        frames = {Timeframe.M15: analyze_frame(m15, Timeframe.M15, CFG.indicators, CFG.regime)}
        frames[Timeframe.H1] = analyze_frame(
            resample(m15, Timeframe.H1), Timeframe.H1, CFG.indicators, CFG.regime
        )

        def flags(bar: int) -> tuple[str, ...]:
            t = pd.Timestamp(m15["close_time"].iloc[bar]).to_pydatetime()
            ctx = context_at(
                frames,
                symbol="XTIUSD",
                entry_timeframe=Timeframe.M15,
                higher_timeframe=Timeframe.H1,
                decision_time=t,
                now_utc=t,
                params=CFG.indicators,
                window=50,
            )
            return ctx.market.quality_flags

        assert flags(119) == ()
        assert any(f.startswith("M15:INVALID_OHLC") for f in flags(120))
        # the next bar opens at the negative close, so bars 120 and 121 are bad; both leave a 50-bar window by 171
        assert any(f.startswith("M15:INVALID_OHLC") for f in flags(170))
        assert not any(f.startswith("M15:") for f in flags(171))

    def test_decision_rejects_with_data_invalid(self, db) -> None:  # type: ignore[no-untyped-def]
        record = engine(db).decide(request(market=make_context(quality_flags=("M15:INVALID_OHLC:1",))))
        assert record.decision is Decision.REJECT
        assert "DATA_INVALID" in record.reason_codes


class TestValuationThroughNegativePrices:
    def broker(self) -> SimulatedBroker:
        return SimulatedBroker(
            {"XTIUSD": WTI}, BacktestConfig(slippage_model="none"), AccountCurrencyOnly("USD")
        )

    def test_gap_through_the_stop_is_an_honest_multi_r_loss(self) -> None:
        br = self.broker()
        br.submit(OrderRequest("XTIUSD", Side.BUY, 0.1, 15.0, 25.0, risk_money=300.0), T)
        br.on_bar("XTIUSD", Bar(T, T + H, 18.0, 18.2, 17.9, 18.1, 0.03))
        events = br.on_bar("XTIUSD", Bar(T + H, T + 2 * H, -10.0, -5.0, -40.0, -37.6, 0.03))
        trade = events[0].trade
        assert trade is not None and trade.exit_reason is ExitReason.STOP_LOSS
        assert trade.exit_price == -10.0  # the gap: filled at the open, not at the stop
        entry = 18.0 + 0.03
        assert trade.profit == pytest.approx((-10.0 - entry) * 1000 * 0.1)
        assert trade.r_multiple is not None and trade.r_multiple < -9
        assert br.balance == pytest.approx(10_000 + trade.profit)

    def test_open_short_profits_and_margin_stays_positive(self) -> None:
        br = self.broker()
        br.submit(OrderRequest("XTIUSD", Side.SELL, 0.1, None, None), T)
        br.on_bar("XTIUSD", Bar(T, T + H, 18.0, 18.2, 17.9, 18.1, 0.03))
        br.on_bar("XTIUSD", Bar(T + H, T + 2 * H, 5.0, 5.0, -40.0, -37.6, 0.03))
        assert br.equity - br.balance == pytest.approx((18.0 - (-37.6 + 0.03)) * 1000 * 0.1)
        assert br.calc_margin(Side.SELL, "XTIUSD", 0.1, -37.6) == pytest.approx(0.1 * 1000 * 37.6 / 100)
        assert br.margin >= 0


def test_backtest_never_enters_while_a_bad_print_is_in_the_window() -> None:
    m15 = sawtooth_m15(1800)
    bad = 1200
    m15.loc[bad, "low"] = -0.5  # one negative print in an otherwise normal uptrend
    data = {
        "EURUSD": SymbolData(EURUSD_SPEC, {Timeframe.M15: m15, Timeframe.H1: resample(m15, Timeframe.H1)})
    }
    config = AppConfig.model_validate(
        {"symbols": {"allowed": ["EURUSD"]}, "backtest": {"slippage_model": "none"}}
    )
    strategies = default_registry().from_config(
        StrategiesConfig(items=[StrategyEntry(name="example_trend_pullback")]), config.timeframes
    )
    start = pd.Timestamp(m15["close_time"].iloc[1000]).to_pydatetime()
    end = pd.Timestamp(m15["close_time"].iloc[1450]).to_pydatetime()
    result = BacktestEngine(config, data, strategies, AccountCurrencyOnly("USD"), start=start, end=end).run()
    bad_close = pd.Timestamp(m15["close_time"].iloc[bad]).to_pydatetime()
    assert all(t.entry_time <= bad_close for t in result.trades), [t.entry_time for t in result.trades]
    assert result.final_equity == pytest.approx(10_000 + sum(t.net for t in result.trades))
