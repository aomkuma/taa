"""Momentum detectors (PLAN §A29, family MOMENTUM, tier T1): divergences, overbought/oversold exits, MACD and
Stochastic crosses, CCI extremes.

Oscillators come from ``app.indicators`` and are memoized on the context. A divergence compares the oscillator
at two consecutive zigzag pivots of the same kind; it is stamped when the second pivot is confirmed. The
oscillator value at a pivot is read at the pivot bar, which is before the confirmation bar.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

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
    swing_level,
)
from app.indicators.common import FloatArray
from app.indicators.momentum import cci, rsi, stochastic
from app.indicators.price_action import SwingKind
from app.indicators.trend import macd

Oscillator = Literal["rsi", "macd", "stoch"]


def oscillator(ctx: EvidenceContext, name: str) -> FloatArray:
    """RSI(14), MACD line (12, 26, 9) or slow %K (14, 3, 3), memoized."""

    def compute() -> FloatArray:
        if name == "rsi":
            return rsi(ctx.close, 14).to_numpy()
        if name == "macd":
            return macd(ctx.close)["macd"].to_numpy()
        return stochastic(ctx.high, ctx.low, ctx.close)["k"].to_numpy()

    return ctx.memo(("osc", name), compute)


def _osc_scale(ctx: EvidenceContext, name: str, t: int) -> float:
    """The oscillator move that counts as a full-strength divergence."""
    if name == "rsi":
        return 10.0
    if name == "stoch":
        return 20.0
    return float(0.5 * ctx.atr_array()[t])  # MACD is in price units


# --- divergences ------------------------------------------------------------------------------------------


class DivergenceParams(DetectorParams):
    degree: str = "minor"
    oscillators: tuple[Oscillator, ...] = Field(default=("rsi", "macd", "stoch"), min_length=1)
    min_bars: int = Field(default=5, ge=2, le=500)  # between the two pivots
    max_bars: int = Field(default=60, ge=3, le=2000)
    max_age_bars: int = Field(default=5, ge=0, le=500)


class Divergence(Detector):
    """Regular and hidden divergences between price and an oscillator at consecutive same-kind pivots.

    Regular bearish: higher price high with a lower oscillator high. Regular bullish: lower price low with a
    higher oscillator low. Hidden bearish: lower price high with a higher oscillator high (trend
    continuation). Hidden bullish: higher price low with a lower oscillator low. Invalidation: a close beyond
    the second pivot.
    """

    id = "momentum.divergence"
    name = "Divergence"
    family = Family.MOMENTUM
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = DivergenceParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        out: list[Evidence] = []
        for j in range(2, len(pivots)):
            p1, p2 = pivots[j - 2], pivots[j]
            gap = p2.pivot_pos - p1.pivot_pos
            if not (params.min_bars <= gap <= params.max_bars):
                continue
            high = p2.kind is SwingKind.HIGH
            for name in params.oscillators:
                osc = oscillator(ctx, name)
                o1, o2 = osc[p1.pivot_pos], osc[p2.pivot_pos]
                if not (np.isfinite(o1) and np.isfinite(o2)) or o1 == o2 or p1.price == p2.price:
                    continue
                price_up, osc_up = p2.price > p1.price, o2 > o1
                if price_up == osc_up:
                    continue  # they agree: no divergence
                # highs: price up / osc down is regular bearish, price down / osc up hidden bearish
                # lows: price down / osc up is regular bullish, price up / osc down hidden bullish
                kind = "regular" if price_up == high else "hidden"
                direction = Direction.BEAR if high else Direction.BULL
                strength = min(1.0, abs(o2 - o1) / max(_osc_scale(ctx, name, p2.pivot_pos), 1e-12))
                out.append(
                    self.make(
                        ctx,
                        p2.confirm_pos,
                        direction,
                        0.5 + 0.5 * strength,
                        key_levels=[swing_level("pivot_1", p1), swing_level("pivot_2", p2)],
                        invalidation=p2.price,
                        details={
                            "oscillator": name,
                            "osc_1": round(float(o1), 6),
                            "osc_2": round(float(o2), 6),
                        },
                        variant=f"{name}.{kind}",
                    )
                )
        return out


# --- overbought / oversold exits --------------------------------------------------------------------------


class ObOsParams(DetectorParams):
    rsi_high: float = Field(default=70, gt=50, lt=100)
    rsi_low: float = Field(default=30, gt=0, lt=50)
    stoch_high: float = Field(default=80, gt=50, lt=100)
    stoch_low: float = Field(default=20, gt=0, lt=50)


class OverboughtOversold(Detector):
    """An oscillator leaving an extreme zone: RSI back below 70 (bearish) or above 30 (bullish); slow %K back
    below 80 / above 20. Invalidation: the price extreme reached while the oscillator was in the zone."""

    id = "momentum.ob_os"
    name = "Overbought/oversold exit"
    family = Family.MOMENTUM
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = ObOsParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        out: list[Evidence] = []
        for name, hi, lo in (
            ("rsi", params.rsi_high, params.rsi_low),
            ("stoch", params.stoch_high, params.stoch_low),
        ):
            osc = oscillator(ctx, name)
            for t in range(1, ctx.n):
                a, b = osc[t - 1], osc[t]
                if not (np.isfinite(a) and np.isfinite(b)):
                    continue
                if a > hi >= b:
                    sign, zone = -1, "overbought"
                elif a < lo <= b:
                    sign, zone = 1, "oversold"
                else:
                    continue
                start = t - 1
                while (
                    start > 0
                    and np.isfinite(osc[start - 1])
                    and (osc[start - 1] - (hi if sign < 0 else lo)) * -sign > 0
                ):
                    start -= 1
                extreme = float(ctx.h[start:t].max() if sign < 0 else ctx.l[start:t].min())
                depth = float((osc[start:t].max() - hi) if sign < 0 else (lo - osc[start:t].min()))
                out.append(
                    self.make(
                        ctx,
                        t,
                        Direction.BULL if sign > 0 else Direction.BEAR,
                        0.5 + 0.5 * min(1.0, depth / 15.0),
                        key_levels=[KeyLevel("zone_extreme", extreme)],
                        invalidation=extreme,
                        details={"oscillator": name, "bars_in_zone": t - start},
                        variant=f"{name}.{zone}_exit",
                    )
                )
        return out


# --- crosses ----------------------------------------------------------------------------------------------


class CrossParams(DetectorParams):
    stoch_high: float = Field(default=80, gt=50, lt=100)
    stoch_low: float = Field(default=20, gt=0, lt=50)


class MomentumCross(Detector):
    """MACD line crossing its signal line (stronger on the far side of zero: a bullish cross below zero is an
    early turn), and slow %K crossing %D inside the overbought/oversold zone."""

    id = "momentum.cross"
    name = "MACD/Stochastic cross"
    family = Family.MOMENTUM
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = CrossParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        m = ctx.memo(("macd_frame",), lambda: macd(ctx.close))
        line, sig = m["macd"].to_numpy(), m["signal"].to_numpy()
        st = ctx.memo(("stoch_frame",), lambda: stochastic(ctx.high, ctx.low, ctx.close))
        k, d = st["k"].to_numpy(), st["d"].to_numpy()
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            s = _cross(line, sig, t)
            if s:
                early = (line[t] < 0) if s > 0 else (line[t] > 0)
                out.append(self._rec(ctx, t, s, 1.0 if early else 0.6, "macd"))
            s = _cross(k, d, t)
            if s and ((s > 0 and d[t - 1] < params.stoch_low) or (s < 0 and d[t - 1] > params.stoch_high)):
                out.append(self._rec(ctx, t, s, 0.8, "stoch"))
        return out

    def _rec(self, ctx: EvidenceContext, t: int, sign: int, q: float, name: str) -> Evidence:
        return self.make(
            ctx,
            t,
            Direction.BULL if sign > 0 else Direction.BEAR,
            q,
            invalidation=float(ctx.l[t] if sign > 0 else ctx.h[t]),
            variant=name,
        )


def _cross(a: FloatArray, b: FloatArray, t: int) -> int:
    """+1 if *a* crossed above *b* at bar *t*, -1 if below, else 0."""
    p0, p1 = a[t - 1] - b[t - 1], a[t] - b[t]
    if not (np.isfinite(p0) and np.isfinite(p1)):
        return 0
    if p0 <= 0 < p1:
        return 1
    if p0 >= 0 > p1:
        return -1
    return 0


# --- CCI extremes -----------------------------------------------------------------------------------------


class CciParams(DetectorParams):
    n: int = Field(default=20, ge=2, le=500)
    extreme: float = Field(default=200, gt=100, le=500)
    lookback: int = Field(default=10, ge=1, le=200)


class CciExtreme(Detector):
    """CCI ``extreme_exit``: back inside ±100 after reaching ±``extreme`` within ``lookback`` bars (a reversal
    from an exhausted move). ``breakout``: crossing ±100 from inside (a momentum push)."""

    id = "momentum.cci_extreme"
    name = "CCI extreme"
    family = Family.MOMENTUM
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = CciParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        v = ctx.memo(("cci", params.n), lambda: cci(ctx.high, ctx.low, ctx.close, params.n).to_numpy())
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            a, b = v[t - 1], v[t]
            if not (np.isfinite(a) and np.isfinite(b)):
                continue
            window = v[max(0, t - params.lookback) : t]
            if a >= 100 > b and np.nanmax(window) >= params.extreme:
                out.append(self._rec(ctx, t, -1, "extreme_exit", np.nanmax(window)))
            elif a <= -100 < b and np.nanmin(window) <= -params.extreme:
                out.append(self._rec(ctx, t, 1, "extreme_exit", -np.nanmin(window)))
            elif a <= 100 < b:
                out.append(self._rec(ctx, t, 1, "breakout", b))
            elif a >= -100 > b:
                out.append(self._rec(ctx, t, -1, "breakout", -b))
        return out

    def _rec(self, ctx: EvidenceContext, t: int, sign: int, kind: str, peak: float) -> Evidence:
        return self.make(
            ctx,
            t,
            Direction.BULL if sign > 0 else Direction.BEAR,
            min(1.0, 0.4 + 0.3 * float(peak) / 200.0),
            invalidation=float(ctx.l[t] if sign > 0 else ctx.h[t]),
            variant=kind,
        )
