"""Chart-pattern detectors (PLAN §A29, family CHART_PATTERN, tier T2).

Patterns are defined algorithmically from runs of consecutive confirmed zigzag pivots with explicit
tolerances, in the spirit of Lo, Mamaysky & Wang (2000) (PLAN R29). Nothing is drawn by eye.

Common rules:
- A pattern is *complete* when its last pivot is confirmed. It becomes evidence only on its **breakout**: the
  first close beyond the neckline/boundary (plus ``breakout_atr × ATR``) at or after completion, within
  ``max_wait_bars``. A close beyond the invalidation level first kills it. The record is stamped at the
  breakout bar.
- Equality tolerance: ``equal_tol_atr × ATR + equal_tol_frac × height``, with ATR taken at completion.
- Targets are measured moves (pattern height projected from the breakout level).
- Quality = 0.4 · fit (how much of the tolerance was used) + 0.3 · symmetry + 0.3 · tick-volume confirmation
  of the breakout bar (``volume_score``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
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
    swing_level,
)
from app.indicators.common import FloatArray
from app.indicators.price_action import Swing, SwingKind

# --- shared geometry --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Line:
    slope: float
    intercept: float

    def at(self, x: float) -> float:
        return self.slope * x + self.intercept

    @classmethod
    def fit(cls, xs: Sequence[float] | FloatArray, ys: Sequence[float] | FloatArray) -> Line:
        """Least-squares line (exact through two points)."""
        slope, intercept = np.polyfit(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float), 1)
        return cls(float(slope), float(intercept))

    def max_residual(self, xs: Sequence[float], ys: Sequence[float]) -> float:
        return max(abs(self.at(x) - y) for x, y in zip(xs, ys, strict=True))


def volume_score(ctx: EvidenceContext, t: int, n: int = 20) -> float:
    """Tick volume of bar *t* against the mean of the *n* bars before it: ratio 2 → 1.0, ratio 1 → 0.33.
    Neutral 0.5 when volume is unavailable."""
    if t < n:
        return 0.5
    base = float(np.mean(ctx.v[t - n : t]))
    if not (np.isfinite(base) and base > 0 and np.isfinite(ctx.v[t])):
        return 0.5
    return float(np.clip((ctx.v[t] / base - 0.5) / 1.5, 0.0, 1.0))


def pattern_quality(fit: float, symmetry: float, volume: float) -> float:
    return float(np.clip(0.4 * fit + 0.3 * symmetry + 0.3 * volume, 0.0, 1.0))


def time_symmetry(xs: Sequence[int]) -> float:
    """1 when consecutive pivots are evenly spaced in time, falling towards 0 as spacing becomes uneven."""
    gaps = np.diff(np.asarray(xs, dtype=float))
    if len(gaps) < 2 or gaps.sum() <= 0:
        return 1.0
    return float(np.clip(1.0 - (gaps.max() - gaps.min()) / gaps.sum(), 0.0, 1.0))


class PatternParams(DetectorParams):
    degree: str = "minor"
    equal_tol_atr: float = Field(default=0.5, ge=0, le=5)
    equal_tol_frac: float = Field(default=0.1, ge=0, le=0.5)
    min_height_atr: float = Field(default=2.0, gt=0, le=50)
    max_wait_bars: int = Field(default=20, ge=1, le=200)
    breakout_atr: float = Field(default=0.05, ge=0, le=2)


def _tol(params: Any, atr: float, height: float) -> float:
    return float(params.equal_tol_atr * atr + params.equal_tol_frac * abs(height))


def find_breakout(
    ctx: EvidenceContext,
    start: int,
    max_wait: int,
    level: Callable[[int], float],
    direction: int,
    dead: Callable[[int], bool],
    buffer: float,
) -> int | None:
    """First bar in ``[start, start + max_wait]`` closing beyond ``level(t)`` by *buffer* in *direction*.

    None if the data ends, the wait expires, or ``dead(t)`` (invalidation) happens first.
    """
    for t in range(start, min(start + max_wait, ctx.last_pos) + 1):
        if dead(t):
            return None
        if (ctx.c[t] - level(t)) * direction > buffer:
            return t
    return None


def _closes_beyond(ctx: EvidenceContext, level: float, sign: int) -> Callable[[int], bool]:
    def check(t: int) -> bool:
        return bool((ctx.c[t] - level) * sign > 0)

    return check


class _Seen:
    """One record per (variant, breakout bar, direction): overlapping pivot windows find the same breakout."""

    def __init__(self) -> None:
        self._keys: set[tuple[str, int, int]] = set()

    def first(self, variant: str, t: int, direction: int) -> bool:
        key = (variant, t, direction)
        if key in self._keys:
            return False
        self._keys.add(key)
        return True


# --- double / triple tops and bottoms, head & shoulders -----------------------------------------------------


class ReversalParams(PatternParams):
    min_separation_bars: int = Field(default=5, ge=1, le=500)  # between the first and last extreme


def _window(pivots: list[Swing], i: int, n: int, top: bool) -> list[Swing] | None:
    w = pivots[i : i + n]
    want = SwingKind.HIGH if top else SwingKind.LOW
    return w if len(w) == n and w[0].kind is want else None


def _came_from_beyond(pivots: list[Swing], i: int, neckline: float, sign: int) -> bool:
    """The move into the first extreme started beyond the neckline: a top forms after a rise from below it.
    Unknown context (pattern starts at the first pivot) fails closed."""
    return i > 0 and (pivots[i - 1].price - neckline) * sign < 0


class _Reversal(Detector):
    """Shared scan for reversal patterns: ``check`` returns the pattern geometry or None."""

    family = Family.CHART_PATTERN
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = ReversalParams
    size: ClassVar[int]
    labels: ClassVar[tuple[str, str]]  # (top variant, bottom variant)

    def check(self, w: list[Swing], sign: int, params: Any, atr: float) -> dict[str, Any] | None:
        raise NotImplementedError

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        atr = ctx.atr_array()
        seen, out = _Seen(), []
        for i in range(len(pivots)):
            for top in (True, False):
                w = _window(pivots, i, self.size, top)
                if w is None:
                    continue
                done = w[-1].confirm_pos
                a = atr[done]
                sign = 1 if top else -1
                if not np.isfinite(a) or w[-1].pivot_pos - w[0].pivot_pos < params.min_separation_bars:
                    continue
                geo = self.check(w, sign, params, float(a))
                if geo is None or not _came_from_beyond(pivots, i, geo["neck_ref"], sign):
                    continue
                neck: Callable[[int], float] = geo["neckline"]
                stop = geo["invalidation"]
                t = find_breakout(
                    ctx,
                    done,
                    params.max_wait_bars,
                    neck,
                    -sign,
                    _closes_beyond(ctx, stop, sign),
                    params.breakout_atr * a,
                )
                variant = self.labels[0 if top else 1]
                if t is None or not seen.first(variant, t, -sign):
                    continue
                level = neck(t)
                out.append(
                    self.make(
                        ctx,
                        t,
                        Direction.BEAR if top else Direction.BULL,
                        pattern_quality(
                            geo["fit"], time_symmetry([p.pivot_pos for p in w]), volume_score(ctx, t)
                        ),
                        key_levels=[
                            *(swing_level(name, p) for name, p in zip(geo["names"], w, strict=True)),
                            KeyLevel("neckline", level),
                        ],
                        invalidation=stop,
                        targets=[level - sign * geo["height"]],
                        details={"height": round(geo["height"], 10), "degree": params.degree},
                        variant=variant,
                    )
                )
        return out


class DoubleTopBottom(_Reversal):
    """M (double top) / W (double bottom): two equal extremes around a neckline, broken by a close."""

    id = "chart.double"
    name = "Double top/bottom"
    size = 3
    labels = ("top", "bottom")

    def check(self, w: list[Swing], sign: int, params: Any, atr: float) -> dict[str, Any] | None:
        e1, neck, e2 = (sign * p.price for p in w)
        height = (e1 + e2) / 2 - neck
        tol = _tol(params, atr, height)
        if height < params.min_height_atr * atr or abs(e1 - e2) > tol:
            return None
        line = sign * neck
        return {
            "neckline": lambda _t: line,
            "neck_ref": line,
            "invalidation": sign * max(e1, e2),
            "height": height,
            "fit": 1.0 - abs(e1 - e2) / tol if tol > 0 else 1.0,
            "names": ("first", "neck", "second"),
        }


class TripleTopBottom(_Reversal):
    """Three equal extremes (within tolerance).

    The neckline is the extreme of the two reactions between them.
    """

    id = "chart.triple"
    name = "Triple top/bottom"
    size = 5
    labels = ("top", "bottom")

    def check(self, w: list[Swing], sign: int, params: Any, atr: float) -> dict[str, Any] | None:
        v = [sign * p.price for p in w]
        tops, necks = v[0::2], v[1::2]
        neck = min(necks)
        height = float(np.mean(tops)) - neck
        tol = _tol(params, atr, height)
        spread = max(tops) - min(tops)
        if height < params.min_height_atr * atr or spread > tol:
            return None
        line = sign * neck
        return {
            "neckline": lambda _t: line,
            "neck_ref": line,
            "invalidation": sign * max(tops),
            "height": height,
            "fit": 1.0 - spread / tol if tol > 0 else 1.0,
            "names": ("first", "neck_1", "second", "neck_2", "third"),
        }


class HeadShoulders(_Reversal):
    """Head and shoulders (top) / inverse (bottom).

    A head beyond two roughly equal shoulders, with the neckline through the two reactions. Invalidated by a
    close beyond the right shoulder.
    """

    id = "chart.head_shoulders"
    name = "Head and shoulders"
    size = 5
    labels = ("top", "inverse")

    def check(self, w: list[Swing], sign: int, params: Any, atr: float) -> dict[str, Any] | None:
        ls, n1, head, n2, rs = (sign * p.price for p in w)
        x = [p.pivot_pos for p in w]
        neck = Line.fit([x[1], x[3]], [n1, n2])
        height = head - neck.at(x[2])
        tol = _tol(params, atr, height)
        prominence = head - max(ls, rs)
        if (
            height < params.min_height_atr * atr
            or prominence <= tol  # otherwise it is a triple top
            or abs(ls - rs) > tol
            or abs(n1 - n2) > tol
        ):
            return None
        return {
            "neckline": lambda t: sign * neck.at(t),
            "neck_ref": sign * min(n1, n2),
            "invalidation": sign * rs,
            "height": height,
            "fit": 1.0 - max(abs(ls - rs), abs(n1 - n2)) / tol if tol > 0 else 1.0,
            "names": ("left_shoulder", "neck_1", "head", "neck_2", "right_shoulder"),
        }


# --- triangles, wedges, rectangles ------------------------------------------------------------------------


class BoundaryParams(PatternParams):
    min_converge: float = Field(default=0.2, ge=0, lt=1)  # end width <= (1 - this) × start width
    fit_tol_atr: float = Field(default=0.5, gt=0, le=5)  # max distance of a pivot from its boundary line


@dataclass(frozen=True, slots=True)
class Boundary:
    kind: str  # rectangle, ascending, descending, symmetrical, rising_wedge, falling_wedge
    upper: Line
    lower: Line
    start: int
    end: int
    height: float
    fit: float


def classify_boundary(w: list[Swing], atr: float, params: Any) -> Boundary | None:
    """Fit lines through the highs and the lows of a pivot window and name the shape (None if it has none)."""
    highs = [p for p in w if p.kind is SwingKind.HIGH]
    lows = [p for p in w if p.kind is SwingKind.LOW]
    if len(highs) < 2 or len(lows) < 2:
        return None
    hx, hy = [p.pivot_pos for p in highs], [p.price for p in highs]
    lx, ly = [p.pivot_pos for p in lows], [p.price for p in lows]
    upper, lower = Line.fit(hx, hy), Line.fit(lx, ly)
    x0, x1 = w[0].pivot_pos, w[-1].pivot_pos
    span = x1 - x0
    w0, w1 = upper.at(x0) - lower.at(x0), upper.at(x1) - lower.at(x1)
    # the actual price range of the pivots: the lines extrapolated to the window's start can exaggerate it
    height = max(hy) - min(ly)
    tol = _tol(params, atr, height)
    fit_tol = params.fit_tol_atr * atr
    err = max(upper.max_residual(hx, hy), lower.max_residual(lx, ly))
    if span <= 0 or w1 <= 0 or height < params.min_height_atr * atr or err > fit_tol:
        return None
    rise_u, rise_l = upper.slope * span, lower.slope * span
    flat_u, flat_l = abs(rise_u) <= tol, abs(rise_l) <= tol
    converging = w1 <= (1 - params.min_converge) * w0
    kind = None
    if flat_u and flat_l:
        kind = "rectangle"
    elif converging and flat_u and rise_l > tol:
        kind = "ascending"
    elif converging and flat_l and rise_u < -tol:
        kind = "descending"
    elif converging and rise_u < -tol and rise_l > tol:
        kind = "symmetrical"
    elif converging and rise_u > tol and rise_l > tol:
        kind = "rising_wedge"
    elif converging and rise_u < -tol and rise_l < -tol:
        kind = "falling_wedge"
    if kind is None:
        return None
    return Boundary(kind, upper, lower, x0, x1, height, 1.0 - err / fit_tol)


class _BoundaryPattern(Detector):
    family = Family.CHART_PATTERN
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = BoundaryParams
    # kind -> allowed breakout directions (+1 up, -1 down) and the direction the pattern favours (0: none)
    kinds: ClassVar[dict[str, tuple[tuple[int, ...], int]]]
    window_sizes: ClassVar[tuple[int, ...]] = (5, 6)

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        atr = ctx.atr_array()
        seen, out = _Seen(), []
        for size in self.window_sizes:
            for i in range(len(pivots) - size + 1):
                w = pivots[i : i + size]
                done = w[-1].confirm_pos
                a = atr[done]
                if not np.isfinite(a):
                    continue
                b = classify_boundary(w, float(a), params)
                if b is None or b.kind not in self.kinds:
                    continue
                allowed, bias = self.kinds[b.kind]
                event = self._breakout(ctx, b, done, allowed, params.max_wait_bars, params.breakout_atr * a)
                if event is None:
                    continue
                t, direction = event
                if not seen.first(b.kind, t, direction):
                    continue
                edge = b.upper.at(t) if direction > 0 else b.lower.at(t)
                other = b.lower.at(t) if direction > 0 else b.upper.at(t)
                agreement = 1.0 if bias in (0, direction) else 0.5
                out.append(
                    self.make(
                        ctx,
                        t,
                        Direction.BULL if direction > 0 else Direction.BEAR,
                        pattern_quality(b.fit, agreement, volume_score(ctx, t)),
                        key_levels=[
                            *(swing_level(f"p{k}", p) for k, p in enumerate(w)),
                            KeyLevel("breakout_edge", edge),
                        ],
                        invalidation=other,
                        targets=[edge + direction * b.height],
                        details={"height": round(b.height, 10), "pivots": size, "degree": params.degree},
                        variant=b.kind,
                    )
                )
        return out

    @staticmethod
    def _breakout(
        ctx: EvidenceContext, b: Boundary, start: int, allowed: tuple[int, ...], max_wait: int, buffer: float
    ) -> tuple[int, int] | None:
        apex = _apex(b)
        for t in range(start, min(start + max_wait, ctx.last_pos) + 1):
            if apex is not None and t > apex:
                return None  # past the apex the lines no longer bound anything
            c = ctx.c[t]
            if c > b.upper.at(t) + buffer:
                return (t, 1) if 1 in allowed else None
            if c < b.lower.at(t) - buffer:
                return (t, -1) if -1 in allowed else None
        return None


def _apex(b: Boundary) -> float | None:
    if b.upper.slope == b.lower.slope:
        return None
    return (b.lower.intercept - b.upper.intercept) / (b.upper.slope - b.lower.slope)


class Triangle(_BoundaryPattern):
    """Ascending (flat top, rising lows), descending (flat bottom, falling highs) or symmetrical (converging)
    triangle, broken by a close beyond a boundary before the apex. Ascending favours up-breaks, descending
    down-breaks; a break against the bias scores lower."""

    id = "chart.triangle"
    name = "Triangle"
    kinds: ClassVar[dict[str, tuple[tuple[int, ...], int]]] = {
        "ascending": ((1, -1), 1),
        "descending": ((1, -1), -1),
        "symmetrical": ((1, -1), 0),
    }


class Wedge(_BoundaryPattern):
    """Rising wedge (both boundaries rise, converging) broken down; falling wedge broken up. A break in the
    wedge's own direction is not a wedge signal."""

    id = "chart.wedge"
    name = "Wedge"
    kinds: ClassVar[dict[str, tuple[tuple[int, ...], int]]] = {
        "rising_wedge": ((-1,), -1),
        "falling_wedge": ((1,), 1),
    }


