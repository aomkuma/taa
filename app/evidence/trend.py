"""Trend detectors (PLAN §A29, family TREND, tier T1): moving-average alignment and crosses, ADX strength.

These describe a *state* (a trend that persists), so they are stamped when the state begins and stay active
for a long ``max_age_bars``. An invalidation level (the mid EMA, or the DI cross level) ends them earlier
through the central activation rule.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
from pydantic import Field, model_validator

from app.evidence.framework import (
    Detector,
    DetectorParams,
    Direction,
    Evidence,
    EvidenceContext,
    Family,
    KeyLevel,
    Tier,
)
from app.indicators.trend import adx


class MaParams(DetectorParams):
    fast: int = Field(default=20, ge=2, le=500)
    mid: int = Field(default=50, ge=3, le=1000)
    slow: int = Field(default=200, ge=4, le=2000)
    max_age_bars: int = Field(default=50, ge=0, le=2000)

    @model_validator(mode="after")
    def _ordered(self) -> MaParams:
        if not self.fast < self.mid < self.slow:
            raise ValueError("EMA periods must satisfy fast < mid < slow")
        return self


class MaAlignment(Detector):
    """``aligned_bull``: EMA fast > mid > slow with the close above the fast EMA, from the bar it starts
    (``aligned_bear`` mirrors it). ``golden_cross`` / ``death_cross``: the mid EMA crossing the slow one.
    ``slow_reclaim`` / ``slow_loss``: the close crossing the slow EMA. Quality rises with ADX (0 → 0.5,
    40+ → 1.0)."""

    id = "trend.ma_alignment"
    name = "Moving-average trend"
    family = Family.TREND
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = MaParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        f, m, s = (ctx.ema_array(n) for n in (params.fast, params.mid, params.slow))
        strength = _adx(ctx)["adx"].to_numpy()
        c = ctx.c
        with np.errstate(invalid="ignore"):
            bull = (f > m) & (m > s) & (c > f)
            bear = (f < m) & (m < s) & (c < f)
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            q = 0.5 + 0.5 * min(1.0, strength[t] / 40.0) if np.isfinite(strength[t]) else 0.5
            if bull[t] and not bull[t - 1]:
                out.append(self._rec(ctx, t, 1, q, "aligned_bull", m[t], f, m, s))
            elif bear[t] and not bear[t - 1]:
                out.append(self._rec(ctx, t, -1, q, "aligned_bear", m[t], f, m, s))
            x = _crossed(m, s, t)
            if x:
                out.append(self._rec(ctx, t, x, q, "golden_cross" if x > 0 else "death_cross", s[t], f, m, s))
            x = _crossed(c, s, t)
            if x:
                out.append(
                    self._rec(ctx, t, x, 0.5 * q, "slow_reclaim" if x > 0 else "slow_loss", s[t], f, m, s)
                )
        return out

    def _rec(
        self, ctx: EvidenceContext, t: int, sign: int, q: float, variant: str, inval: float, *emas: np.ndarray
    ) -> Evidence:
        names = ("ema_fast", "ema_mid", "ema_slow")
        return self.make(
            ctx,
            t,
            Direction.BULL if sign > 0 else Direction.BEAR,
            q,
            key_levels=[KeyLevel(n, float(e[t])) for n, e in zip(names, emas, strict=True)],
            invalidation=float(inval),
            variant=variant,
        )


def _crossed(a: np.ndarray, b: np.ndarray, t: int) -> int:
    d0, d1 = a[t - 1] - b[t - 1], a[t] - b[t]
    if not (np.isfinite(d0) and np.isfinite(d1)):
        return 0
    return 1 if d0 <= 0 < d1 else (-1 if d0 >= 0 > d1 else 0)


def _adx(ctx: EvidenceContext) -> Any:
    return ctx.memo(("adx_frame", 14), lambda: adx(ctx.high, ctx.low, ctx.close, 14))


class AdxParams(DetectorParams):
    threshold: float = Field(default=25, gt=0, lt=100)
    max_age_bars: int = Field(default=20, ge=0, le=2000)


class AdxStrength(Detector):
    """ADX(14) rising through ``threshold`` (a trend gaining strength), in the direction of the dominant
    directional index (+DI above −DI: bullish)."""

    id = "trend.adx_strength"
    name = "ADX trend strength"
    family = Family.TREND
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = AdxParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        frame = _adx(ctx)
        a, pdi, mdi = (frame[k].to_numpy() for k in ("adx", "plus_di", "minus_di"))
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            if not (np.isfinite(a[t - 1]) and np.isfinite(a[t])) or not (a[t - 1] < params.threshold <= a[t]):
                continue
            if pdi[t] == mdi[t]:
                continue
            sign = 1 if pdi[t] > mdi[t] else -1
            out.append(
                self.make(
                    ctx,
                    t,
                    Direction.BULL if sign > 0 else Direction.BEAR,
                    min(1.0, 0.5 + abs(pdi[t] - mdi[t]) / 40.0),
                    invalidation=float(ctx.l[t] if sign > 0 else ctx.h[t]),
                    details={"adx": round(float(a[t]), 2)},
                )
            )
        return out
