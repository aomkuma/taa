"""Trigger T1: the re-test of a broken zone line (research/2026-10-23-entry/SPEC.md T1; the owner's chart of
2026-10-19 .. 22: 4,141 broke, three weaker re-tests from below, the sell at the re-test, the stop above the
swept wick, the target the next line).

Any timeframe; ``anchor`` / ``step`` are the zone grid in force at each bar, lines every half step.

- **Break:** a bar closes beyond a line by more than ``BAND`` x step, after a close on the other side of the
  line within the last ``LOOK`` bars; one break per line until it ends (a line = its place in the grid, the
  anchor and k half steps, since its price moves with the daily step).
- **Re-test:** a later bar reaches the line's band from the break side (a sell: its high >= line - band) and
  closes back on the break side of the line, the bar before it being outside the band - a fresh touch. Every
  re-test is an event: the entry at its close, the stop ``PAD`` x step beyond the most extreme price against
  the break since the break (the swept wicks included).
- **End:** a close back beyond the line by more than the band on the original side (the break failed - that
  bar is then the break the other way), or ``WAIT`` bars after the break.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray
BAND, LOOK, WAIT, PAD = 0.15, 32, 96, 0.05


@dataclass(frozen=True)
class Retest:
    break_bar: int
    line: float
    side: int  # the trade: +1 buy (the line broke upward), -1 sell
    entry_bar: int
    entry: float
    stop: float
    extreme: float  # the most extreme price against the break since it


def zone_retests(
    h: FloatArray, lo: FloatArray, c: FloatArray, anchor: FloatArray, step: FloatArray
) -> list[Retest]:
    """Every T1 event whose re-test bar exists in the given closed bars."""
    n = len(c)
    out: list[Retest] = []
    # a line is its place in the grid (the anchor, k half steps) - its price breathes with the step every day
    active: dict[tuple[float, int], int] = {}  # line -> the bar its current break ends after
    for j in range(1, n):
        a, s = float(anchor[j]), float(step[j])
        if not (math.isfinite(a) and math.isfinite(s) and s > 0):
            continue
        half, band = s / 2, BAND * s
        k0 = math.floor((min(c[j - 1], c[j]) - band - a) / half)
        for kk in range(k0, math.ceil((max(c[j - 1], c[j]) + band - a) / half) + 1):
            line = a + kk * half
            d = 1 if c[j] - line > band else -1 if line - c[j] > band else 0
            key = (round(a, 2), kk)
            if d == 0 or active.get(key, -1) > j:  # a failed break's bar is itself the break back
                continue
            before = c[max(0, j - LOOK) : j]
            if not ((before - line) * d < 0).any():
                continue
            end = _follow(h, lo, c, j, line, d, band, s, out)
            active[key] = end
    return out


def _follow(
    h: FloatArray,
    lo: FloatArray,
    c: FloatArray,
    j: int,
    line: float,
    d: int,
    band: float,
    s: float,
    out: list[Retest],
) -> int:
    """Collect the re-tests of the break at bar ``j`` (direction ``d``); the bar the break ends at."""
    n = len(c)
    extreme = float(c[j])
    for q in range(j + 1, min(j + 1 + WAIT, n)):
        extreme = max(extreme, float(h[q])) if d < 0 else min(extreme, float(lo[q]))
        if (c[q] - line) * d < -band:  # back through: the break failed
            return q
        touch = h[q] >= line - band if d < 0 else lo[q] <= line + band
        before = h[q - 1] >= line - band if d < 0 else lo[q - 1] <= line + band
        if touch and not before and (c[q] - line) * d > 0:
            stop = extreme + PAD * s if d < 0 else extreme - PAD * s
            out.append(Retest(j, line, d, q, float(c[q]), stop, extreme))
    return j + WAIT + 1  # its last bar (j + WAIT) still belongs to it; a new break from the bar after
