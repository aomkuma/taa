"""Market structure (family TREND) and smart-money / Wyckoff (family SMART_MONEY) detectors (PLAN §A29).

Structure works on confirmed zigzag pivots: a pivot is used only from the bar *after* its confirmation.
Smart-money zones (fair value gaps, order blocks, supply/demand) are reported when price **comes back** and
rejects them (a retest), not when they form, so they do not double-count the impulse that created them. A
close through a zone before the retest kills it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
from pydantic import Field

from app.evidence.chart_patterns import Line
from app.evidence.common import Cooldown
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
from app.indicators.price_action import StructureLabel, Swing, SwingKind, label_structure


def _dir(sign: int) -> Direction:
    return Direction.BULL if sign > 0 else Direction.BEAR


@dataclass
class StructureState:
    """Walks bars forward, feeding in pivots once they are usable (the bar after confirmation)."""

    pivots: list[Swing]
    labels: dict[int, StructureLabel | None] = field(default_factory=dict)
    last: dict[SwingKind, Swing] = field(default_factory=dict)
    last_label: dict[SwingKind, StructureLabel | None] = field(default_factory=dict)
    _next: int = 0

    def __post_init__(self) -> None:
        self.labels = {ls.swing.pivot_pos: ls.label for ls in label_structure(self.pivots)}

    def advance(self, t: int) -> list[Swing]:
        """Pivots that became usable at bar *t*."""
        new: list[Swing] = []
        while self._next < len(self.pivots) and self.pivots[self._next].confirm_pos < t:
            p = self.pivots[self._next]
            self.last[p.kind] = p
            self.last_label[p.kind] = self.labels.get(p.pivot_pos)
            new.append(p)
            self._next += 1
        return new

    @property
    def trend(self) -> int:
        hi, lo = self.last_label.get(SwingKind.HIGH), self.last_label.get(SwingKind.LOW)
        if hi is StructureLabel.HH and lo is StructureLabel.HL:
            return 1
        if hi is StructureLabel.LH and lo is StructureLabel.LL:
            return -1
        return 0


class StructureParams(DetectorParams):
    degree: str = "minor"


# --- Dow structure and BOS / CHoCH ------------------------------------------------------------------------


class DowStructure(Detector):
    """Dow theory trend state from confirmed pivots: ``up`` once the last high is a higher high and the last
    low a higher low, ``down`` for lower highs and lower lows. Stamped when the state begins; it lasts until a
    close beyond the last opposite pivot (``max_age_bars`` 50)."""

    id = "structure.dow"
    name = "Dow structure"
    family = Family.TREND
    tier = Tier.T1

    class Params(StructureParams):
        max_age_bars: int = Field(default=50, ge=0, le=2000)

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        st = StructureState(ctx.zigzag(params.degree))
        out: list[Evidence] = []
        prev = 0
        for t in range(ctx.n):
            if not st.advance(t):
                continue
            trend = st.trend
            if trend != 0 and trend != prev:
                guard = st.last[SwingKind.LOW if trend > 0 else SwingKind.HIGH]
                out.append(
                    self.make(
                        ctx,
                        t,
                        _dir(trend),
                        0.7,
                        key_levels=[
                            swing_level("last_high", st.last[SwingKind.HIGH]),
                            swing_level("last_low", st.last[SwingKind.LOW]),
                        ],
                        invalidation=guard.price,
                        variant="up" if trend > 0 else "down",
                    )
                )
            prev = trend
        return out


class BosChoch(Detector):
    """The first close beyond the last confirmed swing. With the trend it is a break of structure (``bos``,
    continuation); against an established trend a change of character (``choch``, the first sign of a
    reversal); with no clear trend a plain ``break``. Invalidation: the last opposite swing."""

    id = "structure.bos_choch"
    name = "Break of structure / change of character"
    family = Family.TREND
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = StructureParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        st = StructureState(ctx.zigzag(params.degree))
        broken: set[int] = set()
        out: list[Evidence] = []
        for t in range(ctx.n):
            st.advance(t)
            for kind, sign in ((SwingKind.HIGH, 1), (SwingKind.LOW, -1)):
                piv = st.last.get(kind)
                opposite = st.last.get(SwingKind.LOW if sign > 0 else SwingKind.HIGH)
                if piv is None or opposite is None or piv.pivot_pos in broken:
                    continue
                if (ctx.c[t] - piv.price) * sign <= 0:
                    continue
                broken.add(piv.pivot_pos)
                trend = st.trend
                kind_name, q = (
                    ("bos", 0.8) if trend == sign else (("choch", 0.7) if trend == -sign else ("break", 0.5))
                )
                out.append(
                    self.make(
                        ctx,
                        t,
                        _dir(sign),
                        q,
                        key_levels=[
                            swing_level("broken_swing", piv),
                            swing_level("opposite_swing", opposite),
                        ],
                        invalidation=opposite.price,
                        variant=kind_name,
                    )
                )
        return out


# --- trendlines and channels ------------------------------------------------------------------------------


class TrendlineParams(StructureParams):
    tol_atr: float = Field(default=0.25, gt=0, le=3)
    parallel_tol: float = Field(
        default=0.3, gt=0, le=2
    )  # relative slope difference that still counts as parallel


class Trendline(Detector):
    """Lines through the last two confirmed swing lows (rising: support) and highs (falling: resistance).

    ``bounce_support`` / ``bounce_resistance``: a later bar probes the line (within ``tol_atr`` × ATR) and
    closes back on its side in the right colour (once per line). ``break_support`` / ``break_resistance``: the
    first close beyond the line by the tolerance, which ends it. Detail ``channel`` is true when both lines
    exist and are near-parallel with the same slope sign.
    """

    id = "structure.trendline"
    name = "Trendline / channel"
    family = Family.TREND
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = TrendlineParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        pivots = ctx.zigzag(params.degree)
        atr = ctx.atr_array()
        out: list[Evidence] = []
        st = StructureState(pivots)
        lines: dict[int, tuple[Line, Swing, Swing] | None] = {1: None, -1: None}  # 1 support, -1 resistance
        bounced: set[tuple[int, int]] = set()
        for t in range(ctx.n):
            for p in st.advance(t):
                sign = 1 if p.kind is SwingKind.LOW else -1
                same = [q for q in pivots if q.kind is p.kind and q.confirm_pos < t]
                if len(same) >= 2:
                    a, b = same[-2], same[-1]
                    rising = b.price > a.price
                    lines[sign] = (
                        (Line.fit([a.pivot_pos, b.pivot_pos], [a.price, b.price]), a, b)
                        if rising == (sign > 0)
                        else None
                    )
            if not np.isfinite(atr[t]):
                continue
            tol = params.tol_atr * float(atr[t])
            channel = self._parallel(lines, params.parallel_tol)
            for sign in (1, -1):
                entry = lines[sign]
                if entry is None:
                    continue
                line, a, b = entry
                level = line.at(t)
                if t <= b.confirm_pos:
                    continue
                name = "support" if sign > 0 else "resistance"
                if (ctx.c[t] - level) * sign < -tol:
                    lines[sign] = None
                    out.append(self._rec(ctx, t, -sign, 0.7, f"break_{name}", level, a, b, channel, level))
                    continue
                probe = ctx.l[t] if sign > 0 else ctx.h[t]
                key = (b.pivot_pos, sign)
                if (
                    key not in bounced
                    and (probe - level) * sign <= tol
                    and (ctx.c[t] - level) * sign > 0
                    and (ctx.c[t] - ctx.o[t]) * sign > 0
                ):
                    bounced.add(key)
                    out.append(
                        self._rec(
                            ctx,
                            t,
                            sign,
                            0.8 if channel else 0.65,
                            f"bounce_{name}",
                            level,
                            a,
                            b,
                            channel,
                            level - sign * tol,
                        )
                    )
        return out

    @staticmethod
    def _parallel(lines: dict[int, tuple[Line, Swing, Swing] | None], tol: float) -> bool:
        s, r = lines[1], lines[-1]
        if s is None or r is None:
            return False
        a, b = s[0].slope, r[0].slope
        return a * b > 0 and abs(a - b) <= tol * max(abs(a), abs(b))

    def _rec(
        self,
        ctx: EvidenceContext,
        t: int,
        sign: int,
        q: float,
        variant: str,
        level: float,
        a: Swing,
        b: Swing,
        channel: bool,
        invalidation: float,
    ) -> Evidence:
        return self.make(
            ctx,
            t,
            _dir(sign),
            q,
            key_levels=[
                swing_level("anchor_1", a),
                swing_level("anchor_2", b),
                KeyLevel("line", float(level)),
            ],
            invalidation=float(invalidation),
            details={"channel": channel},
            variant=variant,
        )


# --- liquidity sweep --------------------------------------------------------------------------------------


class SweepParams(DetectorParams):
    swing_k: int = Field(default=3, ge=1, le=20)
    lookback: int = Field(default=50, ge=5, le=1000)  # how old a swing may be and still hold liquidity


class LiquiditySweep(Detector):
    """A stop hunt: a bar trades beyond a recent confirmed swing high (low), where stops rest, and closes back
    inside. Bearish above highs, bullish below lows. A swing is spent once traded through, swept or not.
    Invalidation: the sweep bar's extreme."""

    id = "smc.liquidity_sweep"
    name = "Liquidity sweep"
    family = Family.SMART_MONEY
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = SweepParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        swings = ctx.swings(params.swing_k)
        atr = ctx.atr_array()
        pools: list[Swing] = []
        j = 0
        out: list[Evidence] = []
        for t in range(ctx.n):
            while j < len(swings) and swings[j].confirm_pos < t:
                pools.append(swings[j])
                j += 1
            pools = [p for p in pools if t - p.pivot_pos <= params.lookback]
            if not np.isfinite(atr[t]):
                continue
            for kind, sign in ((SwingKind.HIGH, -1), (SwingKind.LOW, 1)):
                beyond = ctx.h[t] if kind is SwingKind.HIGH else ctx.l[t]
                taken = [p for p in pools if p.kind is kind and (beyond - p.price) * -sign > 0]
                if not taken:
                    continue
                pools = [p for p in pools if p not in taken]
                pool = max(taken, key=lambda p: p.price * -sign)  # the furthest pool swept
                if (ctx.c[t] - pool.price) * sign <= 0:
                    continue  # closed beyond: a breakout, not a sweep
                wick = abs(beyond - pool.price) / float(atr[t])
                out.append(
                    self.make(
                        ctx,
                        t,
                        _dir(sign),
                        min(1.0, 0.5 + 0.25 * len(taken) + 0.25 * min(wick, 1.0)),
                        key_levels=[swing_level("pool", pool)],
                        invalidation=float(beyond),
                        details={"pools": len(taken)},
                    )
                )
        return out


