"""Candlestick-pattern detectors (PLAN §A29, family CANDLESTICK, tier T1).

Sizes are relative, following TA-Lib's convention: ``ref_range`` is the mean high-low range and ``ref_body``
the mean real body of the **previous** 10 bars. The pure ``*_mask`` functions hold the bare geometry
(cross-checked against TA-Lib in tests). The detectors add:

- **Prior trend** for reversal patterns: the close before the pattern moved at least ``trend_atr`` × ATR over
  ``trend_bars`` bars against the signal (a bullish reversal needs a decline into it).
- **Location weighting**: quality × (0.6 + 0.4 × at_level). ``at_level`` is 1 when a level, Fibonacci or
  trendline detector (``LOCATION_SOURCES``) reported a rejection in the same direction on one of the
  pattern's bars. A hammer on support counts for more than a hammer in mid-air. Detail ``at_levels`` names
  those rejections (sorted i18n keys, comma-joined), so an explanation can say which level it was.
- Invalidation: beyond the pattern's extreme (its lowest low for bullish patterns).

A record is stamped at the pattern's last bar, which is closed when it is evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np
import numpy.typing as npt
from pydantic import Field

from app.evidence.framework import (
    Detector,
    DetectorParams,
    Direction,
    Evidence,
    EvidenceContext,
    Family,
    Tier,
)
from app.indicators.common import FloatArray

IntArray = npt.NDArray[np.int64]

# (detector id, variants that mark a level; None = all). Only rejections count: a break or breakout says price
# went through the level, not that the candle sat on it.
LOCATION_SOURCES: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("fib.retracement", None),
    ("fib.extension_level", None),
    ("fib.cluster", None),
    ("levels.sr_zone", None),
    ("levels.round_number", None),
    ("levels.pivot_points", None),
    ("levels.prev_high_low", ("pdh.reject", "pdl.reject", "pwh.reject", "pwl.reject")),
    ("structure.trendline", ("bounce_support", "bounce_resistance")),
)

# --- reference sizes and bare geometry ----------------------------------------------------------------------


def trailing_mean(values: FloatArray, n: int = 10) -> FloatArray:
    """Mean of the *n* values before each position (NaN until *n* exist): the bar itself is excluded."""
    out = np.full(len(values), np.nan)
    if len(values) > n:
        csum = np.cumsum(np.r_[0.0, values])
        out[n:] = (csum[n:-1] - csum[: -n - 1]) / n
    return out


@dataclass(frozen=True)
class Bars:
    o: FloatArray
    h: FloatArray
    l: FloatArray  # noqa: E741
    c: FloatArray

    @property
    def body(self) -> FloatArray:
        return np.abs(self.c - self.o)

    @property
    def rng(self) -> FloatArray:
        return self.h - self.l

    @property
    def upper(self) -> FloatArray:
        return self.h - np.maximum(self.o, self.c)

    @property
    def lower(self) -> FloatArray:
        return np.minimum(self.o, self.c) - self.l

    @property
    def color(self) -> IntArray:
        return np.sign(self.c - self.o).astype(np.int64)

    @property
    def ref_range(self) -> FloatArray:
        return trailing_mean(self.rng)

    @property
    def ref_body(self) -> FloatArray:
        return trailing_mean(self.body)


def _prev(a: FloatArray | IntArray, k: int = 1) -> FloatArray:
    return np.r_[np.full(k, np.nan), a[:-k].astype(float)] if k else a.astype(float)


def engulfing_mask(b: Bars) -> IntArray:
    """+1 bullish / -1 bearish engulfing (TA-Lib CDLENGULFING geometry): opposite colours, the second body
    covers the first, with at least one edge strictly beyond."""
    o1, c1, col1 = _prev(b.o), _prev(b.c), _prev(b.color)
    bull = (b.color == 1) & (col1 == -1) & (((b.c >= o1) & (b.o < c1)) | ((b.c > o1) & (b.o <= c1)))
    bear = (b.color == -1) & (col1 == 1) & (((b.o >= c1) & (b.c < o1)) | ((b.o > c1) & (b.c <= o1)))
    return bull.astype(np.int64) - bear.astype(np.int64)


def doji_mask(b: Bars, factor: float = 0.1) -> npt.NDArray[np.bool_]:
    """Real body at most ``factor`` × the reference range (TA-Lib CDLDOJI geometry)."""
    with np.errstate(invalid="ignore"):
        return np.asarray(b.body <= factor * b.ref_range, dtype=bool) & np.isfinite(b.ref_range)


def harami_mask(b: Bars) -> IntArray:
    """+1 / -1 harami: a long body, then a short body inside it. The direction is opposite to the first bar's
    colour (TA-Lib CDLHARAMI geometry: long = above, short = below the reference body)."""
    ref = _prev(b.ref_body)
    body1, top1, bot1, col1 = (
        _prev(b.body),
        _prev(np.maximum(b.o, b.c)),
        _prev(np.minimum(b.o, b.c)),
        _prev(b.color),
    )
    with np.errstate(invalid="ignore"):
        ok = (
            (body1 > ref)
            & (b.body < b.ref_body)
            & (np.maximum(b.o, b.c) <= top1)
            & (np.minimum(b.o, b.c) >= bot1)
        )
    return np.where(ok, -col1, 0).astype(np.int64)


def marubozu_mask(b: Bars, shadow: float = 0.1) -> IntArray:
    """+1 / -1 marubozu: a body longer than the reference body, each shadow under ``shadow`` × the
    reference range."""
    with np.errstate(invalid="ignore"):
        ok = (b.body > b.ref_body) & (b.upper < shadow * b.ref_range) & (b.lower < shadow * b.ref_range)
    return np.where(ok, b.color, 0).astype(np.int64)


# --- detector base ----------------------------------------------------------------------------------------


class CandleParams(DetectorParams):
    max_age_bars: int = Field(default=2, ge=0, le=500)
    trend_bars: int = Field(default=5, ge=1, le=100)
    trend_atr: float = Field(default=1.0, ge=0, le=20)


@dataclass(frozen=True, slots=True)
class Match:
    direction: Direction
    geometry: float  # 0..1
    span: int  # number of bars in the pattern (the last one is the evaluation bar)
    variant: str | None = None
    reversal: bool = True  # needs a prior trend against ``direction``


class _Candle(Detector):
    family = Family.CANDLESTICK
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = CandleParams
    depends_on = tuple(det_id for det_id, _ in LOCATION_SOURCES)

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        raise NotImplementedError

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        b = ctx.memo(("candle_bars",), lambda: Bars(ctx.o, ctx.h, ctx.l, ctx.c))
        atr = ctx.atr_array()
        levels = _level_hits(ctx)
        out: list[Evidence] = []
        for t in range(ctx.n):
            if not np.isfinite(atr[t]) or not np.isfinite(b.ref_range[t]):
                continue
            for m in self.match(ctx, b, t, float(atr[t])):
                first = t - m.span + 1
                if first < 1:
                    continue
                if m.reversal and not _prior_trend(ctx, first, -m.direction.sign, params):
                    continue
                at_levels: set[str] = set()
                if m.direction is not Direction.NEUTRAL:
                    for p in range(first, t + 1):
                        at_levels |= levels.get((p, m.direction), set())
                weight = 1.0 if m.direction is Direction.NEUTRAL else 0.6 + 0.4 * bool(at_levels)
                lo, hi = float(ctx.l[first : t + 1].min()), float(ctx.h[first : t + 1].max())
                out.append(
                    self.make(
                        ctx,
                        t,
                        m.direction,
                        m.geometry * weight,
                        invalidation={Direction.BULL: lo, Direction.BEAR: hi}.get(m.direction),
                        details={
                            "at_level": bool(at_levels),
                            "at_levels": ",".join(sorted(at_levels)),
                            "bars": m.span,
                        },
                        variant=m.variant,
                    )
                )
        return out


def _prior_trend(ctx: EvidenceContext, first: int, sign: int, params: Any) -> bool:
    """Did the close before the pattern move ``trend_atr`` × ATR in direction *sign* over ``trend_bars``?"""
    end, start = first - 1, first - 1 - params.trend_bars
    if start < 0:
        return False
    atr = ctx.atr_array()[end]
    return bool(np.isfinite(atr) and (ctx.c[end] - ctx.c[start]) * sign >= params.trend_atr * atr)


def _level_hits(ctx: EvidenceContext) -> dict[tuple[int, Direction], set[str]]:
    """i18n keys of the rejections reported by the location sources, by (bar, direction)."""

    def compute() -> dict[tuple[int, Direction], set[str]]:
        hits: dict[tuple[int, Direction], set[str]] = {}
        for det_id, variants in LOCATION_SOURCES:
            prefix = f"evidence.{det_id}."
            for ev in ctx.results(det_id):
                if variants is not None and ev.i18n_key.removeprefix(prefix) not in variants:
                    continue
                hits.setdefault((ctx.pos_of(ev.detected_at), ev.direction), set()).add(ev.i18n_key)
        return hits

    return ctx.memo(("candle_level_hits",), compute)


def _dir(sign: int) -> Direction:
    return Direction.BULL if sign > 0 else Direction.BEAR


# --- single-bar patterns ----------------------------------------------------------------------------------


class Doji(_Candle):
    """Doji family: body ≤ 10 % of the reference range. ``dragonfly`` (long lower shadow, no upper) is bullish
    after a decline, ``gravestone`` its bearish mirror; ``long_legged`` (both shadows long, a wide bar) and
    ``standard`` are neutral indecision."""

    id = "candle.doji"
    name = "Doji"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        if not doji_mask(b)[t] or b.rng[t] < 0.3 * atr:
            return []
        rng, up, lo = b.rng[t], b.upper[t], b.lower[t]
        if up <= 0.1 * rng and lo >= 0.6 * rng:
            return [Match(Direction.BULL, lo / rng, 1, "dragonfly")]
        if lo <= 0.1 * rng and up >= 0.6 * rng:
            return [Match(Direction.BEAR, up / rng, 1, "gravestone")]
        if up >= 0.3 * rng and lo >= 0.3 * rng and rng >= atr:
            return [Match(Direction.NEUTRAL, 0.6, 1, "long_legged", reversal=False)]
        return [Match(Direction.NEUTRAL, 0.5, 1, "standard", reversal=False)]


def _pin(b: Bars, t: int, atr: float, sign: int) -> float | None:
    """Geometry score of a pin bar whose long tail points against *sign* (a hammer has a lower tail)."""
    rng = b.rng[t]
    tail, nose = (b.lower[t], b.upper[t]) if sign > 0 else (b.upper[t], b.lower[t])
    if rng < 0.5 * atr or tail < 0.6 * rng or nose > 0.15 * rng or tail < 2 * max(b.body[t], 0.05 * rng):
        return None
    return float(min(1.0, tail / rng / 0.8))


class Hammer(_Candle):
    """Hammer / bullish pin bar after a decline: lower tail ≥ 60 % of the range and ≥ 2 × the body, upper
    shadow ≤ 15 %."""

    id = "candle.hammer"
    name = "Hammer / pin bar"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        g = _pin(b, t, atr, 1)
        return [] if g is None else [Match(Direction.BULL, g, 1)]


class ShootingStar(_Candle):
    """Shooting star / bearish pin bar after a rise: the mirror of the hammer."""

    id = "candle.shooting_star"
    name = "Shooting star"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        g = _pin(b, t, atr, -1)
        return [] if g is None else [Match(Direction.BEAR, g, 1)]


class Marubozu(_Candle):
    """Marubozu: a long body with almost no shadows, a continuation candle in its colour (no trend needed)."""

    id = "candle.marubozu"
    name = "Marubozu"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        s = int(marubozu_mask(b)[t])
        if s == 0:
            return []
        return [Match(_dir(s), min(1.0, b.body[t] / max(atr, 1e-12)), 1, reversal=False)]


# --- two-bar patterns -------------------------------------------------------------------------------------


class Engulfing(_Candle):
    """Engulfing: the second body covers the first, opposite colour, after a move the other way."""

    id = "candle.engulfing"
    name = "Engulfing"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        s = int(engulfing_mask(b)[t])
        if s == 0 or t < 1:
            return []
        ratio = b.body[t] / max(b.body[t - 1], 1e-12)
        return [Match(_dir(s), float(min(1.0, 0.5 + 0.25 * ratio)), 2)]


class Harami(_Candle):
    """Harami: a long body then a small body inside it; direction opposite to the first bar."""

    id = "candle.harami"
    name = "Harami"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        s = int(harami_mask(b)[t])
        if s == 0:
            return []
        smallness = 1.0 - b.body[t] / max(b.body[t - 1], 1e-12)
        return [Match(_dir(s), float(np.clip(smallness, 0.0, 1.0)), 2)]


class InsideOutside(_Candle):
    """Inside bar and outside bar.

    Inside: the range sits within a previous "mother" bar of at least average range (neutral compression).
    Outside: an at-least-average bar ranging beyond both ends of the previous one and closing in its top
    (bullish) or bottom (bearish) quarter.
    """

    id = "candle.inside_outside"
    name = "Inside/outside bar"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        if t < 1:
            return []
        if b.h[t] < b.h[t - 1] and b.l[t] > b.l[t - 1] and b.rng[t - 1] >= b.ref_range[t - 1]:
            return [Match(Direction.NEUTRAL, 1.0 - b.rng[t] / b.rng[t - 1], 2, "inside", reversal=False)]
        if b.h[t] > b.h[t - 1] and b.l[t] < b.l[t - 1] and b.rng[t] >= b.ref_range[t]:
            pos = (b.c[t] - b.l[t]) / b.rng[t]
            if pos >= 0.75 and b.color[t] > 0:
                return [Match(Direction.BULL, pos, 2, "outside_bull", reversal=False)]
            if pos <= 0.25 and b.color[t] < 0:
                return [Match(Direction.BEAR, 1 - pos, 2, "outside_bear", reversal=False)]
        return []


class Tweezer(_Candle):
    """Tweezer top (two equal highs, bullish then bearish, after a rise) / bottom (mirror). Equal means within
    5 % of the reference range."""

    id = "candle.tweezer"
    name = "Tweezer"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        if t < 1:
            return []
        eq = 0.05 * b.ref_range[t]
        if abs(b.h[t] - b.h[t - 1]) <= eq and b.color[t - 1] > 0 and b.color[t] < 0:
            return [Match(Direction.BEAR, 1.0 - abs(b.h[t] - b.h[t - 1]) / max(eq, 1e-12) * 0.5, 2, "top")]
        if abs(b.l[t] - b.l[t - 1]) <= eq and b.color[t - 1] < 0 and b.color[t] > 0:
            return [Match(Direction.BULL, 1.0 - abs(b.l[t] - b.l[t - 1]) / max(eq, 1e-12) * 0.5, 2, "bottom")]
        return []


# --- three-bar patterns -----------------------------------------------------------------------------------


class Star(_Candle):
    """Morning star (long bearish bar, small body at or below its close, bullish bar closing above the first
    bar's midpoint) after a decline; evening star mirrors it. FX rarely gaps, so no gap is required."""

    id = "candle.star"
    name = "Morning/evening star"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        if t < 2:
            return []
        for s, label in ((1, "morning"), (-1, "evening")):
            body1, body2 = b.body[t - 2], b.body[t - 1]
            if b.color[t - 2] != -s or b.color[t] != s or body1 < 0.5 * atr or body2 > 0.3 * body1:
                continue
            # the middle body sits beyond the first bar's close (allowing 10 % of its body)
            mid_edge = max(b.o[t - 1], b.c[t - 1]) if s > 0 else min(b.o[t - 1], b.c[t - 1])
            if (mid_edge - b.c[t - 2]) * s > 0.1 * body1:
                continue
            midpoint = (b.o[t - 2] + b.c[t - 2]) / 2
            if (b.c[t] - midpoint) * s <= 0:
                continue
            recovery = (b.c[t] - b.c[t - 2]) * s / body1
            return [Match(_dir(s), float(min(1.0, recovery)), 3, label)]
        return []


class ThreeSoldiersCrows(_Candle):
    """Three white soldiers / three black crows.

    Three long bars of one colour, each opening inside the previous body and closing beyond the previous
    close, with small shadows on the closing side.
    """

    id = "candle.three"
    name = "Three soldiers/crows"

    def match(self, ctx: EvidenceContext, b: Bars, t: int, atr: float) -> list[Match]:
        if t < 2:
            return []
        for s, label in ((1, "soldiers"), (-1, "crows")):
            idx = (t - 2, t - 1, t)
            if any(b.color[i] != s or b.body[i] < 0.5 * atr for i in idx):
                continue
            shadow = b.upper if s > 0 else b.lower
            if any(shadow[i] > 0.3 * b.body[i] for i in idx):
                continue
            ok = all(
                (b.c[i] - b.c[i - 1]) * s > 0
                and min(b.o[i - 1], b.c[i - 1]) <= b.o[i] <= max(b.o[i - 1], b.c[i - 1])
                for i in idx[1:]
            )
            if ok:
                strength = float(np.mean([b.body[i] for i in idx]) / atr)
                return [Match(_dir(s), min(1.0, strength), 3, label, reversal=False)]
        return []
