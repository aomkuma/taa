"""Trend indicators: SMA, EMA, MACD and ADX with +DI/-DI (PLAN §A6, formulas in docs/INDICATORS.md)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.errors import ConfigError
from app.indicators.common import (
    FloatArray,
    as_float,
    check_aligned,
    check_period,
    ema_values,
    rolling_mean,
    to_series,
    true_range_values,
    wilder_values,
)


def sma(close: pd.Series, n: int) -> pd.Series:
    """Arithmetic mean of the last *n* values; the first ``n - 1`` positions are NaN."""
    check_period("n", n)
    return to_series(rolling_mean(as_float(close), n), close, f"sma_{n}")


def ema(close: pd.Series, n: int) -> pd.Series:
    """EMA with ``alpha = 2 / (n + 1)``, seeded with SMA(n); the first ``n - 1`` positions are NaN."""
    check_period("n", n)
    return to_series(ema_values(as_float(close), n), close, f"ema_{n}")


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Columns ``macd`` (EMA_fast - EMA_slow), ``signal`` (EMA of macd) and ``hist`` (macd - signal).

    ``macd`` is first defined at position ``slow - 1``, ``signal``/``hist`` at ``slow + signal - 2``.
    """
    check_period("fast", fast)
    check_period("slow", slow, minimum=2)
    check_period("signal", signal)
    if fast >= slow:
        raise ConfigError(f"MACD fast period must be shorter than slow ({fast} >= {slow})")
    values = as_float(close)
    line = ema_values(values, fast) - ema_values(values, slow)
    sig = ema_values(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig}, index=close.index)


def directional_movement(high: FloatArray, low: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Wilder's +DM/-DM. Only the larger move counts, and only when positive; position 0 is NaN."""
    up = np.concatenate(([np.nan], high[1:] - high[:-1]))
    down = np.concatenate(([np.nan], low[:-1] - low[1:]))
    plus = np.where((up > down) & (up > 0), up, 0.0)
    minus = np.where((down > up) & (down > 0), down, 0.0)
    invalid = ~(np.isfinite(up) & np.isfinite(down))
    plus[invalid] = np.nan
    minus[invalid] = np.nan
    return plus.astype(np.float64), minus.astype(np.float64)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.DataFrame:
    """Columns ``plus_di``, ``minus_di`` and ``adx``, all in [0, 100], using Wilder smoothing.

    ``+DI = 100 * RMA(+DM) / RMA(TR)``; ``DX = 100 * |+DI - -DI| / (+DI + -DI)``; ``ADX = RMA(DX)``.
    DI is first defined at position ``n``, ADX at ``2n - 1``. DI is NaN while the smoothed true range is
    zero (a perfectly flat market has no direction); DX is 0 when both DIs are 0.
    """
    check_period("n", n)
    check_aligned(high, low, close)
    h, lo, c = as_float(high), as_float(low), as_float(close)
    plus_dm, minus_dm = directional_movement(h, lo)
    atr = wilder_values(true_range_values(h, lo, c), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        safe_atr = np.where(atr > 0, atr, np.nan)
        plus_di = 100.0 * wilder_values(plus_dm, n) / safe_atr
        minus_di = 100.0 * wilder_values(minus_dm, n) / safe_atr
        di_sum = plus_di + minus_di
        dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)
    dx[~np.isfinite(di_sum)] = np.nan
    return pd.DataFrame(
        {"plus_di": plus_di, "minus_di": minus_di, "adx": wilder_values(dx, n)}, index=close.index
    )
