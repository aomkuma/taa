"""Shared building blocks for indicators: input coercion, rolling means and recursive smoothers.

Conventions shared by every indicator (see docs/INDICATORS.md):

- Inputs are pandas Series; outputs keep the input index and use ``float64``.
- The value at position *t* depends only on positions <= *t* (no look-ahead).
- Warm-up positions are NaN. Callers treat NaN as "insufficient data" (HOLD).
- Recursive smoothers seed with the simple mean of the first *n* consecutive finite inputs, so leading NaNs
  (the warm-up of an upstream indicator) are skipped. A NaN *after* the seed propagates to every later value:
  validated candles never contain NaN, so one appearing means the data is broken and the output fails closed.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pandas as pd

from app.core.errors import ConfigError, DataQualityError

FloatArray = npt.NDArray[np.float64]


def check_period(name: str, value: int, minimum: int = 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int | np.integer) or value < minimum:
        raise ConfigError(f"{name} must be an integer >= {minimum} (got {value!r})")


def as_float(series: pd.Series) -> FloatArray:
    return series.to_numpy(dtype=np.float64, na_value=np.nan)


def check_aligned(*series: pd.Series) -> None:
    """Multi-input indicators (high/low/close) require series of one frame, not mixed sources."""
    first = series[0]
    for other in series[1:]:
        if len(other) != len(first) or not other.index.equals(first.index):
            raise DataQualityError("indicator inputs must share the same index")


def to_series(values: FloatArray, like: pd.Series, name: str) -> pd.Series:
    return pd.Series(values, index=like.index, name=name, dtype=np.float64)


def rolling_mean(values: FloatArray, n: int) -> FloatArray:
    """Simple moving average; NaN until *n* values are available and wherever the window holds a NaN."""
    return pd.Series(values).rolling(n, min_periods=n).mean().to_numpy(dtype=np.float64)


def first_full_window(values: FloatArray, n: int) -> int | None:
    """Index of the last element of the first window of *n* consecutive finite values."""
    run = 0
    for i, v in enumerate(values):
        run = run + 1 if np.isfinite(v) else 0
        if run >= n:
            return i
    return None


def recursive_smooth(values: FloatArray, n: int, alpha: float) -> FloatArray:
    """``y[t] = alpha * x[t] + (1 - alpha) * y[t-1]``, seeded with the mean of the first full window.

    ``alpha = 2 / (n + 1)`` gives the EMA, ``alpha = 1 / n`` gives Wilder's smoothing (RMA).
    """
    out = np.full(values.shape, np.nan, dtype=np.float64)
    seed_at = first_full_window(values, n)
    if seed_at is None:
        return out
    prev = float(np.mean(values[seed_at - n + 1 : seed_at + 1]))
    out[seed_at] = prev
    keep = 1.0 - alpha
    for i in range(seed_at + 1, len(values)):
        prev = alpha * float(values[i]) + keep * prev
        out[i] = prev
    return out


def ema_values(values: FloatArray, n: int) -> FloatArray:
    return recursive_smooth(values, n, 2.0 / (n + 1))


def wilder_values(values: FloatArray, n: int) -> FloatArray:
    return recursive_smooth(values, n, 1.0 / n)


def true_range_values(high: FloatArray, low: FloatArray, close: FloatArray) -> FloatArray:
    """``max(H - L, |H - C[t-1]|, |L - C[t-1]|)``. Position 0 has no previous close and is NaN."""
    prev_close = np.concatenate(([np.nan], close[:-1]))
    # np.maximum (unlike np.fmax) propagates NaN, so a broken bar never yields a plausible-looking range
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    return tr.astype(np.float64)
