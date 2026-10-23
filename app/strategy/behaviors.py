"""The price behaviours (the forest's animals beyond the first drafts; owner 2026-10-23: "which price
behaviours are still missing?"; PLAN §A37, TAA-1802). Pure functions on closed bars; the knowledge base's
drafts (O11-O22) combine these readings with the others. Definitions are drafts to be measured, not rules.
Moved from research/2026-10-23-entry/knowledge/behaviors.py.

- efficiency    |net move| / the sum of the bar-to-bar moves over the last n closes (1 = one way)
- line_break    the last close sits beyond a grid line it was not beyond k bars ago (a fresh break)
- climax        the last bar: range >= 2 ATR, volume >= 2 x the mean, a wick of half its range
- runaway       the day ran >= 1 step one way and price is beyond yesterday's extreme on that side
- asia_break    after 13:00 Thai: which side of the 07:00-13:00 Thai range today's bars have taken
- recent_sweep  a sweep of an equal-lows / -highs pool (app/strategy/picture.py) in the last bars
- day_levels / level_prices / level_sweep   the day's own levels and their sweeps (L14, L15)
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.strategy import picture as pr

TH = "Asia/Bangkok"


def efficiency(c: np.ndarray, n: int = 12) -> float:
    x = np.asarray(c[-(n + 1) :], dtype=float)
    if len(x) < n + 1:
        return math.nan
    path = float(np.abs(np.diff(x)).sum())
    return abs(float(x[-1] - x[0])) / path if path > 0 else math.nan


def line_break(c: np.ndarray, anchor: float, unit: float, k: int = 4) -> str:
    """'up' / 'down' when the last close is in a higher / lower grid cell (lines every ``unit`` from
    ``anchor``) than the close ``k`` bars before it, else 'none'."""
    if len(c) < k + 1 or not (unit > 0 and math.isfinite(anchor)):
        return "none"
    now, before = math.floor((c[-1] - anchor) / unit), math.floor((c[-1 - k] - anchor) / unit)
    return "up" if now > before else "down" if now < before else "none"


def climax(o: float, h: float, lo: float, c: float, v: float, atr: float, v_mean: float) -> str:
    """'top' (a long upper wick) / 'bottom' (a long lower wick) on a wide, heavy bar, else 'none'."""
    rng = h - lo
    if not (rng >= 2 * atr and v >= 2 * v_mean and rng > 0):
        return "none"
    if h - max(o, c) >= 0.5 * rng:
        return "top"
    if min(o, c) - lo >= 0.5 * rng:
        return "bottom"
    return "none"


def runaway(price: float, y_high: float, y_low: float, run_step: float) -> str:
    if run_step >= 1 and price > y_high:
        return "up"
    if run_step <= -1 and price < y_low:
        return "down"
    return "none"


def asia_break(t_open: pd.DatetimeIndex, h: np.ndarray, lo: np.ndarray, as_of: pd.Timestamp) -> str:
    """Bars closed by ``as_of`` (UTC opens); the Thai day of ``as_of``; 'none' before 13:00 Thai or without an
    Asia range."""
    th = as_of.tz_convert(TH)
    day = th.normalize()
    asia0, london0 = day + pd.Timedelta(hours=7), day + pd.Timedelta(hours=13)
    if th < london0:
        return "none"
    loc = t_open.tz_convert(TH)
    a, b = (loc >= asia0) & (loc < london0), loc >= london0
    if not a.any() or not b.any():
        return "none"
    up, down = h[b].max() > h[a].max(), lo[b].min() < lo[a].min()
    return "both" if up and down else "up" if up else "down" if down else "none"


def day_start(as_of: pd.Timestamp) -> pd.Timestamp:
    """05:00 Thai of the trading day ``as_of`` belongs to (before 05:00 Thai: the day before)."""
    th = as_of.tz_convert(TH)
    start = th.normalize() + pd.Timedelta(hours=5)
    return (start if th >= start else start - pd.Timedelta(days=1)).tz_convert("UTC")


def day_levels(m15: pd.DataFrame, d1: pd.DataFrame, as_of: pd.Timestamp) -> list[str]:
    """The day's own levels (owner 2026-10-23, L15: "the support of the middle of today"): the M15 swing lows
    / highs since 05:00 Thai (a bar's low under both neighbours', a high over both), the day's high and low,
    and yesterday's D1 high and low - bars closed by ``as_of`` only (an M15 bar at open + 15 min, a D1 bar at
    open + 1 day)."""
    x = m15[(m15.index >= day_start(as_of)) & (m15.index + pd.Timedelta(minutes=15) <= as_of)]
    out = []
    lo, hi = x.low.to_numpy(float), x.high.to_numpy(float)
    t = [i.tz_convert(TH).strftime("%H:%M") for i in x.index]
    for i in range(1, len(x) - 1):
        if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]:
            out.append(f"M15 swing low {lo[i]:.2f} at {t[i]}")
        if hi[i] > hi[i - 1] and hi[i] > hi[i + 1]:
            out.append(f"M15 swing high {hi[i]:.2f} at {t[i]}")
    if len(x):
        top, bottom = int(hi.argmax()), int(lo.argmin())
        out.append(f"the day's high {hi[top]:.2f} at {t[top]}, low {lo[bottom]:.2f} at {t[bottom]}")
    y = d1[d1.index + pd.Timedelta(days=1) <= as_of]
    if len(y):
        out.append(f"yesterday's D1 high {y.high.iloc[-1]:.2f}, low {y.low.iloc[-1]:.2f}")
    return out


def level_prices(m15: pd.DataFrame, d1: pd.DataFrame, before: pd.Timestamp) -> list[float]:
    """The prices of the day's own levels known BEFORE ``before`` (bars closed by it): the M15 swing lows /
    highs since 05:00 Thai, the day's high / low so far, yesterday's D1 high / low (L14: the pools a sweep
    takes, beyond the equal-low clusters)."""
    x = m15[(m15.index >= day_start(before)) & (m15.index + pd.Timedelta(minutes=15) <= before)]
    lo, hi = x.low.to_numpy(float), x.high.to_numpy(float)
    out = [float(lo[i]) for i in range(1, len(x) - 1) if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]]
    out += [float(hi[i]) for i in range(1, len(x) - 1) if hi[i] > hi[i - 1] and hi[i] > hi[i + 1]]
    if len(x):
        out += [float(lo.min()), float(hi.max())]
    y = d1[d1.index + pd.Timedelta(days=1) <= before]
    if len(y):
        out += [float(y.low.iloc[-1]), float(y.high.iloc[-1])]
    return out


def level_sweep(
    h: np.ndarray, lo: np.ndarray, c: np.ndarray, levels: list[float], atr: float, recent: int = 6
) -> str:
    """'low' / 'high' / 'none': within the last ``recent`` bars price went 0.1 ATR beyond a level it was on
    the near side of before them (the close before the window), and the last close is back on the near side -
    a sweep and reclaim that may take several bars (2026-10-23 21:30: under the day's low 3,986.62 and the
    line 3,994.09 to 3,975.58, back over the line two bars later). When both sides qualify, the side whose
    extreme came later."""
    if len(c) < recent + 1:
        return "none"
    w_lo, w_hi, before, last = lo[-recent:], h[-recent:], c[-recent - 1], c[-1]
    low = any(before > lv and w_lo.min() < lv - 0.1 * atr and last > lv for lv in levels)
    high = any(before < lv and w_hi.max() > lv + 0.1 * atr and last < lv for lv in levels)
    if low and high:
        return "low" if int(np.argmin(w_lo)) > int(np.argmax(w_hi)) else "high"
    return "low" if low else "high" if high else "none"


def recent_sweep(
    h: np.ndarray, lo: np.ndarray, c: np.ndarray, v: np.ndarray, atr: float, recent: int = 6
) -> str:
    """'low' (a pool under price swept and closed back - the buy picture) / 'high' / 'none', the latest one
    within the last ``recent`` bars."""
    best, side = -1, "none"
    for pool in pr.pools(h, lo, c, atr):
        for s in pr.sweeps(pool, h, lo, c, v, atr):
            if s["i"] >= len(c) - recent and s["i"] > best:
                best, side = s["i"], "low" if pool["name"] == "bottoms" else "high"
    return side
