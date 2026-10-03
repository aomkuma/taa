from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.backtest.conversion import SeriesRates, missing_currencies, needed_currencies
from app.config import BacktestConfig
from app.core.enums import Side
from app.execution.fill_model import Bar
from app.execution.simulated_broker import OrderRequest, SimulatedBroker
from tests.strategy_data import EURUSD_SPEC

T = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
H = timedelta(hours=1)


def closes(*values: float, start: datetime = T) -> pd.DataFrame:
    times = [start + (i + 1) * H for i in range(len(values))]
    return pd.DataFrame({"close_time": pd.to_datetime(times, utc=True), "close": values})


def spec(name: str, base: str, quote: str, **kw: object):  # type: ignore[no-untyped-def]
    return dataclasses.replace(
        EURUSD_SPEC, name=name, currency_base=base, currency_profit=quote, currency_margin=base, **kw
    )


RATES = SeriesRates(
    "USD",
    {
        "USDJPY": ("USD", "JPY", closes(150.0, 152.0)),
        "EURUSD": ("EUR", "USD", closes(1.10, 1.12)),
        "EURCHF": ("EUR", "CHF", closes(0.95, 0.96)),
    },
)


class TestRates:
    def test_direct_and_inverse(self) -> None:
        assert RATES.rate("EUR", T + H) == pytest.approx(1.10)
        assert RATES.rate("JPY", T + H) == pytest.approx(1 / 150)
        assert RATES.rate("USD", T + H) == 1.0

    def test_cross_through_one_currency(self) -> None:
        # CHF -> EUR (1 / 0.95) -> USD (1.10)
        assert RATES.rate("CHF", T + H) == pytest.approx(1.10 / 0.95)
        assert RATES.can_price("CHF")
        assert not RATES.can_price("GBP")

    def test_last_close_at_or_before_no_look_ahead(self) -> None:
        assert RATES.rate("EUR", T + H + timedelta(minutes=59)) == pytest.approx(1.10)  # bar 2 not closed yet
        assert RATES.rate("EUR", T + 2 * H) == pytest.approx(1.12)
        assert RATES.rate("EUR", T) is None  # before the first close

    def test_unknown_currency(self) -> None:
        assert RATES.rate("GBP", T + H) is None

    def test_missing_currencies(self) -> None:
        traded = [spec("GBPJPY", "GBP", "JPY"), spec("AUDUSD", "AUD", "USD")]
        assert needed_currencies(traded, "USD") == {"GBP", "JPY", "AUD"}
        # AUD is priced by the traded AUDUSD itself, JPY by the series; GBP by nothing
        assert missing_currencies(traded, RATES, traded) == ["GBP"]


def test_broker_values_a_jpy_trade_in_usd() -> None:
    usdjpy = spec(
        "USDJPY",
        "USD",
        "JPY",
        digits=3,
        point=0.001,
        tick_size=0.001,
        tick_value=0.67,
        tick_value_profit=0.67,
        tick_value_loss=0.67,
    )
    gbpjpy = spec("GBPJPY", "GBP", "JPY", digits=3, point=0.001, tick_size=0.001)
    rates = SeriesRates(
        "USD",
        {
            "USDJPY": ("USD", "JPY", closes(150.0, 150.0, 150.0)),
            "GBPUSD": ("GBP", "USD", closes(1.3, 1.3, 1.3)),
        },
    )
    br = SimulatedBroker({"USDJPY": usdjpy, "GBPJPY": gbpjpy}, BacktestConfig(slippage_model="none"), rates)
    br.submit(OrderRequest("GBPJPY", Side.BUY, 1.0, None, None), T + H)
    br.on_bar("GBPJPY", Bar(T + H, T + 2 * H, 195.0, 195.5, 194.9, 195.4, 0.0))
    pos = next(iter(br.positions.values()))
    assert pos.entry_price == 195.0
    # 0.4 JPY x 100k = 40,000 JPY at 150 -> 266.67 USD
    assert br.equity - br.balance == pytest.approx(40_000 / 150)
    # the spec's tick value follows the rate: 0.001 * 100k / 150
    assert br.spec_at("GBPJPY").tick_value_loss == pytest.approx(100 / 150)
    # margin on the GBP notional: 100k GBP at 1.3 / leverage 100
    assert br.margin == pytest.approx(100_000 * 1.3 / 100)
