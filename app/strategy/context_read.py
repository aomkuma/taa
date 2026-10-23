"""Volatility, timing, volume and the D1 context of a decision (research/2026-10-23-entry/SPEC.md C6-C9).
Closed bars only; any frame (owner 2026-10-23: no fixed timeframe).

- **C6 volatility:** the frame's ATR(14) over its median of the last ``window`` bars (the current one
  included; at least ``min_periods`` values) - research/2026-10-18-moments/agents/journal/ny_b2/week.py
  ``pressure`` (H1, 480 bars, 100): above 1.1 the one skip rule that held forward in the journal and its
  exam.
- **C7 timing:** minutes from a clock time in a time zone (e.g. 10:00 New York), and whether the time is
  inside a window.
- **C8 volume:** a bar's tick volume over the mean of the same clock time's bars on the previous ``days``
  days that have one.
- **C9 D1 context:** the last closed D1 bar - its direction, its body in the ATR(20) of the bars before it,
  its close position in its range (research/2026-10-18-moments/agents/journal/ny_b2/retest_week.py: strong =
  body >= 1 and position >= 0.7) - and the day so far: from the server day's first bar to a price, in the
  trade's direction, in zone steps (week.py ``context`` ``day_run`` / ``day_rng``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.strategy.plan1_b2 import Bars, mt5_atr
from app.strategy.strong_levels import closed

SERVER_TZ = "Europe/Athens"


def vol_ratio(b: Bars, t: int, window: int = 480, min_periods: int = 100) -> float:
    """C6: ATR(14) of the last closed bar over the median of the last ``window`` ATR values."""
    x = closed(b, t)
    atr = mt5_atr(x.h, x.lo, x.c, 14)
    last = atr[-window:]
    last = last[np.isfinite(last)]
    if len(last) < min_periods or not math.isfinite(atr[-1]):
        return math.nan
    return float(atr[-1] / np.median(last))


def minutes_from(t: int, clock: str, zone: str) -> float:
    """C7: minutes from ``clock`` (HH:MM) of the same local day in ``zone`` to ``t`` (negative before it)."""
    local = pd.Timestamp(t, tz="UTC").tz_convert(zone)
    hh, mm = (int(v) for v in clock.split(":"))
    mark = datetime.combine(local.date(), time(hh, mm), tzinfo=ZoneInfo(zone))
    return (local.to_pydatetime() - mark).total_seconds() / 60


def in_window(t: int, start: str, end: str, zone: str) -> bool:
    """C7: ``start`` <= local time < ``end`` (HH:MM)."""
    return minutes_from(t, start, zone) >= 0 > minutes_from(t, end, zone)


def rel_volume(t_open: np.ndarray, volume: np.ndarray, i: int, days: int = 20) -> float:
    """C8: bar ``i``'s volume over the mean volume of the bars that opened at the same UTC clock time on the
    ``days`` previous calendar days."""
    day_ns = 24 * 3600 * 10**9
    wanted = t_open[i] - day_ns * np.arange(1, days + 1)
    pos = np.searchsorted(t_open, wanted)
    ok = (pos < len(t_open)) & (t_open[np.minimum(pos, len(t_open) - 1)] == wanted)
    if not ok.any():
        return math.nan
    usual = float(volume[pos[ok]].mean())
    return float(volume[i] / usual) if usual > 0 else math.nan


@dataclass(frozen=True)
class DayContext:
    direction: int  # +1 the last closed D1 bar closed up, -1 down, 0 flat
    body_atr: float  # its body over the ATR(20) of the bars before it
    close_pos: float  # 1 = closed at its extreme in its direction, 0 = at the other end
    strong: bool  # body >= 1 and position >= 0.7


def last_day(d1: Bars, t: int) -> DayContext:
    """C9: the last D1 bar closed by ``t``."""
    x = closed(d1, t)
    if len(x.c) < 22:
        return DayContext(0, math.nan, math.nan, False)
    atr = mt5_atr(x.h, x.lo, x.c, 20)
    a = float(atr[-2])  # the ATR known before that day
    o, h, lo, c = float(x.o[-1]), float(x.h[-1]), float(x.lo[-1]), float(x.c[-1])
    d = 1 if c > o else -1 if c < o else 0
    if not (math.isfinite(a) and a > 0) or h == lo or d == 0:
        return DayContext(d, math.nan, math.nan, False)
    body = abs(c - o) / a
    pos = (c - lo) / (h - lo) if d > 0 else (h - c) / (h - lo)
    return DayContext(d, body, pos, body >= 1.0 and pos >= 0.7)


def day_so_far(intra: Bars, t: int, price: float, side: int, step: float) -> tuple[float, float]:
    """C9: (the run from the server day's first closed bar's open to ``price`` in the trade's direction, the
    day's range so far) in zone steps; NaN before the day's first bar closes."""
    x = closed(intra, t)
    if not len(x.c) or not (math.isfinite(step) and step > 0):
        return math.nan, math.nan
    days = pd.DatetimeIndex(x.t_open, tz="UTC").tz_convert(SERVER_TZ).normalize()
    today = pd.Timestamp(t, tz="UTC").tz_convert(SERVER_TZ).normalize()
    keep = np.asarray(days == today)
    if not keep.any():
        return math.nan, math.nan
    o = float(x.o[keep][0])
    return (price - o) * side / step, float(x.h[keep].max() - x.lo[keep].min()) / step
