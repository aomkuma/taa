"""Level detectors (PLAN §A29, family LEVELS, tier T1).

Round numbers, pivot points, previous period high/low, and S/R zones from confirmed swings.

A level "holds" when a bar probes it (within an ATR tolerance) and rejects it (see
:func:`app.evidence.common.touch_rejection`). Each detector reports a given level at most once per trading
period (or per zone), so a level that is retested all day does not flood the confluence score.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import Field

from app.evidence.common import Cooldown, period_keys, previous_period_hlc, tolerance, touch_rejection
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
from app.indicators.price_action import BreakoutStatus, Zone, detect_breakouts, sr_zones

# --- round numbers ----------------------------------------------------------------------------------------


class RoundNumberParams(DetectorParams):
    tol_atr: float = Field(default=0.15, gt=0, le=2)
    half_levels: bool = True
    # None: derived from the price magnitude (EURUSD 1.10 -> 0.01, USDJPY 150 -> 1, XAUUSD 4100 -> 10)
    step: float | None = Field(default=None, gt=0)
    cooldown_bars: int = Field(default=5, ge=0, le=500)


def round_step(price: float) -> float:
    """The "big figure" for a price: two orders of magnitude below its leading digit."""
    return float(10.0 ** (math.floor(math.log10(price)) - 2))


class RoundNumber(Detector):
    """A round price (major = 10 steps, minor = 1 step, half = 0.5 step) probed and rejected."""

    id = "levels.round_number"
    name = "Round number"
    family = Family.LEVELS
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = RoundNumberParams

    WEIGHT: ClassVar[dict[str, float]] = {"major": 1.0, "minor": 0.8, "half": 0.6}

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        out: list[Evidence] = []
        cooldown = Cooldown(params.cooldown_bars)
        for t in range(ctx.n):
            tol, c = tolerance(ctx, t, params.tol_atr), ctx.c[t]
            if not (np.isfinite(tol) and c > 0):
                continue
            step = params.step or round_step(c)
            grid = step / 2 if params.half_levels else step
            first = math.ceil((ctx.l[t] - tol) / grid)
            last = math.floor((ctx.h[t] + tol) / grid)
            for k in range(first, last + 1):
                level = round(k * grid, 10)
                touch = touch_rejection(ctx, t, level, tol)
                if touch is None or not cooldown.allow(t, level, level, touch.direction):
                    continue
                kind = _round_kind(level, step)
                out.append(
                    self.make(
                        ctx,
                        t,
                        touch.direction,
                        touch.quality * self.WEIGHT[kind],
                        key_levels=[KeyLevel("round", level)],
                        invalidation=level - tol if touch.direction is Direction.BULL else level + tol,
                        details={"step": step},
                        variant=kind,
                    )
                )
        return out


def _round_kind(level: float, step: float) -> str:
    units = level / step
    if abs(units / 10 - round(units / 10)) < 1e-6:
        return "major"
    if abs(units - round(units)) < 1e-6:
        return "minor"
    return "half"


# --- pivot points -----------------------------------------------------------------------------------------

PivotMethod = Literal["classic", "fibonacci", "camarilla"]


def pivot_levels(method: str, h: float, lo: float, c: float) -> dict[str, float]:
    """Pivot levels from the previous period's high, low and close."""
    p, rng = (h + lo + c) / 3, h - lo
    if method == "classic":
        return {
            "P": p,
            "R1": 2 * p - lo,
            "S1": 2 * p - h,
            "R2": p + rng,
            "S2": p - rng,
            "R3": h + 2 * (p - lo),
            "S3": lo - 2 * (h - p),
        }
    if method == "fibonacci":
        out = {"P": p}
        for i, r in enumerate((0.382, 0.618, 1.0), start=1):
            out[f"R{i}"], out[f"S{i}"] = p + r * rng, p - r * rng
        return out
    out = {}
    for i, f in enumerate((12, 6, 4, 2), start=1):  # camarilla: (H - L) * 1.1 / f around the close
        out[f"R{i}"], out[f"S{i}"] = c + rng * 1.1 / f, c - rng * 1.1 / f
    return out


def _period(ctx: EvidenceContext) -> str:
    """Daily levels on intraday charts; weekly levels on D1 (a daily pivot would just be the previous bar)."""
    return "week" if ctx.timeframe.seconds >= 86_400 else "day"


class PivotParams(DetectorParams):
    methods: tuple[PivotMethod, ...] = Field(default=("classic",), min_length=1)
    tol_atr: float = Field(default=0.2, gt=0, le=2)