class Rectangle(_BoundaryPattern):
    """Flat top and flat bottom (a trading range), broken by a close beyond either side."""

    id = "chart.rectangle"
    name = "Rectangle"
    kinds: ClassVar[dict[str, tuple[tuple[int, ...], int]]] = {"rectangle": ((1, -1), 0)}


# --- flags and pennants -----------------------------------------------------------------------------------


class FlagParams(DetectorParams):
    degree: str = "minor"
    pole_atr: float = Field(default=4.0, gt=0, le=50)  # minimum pole length
    max_pole_bars: int = Field(default=15, ge=2, le=200)
    min_flag_bars: int = Field(default=3, ge=2, le=200)
    max_flag_bars: int = Field(default=20, ge=3, le=500)
    max_retrace: float = Field(default=0.382, gt=0, lt=1)  # deepest pullback as a fraction of the pole
    breakout_atr: float = Field(default=0.05, ge=0, le=2)


class FlagPennant(Detector):
    """A sharp pole followed by a tight consolidation, broken in the pole's direction.

    The pole runs from the last confirmed pivot to the running extreme since it (``pole_atr`` × ATR within
    ``max_pole_bars``). The consolidation is the bars after that extreme: it must last ``min_flag_bars`` to
    ``max_flag_bars`` and retrace at most ``max_retrace`` of the pole. The breakout is a close beyond the
    regression line of the consolidation's highs (bull) or lows (bear). It is a ``pennant`` when the
    consolidation's high and low lines converge, otherwise a ``flag``. Target: the pole length from the
    breakout.
    """

    id = "chart.flag"
    name = "Flag/pennant"
    family = Family.CHART_PATTERN
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = FlagParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        atr = ctx.atr_array()
        out: list[Evidence] = []
        used: set[tuple[int, int]] = set()
        j = 0
        for t in range(1, ctx.n):
            while j + 1 < len(pivots) and pivots[j + 1].confirm_pos <= t - 1:
                j += 1
            if not pivots or pivots[j].confirm_pos > t - 1 or not np.isfinite(atr[t - 1]):
                continue
            # the pole may start at the last pivot, or at the one before when a deeper flag pullback has
            # already confirmed the pole's tip as a pivot
            for base in (pivots[j], *(pivots[j - 1 : j] if j >= 1 else ())):
                sign = 1 if base.kind is SwingKind.LOW else -1  # a low starts a bull pole
                found = self._at(ctx, t, base, sign, float(atr[t - 1]), params)
                if found is None or (base.pivot_pos, found["tip"]) in used:
                    continue
                used.add((base.pivot_pos, found["tip"]))
                out.append(self._record(ctx, t, base, sign, found, params))
        return out

    @staticmethod
    def _at(
        ctx: EvidenceContext, t: int, base: Swing, sign: int, atr: float, params: Any
    ) -> dict[str, Any] | None:
        ext = ctx.h if sign > 0 else ctx.l
        seg = sign * ext[base.pivot_pos + 1 : t]
        if len(seg) == 0:
            return None
        tip = base.pivot_pos + 1 + int(np.argmax(seg))
        pole = (ext[tip] - base.price) * sign
        flag_len = t - 1 - tip
        if (
            pole < params.pole_atr * atr
            or tip - base.pivot_pos > params.max_pole_bars
            or not (params.min_flag_bars <= flag_len <= params.max_flag_bars)
        ):
            return None
        xs = np.arange(tip + 1, t, dtype=float)
        hi, lo = ctx.h[tip + 1 : t], ctx.l[tip + 1 : t]
        deepest = (ext[tip] - (lo.min() if sign > 0 else hi.max())) * sign
        if deepest > params.max_retrace * pole:
            return None
        upper, lower = Line.fit(xs, hi), Line.fit(xs, lo)
        edge = (upper if sign > 0 else lower).at(t)
        if (ctx.c[t] - edge) * sign <= params.breakout_atr * atr:
            return None
        converging = upper.slope < 0 < lower.slope
        return {
            "tip": tip,
            "pole": pole,
            "edge": edge,
            "deepest": deepest,
            "pennant": converging,
            "lo": lo,
            "hi": hi,
        }

    def _record(
        self, ctx: EvidenceContext, t: int, base: Swing, sign: int, f: dict[str, Any], params: Any
    ) -> Evidence:
        tip_price = (ctx.h if sign > 0 else ctx.l)[f["tip"]]
        lo: FloatArray = f["lo"]
        hi: FloatArray = f["hi"]
        tightness = 1.0 - f["deepest"] / (params.max_retrace * f["pole"])
        shape = "pennant" if f["pennant"] else "flag"
        return self.make(
            ctx,
            t,
            Direction.BULL if sign > 0 else Direction.BEAR,
            pattern_quality(tightness, 1.0, volume_score(ctx, t)),
            key_levels=[
                swing_level("pole_start", base),
                KeyLevel("pole_end", float(tip_price), ctx.time_at(f["tip"])),
                KeyLevel("breakout_edge", f["edge"]),
            ],
            invalidation=float(lo.min() if sign > 0 else hi.max()),
            targets=[float(f["edge"] + sign * f["pole"])],
            details={"pole": round(float(f["pole"]), 10), "degree": params.degree},
            variant=f"{'bull' if sign > 0 else 'bear'}_{shape}",
        )


