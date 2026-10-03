"""Trend, regime and volatility states from indicator values (PLAN §A7).

- **Trend** is direction only: BULLISH when close > EMA(slow) and EMA(mid) > EMA(slow), BEARISH mirrored,
  otherwise NEUTRAL. Strength is the regime's job, so a strategy that wants "a strong uptrend" checks both.
- **Regime:** VOLATILE when the ATR percentile is above ``volatile_atr_percentile`` (checked first: a violent
  market is not a tradeable trend), TRENDING when ADX >= ``trend_adx``, RANGING when ADX < ``range_adx``, and
  UNCLEAR in the gap between the two ADX bands.
- **Volatility state:** ATR percentile bands LOW / NORMAL / HIGH / EXTREME.

Missing inputs (NaN during warm-up) never default to a tradeable state: the trend is NEUTRAL and the regime
UNCLEAR, so strategies HOLD.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from app.config import RegimeConfig
from app.core.enums import Regime, Trend, VolatilityState
from app.indicators.common import FloatArray

ObjectArray = npt.NDArray[np.object_]


def _known(*values: float | None) -> bool:
    return all(v is not None and math.isfinite(v) for v in values)


def classify_trend(close: float | None, ema_mid: float | None, ema_slow: float | None) -> Trend:
    if close is None or ema_mid is None or ema_slow is None or not _known(close, ema_mid, ema_slow):
        return Trend.NEUTRAL
    if close > ema_slow and ema_mid > ema_slow:
        return Trend.BULLISH
    if close < ema_slow and ema_mid < ema_slow:
        return Trend.BEARISH
    return Trend.NEUTRAL


def classify_regime(adx: float | None, atr_percentile: float | None, params: RegimeConfig) -> Regime:
    if adx is None or atr_percentile is None or not _known(adx, atr_percentile):
        return Regime.UNCLEAR
    if atr_percentile > params.volatile_atr_percentile:
        return Regime.VOLATILE
    if adx >= params.trend_adx:
        return Regime.TRENDING
    if adx < params.range_adx:
        return Regime.RANGING
    return Regime.UNCLEAR


def classify_volatility(atr_percentile: float | None, params: RegimeConfig) -> VolatilityState:
    """NaN maps to NORMAL; the regime of the same bar is UNCLEAR then, which already blocks entries."""
    if atr_percentile is None or not _known(atr_percentile):
        return VolatilityState.NORMAL
    if atr_percentile > params.extreme_atr_percentile:
        return VolatilityState.EXTREME
    if atr_percentile > params.high_atr_percentile:
        return VolatilityState.HIGH
    if atr_percentile < params.low_atr_percentile:
        return VolatilityState.LOW
    return VolatilityState.NORMAL


# vectorized forms for whole frames (backtests, charts); element-wise identical to the scalar functions


def trend_series(close: FloatArray, ema_mid: FloatArray, ema_slow: FloatArray) -> ObjectArray:
    out = np.full(len(close), Trend.NEUTRAL.value, dtype=object)
    with np.errstate(invalid="ignore"):
        out[(close > ema_slow) & (ema_mid > ema_slow)] = Trend.BULLISH.value
        out[(close < ema_slow) & (ema_mid < ema_slow)] = Trend.BEARISH.value
    return out


def regime_series(adx: FloatArray, atr_percentile: FloatArray, params: RegimeConfig) -> ObjectArray:
    out = np.full(len(adx), Regime.UNCLEAR.value, dtype=object)
    known = np.isfinite(adx) & np.isfinite(atr_percentile)
    with np.errstate(invalid="ignore"):
        volatile = known & (atr_percentile > params.volatile_atr_percentile)
        out[known & ~volatile & (adx < params.range_adx)] = Regime.RANGING.value
        out[known & ~volatile & (adx >= params.trend_adx)] = Regime.TRENDING.value
    out[volatile] = Regime.VOLATILE.value
    return out


def volatility_series(atr_percentile: FloatArray, params: RegimeConfig) -> ObjectArray:
    out = np.full(len(atr_percentile), VolatilityState.NORMAL.value, dtype=object)
    with np.errstate(invalid="ignore"):
        out[atr_percentile < params.low_atr_percentile] = VolatilityState.LOW.value
        out[atr_percentile > params.high_atr_percentile] = VolatilityState.HIGH.value
        out[atr_percentile > params.extreme_atr_percentile] = VolatilityState.EXTREME.value
    return out
