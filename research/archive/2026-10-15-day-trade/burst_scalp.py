"""Momentum scalping on a burst (owner, 2026-10-15: "if it spikes, the target need not be far, but it must run far
in a short time - is that a kind of scalping?").

A burst bar: range >= ``K`` x ATR(14), the close in the outer quarter of the bar on the burst's side, and the close
beyond the highest high / lowest low of the previous 12 bars. Entry at that close with the burst (spread + slippage
paid), a tight stop and a quick target in ATR, out after ``T`` bars at the latest. ``with_h1``: only bursts in the
H1 map's direction. One position per symbol; bars with both stop and target count as the stop.

Pooled over the 8 traded symbols on M5 (and gold on M1), the bot's hours and all hours except the rollover;
walk-forward halves at 2026-04-08.

    .venv/Scripts/python research/2026-10-15-day-trade/burst_scalp.py
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-15-day-trade")
import box_harness as bh  # noqa: E402
import box_multi as bm  # noqa: E402
import flag_rules as fr  # noqa: E402

K = 2.0
MID = pd.Timestamp("2026-04-08", tz="UTC")


def bursts(m: bm.Market) -> list[tuple[int, int]]:
    a = m.atr["wilder"]
    hh = pd.Series(m.h).shift(1).rolling(12).max().to_numpy()
    ll = pd.Series(m.lo).shift(1).rolling(12).min().to_numpy()
    rng = m.h - m.lo
    out = []
    for t in range(30, len(m.c) - 1):
        if not np.isfinite(a[t]) or rng[t] < K * a[t]:
            continue
        pos = (m.c[t] - m.lo[t]) / rng[t] if rng[t] > 0 else 0.5
        if pos >= 0.75 and m.c[t] > hh[t]:
            out.append((t, 1))
        elif pos <= 0.25 and m.c[t] < ll[t]:
            out.append((t, -1))
    return out


def simulate(
    m: bm.Market,
    evs: list[tuple[int, int]],
    window: bh.Window,
    sl: float,
    tp: float,
    hold: int,
    with_h1: bool,
) -> list[tuple[pd.Timestamp, float]]:
    out: list[tuple[pd.Timestamp, float]] = []
    busy = -1
    a = m.atr["wilder"]
    for t, s in evs:
        ts = m.times[t]
        if t <= busy or not window(ts):
            continue
        if with_h1 and m.ctx.at(ts)[1] != ("UP" if s > 0 else "DOWN"):
            continue
        entry = m.c[t] + s * m.cost[t]
        risk = sl * a[t]
        stop, target = entry - s * risk, entry + s * tp * a[t]
        end = min(t + hold, len(m.c) - 1)
        r, j = None, end
        for k in range(t + 1, end + 1):
            if (m.lo[k] if s > 0 else m.h[k]) * s <= stop * s:
                r, j = -1.0, k
                break
            if (m.h[k] if s > 0 else m.lo[k]) * s >= target * s:
                r, j = (target - entry) * s / risk, k
                break
        if r is None:
            r = (m.c[end] - s * m.cost[end] - entry) * s / risk
        out.append((ts, r))
        busy = j
    return out


if __name__ == "__main__":
    sets = [("M5", bm.SYMBOLS), ("M1", ["XAUUSD"])]
    windows = {k: bh.WINDOWS[k] for k in ("07-20 (bot now)", "00-20:30 (+Asia)")}
    print(
        "| TF | hours | H1 with | stop ATR | target ATR | hold bars | trades | win % | year R/trade | 1st half | 2nd half |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for tf, syms in sets:
        markets = [bm.Market(s, tf) for s in syms]
        evs = [bursts(m) for m in markets]
        for (wname, window), with_h1, sl, tp, hold in itertools.product(
            windows.items(), (False, True), (0.5, 1.0), (0.5, 1.0), (3, 6)
        ):
            rows = [
                x
                for m, e in zip(markets, evs, strict=True)
                for x in simulate(m, e, window, sl, tp, hold, with_h1)
            ]
            if not rows:
                continue
            rs = [r for _, r in rows]
            f = [r for ts, r in rows if ts < MID]
            s2 = [r for ts, r in rows if ts >= MID]
            win = np.mean([r > 0 for r in rs]) * 100
            print(
                f"| {tf} | {wname} | {'yes' if with_h1 else 'no'} | {sl} | {tp} | {hold} | {len(rs)} | {win:.0f} | {fr.stats(rs)} | {fr.stats(f) if f else 'n 0'} | {fr.stats(s2) if s2 else 'n 0'} |"
            )
