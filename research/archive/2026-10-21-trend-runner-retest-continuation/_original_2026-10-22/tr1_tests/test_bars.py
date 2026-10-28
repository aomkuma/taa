# ruff: noqa: S101
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from tr1.bars import aggregate, atr, confirmed_fractals, true_range


def m1_frame() -> pd.DataFrame:
    index = pd.date_range("2025-10-20 00:00", periods=10, freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "open": np.arange(10, dtype=float),
            "high": np.arange(10, dtype=float) + 1.0,
            "low": np.arange(10, dtype=float) - 1.0,
            "close": np.arange(10, dtype=float) + 0.5,
            "tick_volume": 2,
            "spread": np.arange(10) + 20,
        },
        index=index,
    )


def test_aggregate_uses_clock_end_as_availability() -> None:
    result = aggregate(m1_frame(), "5min")
    assert len(result) == 2
    assert result.iloc[0]["open"] == 0.0
    assert result.iloc[0]["high"] == 5.0
    assert result.iloc[0]["low"] == -1.0
    assert result.iloc[0]["close"] == 4.5
    assert result.iloc[0]["tick_volume"] == 10
    assert result.iloc[0]["spread"] == 24
    assert result.iloc[0]["last"] == pd.Timestamp("2025-10-20 00:04", tz="UTC")
    assert result.iloc[0]["avail"] == pd.Timestamp("2025-10-20 00:05", tz="UTC")


def test_aggregate_does_not_expose_a_forming_bar() -> None:
    result = aggregate(m1_frame(), "5min", asof=pd.Timestamp("2025-10-20 00:09", tz="UTC"))
    assert result.index.tolist() == [pd.Timestamp("2025-10-20 00:00", tz="UTC")]


def test_aggregate_rejects_bad_time_inputs() -> None:
    frame = m1_frame().sort_index(ascending=False)
    with pytest.raises(ValueError, match="unique and increasing"):
        aggregate(frame, "5min")
    naive = m1_frame()
    naive.index = naive.index.tz_localize(None)
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        aggregate(naive, "5min")


def test_true_range_and_atr_are_hand_worked() -> None:
    high = np.array([10.0, 13.0, 12.0, 15.0])
    low = np.array([8.0, 9.0, 9.0, 11.0])
    close = np.array([9.0, 12.0, 10.0, 14.0])
    np.testing.assert_allclose(true_range(high, low, close), [np.nan, 4.0, 3.0, 5.0], equal_nan=True)
    np.testing.assert_allclose(atr(high, low, close, 2), [np.nan, np.nan, 3.5, 4.0], equal_nan=True)


def test_fractal_is_available_only_after_the_right_hand_bars_close() -> None:
    index = pd.date_range("2025-10-20", periods=5, freq="5min", tz="UTC")
    bars = pd.DataFrame(
        {
            "high": [1.0, 2.0, 5.0, 2.0, 1.0],
            "low": [0.0, -1.0, -2.0, -1.0, 0.0],
            "avail": index + pd.Timedelta(minutes=5),
        },
        index=index,
    )
    pivots = confirmed_fractals(bars, radius=2)
    assert set(pivots["kind"]) == {"high", "low"}
    assert set(pivots["pivot"]) == {2}
    assert set(pivots["avail"]) == {pd.Timestamp("2025-10-20 00:25", tz="UTC")}