class PivotPoints(Detector):
    """Classic / Fibonacci / Camarilla pivot levels of the previous period, probed and rejected."""

    id = "levels.pivot_points"
    name = "Pivot point"
    family = Family.LEVELS
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = PivotParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        period = _period(ctx)
        keys = period_keys(ctx, period)
        ph, pl, pc = previous_period_hlc(ctx, period)
        done: set[tuple[int, str]] = set()
        out: list[Evidence] = []
        for t in range(ctx.n):
            tol = tolerance(ctx, t, params.tol_atr)
            if not (np.isfinite(tol) and np.isfinite(ph[t])):
                continue
            for method in params.methods:
                for name, level in pivot_levels(method, ph[t], pl[t], pc[t]).items():
                    tag = f"{method}.{name}"
                    if (int(keys[t]), tag) in done:
                        continue
                    touch = touch_rejection(ctx, t, level, tol)
                    if touch is None:
                        continue
                    done.add((int(keys[t]), tag))
                    out.append(
                        self.make(
                            ctx,
                            t,
                            touch.direction,
                            touch.quality,
                            key_levels=[KeyLevel(tag, level)],
                            invalidation=level - tol if touch.direction is Direction.BULL else level + tol,
                            details={"period": period},
                            variant=tag,
                        )
                    )
        return out


# --- previous period high / low ---------------------------------------------------------------------------


class PrevHighLowParams(DetectorParams):
    periods: tuple[Literal["day", "week"], ...] = Field(default=("day", "week"), min_length=1)
    tol_atr: float = Field(default=0.2, gt=0, le=2)


class PrevHighLow(Detector):
    """Previous day/week high and low: rejected (reversal) or broken by a close (continuation)."""

    id = "levels.prev_high_low"
    name = "Previous period high/low"
    family = Family.LEVELS
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = PrevHighLowParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        out: list[Evidence] = []
        for period in params.periods:
            if period == "day" and ctx.timeframe.seconds >= 86_400:
                continue
            keys = period_keys(ctx, period)
            ph, pl, _ = previous_period_hlc(ctx, period)
            done: set[tuple[int, str]] = set()
            prefix = "pd" if period == "day" else "pw"
            for t in range(ctx.n):
                tol = tolerance(ctx, t, params.tol_atr)
                if not (np.isfinite(tol) and np.isfinite(ph[t])):
                    continue
                for side, level in (("h", ph[t]), ("l", pl[t])):
                    tag = f"{prefix}{side}"
                    found = self._event(ctx, t, side, level, tol)
                    if found is None or (int(keys[t]), f"{tag}.{found[0]}") in done:
                        continue
                    kind, direction, quality, invalidation = found
                    done.add((int(keys[t]), f"{tag}.{kind}"))
                    out.append(
                        self.make(
                            ctx,
                            t,
                            direction,
                            quality,
                            key_levels=[KeyLevel(tag, level)],
                            invalidation=invalidation,
                            details={"period": period},
                            variant=f"{tag}.{kind}",
                        )
                    )
        return out

    @staticmethod
    def _event(
        ctx: EvidenceContext, t: int, side: str, level: float, tol: float
    ) -> tuple[str, Direction, float, float] | None:
        prev_close = ctx.c[t - 1] if t > 0 else np.nan
        if side == "h" and ctx.c[t] > level >= prev_close:
            return "break", Direction.BULL, 0.7, level
        if side == "l" and ctx.c[t] < level <= prev_close:
            return "break", Direction.BEAR, 0.7, level
        touch = touch_rejection(ctx, t, level, tol)
        wanted = Direction.BEAR if side == "h" else Direction.BULL
        if touch is None or touch.direction is not wanted:
            return None
        inval = level + tol if wanted is Direction.BEAR else level - tol
        return "reject", wanted, touch.quality, inval


# --- S/R zones --------------------------------------------------------------------------------------------


class ZoneParams(DetectorParams):
    swing_k: int = Field(default=3, ge=1, le=20)
    zone_atr: float = Field(default=0.5, gt=0, le=3)  # max zone width
    min_touches: int = Field(default=3, ge=1, le=20)
    tol_atr: float = Field(default=0.15, gt=0, le=2)
    cooldown_bars: int = Field(default=10, ge=0, le=500)
    min_wick: float = Field(default=0.3, ge=0, le=1)  # rejecting wick as a share of the bar range


def zone_windows(ctx: EvidenceContext, params: Any) -> list[tuple[int, int, list[Zone]]]:
    """``(start, end, zones)``: the zones in force for bars ``start..end``, rebuilt after each new swing.

    Zones for bar *t* come from swings confirmed before *t* and the ATR of the bar before *t*.
    """
    swings = ctx.swings(params.swing_k)
    atr = ctx.atr_array()
    starts = sorted({s.confirm_pos + 1 for s in swings if s.confirm_pos + 1 <= ctx.last_pos})
    out: list[tuple[int, int, list[Zone]]] = []
    for k, start in enumerate(starts):
        end = starts[k + 1] - 1 if k + 1 < len(starts) else ctx.last_pos
        if not np.isfinite(atr[start - 1]):
            continue
        zones = sr_zones(
            swings,
            as_of_pos=start - 1,
            atr_value=float(atr[start - 1]),
            tolerance_atr=params.zone_atr,
            min_touches=params.min_touches,
        )
        out.append((start, end, zones))
    return out


