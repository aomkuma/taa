"""Strong levels ahead and the liquidity pools around a stop (research/2026-10-23-entry/SPEC.md C1 and
C5b).

Owner 2026-10-23: "look at several hundred bars to see the farther overall picture - the next strong levels
price may reach"; "the stop must not sit in a liquidation zone".

- **Swings:** fractal highs / lows of order ``k`` (higher / lower than the ``k`` bars on each side, ties
  none), known only once the ``k`` bars after them have closed. A swing's turn = how far price went away from
  it over the ``TURN_BARS`` bars after it (only bars closed by the decision count).
- **Strong levels** (C5b): the swings of the last ``LOOKBACK_H4`` H4 and ``LOOKBACK_D1`` D1 bars, merged when
  within ``MERGE_STEP`` x the zone step of the cluster's mean; a level is strong with 2+ touches or a turn of
  at least ``MAJOR_STEP`` steps. The anchors of past zone shifts and the lookback's highest high / lowest low
  are strong too.
- **Pools** (C1): where the obvious stops sit - the recent swings of the entry timeframe and H1, the previous
  server day's high / low, the round numbers (every ``ROUND_USD``). A stop within ``POOL_BAND_STEP`` x step
  (at least ``POOL_BAND_MIN`` USD) beyond a pool sits in the liquidation zone.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.strategy.plan1_b2 import Bars

FloatArray = np.ndarray
FRACTAL_K = 2
TURN_BARS = 12
LOOKBACK_H4 = 500
LOOKBACK_D1 = 250
MERGE_STEP = 0.15
MAJOR_STEP = 1.0
POOL_BAND_STEP = 0.05
POOL_BAND_MIN = 1.0
ROUND_USD = 10.0


@dataclass(frozen=True)
class Swing:
    bar: int
    price: float
    kind: int  # +1 a high, -1 a low
    turn: float  # USD away from it over the bars after it, closed by the decision


@dataclass(frozen=True)
class Level:
    price: float
    touches: int
    turn: float  # the largest turn of its swings, USD
    kinds: int  # +1 only highs, -1 only lows, 0 both (a flipped level)
    source: str  # "swings", "shift", "extreme"


def closed(b: Bars, t: int) -> Bars:
    """The bars complete by ``t`` (int64 ns)."""
    keep = b.avail <= t
    return Bars(b.t_open[keep], b.avail[keep], b.o[keep], b.h[keep], b.lo[keep], b.c[keep])


def swings(b: Bars, t: int, k: int = FRACTAL_K, last: int | None = None) -> list[Swing]:
    """The fractal swings of the bars closed by ``t`` whose ``k`` right-hand bars are closed too; ``last``
    limits the search to the latest bars."""
    x = closed(b, t)
    n = len(x.c)
    start = max(k, n - last) if last else k
    out: list[Swing] = []
    for j in range(start, n - k):
        left_h, right_h = x.h[j - k : j], x.h[j + 1 : j + 1 + k]
        left_l, right_l = x.lo[j - k : j], x.lo[j + 1 : j + 1 + k]
        after = slice(j + 1, min(n, j + 1 + TURN_BARS))
        if x.h[j] > left_h.max() and x.h[j] > right_h.max():
            out.append(Swing(j, float(x.h[j]), 1, float(x.h[j] - x.lo[after].min())))
        if x.lo[j] < left_l.min() and x.lo[j] < right_l.min():
            out.append(Swing(j, float(x.lo[j]), -1, float(x.h[after].max() - x.lo[j])))
    return out


def merge(items: Sequence[Swing], tol: float) -> list[Level]:
    """Swings within ``tol`` of the running cluster mean (in price order) become one level."""
    levels: list[Level] = []
    group: list[Swing] = []

    def close_group() -> None:
        if group:
            kinds = {s.kind for s in group}
            levels.append(
                Level(
                    float(np.mean([s.price for s in group])),
                    len(group),
                    max(s.turn for s in group),
                    kinds.pop() if len(kinds) == 1 else 0,
                    "swings",
                )
            )

    for s in sorted(items, key=lambda s: s.price):
        if group and s.price - float(np.mean([g.price for g in group])) > tol:
            close_group()
            group = []
        group.append(s)
    close_group()
    return levels


def strong_levels(
    h4: Bars, d1: Bars, t: int, step: float, shift_anchors: Sequence[float] = ()
) -> list[Level]:
    """The strong levels known at ``t``, sorted by price (``step`` = the zone step in force)."""
    if not (math.isfinite(step) and step > 0):
        return []
    found = swings(h4, t, last=LOOKBACK_H4) + swings(d1, t, last=LOOKBACK_D1)
    out = [lv for lv in merge(found, MERGE_STEP * step) if lv.touches >= 2 or lv.turn >= MAJOR_STEP * step]
    out += [Level(float(a), 1, math.nan, 0, "shift") for a in shift_anchors if math.isfinite(a)]
    x = closed(h4, t)
    if len(x.c):
        span = slice(max(0, len(x.c) - LOOKBACK_H4), None)
        out += [
            Level(float(x.h[span].max()), 1, math.nan, 1, "extreme"),
            Level(float(x.lo[span].min()), 1, math.nan, -1, "extreme"),
        ]
    return sorted(out, key=lambda lv: lv.price)


def room(levels: Sequence[Level], side: int, entry: float, stop: float, band: float) -> float:
    """C5b: the room in R from ``entry`` to the near edge of the first strong level beyond it on the target
    side (``side`` +1 a buy); ``inf`` when none."""
    risk = abs(entry - stop)
    if risk <= 0:
        return math.nan
    ahead = (
        [lv.price - band for lv in levels if lv.price - band > entry]
        if side > 0
        else [lv.price + band for lv in levels if lv.price + band < entry]
    )
    if not ahead:
        return math.inf
    edge = min(ahead) if side > 0 else max(ahead)
    return abs(edge - entry) / risk


def pool_band(step: float) -> float:
    return max(POOL_BAND_STEP * step, POOL_BAND_MIN) if math.isfinite(step) else POOL_BAND_MIN


def stop_check(
    pools: Sequence[float], side: int, entry: float, stop: float, band: float
) -> tuple[bool, float]:
    """C1: (the stop sits in a liquidation zone, the stop's distance beyond the last pool between the entry
    and the stop - the one nearest the stop - in USD; NaN when no pool lies there). The round numbers between
    the entry and the stop count as pools. A stop within ``band`` beyond a pool, or within ``band`` short of
    one, is in the zone."""
    # from the entry to a band past the stop, on the stop's side
    lo, hi = (stop - band, entry) if side > 0 else (entry, stop + band)
    found = [p for p in pools if lo <= p <= hi and p != entry]
    r = math.ceil(lo / ROUND_USD) * ROUND_USD
    while r <= hi:
        if r != entry:
            found.append(r)
        r += ROUND_USD
    in_zone = any(abs(stop - p) <= band for p in found)
    inside = [p for p in found if (p - stop) * side > 0]  # pools between the entry and the stop
    margin = min((p - stop) * side for p in inside) if inside else math.nan
    return in_zone, margin
