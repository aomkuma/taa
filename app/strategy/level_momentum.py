"""Momentum at a level (research/2026-10-23-entry/SPEC.md C4), on any frame.

Owner 2026-10-22/23: read how price arrived at a level and how it behaved at each touch - a level hit
again and again with smaller bounces is being worn down; price that sits at a line a long time tends to
go through it (research/2026-10-23-entry/zone_wait.py: consolidation at a line broke through +0.087 R,
bounced -0.089).

- **Visits:** runs of closed bars inside the level's band since ``since``; a new visit needs more than ``GAP``
  bars since the previous bar in the band (ported from
  research/2026-10-18-moments/agents/journal/ny_b2/week.py ``context``).
- **Bounce** of a visit: the farthest price went from the level on the bounce side over the visit's first bar
  and the ``REACT`` - 1 bars after it (USD).
- **Worn:** the last three bounces each smaller than the one before.
- **Approach:** how far price moved toward the level over the last ``APPROACH`` closed bars, in the frame's
  ATR(14) (positive = toward it).
- **Bars at the line:** the closed bars in the band counted back from the latest one without a break.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.strategy.plan1_b2 import Bars, mt5_atr
from app.strategy.strong_levels import closed

GAP = 3
REACT = 7
APPROACH = 10


@dataclass(frozen=True)
class LevelMomentum:
    touches: int
    bounces: tuple[float, ...]  # USD, oldest first
    worn: bool
    approach: float  # in ATR(14) of the frame, positive = toward the level
    bars_at_line: int


def level_momentum(b: Bars, t: int, level: float, band: float, side: int, since: int) -> LevelMomentum:
    """``side`` = the bounce's direction (+1 up from a support, -1 down from a resistance); only bars that
    opened at or after ``since`` and closed by ``t``."""
    x = closed(b, t)
    keep = x.t_open >= since
    h, lo = x.h[keep], x.lo[keep]
    inside = (lo <= level + band) & (h >= level - band)
    touches, bounces, last = 0, [], -(GAP + 10)
    for i in np.flatnonzero(inside):
        if i - last > GAP:
            touches += 1
            after = slice(i, i + REACT)
            bounces.append(float(h[after].max() - level) if side > 0 else float(level - lo[after].min()))
        last = int(i)
    worn = len(bounces) >= 3 and bounces[-1] < bounces[-2] < bounces[-3]
    run = 0
    for v in inside[::-1]:
        if not v:
            break
        run += 1
    return LevelMomentum(touches, tuple(bounces), worn, _approach(x, level), run)


def _approach(x: Bars, level: float) -> float:
    if len(x.c) <= APPROACH:
        return math.nan
    atr = mt5_atr(x.h, x.lo, x.c, 14)
    unit = float(atr[-1])
    if not (math.isfinite(unit) and unit > 0):
        return math.nan
    before, now = float(x.c[-1 - APPROACH]), float(x.c[-1])
    return (abs(before - level) - abs(now - level)) / unit
