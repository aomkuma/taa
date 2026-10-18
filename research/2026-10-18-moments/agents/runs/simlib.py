"""A vectorised one-trade simulation equal to jlib.Instr.trade (market entries), extended to limit fills (the fill bar
checks only the stop) and absolute prices. Real costs from the jlib instrument.
"""

from __future__ import annotations

import numpy as np


def trade(P, j0: int, s: int, entry: float, sl: float, tp: float, be: float | None, hz: int, ss: float,
          fill_bar: bool = False) -> dict:
    """One trade from bar *j0* (the entry bar). *sl* / *tp*: distances in price from *entry*. *fill_bar*: the entry
    was a limit filled inside bar j0 - that bar can only stop the trade (its favourable extreme may precede the
    fill). Returns exit (win / stop / be / time), pnl (price units, 0.01 lot gold = USD), mins, kind, mfe."""
    n = len(P.o)
    end = min(j0 + hz, n - 1)
    sl_px = entry - s * sl
    if s > 0:
        adv = P.lo[j0:end]
        fav = P.h[j0:end].copy()
    else:
        adv = P.h[j0:end] + P.sp[j0:end]
        fav = P.lo[j0:end] + P.sp[j0:end]
    fav = fav.copy()
    if fill_bar and len(fav):
        fav[0] = entry
    gain = (fav - entry) * s
    hit_sl = (adv - sl_px) * s <= 0
    hit_tp = gain >= tp
    if be is not None:
        arm = np.flatnonzero(gain >= be * tp)
        k_arm = int(arm[0]) if len(arm) else 10**9
    else:
        k_arm = 10**9
    first = np.flatnonzero(hit_sl | hit_tp)
    k1 = int(first[0]) if len(first) else 10**9
    res = None
    if k1 <= k_arm and k1 < len(adv):
        if hit_sl[k1]:
            res = ("stop", (sl_px - s * ss - entry) * s, k1)
        else:
            res = ("win", tp, k1)
    elif k_arm < len(adv):
        rest = slice(k_arm + 1, len(adv))
        hb = (adv[rest] - entry) * s <= 0
        ht = hit_tp[rest]
        f2 = np.flatnonzero(hb | ht)
        if len(f2):
            k2 = k_arm + 1 + int(f2[0])
            res = ("be", (entry - s * ss - entry) * s, k2) if hb[f2[0]] else ("win", tp, k2)
    if res is None:
        x = end - 1
        px = P.c[x] - (P.slip if s > 0 else -(P.sp[x] + P.slip))
        res = ("time", (px - entry) * s, x - j0)
    k = res[2]
    mfe = float(max(gain[:k].max(), 0.0)) if k > 0 else 0.0
    kind = ""
    if res[0] == "stop":
        j = j0 + k
        later = slice(j + 1, min(j0 + 120, n))
        lf = P.h[later] if s > 0 else P.lo[later] + P.sp[later]
        hit = bool((((lf - entry) * s) >= tp).any())
        kind = "3" if hit else ("2" if mfe >= 0.5 * tp else "1")
    return dict(exit=res[0], pnl=float(res[1]), mins=int(k + 1), kind=kind, mfe=mfe, xj=j0 + k)


def market_entry(P, e: int, s: int) -> float:
    return float(P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip))


def limit_fill(P, a: int, b: int, s: int, start: float, f: float, x0: float) -> tuple[int, float, float] | None:
    """A trailing limit at the *f* retracement of the run (start -> the running extreme, from closed bars), live
    on bars a .. b-1; *x0* the extreme up to bar a-1. Returns (fill bar, fill price, the extreme at the fill) or
    None (not filled, or the start broke first)."""
    x = x0
    for j in range(a, b):
        lvl = x - f * (x - start) if s > 0 else x + f * (start - x)
        if s > 0:
            ask_lo = P.lo[j] + P.sp[j]
            if ask_lo <= lvl:
                return j, float(min(lvl, P.o[j] + P.sp[j])), x
            if P.lo[j] < start:
                return None
            x = max(x, P.h[j])
        else:
            if P.h[j] >= lvl:
                return j, float(max(lvl, P.o[j])), x
            if P.h[j] > start:
                return None
            x = min(x, P.lo[j])
    return None


def trade_trail(P, j0: int, s: int, entry: float, sl: float, trail: float, arm: float, hz: int, ss: float,
                tp: float | None = None, fill_bar: bool = False) -> dict:
    """A trailing stop: from the bar after the favourable excursion first reaches *arm* (price distance), the stop
    follows the best price (bid high for a buy, ask low for a sell) at *trail* behind it, never below the entry -
    tightened once per bar after the bar is checked (no look-ahead inside a bar). Optional fixed target *tp*."""
    n = len(P.o)
    end = min(j0 + hz, n - 1)
    stop = entry - s * sl
    best = entry
    armed = False
    for j in range(j0, end):
        adv = P.lo[j] if s > 0 else P.h[j] + P.sp[j]
        fav = P.h[j] if s > 0 else P.lo[j] + P.sp[j]
        if (adv - stop) * s <= 0:
            px = stop - s * ss
            ex = "stop" if not armed else "trail"
            return dict(exit=ex, pnl=float((px - entry) * s), mins=j - j0 + 1, mfe=float((best - entry) * s), xj=j)
        if fill_bar and j == j0:
            continue
        if tp is not None and (fav - entry) * s >= tp:
            return dict(exit="win", pnl=float(tp), mins=j - j0 + 1, mfe=float(tp), xj=j)
        if (fav - best) * s > 0:
            best = fav
        if not armed and (best - entry) * s >= arm:
            armed = True
        if armed:
            new = best - s * trail
            if (new - entry) * s < 0:
                new = entry
            if (new - stop) * s > 0:
                stop = new
    x = end - 1
    px = P.c[x] - (P.slip if s > 0 else -(P.sp[x] + P.slip))
    return dict(exit="time", pnl=float((px - entry) * s), mins=end - j0, mfe=float((best - entry) * s), xj=x)


def kind_of(P, j0: int, xj: int, s: int, entry: float, tp: float, mfe: float) -> str:
    """The owner's three kinds for a stopped trade against a reference target *tp*: 3 = the target reached from the
    entry within 120 min after all, 2 = half way first, 1 = wrong way."""
    n = len(P.o)
    later = slice(xj + 1, min(j0 + 120, n))
    lf = P.h[later] if s > 0 else P.lo[later] + P.sp[later]
    if bool((((lf - entry) * s) >= tp).any()):
        return "3"
    return "2" if mfe >= 0.5 * tp else "1"


def run_x0(P, i_s: int, a: int, s: int) -> float:
    """The run's extreme known before bar *a*, by the catalogue's convention: the start bar contributes only its
    close (its high may precede its low inside the bar), then the later bars' highs (lows for a down-run)."""
    if s > 0:
        return float(max(P.c[i_s], P.h[i_s + 1 : a].max())) if a > i_s + 1 else float(P.c[i_s])
    return float(min(P.c[i_s], P.lo[i_s + 1 : a].min())) if a > i_s + 1 else float(P.c[i_s])