# --- fair value gaps --------------------------------------------------------------------------------------


class FvgParams(DetectorParams):
    min_gap_atr: float = Field(default=0.2, gt=0, le=5)
    max_bars: int = Field(default=50, ge=1, le=1000)  # how long a gap waits for its retest


@dataclass(frozen=True, slots=True)
class Zone:
    low: float
    high: float
    sign: int  # +1 demand-like (expects support), -1 supply-like
    born: int  # bar at which the zone is known


def _retest(ctx: EvidenceContext, z: Zone, max_bars: int) -> int | None:
    """First bar after the zone formed that dips into it and closes back on its side; None if a close through
    the zone (or the wait) ends it first."""
    for u in range(z.born + 1, min(z.born + max_bars, ctx.last_pos) + 1):
        far = z.low if z.sign > 0 else z.high
        near = z.high if z.sign > 0 else z.low
        if (ctx.c[u] - far) * z.sign < 0:
            return None  # closed through the zone: filled / broken
        probe = ctx.l[u] if z.sign > 0 else ctx.h[u]
        if (probe - near) * z.sign <= 0 and (ctx.c[u] - near) * z.sign > 0:
            return u
    return None


class FairValueGap(Detector):
    """A three-bar imbalance: bullish when bar *t*'s low is above bar *t − 2*'s high by ≥ ``min_gap_atr`` ×
    ATR (the middle bar moved too fast to trade both ways). Reported when price returns into the gap and
    closes back above it, within ``max_bars``; a close below the gap first kills it. Bearish mirrors it."""

    id = "smc.fvg"
    name = "Fair value gap retest"
    family = Family.SMART_MONEY
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = FvgParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        atr = ctx.atr_array()
        out: list[Evidence] = []
        for t in range(2, ctx.n):
            if not np.isfinite(atr[t]):
                continue
            for sign in (1, -1):
                lo, hi = (ctx.h[t - 2], ctx.l[t]) if sign > 0 else (ctx.h[t], ctx.l[t - 2])
                gap = hi - lo
                if gap < params.min_gap_atr * atr[t]:
                    continue
                z = Zone(float(lo), float(hi), sign, t)
                u = _retest(ctx, z, params.max_bars)
                if u is not None:
                    out.append(_zone_record(self, ctx, u, z, min(1.0, 0.5 + 0.5 * gap / atr[t]), t))
        return out


