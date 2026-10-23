"""Trigger T2: a rejection at a zone line (research/2026-10-23-entry/SPEC.md T2) - the owner's turn picture
(a level, price action, often a sweep): price arrives at a line and a bar throws it back with a long wick.

Any timeframe; the arrivals are T4's (:func:`app.strategy.zone_break.arrivals`). From an arrival, within
``REJECT_BARS`` bars (the arrival bar included): the first bar whose wick on the arrival side is at least
``WICK`` x its range and that closes back on the side price came from -> enter that way (the bounce) at its
close; the stop ``PAD`` x step beyond the most extreme price since the arrival. A close through the line by
more than the band first ends the search. ``swept`` = the wick went beyond the line itself.

Measured before use as a raw entry (research/2026-10-23-entry/zone_reject_raw.py): bounces at a line lost in
every form tried so far (at once -0.028 R, after a consolidation -0.089) - T2 is a candidate whose weight the
assessment must earn from the other components.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.strategy.zone_break import BAND, PAD, arrivals

FloatArray = np.ndarray
REJECT_BARS = 3
WICK = 0.5


@dataclass(frozen=True)
class Rejection:
    arrival: int
    line: float
    side: int  # the trade: +1 buy (price came from above and was thrown back up), -1 sell
    entry_bar: int
    entry: float
    stop: float
    swept: bool


def zone_rejections(
    o: FloatArray, h: FloatArray, lo: FloatArray, c: FloatArray, anchor: FloatArray, step: FloatArray
) -> list[Rejection]:
    """Every T2 event whose rejection bar exists in the given closed bars."""
    n = len(c)
    out: list[Rejection] = []
    for i, line, came, s in arrivals(h, lo, c, anchor, step):
        band = BAND * s
        for q in range(i, min(i + REJECT_BARS, n)):
            if (c[q] - line) * (-came) > band:  # through the line: no rejection
                break
            rng = h[q] - lo[q]
            wick = (min(o[q], c[q]) - lo[q]) if came > 0 else (h[q] - max(o[q], c[q]))
            if rng > 0 and wick >= WICK * rng and (c[q] - line) * came > 0:
                ext = float(lo[i : q + 1].min()) if came > 0 else float(h[i : q + 1].max())
                stop = ext - PAD * s if came > 0 else ext + PAD * s
                swept = ext < line if came > 0 else ext > line
                out.append(Rejection(i, line, came, q, float(c[q]), stop, swept))
                break
    return out
