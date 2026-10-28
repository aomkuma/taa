# ruff: noqa: S101
from __future__ import annotations

import pandas as pd
import pytest
from tr1.simulation import ExitReason, Fill, market_fill, run_trade, stop_entry_fill


def ticks(bid: list[float], ask: list[float] | None = None) -> pd.DataFrame:
    times = pd.date_range("2025-10-20", periods=len(bid), freq="1s", tz="UTC")
    asks = [value + 0.2 for value in bid] if ask is None else ask
    return pd.DataFrame({"time_utc": times, "bid": bid, "ask": asks})


def test_market_fill_pays_the_spread_and_adverse_slippage() -> None:
    stream = ticks([100.0, 100.1])
    buy = market_fill(stream, 1, pd.Timestamp("2025-10-20", tz="UTC"), slippage=0.1)
    sell = market_fill(stream, -1, pd.Timestamp("2025-10-20", tz="UTC"), slippage=0.1)
    assert buy is not None
    assert buy.price == pytest.approx(100.3)
    assert sell is not None
    assert sell.price == pytest.approx(99.9)


def test_stop_entry_uses_the_first_worse_quote_after_a_gap() -> None:
    stream = ticks([99.0, 101.0, 102.0])
    active = pd.Timestamp("2025-10-20", tz="UTC")
    fill = stop_entry_fill(stream, 1, 100.0, active, active + pd.Timedelta(seconds=2), slippage=0.1)
    assert fill is not None
    assert fill.index == 1
    assert fill.price == pytest.approx(101.3)


def test_stop_is_filled_at_the_worse_quote_after_a_gap() -> None:
    stream = ticks([100.0, 99.5, 97.0])
    fill = Fill(0, pd.Timestamp("2025-10-20", tz="UTC"), 100.2)
    result = run_trade(stream, 1, fill, 98.0, 104.0, fill.time + pd.Timedelta(seconds=10))
    assert result is not None
    assert result.reason is ExitReason.STOP
    assert result.exit_price == 97.0
    assert result.pnl == pytest.approx(-3.2)


def test_target_is_booked_at_the_target_not_a_better_quote() -> None:
    stream = ticks([100.0, 105.0])
    fill = Fill(0, pd.Timestamp("2025-10-20", tz="UTC"), 100.2)
    result = run_trade(stream, 1, fill, 98.0, 104.0, fill.time + pd.Timedelta(seconds=10))
    assert result is not None
    assert result.reason is ExitReason.TARGET
    assert result.exit_price == 104.0
    assert result.r == pytest.approx((104.0 - 100.2) / (100.2 - 98.0))


def test_time_exit_uses_the_first_quote_at_or_after_timeout() -> None:
    stream = ticks([100.0, 100.5, 101.0])
    fill = Fill(0, pd.Timestamp("2025-10-20", tz="UTC"), 100.2)
    result = run_trade(stream, 1, fill, 98.0, None, fill.time + pd.Timedelta(seconds=1))
    assert result is not None
    assert result.reason is ExitReason.TIME
    assert result.exit_time == fill.time + pd.Timedelta(seconds=1)
    assert result.exit_price == 100.5


def test_missing_future_tick_returns_none() -> None:
    stream = ticks([100.0])
    active = pd.Timestamp("2025-10-20 00:00:01", tz="UTC")
    assert market_fill(stream, 1, active) is None
    assert stop_entry_fill(stream, 1, 101.0, active, active + pd.Timedelta(seconds=1)) is None


def test_same_timestamp_quotes_keep_their_file_order() -> None:
    time = pd.Timestamp("2025-10-20", tz="UTC")
    stream = pd.DataFrame(
        {
            "time_utc": [time, time],
            "bid": [97.0, 105.0],
            "ask": [97.2, 105.2],
        }
    )
    fill = Fill(0, time, 100.2)
    result = run_trade(stream, 1, fill, 98.0, 104.0, time + pd.Timedelta(seconds=1))
    assert result is not None
    assert result.reason is ExitReason.STOP