def _zone_record(det: Detector, ctx: EvidenceContext, u: int, z: Zone, q: float, origin: int) -> Evidence:
    return det.make(
        ctx,
        u,
        _dir(z.sign),
        q,
        key_levels=[KeyLevel("zone_low", z.low), KeyLevel("zone_high", z.high)],
        invalidation=z.low if z.sign > 0 else z.high,
        details={"zone_bar": ctx.time_at(origin).isoformat()},
    )


# --- order blocks and supply / demand ---------------------------------------------------------------------


class DepartureParams(DetectorParams):
    displacement_atr: float = Field(default=2.0, gt=0, le=20)  # move of the departure leg
    max_leg_bars: int = Field(default=3, ge=1, le=20)
    break_lookback: int = Field(default=10, ge=2, le=200)  # the leg must clear this many bars' extreme
    max_bars: int = Field(default=50, ge=1, le=1000)  # how long a zone waits for its retest
    base_atr: float = Field(default=0.6, gt=0, le=5)  # base bars: range at most this × ATR
    max_base_bars: int = Field(default=4, ge=1, le=20)


def departures(ctx: EvidenceContext, params: Any) -> list[tuple[int, int, int]]:
    """``(start, end, sign)`` of displacement legs: ≤ ``max_leg_bars`` bars moving ≥ ``displacement_atr`` ×
    ATR and closing beyond the previous ``break_lookback`` bars' extreme. One leg per end bar, the
    shortest."""
    atr = ctx.atr_array()
    out: list[tuple[int, int, int]] = []
    last_end = -1
    for d in range(params.break_lookback + params.max_leg_bars, ctx.n):
        if not np.isfinite(atr[d]) or d <= last_end:
            continue
        for k in range(1, params.max_leg_bars + 1):
            s = d - k + 1
            move = ctx.c[d] - ctx.o[s]
            if abs(move) < params.displacement_atr * atr[d]:
                continue
            sign = 1 if move > 0 else -1
            ref = ctx.h[s - params.break_lookback : s] if sign > 0 else ctx.l[s - params.break_lookback : s]
            if (ctx.c[d] - (ref.max() if sign > 0 else ref.min())) * sign > 0:
                out.append((s, d, sign))
                last_end = d
                break
    return out


