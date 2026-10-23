"""The big picture's trend from hundreds of bars (owner 2026-10-23: "load several hundred candles to see
the trend and the big support / resistance"; the 3-bar structure of structure_read.py read the H1 / H4
downtrend of Aug-Oct 2026 as "mixed" while H4 made seven lower highs in a row). Any frame.

- **Swings:** a ZigZag on the last ``LOOKBACK`` closed bars - a turn counts once price has moved at least
  ``SIZE_ATR`` x the frame's ATR(14) (at the end of the window, so the size is relative) back from the
  extreme.
- **The running leg:** once it has gone past the last confirmed swing of its kind it counts as the newest
  swing (a new low made is a lower low now, not after a reverse move confirms it).
- **Trend:** from the swings, newest first: how many highs in a row were each lower than the one before
  (``lower_highs``), the same for lower lows, higher highs and higher lows. Down = the newest high AND the
  newest low lower than the ones before; up = both higher; otherwise 0 (a range or a turn).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.strategy.plan1_b2 import Bars, mt5_atr
from app.strategy.strong_levels import closed

LOOKBACK = 500
SIZE_ATR = 3.0


@dataclass(frozen=True)
class BigTrend:
    sign: int  # -1 down (LH + LL), +1 up (HH + HL), 0 neither
    lower_highs: int  # consecutive, counted back from the newest high
    lower_lows: int
    higher_highs: int
    higher_lows: int
    highs: tuple[float, ...]  # the swing highs (the running leg's last), oldest first
    lows: tuple[float, ...]
    size: float  # the swing size used, in price


def zigzag(h: np.ndarray, lo: np.ndarray, size: float) -> tuple[list[tuple[int, int, float]], int, float]:
    """Confirmed swings (bar, +1 high / -1 low, price) of a ZigZag that needs ``size`` to turn, the running
    leg's direction (+1 up, -1 down, 0 none yet) and its extreme so far."""
    out: list[tuple[int, int, float]] = []
    if not len(h) or not (math.isfinite(size) and size > 0):
        return out, 0, math.nan
    # 0 before the first turn (both extremes tracked; the first turn always passes the other one, so no
    # swing is lost), +1 an up leg running (its high not confirmed), -1 a down leg
    direction = 0
    hi, hi_i, low, low_i = float(h[0]), 0, float(lo[0]), 0
    for i in range(1, len(h)):
        if direction >= 0 and h[i] > hi:
            hi, hi_i = float(h[i]), i
        if direction <= 0 and lo[i] < low:
            low, low_i = float(lo[i]), i
        if direction >= 0 and hi - lo[i] >= size and hi_i < i:
            out.append((hi_i, 1, hi))
            direction, low, low_i = -1, float(lo[i]), i
        elif direction <= 0 and h[i] - low >= size and low_i < i:
            out.append((low_i, -1, low))
            direction, hi, hi_i = 1, float(h[i]), i
    return out, direction, (hi if direction > 0 else low if direction < 0 else math.nan)


def _run(values: list[float], lower: bool) -> int:
    n = 0
    for newer, older in zip(values[::-1], values[-2::-1], strict=False):
        if (newer < older) if lower else (newer > older):
            n += 1
        else:
            break
    return n


def trend_from(h: np.ndarray, lo: np.ndarray, size: float) -> BigTrend:
    """The trend of a run of bars with a given swing size."""
    pts, leg, extreme = zigzag(h, lo, size)
    highs = [p for _, k, p in pts if k == 1]
    lows = [p for _, k, p in pts if k == -1]
    if leg < 0 and lows and extreme < lows[-1]:
        lows.append(extreme)
    elif leg > 0 and highs and extreme > highs[-1]:
        highs.append(extreme)
    lh, ll = _run(highs, True), _run(lows, True)
    hh, hl = _run(highs, False), _run(lows, False)
    sign = -1 if lh >= 1 and ll >= 1 else 1 if hh >= 1 and hl >= 1 else 0
    return BigTrend(sign, lh, ll, hh, hl, tuple(highs), tuple(lows), size)


def big_trend(b: Bars, t: int, lookback: int = LOOKBACK, size_atr: float = SIZE_ATR) -> BigTrend:
    """The trend of the frame ``b`` at ``t`` from its last ``lookback`` closed bars."""
    x = closed(b, t)
    h, lo, c = x.h[-lookback:], x.lo[-lookback:], x.c[-lookback:]
    atr = mt5_atr(h, lo, c, 14)
    size = size_atr * float(atr[-1]) if len(atr) and math.isfinite(atr[-1]) else math.nan
    return trend_from(h, lo, size)
