"""Chart read: one timeframe's chart read the way a trader does (TAA-L813, docs/CHART_READ.md §4).

Pure functions over closed candles of one timeframe (open/high/low/close indexed by close time).
:class:`ChartReadFrame` computes the swings and the ATR of a frame once; :meth:`ChartReadFrame.at` reads
bar *pos*: structure, levels with roles, trendlines, the leg in progress, events at levels and two scenarios.

**Swings: the MT5 standard ZigZag** (Depth 12, Deviation 5 points, Backstep 3; owner, 2026-10-14), ported from
MetaQuotes' ``ZigZag.mq5`` in its two passes (:func:`zigzag_pivots`):

1. maps, per bar ``s`` from bars <= ``s``: the lowest low of the last ``depth`` bars is a low candidate when
   it is new and the bar's low is within ``deviation`` points of it; a new candidate erases weaker candidates
   of the last ``backstep`` bars. Same for highs;
2. cutting, forward: highs and lows alternate; while searching for a peak a lower low replaces the pending
   low, and the first high candidate fixes the pending low (and the reverse).

**No repainting.** MT5 redraws its last leg; the bot may not. A pivot is used only once it is fixed (the
opposite candidate was registered at bar ``s``) and only from bar ``s + backstep``, when the candidate maps it
was cut from are final (a map value can be erased by the next ``backstep`` bars only). So the read at bar
*t* on the full data equals the read on the data cut at *t* (the prefix property, tested).

In a straight leg the backstep erases every candidate but the leg's extreme, so a pivot becomes known only
once the next leg's extreme has held for ``backstep`` bars (the read lags the chart by about one leg; the
structure's ``broken`` flag catches a turn earlier).

The pivots of a frame depend on where the frame starts (the indicator's state converges after a few legs), so
a frame should start well before the bars that are read.

Conventions:

- distances are in ATR(``atr_period``) of the read bar; a bar without a finite ATR has no read (warm-up);
- every level/line test uses the close, probes use the high/low; the tolerance is ``tol_atr`` × ATR of the
  bar tested;
- ``retrace`` = (P1 − close) / (P1 − P0) for the last two fixed pivots P0 → P1: 0 at the last pivot, 1 back at
  the start of the previous leg (the close's position, not the leg's extreme; §4.5).
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

from app.core.errors import ConfigError, DataQualityError
from app.indicators.common import FloatArray, as_float, check_period
from app.indicators.price_action import StructureLabel, Swing, SwingKind
from app.indicators.volatility import atr


class Structure(StrEnum):
    UP = "UP"  # last high HH and last low HL
    DOWN = "DOWN"  # last high LH and last low LL
    CONTRACTING = "CONTRACTING"  # LH and HL (a triangle)
    BROADENING = "BROADENING"  # HH and LL (a megaphone)
    FLAT = "FLAT"  # an equal high or low in the pair
    NONE = "NONE"  # fewer than two pivots of each kind


class LevelRole(StrEnum):
    SUPPORT = "SUPPORT"  # below the close, never closed through
    RESISTANCE = "RESISTANCE"  # above the close, never closed through
    FLIPPED = "FLIPPED"  # closed through once, now on the other side
    SPENT = "SPENT"  # closed through both ways; dropped from the read


class EventKind(StrEnum):
    BREAK_HOLD = "BREAK_HOLD"
    SWEEP_RECLAIM = "SWEEP_RECLAIM"
    RETEST = "RETEST"


class ScenarioKind(StrEnum):
    BREAK = "BREAK"  # the tested level breaks and holds: on to the next level beyond it
    REJECT = "REJECT"  # the tested level holds (or a false break reclaims it): back to the opposite level


MIXED = frozenset({Structure.CONTRACTING, Structure.BROADENING, Structure.FLAT})


DISPLAY_SPENT = 4
DISPLAY_MINOR_DEPTH = 5


@dataclass(frozen=True, slots=True)
class ChartReadParams:
    depth: int = 12
    deviation: int = 5  # points
    backstep: int = 3
    atr_period: int = 14
    equal_atr: float = 0.1
    max_swings: int = 8
    level_lookback: int = 300
    level_tol_atr: float = 0.5
    max_levels: int = 6  # per side
    tol_atr: float = 0.25
    event_bars: int = 3
    hold_bars: int = 1
    reclaim_bars: int = 1
    # closes through, both ways, before a level is dropped as SPENT (the PWA chart: for_display)
    spent_crossings: int = 2
    # a smaller ZigZag for the levels near the price; 0: major swings only (the PWA chart: for_display)
    minor_depth: int = 0
    prov_atr: float = 1.0  # the leg's extreme counts as a provisional pivot once price came back this far

    def __post_init__(self) -> None:
        for name in ("depth", "backstep", "atr_period", "max_swings", "level_lookback", "max_levels"):
            check_period(name, getattr(self, name))
        for name in ("event_bars", "hold_bars", "reclaim_bars"):
            check_period(name, getattr(self, name))
        check_period("deviation", self.deviation, minimum=0)
        if self.backstep >= self.depth:
            raise ConfigError(f"backstep must be < depth (got {self.backstep} >= {self.depth})")
        check_period("spent_crossings", self.spent_crossings, minimum=2)
        check_period("minor_depth", self.minor_depth, minimum=0)
        if 0 < self.minor_depth <= 1:
            raise ConfigError("minor_depth must be 0 (off) or >= 2")
        for name in ("equal_atr", "level_tol_atr", "tol_atr", "prov_atr"):
            v = getattr(self, name)
            if not (math.isfinite(v) and v >= 0):
                raise ConfigError(f"{name} must be >= 0 (got {v!r})")

    def for_display(self) -> ChartReadParams:
        """The read drawn on the PWA chart: closer to what a trader draws now (the minor swings' levels, a
        level spent only after ``DISPLAY_SPENT`` crossings). Rules keep these parameters until a backtest
        passes the change (owner, 2026-10-15; research/2026-10-14-chart-read/eye_check_score.py)."""
        return replace(self, spent_crossings=DISPLAY_SPENT, minor_depth=DISPLAY_MINOR_DEPTH)


@dataclass(frozen=True, slots=True)
class Pivot:
    kind: SwingKind
    price: float
    at: datetime  # close time of the pivot bar
    known_at: datetime  # first bar a live run knows it
    label: StructureLabel | None  # None for the first pivot of its kind


@dataclass(frozen=True, slots=True)
class Leg:
    """The leg in progress since the last fixed pivot (never used as a pivot)."""

    direction: int  # +1 up from a low, -1 down from a high
    start: float  # the last pivot's price
    extreme: float  # the furthest price since, in the leg's direction
    bars: int
    leg_atr: float  # |extreme - start| / ATR
    from_pivot_atr: float  # (close - start) * direction / ATR
    retrace: float | None  # see the module docstring; None without a previous leg


@dataclass(frozen=True, slots=True)
class Level:
    price: float
    role: LevelRole
    above: bool  # above the close (acts as resistance); FLIPPED included
    touches: int
    first_at: datetime
    last_at: datetime
    retests: int  # FLIPPED: touches from the new side that closed away
    dist_atr: float
    minor: bool = False  # only minor swings make it (the levels near the price a trader also draws)


@dataclass(frozen=True, slots=True)
class TrendLine:
    kind: SwingKind  # HIGH = through falling tops (resistance), LOW = through rising bottoms (support)
    a_at: datetime
    a_price: float
    b_at: datetime
    b_price: float
    value: float  # the line at the read bar
    slope_atr: float  # per bar
    dist_atr: float  # (close - value) / ATR
    touches: int  # the two pivots plus later probes within the tolerance that closed on its side
    broken: bool
    broken_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReadEvent:
    kind: EventKind
    direction: int  # +1 bullish (a break up, a low swept and reclaimed, a retest from above), -1 bearish
    price: float  # the level, or the trendline's value on the event bar
    trendline: bool
    at: datetime  # the break, sweep or retest bar
    known_at: datetime  # the bar that completed it (hold / reclaim)


@dataclass(frozen=True, slots=True)
class Scenario:
    kind: ScenarioKind
    direction: int
    trigger: float  # the tested level
    target: float | None  # the next level that way; None when the read has none


@dataclass(frozen=True, slots=True)
class ChartRead:
    timeframe: str
    at: datetime
    close: float
    atr: float
    digits: int
    structure: Structure
    invalidation: float | None  # DOWN: the last LH; UP: the last HL
    broken: bool  # a close beyond the invalidation since the last pivot
    age_legs: int  # pivots since the structure last changed
    pivots: tuple[Pivot, ...] = ()
    leg: Leg | None = None
    levels: tuple[Level, ...] = ()  # highest first
    trendlines: tuple[TrendLine, ...] = ()
    events: tuple[ReadEvent, ...] = ()
    scenarios: tuple[Scenario, ...] = ()
    retrace_major: float | None = None  # the close inside the next-higher timeframe's last leg (§4.5)
    tol_atr: float = 0.25  # the read's tolerance (ChartReadParams.tol_atr), for "at a level" tests
    # the read "now": the leg's extreme as a provisional pivot once price came back ``prov_atr`` ATR from it
    # (data up to this bar only, but it can still move: the no-repaint read above is what rules use first)
    provisional: Pivot | None = None
    structure_now: Structure | None = None
    invalidation_now: float | None = None

    def nearest(self, *, above: bool) -> Level | None:
        side = [lv for lv in self.levels if lv.above is above]
        return min(side, key=lambda lv: lv.dist_atr, default=None)

    def scenario_text(self) -> str:
        """The scenarios in English for decision explanations (the PWA renders them from keys)."""
        return scenario_text(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "at": self.at.isoformat(),
            "close": self.close,
            "atr": self.atr,
            "digits": self.digits,
            "structure": self.structure.value,
            "invalidation": self.invalidation,
            "broken": self.broken,
            "age_legs": self.age_legs,
            "retrace_major": self.retrace_major,
            "tol_atr": self.tol_atr,
            "provisional": None if self.provisional is None else _pivot_dict(self.provisional),
            "structure_now": None if self.structure_now is None else self.structure_now.value,
            "invalidation_now": self.invalidation_now,
            "pivots": [
                {
                    "kind": p.kind.value,
                    "price": p.price,
                    "at": p.at.isoformat(),
                    "known_at": p.known_at.isoformat(),
                    "label": None if p.label is None else p.label.value,
                }
                for p in self.pivots
            ],
            "leg": None
            if self.leg is None
            else {
                "direction": self.leg.direction,
                "start": self.leg.start,
                "extreme": self.leg.extreme,
                "bars": self.leg.bars,
                "leg_atr": self.leg.leg_atr,
                "from_pivot_atr": self.leg.from_pivot_atr,
                "retrace": self.leg.retrace,
            },
            "levels": [
                {
                    "price": lv.price,
                    "role": lv.role.value,
                    "above": lv.above,
                    "touches": lv.touches,
                    "first_at": lv.first_at.isoformat(),
                    "last_at": lv.last_at.isoformat(),
                    "retests": lv.retests,
                    "dist_atr": lv.dist_atr,
                    "minor": lv.minor,
                }
                for lv in self.levels
            ],
            "trendlines": [
                {
                    "kind": tl.kind.value,
                    "a_at": tl.a_at.isoformat(),
                    "a_price": tl.a_price,
                    "b_at": tl.b_at.isoformat(),
                    "b_price": tl.b_price,
                    "value": tl.value,
                    "slope_atr": tl.slope_atr,
                    "dist_atr": tl.dist_atr,
                    "touches": tl.touches,
                    "broken": tl.broken,
                    "broken_at": None if tl.broken_at is None else tl.broken_at.isoformat(),
                }
                for tl in self.trendlines
            ],
            "events": [
                {
                    "kind": e.kind.value,
                    "direction": e.direction,
                    "price": e.price,
                    "trendline": e.trendline,
                    "at": e.at.isoformat(),
                    "known_at": e.known_at.isoformat(),
                }
                for e in self.events
            ],
            "scenarios": [
                {"kind": s.kind.value, "direction": s.direction, "trigger": s.trigger, "target": s.target}
                for s in self.scenarios
            ],
            "text": self.scenario_text(),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ChartRead:
        leg = d["leg"]
        return cls(
            timeframe=str(d["timeframe"]),
            at=datetime.fromisoformat(d["at"]),
            close=float(d["close"]),
            atr=float(d["atr"]),
            digits=int(d["digits"]),
            structure=Structure(d["structure"]),
            invalidation=d["invalidation"],
            broken=bool(d["broken"]),
            age_legs=int(d["age_legs"]),
            retrace_major=d.get("retrace_major"),
            tol_atr=float(d.get("tol_atr", 0.25)),
            provisional=None if d.get("provisional") is None else _pivot_from(d["provisional"]),
            structure_now=None if d.get("structure_now") is None else Structure(d["structure_now"]),
            invalidation_now=d.get("invalidation_now"),
            pivots=tuple(
                Pivot(
                    SwingKind(p["kind"]),
                    float(p["price"]),
                    datetime.fromisoformat(p["at"]),
                    datetime.fromisoformat(p["known_at"]),
                    None if p["label"] is None else StructureLabel(p["label"]),
                )
                for p in d["pivots"]
            ),
            leg=None
            if leg is None
            else Leg(
                int(leg["direction"]),
                float(leg["start"]),
                float(leg["extreme"]),
                int(leg["bars"]),
                float(leg["leg_atr"]),
                float(leg["from_pivot_atr"]),
                leg["retrace"],
            ),
            levels=tuple(
                Level(
                    float(lv["price"]),
                    LevelRole(lv["role"]),
                    bool(lv["above"]),
                    int(lv["touches"]),
                    datetime.fromisoformat(lv["first_at"]),
                    datetime.fromisoformat(lv["last_at"]),
                    int(lv["retests"]),
                    float(lv["dist_atr"]),
                    bool(lv.get("minor", False)),
                )
                for lv in d["levels"]
            ),
            trendlines=tuple(
                TrendLine(
                    SwingKind(tl["kind"]),
                    datetime.fromisoformat(tl["a_at"]),
                    float(tl["a_price"]),
                    datetime.fromisoformat(tl["b_at"]),
                    float(tl["b_price"]),
                    float(tl["value"]),
                    float(tl["slope_atr"]),
                    float(tl["dist_atr"]),
                    int(tl["touches"]),
                    bool(tl["broken"]),
                    None if tl["broken_at"] is None else datetime.fromisoformat(tl["broken_at"]),
                )
                for tl in d["trendlines"]
            ),
            events=tuple(
                ReadEvent(
                    EventKind(e["kind"]),
                    int(e["direction"]),
                    float(e["price"]),
                    bool(e["trendline"]),
                    datetime.fromisoformat(e["at"]),
                    datetime.fromisoformat(e["known_at"]),
                )
                for e in d["events"]
            ),
            scenarios=tuple(
                Scenario(ScenarioKind(s["kind"]), int(s["direction"]), float(s["trigger"]), s["target"])
                for s in d["scenarios"]
            ),
        )


def _pivot_dict(p: Pivot) -> dict[str, Any]:
    return {
        "kind": p.kind.value,
        "price": p.price,
        "at": p.at.isoformat(),
        "known_at": p.known_at.isoformat(),
        "label": None if p.label is None else p.label.value,
    }


def _pivot_from(d: Mapping[str, Any]) -> Pivot:
    return Pivot(
        SwingKind(d["kind"]),
        float(d["price"]),
        datetime.fromisoformat(d["at"]),
        datetime.fromisoformat(d["known_at"]),
        None if d["label"] is None else StructureLabel(d["label"]),
    )


# --- the MT5 ZigZag ---------------------------------------------------------------------------------------


def zigzag_pivots(
    high: FloatArray,
    low: FloatArray,
    point: float,
    *,
    depth: int = 12,
    deviation: int = 5,
    backstep: int = 3,
    index: Sequence[Any] | None = None,
) -> list[Swing]:
    """The fixed pivots of MT5's ZigZag(depth, deviation, backstep); ``confirm_pos`` = the first bar that
    knows the pivot (the opposite candidate's bar + ``backstep``). Pivots alternate HIGH/LOW."""
    if not (math.isfinite(point) and point > 0):
        raise ConfigError(f"point must be > 0 (got {point!r})")
    if len(high) != len(low):
        raise DataQualityError("zigzag: high and low differ in length")
    n = len(high)
    hmap, lmap = _zigzag_maps(high, low, point, depth, deviation, backstep)
    idx: Sequence[Any] = index if index is not None else range(n)
    out: list[Swing] = []
    pending: tuple[SwingKind, int, float] | None = None  # MT5's last drawn point, still movable
    for s in range(depth, n):
        h, lo = float(hmap[s]), float(lmap[s])
        if pending is None:
            if h != 0:
                pending = (SwingKind.HIGH, s, float(h))
            if lo != 0:  # MT5 checks the low second, so a bar that is both starts with the low
                pending = (SwingKind.LOW, s, float(lo))
            continue
        kind, pos, price = pending
        if kind is SwingKind.LOW:  # searching for a peak
            if lo != 0 and lo < price and h == 0:
                pending = (SwingKind.LOW, s, float(lo))
            elif h != 0 and lo == 0:
                if s + backstep < n:
                    out.append(Swing(kind, price, pos, s + backstep, idx[pos], idx[s + backstep]))
                pending = (SwingKind.HIGH, s, float(h))
        else:  # searching for a bottom
            if h != 0 and h > price and lo == 0:
                pending = (SwingKind.HIGH, s, float(h))
            elif lo != 0 and h == 0:
                if s + backstep < n:
                    out.append(Swing(kind, price, pos, s + backstep, idx[pos], idx[s + backstep]))
                pending = (SwingKind.LOW, s, float(lo))
    return out


def _zigzag_maps(
    high: FloatArray, low: FloatArray, point: float, depth: int, deviation: int, backstep: int
) -> tuple[FloatArray, FloatArray]:
    n = len(high)
    hmap, lmap = np.zeros(n), np.zeros(n)
    last_low = last_high = 0.0
    dev = deviation * point
    for s in range(depth, n):
        val = float(low[s - depth + 1 : s + 1].min())
        if val == last_low:
            val = 0.0
        else:
            last_low = val
            if low[s] - val > dev:
                val = 0.0
            else:
                for b in range(1, backstep + 1):
                    if lmap[s - b] != 0 and lmap[s - b] > val:
                        lmap[s - b] = 0.0
        lmap[s] = val if low[s] == val else 0.0
        val = float(high[s - depth + 1 : s + 1].max())
        if val == last_high:
            val = 0.0
        else:
            last_high = val
            if val - high[s] > dev:
                val = 0.0
            else:
                for b in range(1, backstep + 1):
                    if hmap[s - b] != 0 and hmap[s - b] < val:
                        hmap[s - b] = 0.0
        hmap[s] = val if high[s] == val else 0.0
    return hmap, lmap


# --- the frame and the read -------------------------------------------------------------------------------


def _structure(high_label: StructureLabel | None, low_label: StructureLabel | None) -> Structure:
    if high_label is None or low_label is None:
        return Structure.NONE
    if high_label is StructureLabel.EQH or low_label is StructureLabel.EQL:
        return Structure.FLAT
    up_high = high_label is StructureLabel.HH
    up_low = low_label is StructureLabel.HL
    if up_high and up_low:
        return Structure.UP
    if not up_high and not up_low:
        return Structure.DOWN
    return Structure.CONTRACTING if up_low else Structure.BROADENING


def retrace_into(p0: float, p1: float, price: float) -> float | None:
    """*price* inside the leg P0 → P1: 0 at P1, 1 back at P0 (beyond either end: < 0 or > 1)."""
    span = p1 - p0
    if span == 0:
        return None
    return round((p1 - price) / span, 4)


def with_major(read: ChartRead, higher: ChartRead | None) -> ChartRead:
    """*read* with ``retrace_major``: its close inside the last leg of *higher* (H1 → H4, H4 → D1)."""
    if higher is None or len(higher.pivots) < 2:
        return read
    p0, p1 = higher.pivots[-2].price, higher.pivots[-1].price
    return replace(read, retrace_major=retrace_into(p0, p1, read.close))


class ChartReadFrame:
    """Swings, labels and ATR of one candle frame, computed once; :meth:`at` reads one bar."""

    def __init__(
        self, timeframe: str, candles: pd.DataFrame, point: float, params: ChartReadParams | None = None
    ) -> None:
        self.timeframe = timeframe
        self.p = params or ChartReadParams()
        self.point = float(point)
        self.digits = max(0, round(-math.log10(self.point))) if self.point > 0 else 0
        self.index = candles.index
        self.o = as_float(candles["open"])
        self.h = as_float(candles["high"])
        self.lo = as_float(candles["low"])
        self.c = as_float(candles["close"])
        self.atr = as_float(atr(candles["high"], candles["low"], candles["close"], self.p.atr_period))
        self.tol = self.p.tol_atr * self.atr  # NaN during the ATR's warm-up
        self._tol0 = np.nan_to_num(self.tol, nan=0.0)
        self.times = [_ts(x) for x in self.index]
        self.pivots = zigzag_pivots(
            self.h,
            self.lo,
            self.point,
            depth=self.p.depth,
            deviation=self.p.deviation,
            backstep=self.p.backstep,
            index=self.times,
        )
        self._confirm = [s.confirm_pos for s in self.pivots]
        self.minor = (
            zigzag_pivots(
                self.h,
                self.lo,
                self.point,
                depth=self.p.minor_depth,
                deviation=self.p.deviation,
                backstep=min(self.p.backstep, self.p.minor_depth - 1),
                index=self.times,
            )
            if self.p.minor_depth
            else []
        )
        self._minor_confirm = [s.confirm_pos for s in self.minor]
        self.labels = self._label()
        self._trend, self._changed = self._trends()

    def _label(self) -> list[StructureLabel | None]:
        last: dict[SwingKind, float] = {}
        out: list[StructureLabel | None] = []
        for s in self.pivots:
            prev = last.get(s.kind)
            label: StructureLabel | None = None
            if prev is not None:
                a = self.atr[s.confirm_pos]
                tol = self.p.equal_atr * float(a) if math.isfinite(a) else 0.0
                diff = s.price - prev
                if s.kind is SwingKind.HIGH:
                    label = (
                        StructureLabel.EQH
                        if abs(diff) <= tol
                        else (StructureLabel.HH if diff > 0 else StructureLabel.LH)
                    )
                else:
                    label = (
                        StructureLabel.EQL
                        if abs(diff) <= tol
                        else (StructureLabel.HL if diff > 0 else StructureLabel.LL)
                    )
            out.append(label)
            last[s.kind] = s.price
        return out

    def _trends(self) -> tuple[list[Structure], list[int]]:
        """The structure after each pivot, and the pivot at which that value began."""
        cur: dict[SwingKind, StructureLabel | None] = {SwingKind.HIGH: None, SwingKind.LOW: None}
        trend: list[Structure] = []
        changed: list[int] = []
        for i, (s, label) in enumerate(zip(self.pivots, self.labels, strict=True)):
            if label is not None:
                cur[s.kind] = label
            t = _structure(cur[SwingKind.HIGH], cur[SwingKind.LOW])
            changed.append(i if not trend or trend[-1] is not t else changed[-1])
            trend.append(t)
        return trend, changed

    def pos_at(self, t: Any) -> int:
        """The position of the last bar closed at or before *t* (-1 if none)."""
        return int(self.index.searchsorted(pd.Timestamp(t), side="right")) - 1

    def at(self, pos: int) -> ChartRead | None:
        """The read at bar *pos*; None before the ATR's warm-up."""
        if not 0 <= pos < len(self.c):
            return None
        a = float(self.atr[pos])
        if not (math.isfinite(a) and a > 0):
            return None
        k = bisect.bisect_right(self._confirm, pos)
        known = self.pivots[:k]
        close = float(self.c[pos])
        structure = self._trend[k - 1] if k else Structure.NONE
        invalidation = self._invalidation(known, structure)
        broken = False
        if invalidation is not None and known:
            seg = self.c[known[-1].pivot_pos + 1 : pos + 1]
            broken = bool(
                (seg > invalidation).any() if structure is Structure.DOWN else (seg < invalidation).any()
            )
        major = {(s.kind, s.pivot_pos) for s in known}  # known at pos only: no look-ahead
        minor = [
            s
            for s in self.minor[: bisect.bisect_right(self._minor_confirm, pos)]
            if (s.kind, s.pivot_pos) not in major  # a major pivot is not counted twice
        ]
        levels = self._levels(known, pos, a, minor)
        lines = self._trendlines(known, structure, pos, a)
        leg = self._leg(known, pos, a)
        provisional, structure_now, invalidation_now = self._now(known, k, leg, pos, a)
        read = ChartRead(
            timeframe=self.timeframe,
            at=self.times[pos],
            close=close,
            atr=a,
            digits=self.digits,
            structure=structure,
            invalidation=invalidation,
            broken=broken,
            age_legs=(k - 1 - self._changed[k - 1]) if k else 0,
            pivots=tuple(
                Pivot(s.kind, s.price, self.times[s.pivot_pos], self.times[s.confirm_pos], self.labels[i])
                for i, s in enumerate(known[-self.p.max_swings :], start=max(0, k - self.p.max_swings))
            ),
            leg=leg,
            levels=tuple(lv for lv, _ in levels),
            trendlines=tuple(tl for tl, _ in lines),
            events=self._events(levels, lines, pos),
            tol_atr=self.p.tol_atr,
            provisional=provisional,
            structure_now=structure_now,
            invalidation_now=invalidation_now,
        )
        return replace(read, scenarios=scenarios(read))

    def _now(
        self, known: Sequence[Swing], k: int, leg: Leg | None, pos: int, a: float
    ) -> tuple[Pivot | None, Structure | None, float | None]:
        """The provisional pivot (the leg's extreme once price came back ``prov_atr`` ATR from it) and the
        structure and invalidation with it; without one, the confirmed read."""
        if not known:
            return None, None, None
        last_label: dict[SwingKind, StructureLabel | None] = {SwingKind.HIGH: None, SwingKind.LOW: None}
        last_price: dict[SwingKind, float] = {}
        for i in range(k - 1, -1, -1):
            s = self.pivots[i]
            if s.kind not in last_price:
                last_price[s.kind] = s.price
                last_label[s.kind] = self.labels[i]
            if len(last_price) == 2:
                break
        provisional = None
        if leg is not None and abs(leg.extreme - float(self.c[pos])) >= self.p.prov_atr * a:
            kind = SwingKind.LOW if leg.direction < 0 else SwingKind.HIGH
            start = known[-1].pivot_pos + 1
            seg = (self.lo if kind is SwingKind.LOW else self.h)[start : pos + 1]
            at = start + int(seg.argmin() if kind is SwingKind.LOW else seg.argmax())
            prev = last_price.get(kind)
            label = None
            if prev is not None:
                diff = leg.extreme - prev
                if abs(diff) <= self.p.equal_atr * a:
                    label = StructureLabel.EQL if kind is SwingKind.LOW else StructureLabel.EQH
                elif kind is SwingKind.LOW:
                    label = StructureLabel.HL if diff > 0 else StructureLabel.LL
                else:
                    label = StructureLabel.HH if diff > 0 else StructureLabel.LH
            provisional = Pivot(kind, leg.extreme, self.times[at], self.times[pos], label)
            last_label[kind], last_price[kind] = label, leg.extreme
        now = _structure(last_label[SwingKind.HIGH], last_label[SwingKind.LOW])
        want = {Structure.DOWN: SwingKind.HIGH, Structure.UP: SwingKind.LOW}.get(now)
        return provisional, now, None if want is None else last_price.get(want)

    @staticmethod
    def _invalidation(known: Sequence[Swing], structure: Structure) -> float | None:
        want = {Structure.DOWN: SwingKind.HIGH, Structure.UP: SwingKind.LOW}.get(structure)
        if want is None:
            return None
        return next((s.price for s in reversed(known) if s.kind is want), None)

    def _leg(self, known: Sequence[Swing], pos: int, a: float) -> Leg | None:
        if not known:
            return None
        last = known[-1]
        direction = -1 if last.kind is SwingKind.HIGH else 1
        if pos <= last.pivot_pos:  # cannot happen: a pivot is known only after its bar
            return None
        window = self.lo if direction < 0 else self.h
        seg = window[last.pivot_pos + 1 : pos + 1]
        extreme = float(seg.min() if direction < 0 else seg.max())
        close = float(self.c[pos])
        return Leg(
            direction=direction,
            start=last.price,
            extreme=extreme,
            bars=pos - last.pivot_pos,
            leg_atr=round(abs(extreme - last.price) / a, 4),
            from_pivot_atr=round((close - last.price) * direction / a, 4),
            retrace=retrace_into(known[-2].price, last.price, close) if len(known) >= 2 else None,
        )

    # --- levels --------------------------------------------------------------------------------------

    def _levels(
        self, known: Sequence[Swing], pos: int, a: float, minor: Sequence[Swing] = ()
    ) -> list[tuple[Level, int]]:
        """Non-spent levels at *pos* (highest first) with the position of their first pivot; the minor
        swings add levels of their own (``Level.minor`` when no major swing is in the cluster)."""
        start = pos - self.p.level_lookback + 1
        recent = sorted(
            [(s, False) for s in known if s.pivot_pos >= start]
            + [(s, True) for s in minor if s.pivot_pos >= start],
            key=lambda x: x[0].price,
        )
        tol = self.p.level_tol_atr * a
        clusters: list[list[Swing]] = []
        minor_only: list[bool] = []
        for s, is_minor in recent:
            if clusters and s.price - clusters[-1][0].price <= tol:
                clusters[-1].append(s)
                minor_only[-1] = minor_only[-1] and is_minor
            else:
                clusters.append([s])
                minor_only.append(is_minor)
        above: list[tuple[Level, int]] = []
        below: list[tuple[Level, int]] = []
        close = float(self.c[pos])
        for members, only_minor in zip(clusters, minor_only, strict=True):
            level = self._level(members, pos, a, close)
            if level is None:
                continue
            if only_minor:
                level = (replace(level[0], minor=True), level[1])
            (above if level[0].above else below).append(level)
        above.sort(key=lambda x: x[0].dist_atr)
        below.sort(key=lambda x: x[0].dist_atr)
        out = above[: self.p.max_levels] + below[: self.p.max_levels]
        out.sort(key=lambda x: -x[0].price)
        return out

    def _level(self, members: list[Swing], pos: int, a: float, close: float) -> tuple[Level, int] | None:
        price = sum(m.price for m in members) / len(members)
        first = min(members, key=lambda m: m.pivot_pos)
        last = max(members, key=lambda m: m.pivot_pos)
        side = -1 if first.kind is SwingKind.HIGH else 1  # the closes' side: below a top, above a bottom
        crossings, flip_pos, side = self._crossings(price, first.pivot_pos + 1, pos, side)
        if crossings >= self.p.spent_crossings:
            return None  # SPENT: closed through back and forth too often to hold a role
        if crossings % 2 == 1:  # on the other side of where it formed: its role flipped
            role = LevelRole.FLIPPED
            retests = self._retests(price, side, flip_pos + 1, pos)
        else:
            role = LevelRole.SUPPORT if side > 0 else LevelRole.RESISTANCE
            retests = 0
        level = Level(
            price=price,
            role=role,
            above=side < 0,
            touches=len(members),
            first_at=self.times[first.pivot_pos],
            last_at=self.times[last.pivot_pos],
            retests=retests,
            dist_atr=round(abs(close - price) / a, 4),
        )
        return level, first.pivot_pos

    def _crossings(self, price: float, start: int, end: int, side: int) -> tuple[int, int, int]:
        """Closes through *price* from *start* to *end*: (count, the last one's bar, the side after it).

        A close through is a close beyond *price* by the tolerance whose next ``hold_bars`` closes stay beyond
        *price* (a break that holds); a close inside the band keeps the side, and a break that closes back
        (a false break) does not count, so it never spends the level it swept.
        """
        if start > end:
            return 0, -1, side
        c = self.c[start : end + 1]
        tol = self._tol0[start : end + 1]
        sides = np.where(c > price + tol, 1, np.where(c < price - tol, -1, 0))
        at = np.flatnonzero(sides)
        vals = sides[at]
        hold = self.p.hold_bars
        count, last, k = 0, -1, 0
        while k < len(vals):
            rest = np.flatnonzero(vals[k:] != side)
            if len(rest) == 0:
                break
            k += int(rest[0])
            x, s = start + int(at[k]), int(vals[k])
            if x + hold > end:
                break  # not held yet as of *end*
            if bool(((self.c[x + 1 : x + hold + 1] - price) * s > 0).all()):
                count, last, side = count + 1, x, s
            k += 1
        return count, last, side

    def _touch_away(self, price: float, side: int, j: int) -> bool:
        """Bar *j* probes *price* from *side* within the tolerance and closes on that side in its colour."""
        return self._retests(price, side, j, j) > 0

    def _retests(self, price: float, side: int, start: int, end: int) -> int:
        """Bars from *start* to *end* that :meth:`_touch_away` from *price*."""
        if start > end:
            return 0
        sl = slice(start, end + 1)
        probe = self.lo[sl] if side > 0 else self.h[sl]
        c = self.c[sl]
        with np.errstate(invalid="ignore"):
            ok = (
                ((probe - price) * side <= self.tol[sl])
                & ((c - price) * side > 0)
                & ((c - self.o[sl]) * side > 0)
            )
        return int(ok.sum())

    # --- trendlines ----------------------------------------------------------------------------------

    def _trendlines(
        self, known: Sequence[Swing], structure: Structure, pos: int, a: float
    ) -> list[tuple[TrendLine, tuple[Swing, Swing]]]:
        out: list[tuple[TrendLine, tuple[Swing, Swing]]] = []
        for kind, ok in (
            (SwingKind.HIGH, structure in (Structure.DOWN, Structure.CONTRACTING)),
            (SwingKind.LOW, structure in (Structure.UP, Structure.CONTRACTING)),
        ):
            if not ok:
                continue
            same = [s for s in known if s.kind is kind]
            if len(same) < 2:
                continue
            p, q = same[-2], same[-1]
            falling_tops = kind is SwingKind.HIGH and q.price < p.price
            rising_bottoms = kind is SwingKind.LOW and q.price > p.price
            if not (falling_tops or rising_bottoms):
                continue
            out.append((self._line(kind, p, q, pos, a), (p, q)))
        return out

    @staticmethod
    def _line_at(p: Swing, q: Swing, j: int | FloatArray) -> Any:
        slope = (q.price - p.price) / (q.pivot_pos - p.pivot_pos)
        return p.price + slope * (j - p.pivot_pos)

    def _line(self, kind: SwingKind, p: Swing, q: Swing, pos: int, a: float) -> TrendLine:
        side = -1 if kind is SwingKind.HIGH else 1  # the closes' side of the line
        touches, broken_pos = 2, None
        for j in range(q.pivot_pos + 1, pos + 1):
            tol = self._tol(j)
            if tol is None:
                continue
            value = float(self._line_at(p, q, j))
            if (self.c[j] - value) * side < -tol:
                broken_pos = j
                break
            probe = self.h[j] if side < 0 else self.lo[j]
            if abs(probe - value) <= tol and (self.c[j] - value) * side > 0:
                touches += 1
        value = float(self._line_at(p, q, pos))
        slope = (q.price - p.price) / (q.pivot_pos - p.pivot_pos)
        return TrendLine(
            kind=kind,
            a_at=self.times[p.pivot_pos],
            a_price=p.price,
            b_at=self.times[q.pivot_pos],
            b_price=q.price,
            value=value,
            slope_atr=round(slope / a, 5),
            dist_atr=round((float(self.c[pos]) - value) / a, 4),
            touches=touches,
            broken=broken_pos is not None,
            broken_at=None if broken_pos is None else self.times[broken_pos],
        )

    # --- events --------------------------------------------------------------------------------------

    def _events(
        self,
        levels: Sequence[tuple[Level, int]],
        lines: Sequence[tuple[TrendLine, tuple[Swing, Swing]]],
        pos: int,
    ) -> tuple[ReadEvent, ...]:
        p = self.p
        first_known = pos - p.event_bars + 1
        lookback = max(p.hold_bars, p.reclaim_bars) + p.event_bars
        found: dict[tuple[EventKind, int, float, bool], ReadEvent] = {}

        def add(kind: EventKind, direction: int, price: float, trendline: bool, j: int, known: int) -> None:
            if known < first_known or known > pos:
                return
            key = (kind, direction, round(price, 10), trendline)
            ev = ReadEvent(kind, direction, price, trendline, self.times[j], self.times[known])
            prev = found.get(key)
            if prev is None or prev.known_at < ev.known_at:
                found[key] = ev

        start = max(1, pos - lookback)
        for level, first_pos in levels:
            lv = level.price
            for j in range(max(start, first_pos + 1), pos + 1):
                tol = self._tol(j)
                if tol is None:
                    continue
                for d in (1, -1):
                    hold = self._break_hold(j, d, lambda _i, v=lv: v, tol)
                    if hold is not None:
                        add(EventKind.BREAK_HOLD, d, lv, False, j, hold)
                    reclaim = self._sweep_reclaim(j, d, lv, tol)
                    if reclaim is not None:
                        add(EventKind.SWEEP_RECLAIM, -d, lv, False, j, reclaim)
                if level.role is LevelRole.FLIPPED:
                    side = -1 if level.above else 1
                    if self._touch_away(lv, side, j):
                        add(EventKind.RETEST, side, lv, False, j, j)
        for line, (sp, sq) in lines:
            for j in range(max(start, sq.pivot_pos + 1), pos + 1):
                tol = self._tol(j)
                if tol is None:
                    continue
                d = 1 if line.kind is SwingKind.HIGH else -1  # a resistance line breaks up, a support down
                hold = self._break_hold(j, d, lambda i, a=sp, b=sq: float(self._line_at(a, b, i)), tol)
                if hold is not None:
                    add(EventKind.BREAK_HOLD, d, float(self._line_at(sp, sq, j)), True, j, hold)
        return tuple(sorted(found.values(), key=lambda e: (e.known_at, e.kind.value, e.price)))

    def _tol(self, j: int) -> float | None:
        t = float(self.tol[j])
        return t if math.isfinite(t) else None

    def _break_hold(self, j: int, d: int, value: Any, tol: float) -> int | None:
        """A close beyond the level by *tol* in direction *d* at bar *j* (the previous close was not), and the
        next ``hold_bars`` closes stay beyond the level: the bar that completed it, else None."""
        lv, prev_lv = value(j), value(j - 1)
        prev_tol = self._tol(j - 1) or 0.0
        if not ((self.c[j] - lv) * d > tol and (self.c[j - 1] - prev_lv) * d <= prev_tol):
            return None
        done = j + self.p.hold_bars
        if done >= len(self.c):
            return None
        for i in range(j + 1, done + 1):
            if (self.c[i] - value(i)) * d <= 0:
                return None
        return done

    def _sweep_reclaim(self, j: int, d: int, lv: float, tol: float) -> int | None:
        """Bar *j* trades beyond the level by *tol* in direction *d* from a close on the other side, and a
        close is back on that side within ``reclaim_bars``: the reclaiming bar, else None."""
        probe = self.h[j] if d > 0 else self.lo[j]
        if not ((probe - lv) * d >= tol and (self.c[j - 1] - lv) * d < 0):
            return None
        for i in range(j, min(j + self.p.reclaim_bars, len(self.c) - 1) + 1):
            if (self.c[i] - lv) * d < 0:
                return i
        return None


def _ts(value: object) -> datetime:
    return pd.Timestamp(value).to_pydatetime()  # type: ignore[arg-type]


# --- scenarios --------------------------------------------------------------------------------------------


def scenarios(read: ChartRead) -> tuple[Scenario, ...]:
    """The two main paths at the level being tested (the nearer of the nearest support and resistance)."""
    up, down = read.nearest(above=True), read.nearest(above=False)
    if up is None and down is None:
        return ()
    tested_above = down is None or (up is not None and up.dist_atr < down.dist_atr)
    tested = up if tested_above else down
    if tested is None:  # unreachable: one of the two exists
        return ()
    d = 1 if tested_above else -1
    beyond = [lv.price for lv in read.levels if (lv.price - tested.price) * d > 0]
    target = min(beyond, key=lambda x: abs(x - tested.price), default=None)
    other = down if tested_above else up
    return (
        Scenario(ScenarioKind.BREAK, d, tested.price, target),
        Scenario(ScenarioKind.REJECT, -d, tested.price, None if other is None else other.price),
    )


def scenario_text(read: ChartRead) -> str:
    def f(x: float | None) -> str:
        return "-" if x is None else f"{x:,.{read.digits}f}"

    parts: list[str] = []
    for s in read.scenarios:
        way = "above" if s.direction > 0 else "below"
        nxt = "resistance" if s.direction > 0 else "support"
        if s.kind is ScenarioKind.BREAK:
            parts.append(f"break {way} {f(s.trigger)} that holds -> next {nxt} {f(s.target)}")
        else:
            parts.append(
                f"rejected at {f(s.trigger)} (or a false break that reclaims it) -> {nxt} {f(s.target)}"
            )
    if read.invalidation is not None:
        end = "above" if read.structure is Structure.DOWN else "below"
        parts.append(f"the {read.structure.value.lower()} trend ends {end} {f(read.invalidation)}")
    return "; ".join(parts)
