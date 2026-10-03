"""Momentum indicators: RSI, Stochastic and CCI (PLAN §A6, formulas in docs/INDICATORS.md)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from app.indicators.common import (
    FloatArray,
    as_float,
    check_aligned,
    check_period,
    rolling_mean,
    to_series,
    wilder_values,
)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder RSI in [0, 100]; first defined at position *n*.

    NaN while both average gain and average loss are 0 (no price change at all): the oscillator is undefined
    there, and a fabricated neutral 50 could pass a threshold check.
    """
    check_period("n", n)
    c = as_float(close)
    change = np.concatenate(([np.nan], np.diff(c)))
    avg_gain = wilder_values(np.where(np.isnan(change), np.nan, np.maximum(change, 0.0)), n)
    avg_loss = wilder_values(np.where(np.isnan(change), np.nan, np.maximum(-change, 0.0)), n)
    total = avg_gain + avg_loss
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(total > 0, 100.0 * avg_gain / total, np.nan)
    return to_series(out, close, f"rsi_{n}")


def rolling_extremes(high: FloatArray, low: FloatArray, n: int) -> tuple[FloatArray, FloatArray]:
    """Highest high and lowest low of the last *n* bars (NaN during warm-up or if the window holds a NaN)."""
    hh = pd.Series(high).rolling(n, min_periods=n).max().to_numpy(dtype=np.float64)
    ll = pd.Series(low).rolling(n, min_periods=n).min().to_numpy(dtype=np.float64)
    return hh, ll


def stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14, k_smooth: int = 3, d: int = 3
) -> pd.DataFrame:
    """Slow stochastic: columns ``k`` and ``d`` in [0, 100].

    ``raw = 100 (C - LL_k) / (HH_k - LL_k)``; ``k = SMA_k_smooth(raw)``; ``d = SMA_d(k)``.
    ``k_smooth = 1`` gives the fast stochastic. A zero range (HH = LL) is NaN.
    First defined: k at ``k + k_smooth - 2``, d at ``k + k_smooth + d - 3``.
    """
    check_period("k", k)
    check_period("k_smooth", k_smooth)
    check_period("d", d)
    check_aligned(high, low, close)
    hh, ll = rolling_extremes(as_float(high), as_float(low), k)
    rng = hh - ll
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = np.where(rng > 0, 100.0 * (as_float(close) - ll) / rng, np.nan)
    slow_k = rolling_mean(raw, k_smooth)
    return pd.DataFrame({"k": slow_k, "d": rolling_mean(slow_k, d)}, index=close.index)


def cci(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 20) -> pd.Series:
    """``(TP - SMA_n(TP)) / (0.015 * MAD_n)`` with ``TP = (H + L + C) / 3``; first defined at ``n - 1``.

    MAD is the mean absolute deviation of the window from its own mean. A flat window is NaN.
    """
    check_period("n", n, minimum=2)
    check_aligned(high, low, close)
    tp = (as_float(high) + as_float(low) + as_float(close)) / 3.0
    out = np.full(tp.shape, np.nan, dtype=np.float64)
    if len(tp) >= n:
        windows = sliding_window_view(tp, n)
        mean = windows.mean(axis=1)
        mad = np.abs(windows - mean[:, None]).mean(axis=1)
        # flatness is tested exactly: the float mean of equal values is not exact, so MAD > 0 would let
        # rounding noise through as a large CCI
        flat = np.ptp(windows, axis=1) == 0
        with np.errstate(divide="ignore", invalid="ignore"):
            out[n - 1 :] = np.where(flat, np.nan, (tp[n - 1 :] - mean) / (0.015 * mad))
    return to_series(out, close, f"cci_{n}")
