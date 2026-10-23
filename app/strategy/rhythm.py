"""The rhythm of a frame (owner 2026-10-23: "look at every TF - at this moment, which TF has a rhythm and
which does not"; PLAN §A37, TAA-1802). Moved from research/2026-10-23-entry/rhythm_scan.py, which now
imports it.

- **Rhythm swings:** a ZigZag of ``SIZE_ATR`` x the frame's ATR(14) on its last ``WINDOW`` closed bars.
- **Rhythm:** down when the last two rhythm highs AND lows are lower and the big trend
  (app/strategy/big_trend.py, 500 bars) is down; up mirrored; otherwise none.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.strategy import big_trend as bt
from app.strategy.plan1_b2 import Bars, mt5_atr

WINDOW = 300
SIZE_ATR = 2.0


@dataclass(frozen=True)
class Rhythm:
    sign: int  # +1 up, -1 down, 0 none
    atr: float  # ATR(14) of the window's last bar
    swings: list[tuple[int, int, float]]  # (bar index in the window, +1 high / -1 low, price)
    leg: int  # the running leg's direction (+1 / -1 / 0)
    big: bt.BigTrend


def rhythm(x: Bars, t: int) -> Rhythm:
    """The rhythm of a frame whose bars ``x`` are already closed by ``t``."""
    h, lo, c = x.h[-WINDOW:], x.lo[-WINDOW:], x.c[-WINDOW:]
    atr = float(mt5_atr(h, lo, c, 14)[-1])
    big = bt.big_trend(x, t)
    pts, leg, _ = bt.zigzag(h, lo, SIZE_ATR * atr)
    highs = [p for _, k, p in pts if k == 1]
    lows = [p for _, k, p in pts if k == -1]
    return Rhythm(classify(highs, lows, big.sign), atr, pts, leg, big)


def classify(highs: list[float], lows: list[float], big_sign: int) -> int:
    """-1 when the last two highs AND the last two lows are lower and the big trend is down; +1 mirrored."""
    if len(highs) < 2 or len(lows) < 2:
        return 0
    down = highs[-1] < highs[-2] and lows[-1] < lows[-2]
    up = highs[-1] > highs[-2] and lows[-1] > lows[-2]
    return -1 if down and big_sign < 0 else 1 if up and big_sign > 0 else 0
