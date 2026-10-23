"""Trigger T4: price consolidates at a zone line, then the box breaks
(research/2026-10-23-entry/SPEC.md T4).

Owner 2026-10-23: "when price reaches a zone, wait for it to consolidate and then look for the
trade - better than trading the moment it arrives". Measured on M15 2023-09 .. 2026-10
(research/2026-10-23-entry/zone_wait.py): the break of the box THROUGH the line +0.087 R a trade,
positive in all four years; the same box breaking back the way price came (the bounce) -0.089,
negative in all four; entering the bounce at the arrival -0.028.

Any timeframe; ``anchor`` / ``step`` are the zone grid in force at each bar
(``zone_grid.grid_at``), lines every half step. Ported 1:1 from zone_wait.py:

- **Arrival:** the first bar touching a line's band (``BAND`` x step) after price was at least
  ``AWAY`` x step from the line within the last ``LOOK`` bars, not in the band in the ``QUIET``
  bars before, and not the same line's arrival within ``LOOK`` bars.
- **Box:** within ``WAIT`` bars of the arrival, ``BOX_N`` consecutive bars inside a box at most
  ``BOX_H`` x step tall that overlaps the band; then the first close out of the (growing) box is
  the entry, that way; the stop ``PAD`` x step beyond the box. A close through the line by more
  than the band before any box ends the search.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray
BAND, AWAY, LOOK, WAIT, BOX_N, BOX_H, PAD = 0.15, 0.5, 32, 48, 8, 0.3, 0.05
QUIET = 8  # bars before the arrival that must be outside the band


@dataclass(frozen=True)
class ZoneBreak:
    arrival: int  # bar of the arrival
    line: float
    came: int  # +1 price came from above (into support), -1 from below
    entry_bar: int  # the bar whose close breaks the box
    side: int  # +1 buy, -1 sell
    through: bool  # the break goes through the line (not back the way price came)
    entry: float  # that bar's close
    stop: float
    box_lo: float
    box_hi: float
    bars_at_line: int  # bars from the arrival to the entry


def zone_breaks(
    h: FloatArray, lo: FloatArray, c: FloatArray, anchor: FloatArray, step: FloatArray, start: int = LOOK
) -> list[ZoneBreak]:
    """Every T4 event whose entry bar exists in the given closed bars (bars ``start`` .. on as arrivals)."""
    n = len(c)
    out: list[ZoneBreak] = []
    last_arrival: dict[float, int] = {}
    for i in range(max(start, LOOK), n):
        a, s = float(anchor[i]), float(step[i])
        if not (math.isfinite(a) and math.isfinite(s) and s > 0):
            continue
        half = s / 2
        band = BAND * s
        first = math.floor((lo[i] - band - a) / half)
        for kk in range(first, math.ceil((h[i] + band - a) / half) + 1):
            line = a + kk * half
            if not (lo[i] <= line + band and h[i] >= line - band):
                continue
            prev_h, prev_l = h[i - LOOK : i], lo[i - LOOK : i]
            far = max(prev_h.max() - line, line - prev_l.min()) >= AWAY * s
            near_before = bool(((prev_l <= line + band) & (prev_h >= line - band))[-QUIET:].any())
            key = round(line, 2)
            if not far or near_before or (key in last_arrival and i - last_arrival[key] < LOOK):
                continue
            last_arrival[key] = i
            came = 1 if c[i - 1] > line else -1
            event = _box(h, lo, c, i, line, came, s)
            if event is not None:
                out.append(event)
    return out


def _box(
    h: FloatArray, lo: FloatArray, c: FloatArray, i: int, line: float, came: int, s: float
) -> ZoneBreak | None:
    n, band = len(c), BAND * s
    for j in range(i + 1, min(i + WAIT, n)):
        if (c[j] - line) * (-came) > band:  # broke straight through: no consolidation
            return None
        if j - i + 1 < BOX_N:
            continue
        box_h, box_l = float(h[j - BOX_N + 1 : j + 1].max()), float(lo[j - BOX_N + 1 : j + 1].min())
        if box_h - box_l > BOX_H * s or not (box_l <= line + band and box_h >= line - band):
            continue
        for q in range(j + 1, min(j + WAIT, n)):
            if c[q] > box_h or c[q] < box_l:
                side = 1 if c[q] > box_h else -1
                stop = box_l - PAD * s if side > 0 else box_h + PAD * s
                return ZoneBreak(i, line, came, q, side, side != came, float(c[q]), stop, box_l, box_h, q - i)
            box_h, box_l = max(box_h, float(h[q])), min(box_l, float(lo[q]))
        return None
    return None
