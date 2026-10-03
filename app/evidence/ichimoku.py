"""Ichimoku detectors (PLAN §A29, family ICHIMOKU, tier T1), periods 9 / 26 / 52.

- Tenkan = midpoint of the last 9 bars' high/low; Kijun = the same over 26.
- Senkou A = (Tenkan + Kijun) / 2 and Senkou B = midpoint over 52, both *plotted* 26 bars ahead. The cloud at
  bar *t* is therefore made of the Senkou values computed at bar ``t − 26``: nothing after *t* is used.
- Chikou = the close plotted 26 bars back. Comparing it with price "back then" means comparing ``close[t]``
  with ``close[t − 26]``, which is known at *t*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np
from pydantic import Field

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
from app.indicators.common import FloatArray


@dataclass(frozen=True)
class Ichimoku:
    tenkan: FloatArray
    kijun: FloatArray
    cloud_a: FloatArray  # Senkou A in force at each bar (computed 26 bars earlier)
    cloud_b: FloatArray
    lead_a: FloatArray  # Senkou A computed at each bar (the cloud 26 bars ahead)
    lead_b: FloatArray

    @property
    def cloud_top(self) -> FloatArray:
        return np.maximum(self.cloud_a, self.cloud_b)  # NaN while the cloud is not yet defined

    @property
    def cloud_bottom(self) -> FloatArray:
        return np.minimum(self.cloud_a, self.cloud_b)


def _mid(ctx: EvidenceContext, n: int) -> FloatArray:
    hh = ctx.high.rolling(n, min_periods=n).max().to_numpy()
    ll = ctx.low.rolling(n, min_periods=n).min().to_numpy()
    return (hh + ll) / 2


def _shift(values: FloatArray, k: int) -> FloatArray:
    return np.r_[np.full(k, np.nan), values[:-k]] if len(values) > k else np.full(len(values), np.nan)


def ichimoku(ctx: EvidenceContext, tenkan: int = 9, kijun: int = 26, senkou: int = 52) -> Ichimoku:
    def compute() -> Ichimoku:
        t, k = _mid(ctx, tenkan), _mid(ctx, kijun)
        lead_a, lead_b = (t + k) / 2, _mid(ctx, senkou)
        return Ichimoku(t, k, _shift(lead_a, kijun), _shift(lead_b, kijun), lead_a, lead_b)

    return ctx.memo(("ichimoku", tenkan, kijun, senkou), compute)


class IchimokuParams(DetectorParams):
    tenkan: int = Field(default=9, ge=2, le=200)
    kijun: int = Field(default=26, ge=3, le=400)
    senkou: int = Field(default=52, ge=4, le=800)


def _dir(sign: int) -> Direction:
    return Direction.BULL if sign > 0 else Direction.BEAR


class KumoBreakout(Detector):
    """``breakout``: the first close above the cloud top (below the bottom) after closing inside or beyond
    the other side. ``twist``: Senkou A crossing Senkou B at the current bar, i.e. the cloud 26 bars ahead
    changes colour (known now, because it is computed from past bars)."""

    id = "ichimoku.kumo"
    name = "Ichimoku cloud"
    family = Family.ICHIMOKU
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = IchimokuParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        ich = ichimoku(ctx, params.tenkan, params.kijun, params.senkou)
        top, bot, c = ich.cloud_top, ich.cloud_bottom, ctx.c
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            if np.isfinite(top[t - 1]) and np.isfinite(top[t]):
                thick = (top[t] - bot[t]) / max(float(ctx.atr_array()[t]), 1e-12)
                if c[t] > top[t] and c[t - 1] <= top[t - 1]:
                    out.append(
                        self._rec(ctx, t, 1, 0.6 + 0.4 * min(1.0, thick / 2), "breakout", top[t], bot[t])
                    )
                elif c[t] < bot[t] and c[t - 1] >= bot[t - 1]:
                    out.append(
                        self._rec(ctx, t, -1, 0.6 + 0.4 * min(1.0, thick / 2), "breakout", bot[t], top[t])
                    )
            a0, b0, a1, b1 = ich.lead_a[t - 1], ich.lead_b[t - 1], ich.lead_a[t], ich.lead_b[t]
            if np.isfinite([a0, b0, a1, b1]).all():
                if a0 <= b0 and a1 > b1:
                    out.append(self._rec(ctx, t, 1, 0.5, "twist", a1, b1))
                elif a0 >= b0 and a1 < b1:
                    out.append(self._rec(ctx, t, -1, 0.5, "twist", a1, b1))
        return out

    def _rec(
        self, ctx: EvidenceContext, t: int, sign: int, q: float, variant: str, level: float, other: float
    ) -> Evidence:
        return self.make(
            ctx,
            t,
            _dir(sign),
            q,
            key_levels=[KeyLevel("cloud_edge", float(level)), KeyLevel("cloud_other", float(other))],
            invalidation=float(other) if variant == "breakout" else None,
            variant=variant,
        )


class TkCross(Detector):
    """Tenkan crossing Kijun. Strength follows the cross's position against the cloud: a bullish cross
    above the cloud is strong (1.0), inside it neutral (0.7), below it weak (0.4); mirrored for bearish
    crosses."""

    id = "ichimoku.tk_cross"
    name = "Tenkan/Kijun cross"
    family = Family.ICHIMOKU
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = IchimokuParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        ich = ichimoku(ctx, params.tenkan, params.kijun, params.senkou)
        tk, kj, top, bot = ich.tenkan, ich.kijun, ich.cloud_top, ich.cloud_bottom
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            d0, d1 = tk[t - 1] - kj[t - 1], tk[t] - kj[t]
            if not (np.isfinite(d0) and np.isfinite(d1)):
                continue
            sign = 1 if d0 <= 0 < d1 else (-1 if d0 >= 0 > d1 else 0)
            if sign == 0:
                continue
            level = kj[t]
            if not np.isfinite(top[t]):
                q = 0.5
            elif (sign > 0 and level > top[t]) or (sign < 0 and level < bot[t]):
                q = 1.0  # on the strong side of the cloud
            elif bot[t] <= level <= top[t]:
                q = 0.7
            else:
                q = 0.4
            out.append(
                self.make(
                    ctx,
                    t,
                    _dir(sign),
                    q,
                    key_levels=[KeyLevel("tenkan", float(tk[t])), KeyLevel("kijun", float(kj[t]))],
                    invalidation=float(kj[t]),
                )
            )
        return out


class Chikou(Detector):
    """Chikou confirmation: the first bar at which the close is above both the close and the cloud top of
    ``kijun`` bars ago (bullish), i.e. the lagging line has cleared price and cloud. Bearish mirrors it below
    the close and the cloud bottom."""

    id = "ichimoku.chikou"
    name = "Chikou confirmation"
    family = Family.ICHIMOKU
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = IchimokuParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        ich = ichimoku(ctx, params.tenkan, params.kijun, params.senkou)
        k, c = params.kijun, ctx.c
        out: list[Evidence] = []

        def clear(t: int, sign: int) -> bool | None:
            back = t - k
            edge = ich.cloud_top[back] if sign > 0 else ich.cloud_bottom[back]
            if back < 0 or not np.isfinite(edge):
                return None
            level = max(c[back], edge) if sign > 0 else min(c[back], edge)
            return bool((c[t] - level) * sign > 0)

        for t in range(k + 1, ctx.n):
            for sign in (1, -1):
                now, before = clear(t, sign), clear(t - 1, sign)
                if now and before is False:
                    back = t - k
                    out.append(
                        self.make(
                            ctx,
                            t,
                            _dir(sign),
                            0.7,
                            key_levels=[KeyLevel("price_then", float(c[back]))],
                            invalidation=float(c[back]),
                        )
                    )
        return out
