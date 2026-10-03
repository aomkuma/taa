"""Fibonacci detectors (PLAN §A29, family FIBONACCI, tier T1).

An *impulse* is a pair of consecutive confirmed zigzag pivots A → B (degree ``params.degree``). It is the
"last impulse" for the bars after B's confirmation, up to and including the bar that confirms the next pivot.
Using only pivots confirmed *before* the bar keeps a pivot and a touch on the same bar from being ambiguous.

- Retracement level ``r``: ``B - r·(B - A)`` (for a down impulse the signs flip).
- Extension ``e`` (targets): ``A + e·(B - A)``, i.e. external retracements measured from the impulse origin.
- An impulse is spent once a close goes beyond its origin A (a 100 % retracement).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import Field, field_validator

from app.evidence.common import Cooldown, tolerance, touch_rejection
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
from app.indicators.price_action import Swing, SwingKind

RETRACEMENTS = (0.236, 0.382, 0.5, 0.618, 0.786)
EXTENSIONS = (1.272, 1.618)
# Relative weight of each retracement in quality: the 50-61.8 % area is the classic reaction zone.
LEVEL_WEIGHT = {0.236: 0.6, 0.382: 0.85, 0.5: 0.95, 0.618: 1.0, 0.786: 0.8}


@dataclass(frozen=True, slots=True)
class Impulse:
    a: Swing  # origin
    b: Swing  # end
    start: int  # first bar for which this is the last impulse
    end: int  # last bar (inclusive)

    @property
    def direction(self) -> Direction:
        return Direction.BULL if self.b.kind is SwingKind.HIGH else Direction.BEAR

    @property
    def size(self) -> float:
        return abs(self.b.price - self.a.price)

    def retracement(self, r: float) -> float:
        return self.b.price - self.direction.sign * r * self.size

    def extension(self, e: float) -> float:
        return self.a.price + self.direction.sign * e * self.size

    def key_levels(self) -> list[KeyLevel]:
        return [swing_level("impulse_start", self.a), swing_level("impulse_end", self.b)]


def impulses(pivots: list[Swing], last_pos: int) -> Iterator[Impulse]:
    for i in range(len(pivots) - 1):
        a, b = pivots[i], pivots[i + 1]
        start = b.confirm_pos + 1
        end = pivots[i + 2].confirm_pos if i + 2 < len(pivots) else last_pos
        if start <= end:
            yield Impulse(a, b, start, end)


def _broken(ctx: EvidenceContext, imp: Impulse, t: int) -> bool:
    """A close beyond the impulse origin ends it."""
    return bool((ctx.c[t] - imp.a.price) * imp.direction.sign < 0)


class FibParams(DetectorParams):
    degree: str = "intermediate"
    tol_atr: float = Field(default=0.25, gt=0, le=2)


# --- retracement ------------------------------------------------------------------------------------------


class RetracementParams(FibParams):
    levels: tuple[float, ...] = Field(default=RETRACEMENTS, min_length=1)


class FibRetracement(Detector):
    """Price probes a retracement level of the last impulse and rejects it (support in an up impulse)."""

    id = "fib.retracement"
    name = "Fibonacci retracement"
    family = Family.FIBONACCI
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = RetracementParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        out: list[Evidence] = []
        for imp in impulses(ctx.zigzag(params.degree), ctx.last_pos):
            pending = set(params.levels)
            for t in range(imp.start, imp.end + 1):
                if _broken(ctx, imp, t) or not pending:
                    break
                tol = tolerance(ctx, t, params.tol_atr)
                for r in sorted(pending):
                    level = imp.retracement(r)
                    touch = touch_rejection(ctx, t, level, tol)
                    if touch is None or touch.direction is not imp.direction:
                        continue
                    pending.discard(r)
                    out.append(
                        self.make(
                            ctx,
                            t,
                            imp.direction,
                            touch.quality * LEVEL_WEIGHT.get(r, 0.7),
                            key_levels=[*imp.key_levels(), KeyLevel(f"fib_{r * 100:.1f}", level)],
                            invalidation=imp.a.price,
                            targets=[imp.b.price, *(imp.extension(e) for e in EXTENSIONS)],
                            details={"ratio": r, "degree": params.degree},
                            variant=f"{r * 100:.1f}",
                        )
                    )
        return out


# --- golden zone ------------------------------------------------------------------------------------------


class GoldenZoneParams(FibParams):
    zone: tuple[float, float] = (0.5, 0.618)
    floor: float = Field(default=0.786, gt=0, lt=1)
    min_wick: float = Field(default=0.3, ge=0, le=1)


class FibGoldenZone(Detector):
    """Pullback into the 50–61.8 % zone of the last impulse, then a rejection candle.

    The candle closes in the impulse's direction with a rejecting wick. The setup fails below 78.6 %
    (``invalidation``).
    """

    id = "fib.golden_zone"
    name = "Fibonacci golden-zone rejection"
    family = Family.FIBONACCI
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = GoldenZoneParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        out: list[Evidence] = []
        shallow, deep = sorted(params.zone)
        for imp in impulses(ctx.zigzag(params.degree), ctx.last_pos):
            sign = imp.direction.sign
            edge, inner, floor = (
                imp.retracement(shallow),
                imp.retracement(deep),
                imp.retracement(params.floor),
            )
            for t in range(imp.start, imp.end + 1):
                o, h, lo, c = ctx.o[t], ctx.h[t], ctx.l[t], ctx.c[t]
                if (c - floor) * sign < 0 or _broken(ctx, imp, t):
                    break  # closed beyond the floor: the zone failed for this impulse
                rng = h - lo
                probe = lo if sign > 0 else h
                if rng <= 0 or (probe - edge) * sign > 0 or (probe - floor) * sign <= 0:
                    continue  # did not reach the zone, or went past the floor
                wick = ((min(o, c) - lo) if sign > 0 else (h - max(o, c))) / rng
                if (c - o) * sign <= 0 or (c - inner) * sign < 0 or wick < params.min_wick:
                    continue  # no rejection candle
                depth_fit = 1.0 - min(1.0, abs(probe - inner) / max(abs(edge - inner), 1e-12))
                out.append(
                    self.make(
                        ctx,
                        t,
                        imp.direction,
                        0.5 * min(1.0, wick / 0.6) + 0.5 * depth_fit,
                        key_levels=[
                            *imp.key_levels(),
                            KeyLevel("zone_edge", edge),
                            KeyLevel("zone_inner", inner),
                            KeyLevel("floor", floor),
                        ],
                        invalidation=floor,
                        targets=[imp.b.price, imp.extension(1.272)],
                        details={"wick_ratio": round(float(wick), 4), "degree": params.degree},
                    )
                )
                break  # once per impulse
        return out


# --- extension --------------------------------------------------------------------------------------------


class ExtensionParams(FibParams):
    min_retrace: float = Field(default=0.236, ge=0, lt=1)
    max_retrace: float = Field(default=0.786, gt=0, lt=1)


class FibExtension(Detector):
    """Continuation after a pullback, with Fibonacci extension targets.

    A → B impulse, C retracement pivot (between ``min_retrace`` and ``max_retrace``), then the first close
    beyond B. Targets are the 127.2 % and 161.8 % extensions of A → B.
    """

    id = "fib.extension"
    name = "Fibonacci extension targets"
    family = Family.FIBONACCI
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = ExtensionParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        out: list[Evidence] = []
        for i in range(len(pivots) - 2):
            a, b, cpiv = pivots[i], pivots[i + 1], pivots[i + 2]
            imp = Impulse(a, b, 0, 0)
            sign = imp.direction.sign
            depth = abs(b.price - cpiv.price) / imp.size if imp.size > 0 else np.nan
            if not (params.min_retrace <= depth <= params.max_retrace):
                continue
            end = pivots[i + 3].confirm_pos if i + 3 < len(pivots) else ctx.last_pos
            for t in range(cpiv.confirm_pos + 1, end + 1):
                if (ctx.c[t] - cpiv.price) * sign < 0:
                    break
                if (ctx.c[t] - b.price) * sign > 0:
                    out.append(
                        self.make(
                            ctx,
                            t,
                            imp.direction,
                            1.0 if 0.382 <= depth <= 0.618 else 0.7,
                            key_levels=[*imp.key_levels(), swing_level("pullback", cpiv)],
                            invalidation=cpiv.price,
                            targets=[imp.extension(e) for e in EXTENSIONS],
                            details={"retrace_depth": round(float(depth), 4), "degree": params.degree},
                        )
                    )
                    break
        return out


# --- extension levels as support / resistance -------------------------------------------------------------

EXTENSION_LEVELS = (1.272, 1.618, 2.618, 4.236)
# 161.8 % is the most watched extension; the deep 423.6 % and the shallow 127.2 % less so
EXTENSION_WEIGHT = {1.272: 0.8, 1.618: 1.0, 2.618: 0.9, 4.236: 0.8}


class ExtensionLevelParams(FibParams):
    ratios: tuple[float, ...] = Field(default=EXTENSION_LEVELS, min_length=1)
    methods: tuple[Literal["external", "projection"], ...] = Field(
        default=("external", "projection"), min_length=1
    )

    @field_validator("ratios")
    @classmethod
    def _beyond_one(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if any(not (1.0 < r <= 10.0) for r in value):
            raise ValueError("extension ratios must be in (1, 10]")
        return value


class FibExtensionLevel(Detector):
    """Fibonacci extension levels acting as resistance (beyond an up leg) or support (beyond a down leg).

    ``external`` (two-point): ``A + r·(B − A)`` of the leg A → B. ``projection`` (trend-based, three-point):
    ``C + r·(B − A)``, projected from the pullback pivot C (which must not retrace beyond A). A leg's levels
    stay in force from the last anchor's confirmation until the trend's next same-direction extreme D is
    confirmed, as traders keep them drawn; a close beyond A ends them. Reported when price probes a level
    and is rejected against the leg (exhaustion), once per level; a level that is closed through is spent.
    """

    id = "fib.extension_level"
    name = "Fibonacci extension level"
    family = Family.FIBONACCI
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = ExtensionLevelParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        out: list[Evidence] = []
        for i in range(len(pivots) - 1):
            a, b = pivots[i], pivots[i + 1]
            leg = Impulse(a, b, 0, 0)
            end = pivots[i + 3].confirm_pos if i + 3 < len(pivots) else ctx.last_pos
            if "external" in params.methods:
                levels = {r: leg.extension(r) for r in params.ratios}
                out += self._levels(ctx, leg, b.confirm_pos + 1, end, levels, "external", [], params)
            if "projection" in params.methods and i + 2 < len(pivots):
                c = pivots[i + 2]
                sign = leg.direction.sign
                if (c.price - a.price) * sign > 0:  # the pullback held above A
                    levels = {r: c.price + sign * r * leg.size for r in params.ratios}
                    anchor = [swing_level("pullback", c)]
                    out += self._levels(
                        ctx, leg, c.confirm_pos + 1, end, levels, "projection", anchor, params
                    )
        return out

    def _levels(
        self,
        ctx: EvidenceContext,
        leg: Impulse,
        start: int,
        end: int,
        levels: dict[float, float],
        method: str,
        extra: list[KeyLevel],
        params: Any,
    ) -> list[Evidence]:
        sign = leg.direction.sign
        against = Direction.BEAR if sign > 0 else Direction.BULL
        pending = dict(levels)
        out: list[Evidence] = []
        for t in range(start, end + 1):
            if _broken(ctx, leg, t) or not pending:
                break
            tol = tolerance(ctx, t, params.tol_atr)
            if not np.isfinite(tol):
                continue
            for r, level in sorted(pending.items()):
                if (ctx.c[t] - level) * sign > tol:
                    del pending[r]  # closed through: no longer a barrier
                    continue
                touch = touch_rejection(ctx, t, level, tol)
                if touch is None or touch.direction is not against:
                    continue
                del pending[r]
                out.append(
                    self.make(
                        ctx,
                        t,
                        against,
                        touch.quality * EXTENSION_WEIGHT.get(r, 0.8),
                        key_levels=[*leg.key_levels(), *extra, KeyLevel(f"ext_{r * 100:.1f}", level)],
                        invalidation=level + sign * tol,
                        targets=[leg.b.price],
                        details={"ratio": r, "method": method, "degree": params.degree},
                        variant=f"{method}.{r * 100:.1f}",
                    )
                )
        return out


# --- cluster ----------------------------------------------------------------------------------------------


class ClusterParams(DetectorParams):
    degrees: tuple[str, ...] = ("minor", "intermediate", "major")
    cluster_atr: float = Field(default=0.3, gt=0, le=3)  # max span of a cluster
    tol_atr: float = Field(default=0.25, gt=0, le=2)
    min_levels: int = Field(default=2, ge=2, le=10)
    cooldown_bars: int = Field(default=10, ge=0, le=500)


class FibCluster(Detector):
    """Coinciding Fibonacci levels of different degrees, probed and rejected.

    Levels from the last impulses of each degree that lie within ``cluster_atr`` of each other form a cluster.
    Only levels from *distinct* impulses count, so one impulse seen at two degrees is not a cluster.
    """

    id = "fib.cluster"
    name = "Fibonacci cluster"
    family = Family.FIBONACCI
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = ClusterParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        by_degree = {d: list(impulses(ctx.zigzag(d), ctx.last_pos)) for d in params.degrees}
        # bars at which some degree's last impulse changes: clusters are rebuilt there
        changes = sorted({imp.start for imps in by_degree.values() for imp in imps})
        out: list[Evidence] = []
        cooldown = Cooldown(params.cooldown_bars)
        for k, start in enumerate(changes):
            end = changes[k + 1] - 1 if k + 1 < len(changes) else ctx.last_pos
            atr = ctx.atr_array()[start - 1] if start > 0 else np.nan
            if not np.isfinite(atr):
                continue
            levels = self._levels(by_degree, start)
            for cluster in _clusters(levels, params.cluster_atr * atr, params.min_levels):
                lo_lv, hi_lv = cluster[0][0], cluster[-1][0]
                for t in range(start, end + 1):
                    tol = tolerance(ctx, t, params.tol_atr)
                    touch = touch_rejection(ctx, t, (lo_lv + hi_lv) / 2, tol + (hi_lv - lo_lv) / 2)
                    if touch is None:
                        continue
                    if not cooldown.allow(t, lo_lv, hi_lv, touch.direction):
                        break
                    out.append(
                        self.make(
                            ctx,
                            t,
                            touch.direction,
                            touch.quality * min(1.0, 0.4 + 0.2 * len(cluster)),
                            key_levels=[KeyLevel(name, price) for price, name, _ in cluster],
                            invalidation=lo_lv - tol if touch.direction is Direction.BULL else hi_lv + tol,
                            details={"levels": len(cluster)},
                        )
                    )
                    break  # once per cluster
        return out

    @staticmethod
    def _levels(by_degree: dict[str, list[Impulse]], t: int) -> list[tuple[float, str, tuple[int, int]]]:
        levels: list[tuple[float, str, tuple[int, int]]] = []
        seen: set[tuple[int, int]] = set()
        for degree, imps in by_degree.items():
            current = [imp for imp in imps if imp.start <= t <= imp.end]
            if not current:
                continue
            imp = current[0]
            key = (imp.a.pivot_pos, imp.b.pivot_pos)
            if key in seen:
                continue
            seen.add(key)
            levels += [(imp.retracement(r), f"{degree}_ret_{r * 100:.1f}", key) for r in RETRACEMENTS[1:]]
            levels += [(imp.extension(e), f"{degree}_ext_{e * 100:.1f}", key) for e in EXTENSIONS]
        return sorted(levels)


def _clusters(
    levels: list[tuple[float, str, tuple[int, int]]], span: float, min_levels: int
) -> list[list[tuple[float, str, tuple[int, int]]]]:
    out: list[list[tuple[float, str, tuple[int, int]]]] = []
    current: list[tuple[float, str, tuple[int, int]]] = []
    for lv in levels:
        if current and lv[0] - current[0][0] > span:
            out.append(current)
            current = []
        current.append(lv)
    if current:
        out.append(current)
    return [c for c in out if len(c) >= min_levels and len({imp for _, _, imp in c}) >= 2]
