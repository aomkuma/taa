"""Q6c - why does the 13:00 Thai opening-range break pay in P1 / P2 (18 of 18 settings) and lose in O1 / O2 (18 of 18)?

Written before computing. Two candidate reasons, both read from orb_sens_trades.parquet (no new trades):
(a) the costs: R gross = R + (the entry cost + the stop slippage) / risk; if the gross R is positive in O1 / O2 too,
    the costs against a small range are the reason;
(b) the season: gold's 20-day average daily range (ADR20, server-day D1 bars complete before the open) - the cut at
    35 USD is the one S1 found on 2026-10-17 (docs/OWNER_GOALS.md: under 35 -0.193 R, 35 and above +0.179), written
    here before reading. Also the H1 ATR at the open in USD: < 8, 8-15, >= 15.
Reported for the opens.py setting (L 15, k 2, X 60) and for all 18 settings pooled, per open, per period.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/orb_season.py > .../strategist/out_orb_season.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import slib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import indicators  # noqa: E402

T = pd.read_parquet(slib.HERE / "orb_sens_trades.parquet")
m = slib.m1("2023-08-01")
d1 = indicators.bars(m, "1D")
rng = (d1.high - d1.low).to_numpy()
adr20 = pd.Series(rng).rolling(20).mean().to_numpy()
d_av = pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8
j = indicators.at(d_av, pd.DatetimeIndex(T.t0).as_unit("ns").asi8)
T["adr20"] = np.where(j >= 0, adr20[np.clip(j, 0, None)], np.nan)
T["Rg"] = T.R + T.cost / T.risk
T["season"] = np.where(T.adr20 >= 35, "ADR20>=35", "ADR20<35")
T["hb"] = pd.cut(T.H, [0, 8, 15, 1e9], labels=["H1ATR<8", "8-15", ">=15"])
PER = ["O1", "O2", "P1", "P2"]

print("ADR20 median per period: " + ", ".join(f"{p} {T[T.per == p].adr20.median():.1f}" for p in PER))
print("H1 ATR at the open, median per period: " + ", ".join(f"{p} {T[T.per == p].H.median():.1f}" for p in PER))
print("cost / risk, median per period (13 Thai, L15 k2 X60): " + ", ".join(
    f"{p} {(T[(T.per == p) & (T.open == '13 Thai') & (T.L == 15) & (T.k == 2.0) & (T.X == 60)].cost / T.risk).median():.3f}" for p in PER))
for name in T.open.unique():
    for lab, G in (("L15 k2 X60", T[(T.open == name) & (T.L == 15) & (T.k == 2.0) & (T.X == 60)]),
                   ("all 18 settings pooled", T[T.open == name])):
        print(f"\n=== {name}, {lab}")
        print("  net R / gross R by period: " + " | ".join(
            f"{p} {G[G.per == p].R.mean():+.3f} / {G[G.per == p].Rg.mean():+.3f} ({(G.per == p).sum()})" for p in PER))
        for col, vals in (("season", ["ADR20<35", "ADR20>=35"]), ("hb", ["H1ATR<8", "8-15", ">=15"])):
            for v in vals:
                print(f"  {v:10s} " + " | ".join(
                    f"{p} {G[(G.per == p) & (G[col] == v)].R.mean():+.3f} ({((G.per == p) & (G[col] == v)).sum():4d})" for p in PER)
                      + f"  | all {G[G[col] == v].R.mean():+.3f} ({(G[col] == v).sum()})")
