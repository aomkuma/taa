"""Price structure, its clarity, the trend across frames and the market's phase
(research/2026-10-23-entry/SPEC.md C2 and C3). Every function works on any timeframe (owner 2026-10-23: no
fixed timeframe) and reads only the bars closed by the decision time.

- **Structure** of a frame: its last two confirmed fractal highs and lows (order ``k``) - higher highs and
  higher lows = +1, lower highs and lower lows = -1, anything else 0 (ported from
  research/2026-10-18-moments/agents/journal/ny_b2/week.py ``structure``: ``k`` = 1, the last 200 bars).
- **Clarity:** the last four swings alternate high / low and every leg between them is at least
  ``MIN_LEG_ATR`` x the frame's ATR(14) - a readable picture, not noise.
- **Phase:** the last ``n`` closes each moved the same way from the close before (a one-way run: +1 / -1),
  otherwise 0 (week.py ``run3`` with n = 3 on D1).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from app.strategy.plan1_b2 import Bars, mt5_atr
from app.strategy.strong_levels import closed

LOOKBACK = 200
MIN_LEG_ATR = 2.0


@dataclass(frozen=True)
class Structure:
    sign: int  # +1 HH/HL, -1 LH/LL, 0 mixed or too few swings
    clear: bool
    highs: tuple[float, ...]  # the last two confirmed fractal highs, older first
    lows: tuple[float, ...]


def fractal_points(h: np.ndarray, lo: np.ndarray, k: int) -> list[tuple[int, int, float]]:
    """(bar, +1 high / -1 low, price) of every fractal whose ``k`` bars on each side exist, in bar order;
    a bar can be both."""
    out: list[tuple[int, int, float]] = []
    for j in range(k, len(h) - k):
        if h[j] > h[j - k : j].max() and h[j] > h[j + 1 : j + 1 + k].max():
            out.append((j, 1, float(h[j])))
        if lo[j] < lo[j - k : j].min() and lo[j] < lo[j + 1 : j + 1 + k].min():
            out.append((j, -1, float(lo[j])))
    return out


def structure(b: Bars, t: int, k: int = 1, lookback: int = LOOKBACK) -> Structure:
    """The frame's structure at ``t`` from its last ``lookback`` closed bars."""
    x = closed(b, t)
    h, lo, c = x.h[-lookback:], x.lo[-lookback:], x.c[-lookback:]
    pts = fractal_points(h, lo, k)
    highs = tuple(p for _, kind, p in pts if kind == 1)[-2:]
    lows = tuple(p for _, kind, p in pts if kind == -1)[-2:]
    sign = 0
    if len(highs) == 2 and len(lows) == 2:
        if highs[1] > highs[0] and lows[1] > lows[0]:
            sign = 1
        elif highs[1] < highs[0] and lows[1] < lows[0]:
            sign = -1
    return Structure(sign, _clear(pts, h, lo, c), highs, lows)


def _clear(pts: list[tuple[int, int, float]], h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> bool:
    last = pts[-4:]
    if len(last) < 4 or any(a[1] == b[1] for a, b in pairwise(last)):
        return False
    atr = mt5_atr(h, lo, c, 14)
    unit = float(atr[-1]) if len(atr) and np.isfinite(atr[-1]) else float("nan")
    if not np.isfinite(unit) or unit <= 0:
        return False
    return all(abs(b[2] - a[2]) >= MIN_LEG_ATR * unit for a, b in pairwise(last))


def phase(b: Bars, t: int, n: int = 3) -> int:
    """+1 / -1 when each of the last ``n`` closed bars closed beyond the close before it the same way, else
    0."""
    c = closed(b, t).c
    if len(c) < n + 1:
        return 0
    s = np.sign(np.diff(c[-(n + 1) :]))
    return int(s[-1]) if s[-1] != 0 and bool((s == s[-1]).all()) else 0


def trend(frames: list[Bars], t: int, side: int, k: int = 1) -> list[int]:
    """Each frame's structure sign times the trade's side (+1 the frame agrees with the trade)."""
    return [structure(f, t, k).sign * side for f in frames]
