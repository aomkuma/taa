"""Q6b - is the opening-range break at the owner's 13:00 Thai open a cell picked by luck, or does it hold around its
settings and in the older history? (opens.py found ORB15 13:00 Thai +0.205 / +0.129 R, the best of 9 cells.)

Written before computing - a sensitivity read, nothing is chosen from it:
- the same ORB as opens.py (M1, mlib costs): the range of the first L minutes after the open, the first close beyond
  it in the next 60 minutes, that way at the next open, stop = the range's other side (no trade if the range > 1.5 H),
  target k R, out after X minutes;
- the grid: L = 10 / 15 / 30; k = 1.5 / 2 / 3; X = 60 / 120 - every cell printed;
- the opens: 07:00, 13:00 Thai and 09:30 NY (the owner's), plus 08:00 London (London's own clock) as the contrast;
- the periods: P1, P2 and the older learning history before them, cut into two halves O1 2023-10-18 .. 2024-10-17 and
  O2 2024-10-18 .. 2025-10-17 (pre-exam data; the owner's rule allows the 3-year history once the latest 12 months
  show something - this is a robustness read only, never used to pick a setting). The exam is not loaded (slib).
Each cell: R mean per period, and the share of cells (of 18 per open) positive in all four periods.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/orb_sens.py > .../strategist/out_orb_sens.txt
"""

from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

import mlib
import slib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import foundation as F  # noqa: E402
import indicators  # noqa: E402

m = slib.m1("2023-09-01")
o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
spr = m.spread.to_numpy(float) * 0.01 + 0.08
ti = m.index.asi8
h1 = indicators.bars(m, "1h")
atr = F.atr(h1.high.to_numpy(float), h1.low.to_numpy(float), h1.close.to_numpy(float), 14)
h_av = pd.DatetimeIndex(h1["avail"]).as_unit("ns").asi8
MIN = 60 * 10**9
PER = {"O1": ("2023-10-18", "2024-10-18"), "O2": ("2024-10-18", "2025-10-18"), "P1": ("2025-10-18", "2026-01-16"),
       "P2": ("2026-01-16", "2026-04-18")}


def period(t: pd.Timestamp) -> str:
    for k, (a, b) in PER.items():
        if pd.Timestamp(a, tz="UTC") <= t < pd.Timestamp(b, tz="UTC"):
            return k
    return ""


def open_time(name: str, day: pd.Timestamp) -> pd.Timestamp:
    d = day.tz_localize(None)
    if name == "Asia 07 Thai":
        return (d + pd.Timedelta(hours=7)).tz_localize(slib.TH).tz_convert("UTC")
    if name == "13 Thai":
        return (d + pd.Timedelta(hours=13)).tz_localize(slib.TH).tz_convert("UTC")
    if name == "08 London":
        return (d + pd.Timedelta(hours=8)).tz_localize("Europe/London").tz_convert("UTC")
    return (d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC")


OPENS = ["Asia 07 Thai", "13 Thai", "08 London", "NY 09:30"]
GRID = list(product((10, 15, 30), (1.5, 2.0, 3.0), (60, 120)))
rows = []
for day in pd.bdate_range("2023-10-18", "2026-04-17"):
    for name in OPENS:
        t0 = open_time(name, day)
        per = period(t0)
        if not per:
            continue
        i0 = np.searchsorted(ti, t0.value)
        if i0 >= len(ti) or i0 == 0 or ti[i0] - t0.value > 5 * MIN:
            continue
        j = indicators.at(h_av, np.array([t0.value]))[0]
        if j < 0 or not np.isfinite(atr[j]):
            continue
        H = atr[j]
        slip = 0.20 if name == "NY 09:30" else 0.15
        for L, k_r, X in GRID:
            iL = np.searchsorted(ti, t0.value + L * MIN)
            if iL <= i0 or iL >= len(ti):
                continue
            rh, rl = h[i0:iL].max(), lo[i0:iL].min()
            if rh - rl > 1.5 * H:
                continue
            i_end = np.searchsorted(ti, ti[iL] + 60 * MIN)
            for k in range(iL, min(i_end, len(c) - 1)):
                side = 1 if c[k] > rh else (-1 if c[k] < rl else 0)
                if side:
                    i_in = k + 1
                    e = o[i_in] + spr[i_in] + 0.07 if side > 0 else o[i_in] - 0.07
                    stop = rl if side > 0 else rh
                    risk = (e - stop) * side
                    if risk > 0:
                        i_last = np.searchsorted(ti, ti[i_in] + X * MIN) - 1
                        r = mlib.trade(o, h, lo, c, spr, i_in, side, stop, e + side * k_r * risk, i_last, slip)
                        if r:
                            rows.append(dict(open=name, per=per, L=L, k=k_r, X=X, side=side, R=r[0] / r[1], pnl=r[0], risk=r[1], H=H,
                                             cost=spr[i_in] + 0.07 + slip, t0=t0, exit=r[2]))
                    break

T = pd.DataFrame(rows)
T.to_parquet(slib.HERE / "orb_sens_trades.parquet")
for name in OPENS:
    print(f"=== {name}  (R per trade: O1 | O2 | P1 | P2; n per period in brackets)")
    allpos = 0
    for L, k_r, X in GRID:
        g = T[(T.open == name) & (T.L == L) & (T.k == k_r) & (T.X == X)]
        cells = [g[g.per == p].R for p in PER]
        pos = all(len(x) and x.mean() > 0 for x in cells)
        allpos += pos
        print(f"  L {L:2d} k {k_r:.1f} X {X:3d}: " + " | ".join(f"{x.mean():+.3f} ({len(x):3d})" for x in cells)
              + ("   all > 0" if pos else ""))
    print(f"  cells positive in all four periods: {allpos} of {len(GRID)}")
    g = T[(T.open == name) & (T.L == 15) & (T.k == 2.0) & (T.X == 60)]
    for p in PER:
        x = g[g.per == p]
        print(f"  the opens.py setting (L 15, k 2, X 60) {p}: {slib.row(x)}")
    print()