# --- cup and handle ---------------------------------------------------------------------------------------


class CupParams(DetectorParams):
    degree: str = "intermediate"
    rim_tol_frac: float = Field(default=0.15, ge=0, le=0.5)  # rims equal within this share of the depth
    min_depth_atr: float = Field(default=3.0, gt=0, le=100)
    min_cup_bars: int = Field(default=15, ge=5, le=2000)
    # share of the cup's closes within ``bottom_band`` × depth of the low: a U lingers there, a V does not
    min_bottom_dwell: float = Field(default=0.15, ge=0, le=1)
    bottom_band: float = Field(default=0.1, gt=0, le=0.5)
    max_handle: float = Field(default=0.5, gt=0, lt=1)  # handle depth as a share of the cup depth
    max_handle_bars: int = Field(default=20, ge=1, le=500)
    breakout_atr: float = Field(default=0.05, ge=0, le=2)


class CupHandle(Detector):
    """Cup and handle (bullish).

    A rounded bottom between two roughly equal rims, a shallow handle, then a close above the rim.

    Left rim = the HIGH pivot before a recent confirmed LOW pivot (the cup bottom); right rim = the running
    high since the bottom; the handle = the bars after the right rim. Roundness is the share of the cup's
    closes within ``bottom_band`` × depth of the low ("bottom dwell"): a rounded U lingers near the bottom (a
    cosine cup ≈ 20 %), a V does not (≈ 10 %). It must reach ``min_bottom_dwell``. Target: the cup depth above
    the rim.
    """

    id = "chart.cup_handle"
    name = "Cup and handle"
    family = Family.CHART_PATTERN
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = CupParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        atr = ctx.atr_array()
        out: list[Evidence] = []
        used: set[int] = set()
        j = 0
        for t in range(1, ctx.n):
            while j + 1 < len(pivots) and pivots[j + 1].confirm_pos <= t - 1:
                j += 1
            if j < 1 or pivots[j].confirm_pos > t - 1 or not np.isfinite(atr[t - 1]):
                continue
            # the bottom is one of the two latest LOW pivots: a deep handle may already have confirmed the
            # right rim (a HIGH) and even the handle low as pivots
            for k in (j, j - 1, j - 2):
                if k < 1 or pivots[k].kind is not SwingKind.LOW or pivots[k].pivot_pos in used:
                    continue
                ev = self._at(ctx, t, pivots[k - 1], pivots[k], float(atr[t - 1]), params)
                if ev is not None:
                    used.add(pivots[k].pivot_pos)
                    out.append(ev)
                    break
        return out

    def _at(
        self, ctx: EvidenceContext, t: int, left: Swing, bottom: Swing, atr: float, params: Any
    ) -> Evidence | None:
        seg = ctx.h[bottom.pivot_pos + 1 : t]
        if len(seg) < 2:
            return None
        right_pos = bottom.pivot_pos + 1 + int(np.argmax(seg))
        right = float(ctx.h[right_pos])
        depth = (left.price + right) / 2 - bottom.price
        handle_len = t - 1 - right_pos
        if (
            depth < params.min_depth_atr * atr
            or abs(left.price - right) > params.rim_tol_frac * depth
            or right_pos - left.pivot_pos < params.min_cup_bars
            or not (1 <= handle_len <= params.max_handle_bars)
        ):
            return None
        handle_low = float(ctx.l[right_pos + 1 : t].min())
        if right - handle_low > params.max_handle * depth or handle_low <= bottom.price:
            return None
        rim = max(left.price, right)
        if ctx.c[t] - rim <= params.breakout_atr * atr:
            return None
        cup = ctx.c[left.pivot_pos : right_pos + 1]
        dwell = float(np.mean(cup <= bottom.price + params.bottom_band * depth))
        if dwell < params.min_bottom_dwell:
            return None  # a V: it touched the bottom and left
        roundness = min(1.0, dwell / (2 * params.min_bottom_dwell))
        rim_fit = (
            1.0 - abs(left.price - right) / (params.rim_tol_frac * depth) if params.rim_tol_frac > 0 else 1
        )
        return self.make(
            ctx,
            t,
            Direction.BULL,
            pattern_quality(0.5 * rim_fit + 0.5 * roundness, roundness, volume_score(ctx, t)),
            key_levels=[
                swing_level("left_rim", left),
                swing_level("bottom", bottom),
                KeyLevel("right_rim", right, ctx.time_at(right_pos)),
                KeyLevel("handle_low", handle_low),
            ],
            invalidation=handle_low,
            targets=[rim + depth],
            details={"depth": round(depth, 10), "roundness": round(roundness, 4), "degree": params.degree},
        )
