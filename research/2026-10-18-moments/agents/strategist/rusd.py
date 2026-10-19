"""Q2 - R against USD: does the trade's risk size (USD at 0.01 lot) decide the money result?

Written before computing: the developer's B2 (P3) and W (P4) trades, news cost 0, per part. (a) R and USD by the
risk's size in USD (<= 10, 10-20, 20-35, 35-60, > 60) and by the risk in the entry TF's ATR (the pattern's `atr`
column). (b) The correlation of risk with R. (c) What a fixed-USD-risk account gets (R x a fixed amount) against the
fixed 0.01 lot (USD). (d) Risk caps written here before reading (risk <= 20 / 30 USD; risk <= 4 entry-TF ATR), the
trades kept as they were (no replacement trades - a cap's own effect, not a stream).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/rusd.py > .../strategist/out_rusd.txt
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import slib

SETS = {"B2 (P3)": slib.dev_trades("p3_trades_all.parquet", "B2"), "W (P4)": slib.dev_trades("p4_trades_W_WL.parquet", "W")}
BINS = [0, 10, 20, 35, 60, 1e9]
LAB = ["<=10", "10-20", "20-35", "35-60", ">60"]

for name, d in SETS.items():
    print(f"=== {name}")
    d["rb"] = pd.cut(d.risk, BINS, labels=LAB)
    d["ratr"] = d.risk / d.atr
    for p in ("P1", "P2"):
        x = d[d.part == p]
        print(f"  {p}: all  {slib.row(x)}  median risk {x.risk.median():.1f} USD; corr(risk, R) {np.corrcoef(x.risk, x.R)[0, 1]:+.3f};"
              f" USD if every trade risked the median: {x.R.sum() * x.risk.median():+.1f}")
        for b in LAB:
            y = x[x.rb == b]
            print(f"     risk {b:>6s} USD  {slib.row(y)}")
        q = x.ratr.quantile([0.33, 0.67]).to_numpy()
        for lab, y in (("risk < 1/3 q of ATRs", x[x.ratr < q[0]]), ("middle", x[(x.ratr >= q[0]) & (x.ratr < q[1])]),
                       ("risk > 2/3 q of ATRs", x[x.ratr >= q[1]])):
            print(f"     {lab:22s} {slib.row(y)}   (ATRs {y.ratr.median():.1f})")
        for lab, y in (("cap risk <= 20 USD", x[x.risk <= 20]), ("cap risk <= 30 USD", x[x.risk <= 30]),
                       ("cap risk <= 4 entry ATR", x[x.ratr <= 4])):
            print(f"     {lab:24s} {slib.row(y)}")
    print()
