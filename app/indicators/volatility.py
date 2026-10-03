"""Volatility indicators: ATR, Bollinger Bands, historical volatility and ATR percentile (PLAN §A6)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from app.core.errors import ConfigError
from app.indicators.common import (
    as_float,
    check_aligned,
    check_period,
    rolling_mean,
    to_series,
    true_range_values,
    wilder_values,
)


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """``max(H - L, |H - C[t-1]|, |L - C[t-1]|)``; position 0 has no previous close and is NaN."""
    check_aligned(high, low, close)
    return to_series(true_range_values(as_float(high), as_float(low), as_float(close)), close, "true_range")


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder-smoothed true range, in price units; first defined at position *n*."""
    check_period("n", n)
    check_aligned(high, low, close)
    tr = true_range_values(as_float(high), as_float(low), as_float(close))
    return to_series(wilder_values(tr, n), close, f"atr_{n}")


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Columns ``mid`` (SMA), ``upper``/``lower`` (mid ± k·σ, population σ), ``width`` and ``percent_b``.

    ``width = (upper - lower) / mid``; ``percent_b = (C - lower) / (upper - lower)``, NaN for a flat window.
    All columns are first defined at ``n - 1``.
    """
    check_period("n", n, minimum=2)
    if not (math.isfinite(k) and k > 0):
        raise ConfigError(f"Bollinger k must be > 0 (got {k!r})")
    c = as_float(close)
    mid = rolling_mean(c, n)
    sigma = np.full(c.shape, np.nan, dtype=np.float64)
    flat = np.zeros(c.shape, dtype=bool)
    if len(c) >= n:
        windows = sliding_window_view(c, n)
        sigma[n - 1 :] = windows.std(axis=1, ddof=0)
        # exact flatness test: rolling float sums leave rounding noise where σ should be 0
        flat[n - 1 :] = np.ptp(windows, axis=1) == 0
    sigma[flat] = 0.0
    upper, lower = mid + k * sigma, mid - k * sigma
    band = upper - lower
    with np.errstate(divide="ignore", invalid="ignore"):
        width = np.where(mid > 0, band / mid, np.nan)
        percent_b = np.where(band > 0, (c - lower) / band, np.nan)
    return pd.DataFrame(
        {"mid": mid, "upper": upper, "lower": lower, "width": width, "percent_b": percent_b},
        index=close.index,
    )


def historical_volatility(close: pd.Series, n: int = 20, *, bars_per_year: float) -> pd.Series:
    """Annualized volatility: sample stdev (ddof=1) of the last *n* log returns × √bars_per_year.

    *bars_per_year* depends on the timeframe and the market's trading hours (``Timeframe.bars_per_year``
    assumes a 24x5 market; crypto trades 24x7). A decimal fraction (0.12 = 12 %); first defined at
    position *n*. Non-positive prices are NaN.
    """
    check_period("n", n, minimum=2)
    if not (math.isfinite(bars_per_year) and bars_per_year > 0):
        raise ConfigError(f"bars_per_year must be > 0 (got {bars_per_year!r})")
    c = as_float(close)
    with np.errstate(divide="ignore", invalid="ignore"):
        log_c = np.where(c > 0, np.log(c), np.nan)
    returns = np.concatenate(([np.nan], np.diff(log_c)))
    std = pd.Series(returns).rolling(n, min_periods=n).std(ddof=1).to_numpy(dtype=np.float64)
    return to_series(std * math.sqrt(bars_per_year), close, f"hv_{n}")


def atr_percentile(atr_values: pd.Series, lookback: int = 100) -> pd.Series:
    """Where the current ATR sits among the previous ``lookback - 1`` values, in [0, 100].

    ``100 · count(prev ≤ current) / (lookback - 1)`` over the window ending at *t*: 100 means the highest
    ATR of the window, 0 the lowest. Defined once *lookback* consecutive finite ATR values exist
    (for ATR(n): at position ``n + lookback - 1``).
    """
    check_period("lookback", lookback, minimum=2)
    a = as_float(atr_values)
    out = np.full(a.shape, np.nan, dtype=np.float64)
    if len(a) >= lookback:
        windows = sliding_window_view(a, lookback)
        current = windows[:, -1]
        counts = (windows[:, :-1] <= current[:, None]).sum(axis=1)
        pct = 100.0 * counts / (lookback - 1)
        complete = np.isfinite(windows).all(axis=1)
        out[lookback - 1 :] = np.where(complete, pct, np.nan)
    return to_series(out, atr_values, f"atr_pct_{lookback}")