def _zone_levels(z: Zone) -> list[KeyLevel]:
    return [KeyLevel("zone_low", z.low), KeyLevel("zone_high", z.high)]


class SRZone(Detector):
    """A support/resistance zone of clustered swings, tested and rejected.

    The zone needs at least ``min_touches`` swings and is tested from the side it was approached from.
    """

    id = "levels.sr_zone"
    name = "Support/resistance zone"
    family = Family.LEVELS
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = ZoneParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        out: list[Evidence] = []
        cooldown = Cooldown(params.cooldown_bars)
        for start, end, zones in zone_windows(ctx, params):
            for z in zones:
                for t in range(max(start, 1), end + 1):
                    tol = tolerance(ctx, t, params.tol_atr)
                    o, h, lo, c, prev = ctx.o[t], ctx.h[t], ctx.l[t], ctx.c[t], ctx.c[t - 1]
                    rng = h - lo
                    if not (np.isfinite(tol) and rng > 0):
                        continue
                    if (
                        prev > z.high
                        and lo <= z.high + tol
                        and min(o, c) >= z.low
                        and c > z.high
                        and (min(o, c) - lo) / rng >= params.min_wick
                    ):
                        direction, inval = Direction.BULL, z.low - tol
                    elif (
                        prev < z.low
                        and h >= z.low - tol
                        and max(o, c) <= z.high
                        and c < z.low
                        and (h - max(o, c)) / rng >= params.min_wick
                    ):
                        direction, inval = Direction.BEAR, z.high + tol
                    else:
                        continue
                    if not cooldown.allow(t, z.low, z.high, direction):
                        break
                    out.append(
                        self.make(
                            ctx,
                            t,
                            direction,
                            min(1.0, 0.4 + 0.15 * z.touches),
                            key_levels=_zone_levels(z),
                            invalidation=inval,
                            details={"touches": z.touches},
                        )
                    )
                    break  # once per zone per window
        return out


class BreakoutParams(ZoneParams):
    min_touches: int = Field(default=2, ge=1, le=20)
    buffer_atr: float = Field(default=0.1, ge=0, le=2)
    confirm_bars: int = Field(default=3, ge=1, le=20)
    # bars that must close on the pre-breakout side: a base under resistance, not a whipsaw through it
    min_bars_before: int = Field(default=5, ge=1, le=100)


class SRBreakout(Detector):
    """A close through an S/R zone, judged after ``confirm_bars``.

    Holding outside is a continuation; a close back inside within those bars is a false breakout (evidence in
    the opposite direction). The record is stamped when the outcome is decided, never earlier.
    """

    id = "levels.sr_breakout"
    name = "S/R zone breakout"
    family = Family.LEVELS
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = BreakoutParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        out: list[Evidence] = []
        seen: set[tuple[int, int]] = set()  # (breakout bar, direction): one event even if several zones break
        for start, end, zones in zone_windows(ctx, params):
            events = detect_breakouts(
                ctx.close,
                ctx.atr(),
                zones,
                buffer_atr=params.buffer_atr,
                false_breakout_bars=params.confirm_bars,
                start_pos=max(start, 1),
            )
            for b in events:
                if b.pos > end or b.resolved_pos is None or (b.pos, b.direction) in seen:
                    continue
                if not _based(ctx, b.pos, b.direction, b.zone, params.min_bars_before):
                    continue
                seen.add((b.pos, b.direction))
                confirmed = b.status is BreakoutStatus.CONFIRMED
                direction = Direction.BULL if (b.direction > 0) == confirmed else Direction.BEAR
                out.append(
                    self.make(
                        ctx,
                        b.resolved_pos,
                        direction,
                        min(1.0, 0.4 + 0.15 * b.zone.touches),
                        key_levels=[*_zone_levels(b.zone), KeyLevel("breakout_level", b.level)],
                        invalidation=(b.zone.high if b.direction > 0 else b.zone.low)
                        if confirmed
                        else (ctx.h[b.pos] if b.direction > 0 else ctx.l[b.pos]),
                        details={"touches": b.zone.touches, "breakout_bar": ctx.time_at(b.pos).isoformat()},
                        variant="confirmed" if confirmed else "false",
                    )
                )
        return out


def _based(ctx: EvidenceContext, pos: int, direction: int, zone: Zone, bars: int) -> bool:
    """The zone acted on the breakout side (resistance had swing highs, support swing lows) and the
    *bars* closes before the breakout stayed on the near side of it."""
    if pos < bars:
        return False
    before = ctx.c[pos - bars : pos]
    if direction > 0:
        return zone.high_touches > 0 and bool((before <= zone.high).all())
    return zone.low_touches > 0 and bool((before >= zone.low).all())
