"""MetaTrader 5's ZigZag (MQL5/Indicators/Examples/ZigZag.mq5), the indicator on the owner's chart (owner
2026-10-26: "can ZigZag help - like this"). Any frame.

The two passes of the original:

1. Per bar, from bar ``depth`` on: the lowest low of the last ``depth`` bars, when it is new (not the previous
   window's) and this bar's low is within ``deviation`` of it, clears the higher low candidates of the
   ``backstep`` bars before; this bar is a low candidate when its own low is that lowest low. The mirror for
   highs.
2. The candidates in time order, alternating: after a low, a lower low moves it and the next high candidate
   starts the peak; after a high, a higher high moves it and the next low candidate starts the bottom.

``deviation`` is in price (the indicator's 5 points = 0.05 on gold). The last point is still forming: it moves
with new bars (it repaints) and is returned apart from the confirmed ones.

Checked against the owner's M15 chart of 22-26 Oct 2026 (FBS): the lows 3,986.62 / 3,975.58 / 3,978.12 and the
highs 4,034.23 / 4,004.20 / the forming 4,019.36 fall on the chart's turning points.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEPTH, DEVIATION, BACKSTEP = 12, 0.05, 3  # the indicator's defaults on gold (5 points)


@dataclass(frozen=True)
class Swing:
    bar: int
    price: float
    kind: int  # +1 a high, -1 a low


def zigzag(
    high: np.ndarray,
    low: np.ndarray,
    depth: int = DEPTH,
    deviation: float = DEVIATION,
    backstep: int = BACKSTEP,
) -> tuple[list[Swing], Swing | None]:
    """(the confirmed swings, oldest first, alternating; the last point, still forming - or None)."""
    h, lo = np.asarray(high, float), np.asarray(low, float)
    n = len(h)
    low_map, high_map = np.zeros(n), np.zeros(n)
    last_low = last_high = 0.0
    for shift in range(depth, n):
        val = float(lo[shift - depth + 1 : shift + 1].min())
        if val == last_low:
            val = 0.0
        else:
            last_low = val
            if lo[shift] - val > deviation:
                val = 0.0
            else:
                for back in range(1, backstep + 1):
                    if low_map[shift - back] != 0 and low_map[shift - back] > val:
                        low_map[shift - back] = 0.0
        low_map[shift] = val if lo[shift] == val else 0.0
        val = float(h[shift - depth + 1 : shift + 1].max())
        if val == last_high:
            val = 0.0
        else:
            last_high = val
            if val - h[shift] > deviation:
                val = 0.0
            else:
                for back in range(1, backstep + 1):
                    if high_map[shift - back] != 0 and high_map[shift - back] < val:
                        high_map[shift - back] = 0.0
        high_map[shift] = val if h[shift] == val else 0.0
    kind = np.zeros(n, dtype=int)  # +1 / -1 where a point stands
    search, lh, ll, lh_pos, ll_pos = 0, 0.0, 0.0, 0, 0
    for shift in range(depth, n):
        if search == 0:
            if ll == 0 and lh == 0:
                if high_map[shift] != 0:
                    lh, lh_pos, search, kind[shift] = float(h[shift]), shift, -1, 1
                if low_map[shift] != 0:
                    ll, ll_pos, search, kind[shift] = float(lo[shift]), shift, 1, -1
        elif search == 1:  # after a low: a lower low moves it; a high starts the peak
            if low_map[shift] != 0 and low_map[shift] < ll and high_map[shift] == 0:
                kind[ll_pos] = 0
                ll_pos, ll, kind[shift] = shift, float(low_map[shift]), -1
            if high_map[shift] != 0 and low_map[shift] == 0:
                lh, lh_pos, kind[shift], search = float(high_map[shift]), shift, 1, -1
        else:  # after a high: a higher high moves it; a low starts the bottom
            if high_map[shift] != 0 and high_map[shift] > lh and low_map[shift] == 0:
                kind[lh_pos] = 0
                lh_pos, lh, kind[shift] = shift, float(high_map[shift]), 1
            if low_map[shift] != 0 and high_map[shift] == 0:
                ll, ll_pos, kind[shift], search = float(low_map[shift]), shift, -1, 1
    points = [
        Swing(int(i), float(h[i] if kind[i] == 1 else lo[i]), int(kind[i])) for i in np.flatnonzero(kind)
    ]
    if not points:
        return [], None
    return points[:-1], points[-1]