class OrderBlock(Detector):
    """The last opposite-colour candle before a displacement leg (for a bullish leg: the last bearish bar
    within 5 bars before it). Reported when price returns into that candle's range and closes back out of
    it in the leg's direction."""

    id = "smc.order_block"
    name = "Order block retest"
    family = Family.SMART_MONEY
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = DepartureParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        out: list[Evidence] = []
        for s, d, sign in departures(ctx, params):
            ob = next((i for i in range(s, max(s - 6, 0), -1) if (ctx.c[i] - ctx.o[i]) * sign < 0), None)
            if ob is None:
                continue
            z = Zone(float(ctx.l[ob]), float(ctx.h[ob]), sign, d)
            u = _retest(ctx, z, params.max_bars)
            if u is not None:
                out.append(_zone_record(self, ctx, u, z, 0.7, ob))
        return out


class SupplyDemand(Detector):
    """A base of 1–``max_base_bars`` tight bars (range ≤ ``base_atr`` × ATR) right before a displacement leg:
    demand below a rally, supply above a drop. Reported on the first retest that closes back out of the zone
    in
    the leg's direction."""

    id = "smc.supply_demand"
    name = "Supply/demand zone retest"
    family = Family.SMART_MONEY
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = DepartureParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        atr = ctx.atr_array()
        out: list[Evidence] = []
        for s, d, sign in departures(ctx, params):
            base: list[int] = []
            i = s - 1
            while i >= 0 and len(base) < params.max_base_bars and np.isfinite(atr[i]):
                if ctx.h[i] - ctx.l[i] > params.base_atr * atr[i]:
                    break
                base.append(i)
                i -= 1
            if not base:
                continue
            z = Zone(float(ctx.l[base].min()), float(ctx.h[base].max()), sign, d)
            u = _retest(ctx, z, params.max_bars)
            if u is not None:
                out.append(_zone_record(self, ctx, u, z, min(1.0, 0.5 + 0.1 * len(base)), base[-1]))
        return out


