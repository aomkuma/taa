"""Volume features from MT5 *tick* volume (PLAN §A6).

FX and CFD symbols at a retail broker have no exchange volume: ``tick_volume`` counts price updates, which
tracks activity but is broker-specific. Features are therefore *relative* (the bar against its own recent
history), never absolute thresholds, and are not comparable across brokers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators.common import FloatArray, as_float, check_period, to_series


def _prior_window(volume: pd.Series, n: int) -> tuple[FloatArray, FloatArray]:
    """Mean and sample stdev of the *previous* n bars, so the bar being judged is not part of its baseline."""
    prior = pd.Series(as_float(volume)).shift(1).rolling(n, min_periods=n)
    return prior.mean().to_numpy(dtype=np.float64), prior.std(ddof=1).to_numpy(dtype=np.float64)


def volume_ratio(volume: pd.Series, n: int = 20) -> pd.Series:
    """``V[t] / mean(V[t-n .. t-1])``: 1 = typical, 2 = twice the recent average. First defined at *n*.

    NaN while the baseline average is 0 (no ticks at all, e.g. a dead session).
    """
    check_period("n", n)
    mean, _ = _prior_window(volume, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(mean > 0, as_float(volume) / mean, np.nan)
    return to_series(out, volume, f"volume_ratio_{n}")


def volume_zscore(volume: pd.Series, n: int = 20) -> pd.Series:
    """``(V[t] - mean) / stdev`` over the previous *n* bars (ddof=1).

    First defined at *n*; NaN if stdev is 0.
    """
    check_period("n", n, minimum=2)
    mean, std = _prior_window(volume, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(std > 0, (as_float(volume) - mean) / std, np.nan)
    return to_series(out, volume, f"volume_z_{n}")
