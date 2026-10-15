"""Three things traders do differently, on the pooled box breakouts of the 8 traded symbols (owner, 2026-10-15).

1. ``trail``: let winners run - no target, the stop trails 3 ATR behind the best price since entry (a chandelier
   stop), up to 200 bars; against ``level`` (the next H1 level, <= 3 R; the rule as built).
2. ``touches``: only boxes whose broken edge was tested: at least 3 of the box's 12 bars reached within 0.25 ATR of
   it (a level that held, not any 12-bar range).
3. ``fade``: the false-break check - trade back into the box at the break close, stop 0.5 ATR beyond the break
   bar's extreme, target the box's middle.

Same events and limits as ``box_multi.py`` (one position per symbol, 12-bar cooldown, real costs, hours on the
entry bar, H1 map with the break for 1 and 2; the fade needs no trend filter but uses the same events).

    .venv/Scripts/python research/2026-10-15-day-trade/box_levers.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-15-day-trade")
import box_harness as bh  # noqa: E402
import box_multi as bm  # noqa: E402
import flag_rules as fr  # noqa: E402

MID = pd.Timestamp("2026-04-08", tz="UTC")


def touches(m: bm.Market, t: int, s: int, edge: float) -> int:
    a = m.atr["wilder"][t]
    near = (m.h[t - 12 : t] if s > 0 else m.lo[t - 12 : t]) * s >= (edge - s * 0.25 * a) * s
    return int(near.sum())


def simulate(
    m: bm.Market, evs: list[tuple[int, int, float, float]], window: bh.Window, mode: str
) -> list[tuple[pd.Timestamp, float]]:
    out: list[tuple[pd.Timestamp, float]] = []
    busy, selected = -1, -(10**9)
    a_all = m.atr["wilder"]
    for t, s, other, edge in evs:
        ts = m.times[t]
        if not window(ts):
            continue
        levels, h1 = m.ctx.at(ts)
        fade = mode == "fade"
        if not fade and h1 != ("UP" if s > 0 else "DOWN"):
            continue
        if mode == "touches" and touches(m, t, s, edge) < 3:
            continue
        side = -s if fade else s
        a = a_all[t]
        entry = m.c[t] + side * m.cost[t]
        if fade:
            extreme = m.h[t] if s > 0 else m.lo[t]
            stop = extreme + s * 0.5 * a
            target = (edge + other) / 2
        else:
            stop = other - s * m.cost[t]
            target = None
        risk = (entry - stop) * side
        if risk <= 0 or not np.isfinite(a):
            continue
        if not fade:
            ahead = sorted((lv - entry) * s for lv in levels if (lv - entry) * s > 0)
            near = ahead[0] / risk if ahead else None
            if near is not None and near < bh.ROOM_R:
                continue
            if mode != "trail":
                target = entry + s * (min(bh.CAP_R, near) if near is not None else bh.CAP_R) * risk
        if t - selected < bh.COOLDOWN:
            continue
        selected = t
        if t <= busy:
            continue
        limit = 200 if mode == "trail" else bh.TIME_STOP
        end = min(t + limit, len(m.c) - 1)
        r, j, best, trail = None, end, entry, stop
        for k in range(t + 1, end + 1):
            if (m.lo[k] if side > 0 else m.h[k]) * side <= trail * side:
                r, j = (trail - entry) * side / risk, k
                break
            if target is not None and (m.h[k] if side > 0 else m.lo[k]) * side >= target * side:
                r, j = (target - entry) * side / risk, k
                break
            if mode == "trail":
                best = max(best, m.h[k]) if side > 0 else min(best, m.lo[k])
                trail = max(trail, best - 3 * a_all[k]) if side > 0 else min(trail, best + 3 * a_all[k])
        if r is None:
            r = (m.c[end] - entry) * side / risk
        out.append((ts, r))
        busy = j
    return out


if __name__ == "__main__":
    windows = {k: bh.WINDOWS[k] for k in ("07-20 (bot now)", "00-20:30 (+Asia)")}
    print("| TF | hours | lever | year R/trade | 1st half | 2nd half |")
    print("|---|---|---|---|---|---|")
    for tf in ("M5", "M15"):
        markets = [bm.Market(sym, tf) for sym in bm.SYMBOLS]
        evs = [bh.events(m, "wilder", "latest") for m in markets]  # type: ignore[arg-type]
        for wname, window in windows.items():
            for mode in ("level", "trail", "touches", "fade"):
                rows = [x for m, e in zip(markets, evs, strict=True) for x in simulate(m, e, window, mode)]
                rs = [r for _, r in rows]
                f = [r for ts, r in rows if ts < MID]
                s2 = [r for ts, r in rows if ts >= MID]
                print(f"| {tf} | {wname} | {mode} | {fr.stats(rs)} | {fr.stats(f)} | {fr.stats(s2)} |")