# --- Wyckoff ----------------------------------------------------------------------------------------------


class WyckoffParams(DetectorParams):
    range_bars: int = Field(default=30, ge=5, le=1000)
    min_range_atr: float = Field(default=2.0, gt=0, le=50)
    max_range_atr: float = Field(default=6.0, gt=0, le=100)
    max_drift: float = Field(default=0.5, gt=0, le=1)  # net move across the range ÷ its height: sideways
    cooldown_bars: int = Field(default=10, ge=0, le=500)


class WyckoffSpring(Detector):
    """In a sideways trading range of the last ``range_bars`` bars, a ``spring`` dips below the range low and
    closes back inside (bullish); an ``upthrust`` pokes above the range high and closes back inside
    (bearish)."""

    id = "wyckoff.spring_upthrust"
    name = "Wyckoff spring/upthrust"
    family = Family.SMART_MONEY
    tier = Tier.T2
    Params: ClassVar[type[DetectorParams]] = WyckoffParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        atr = ctx.atr_array()
        n = params.range_bars
        cooldown = Cooldown(params.cooldown_bars)
        out: list[Evidence] = []
        for t in range(n, ctx.n):
            a = atr[t - 1]
            if not np.isfinite(a):
                continue
            hi, lo = float(ctx.h[t - n : t].max()), float(ctx.l[t - n : t].min())
            height = hi - lo
            drift = abs(ctx.c[t - 1] - ctx.c[t - n])
            if (
                not (params.min_range_atr * a <= height <= params.max_range_atr * a)
                or drift > params.max_drift * height
            ):
                continue
            if ctx.l[t] < lo and lo < ctx.c[t] < hi:
                sign, level, extreme, kind = 1, lo, float(ctx.l[t]), "spring"
            elif ctx.h[t] > hi and lo < ctx.c[t] < hi:
                sign, level, extreme, kind = -1, hi, float(ctx.h[t]), "upthrust"
            else:
                continue
            if not cooldown.allow(t, level, level, _dir(sign)):
                continue
            out.append(
                self.make(
                    ctx,
                    t,
                    _dir(sign),
                    min(1.0, 0.5 + 0.5 * abs(ctx.c[t] - level) / max(height, 1e-12) * 2),
                    key_levels=[KeyLevel("range_high", hi), KeyLevel("range_low", lo)],
                    invalidation=extreme,
                    targets=[hi if sign > 0 else lo],
                    variant=kind,
                )
            )
        return out
