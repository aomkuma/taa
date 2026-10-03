"""Numeric invariants of the indicators on arbitrary valid OHLC data (hypothesis)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from app.indicators.momentum import cci, rsi, stochastic
from app.indicators.price_action import candle_anatomy, find_swings
from app.indicators.trend import adx, ema, sma
from app.indicators.volatility import atr, atr_percentile, bollinger

EPS = 1e-9


@st.composite
def ohlc(draw: st.DrawFn, min_size: int = 5, max_size: int = 120) -> pd.DataFrame:
    n = draw(st.integers(min_size, max_size))
    steps = draw(arrays(np.float64, n, elements=st.floats(-0.02, 0.02)))
    wicks = draw(arrays(np.float64, (2, n), elements=st.floats(0.0, 0.01)))
    close = 100.0 * np.exp(np.cumsum(steps))
    open_ = np.concatenate(([100.0], close[:-1]))
    high = np.maximum(open_, close) * (1 + wicks[0])
    low = np.minimum(open_, close) * (1 - wicks[1])
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def in_range(s: pd.Series | pd.DataFrame, lo: float, hi: float) -> bool:
    values = np.asarray(s, dtype=float)
    values = values[np.isfinite(values)]
    return bool(((values >= lo - EPS) & (values <= hi + EPS)).all())


@settings(max_examples=60, deadline=None)
@given(ohlc(), st.integers(2, 20))
def test_oscillators_are_bounded(df: pd.DataFrame, n: int) -> None:
    h, lo, c = df["high"], df["low"], df["close"]
    assert in_range(rsi(c, n), 0, 100)
    assert in_range(stochastic(h, lo, c, n, 3, 3), 0, 100)
    assert in_range(adx(h, lo, c, n), 0, 100)
    assert in_range(atr_percentile(atr(h, lo, c, 2), 10), 0, 100)


@settings(max_examples=60, deadline=None)
@given(ohlc(), st.integers(2, 20))
def test_averages_stay_within_input_range(df: pd.DataFrame, n: int) -> None:
    c = df["close"]
    lo_c, hi_c = float(c.min()), float(c.max())
    assert in_range(sma(c, n), lo_c, hi_c)
    assert in_range(ema(c, n), lo_c, hi_c)
    bands = bollinger(c, n).dropna()
    assert (bands["lower"] <= bands["mid"] + EPS).all() and (bands["mid"] <= bands["upper"] + EPS).all()


@settings(max_examples=60, deadline=None)
@given(ohlc(), st.integers(2, 20))
def test_atr_is_positive_and_below_max_true_range(df: pd.DataFrame, n: int) -> None:
    h, lo, c = df["high"], df["low"], df["close"]
    values = atr(h, lo, c, n).dropna()
    max_tr = float(np.max(np.maximum(h - lo, np.abs(h - c.shift(1)).fillna(0))))
    assert (values >= 0).all() and (values <= max_tr + EPS).all()
    assert np.isfinite(cci(h, lo, c, n).dropna()).all()


@settings(max_examples=60, deadline=None)
@given(ohlc())
def test_candle_ratios_partition_the_range(df: pd.DataFrame) -> None:
    out = candle_anatomy(df["open"], df["high"], df["low"], df["close"]).dropna()
    total = out["body_ratio"] + out["upper_wick_ratio"] + out["lower_wick_ratio"]
    assert np.allclose(total, 1.0)
    assert in_range(out[["body_ratio", "upper_wick_ratio", "lower_wick_ratio"]], 0, 1)


@settings(max_examples=60, deadline=None)
@given(ohlc(), st.integers(1, 5))
def test_swings_are_confirmed_k_bars_later_and_are_local_extremes(df: pd.DataFrame, k: int) -> None:
    h, lo = df["high"].to_numpy(), df["low"].to_numpy()
    for s in find_swings(df["high"], df["low"], k):
        assert s.confirm_pos == s.pivot_pos + k < len(df)
        window = slice(s.pivot_pos - k, s.pivot_pos + k + 1)
        if s.kind == "HIGH":
            assert s.price == h[s.pivot_pos] == h[window].max()
        else:
            assert s.price == lo[s.pivot_pos] == lo[window].min()
