"""The trend agent's suggestion (2026-10-17), design only (A, B): after a big first minute (>= 3 x the hour's mean
1-minute range) on FOMC (14:00) and PCE, follow it from the next open with a stop of 6 pre, hold up to 60/120/180
minutes, the stop trailing 1 R behind the best price once +1 R is reached; with and without an H1 trend
agreement (the last closed H1 close above / below its EMA20). CPI faded the same way.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/trend_suggestion.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import Gold, events, summary  # noqa: E402

G = Gold()
h1 = pd.Series(G.c, index=G.ot).resample("1h").last().dropna()
ema = h1.ewm(span=20, adjust=False).mean()
trend = np.sign(h1 - ema)
ev = events(extra=True)
ev = ev[(ev.per != "T") & ev.main.isin(["FOMC", "PCE", "CPI"])]
rng = G.h - G.lo
rows = []
for r in ev.itertuples():
    i = G.pos.get(r.t)
    if i is None:
        continue
    i = int(i)
    pre = rng[i - 60 : i].mean()
    mv = G.c[i] - G.o[i]
    if abs(mv) < 3 * pre:
        continue
    s = int(np.sign(mv)) * (-1 if r.main == "CPI" else 1)
    last_h1 = r.t.floor("h") - pd.Timedelta(hours=1)
    tr = trend.get(last_h1, 0)
    for hz in (60, 120, 180):
        out = G.trade(i + 1, s, 6 * pre, None, hz, trail=6 * pre, kind_tp=12 * pre)
        opp = G.trade(i + 1, -s, 6 * pre, None, hz, trail=6 * pre, kind_tp=12 * pre)
        rows.append(dict(t=r.t, main=r.main, per=r.per, hz=hz, agree=tr == s, R=out["R"], usd=out["usd"],
                         exit=out["exit"], kind=out["kind"], Ropp=opp["R"]))
d = pd.DataFrame(rows)
for (m, hz), x in d.groupby(["main", "hz"]):
    for per in "AB":
        y = x[x.per == per]
        z = y[y.agree]
        print(summary(y, f"{m} {hz} {per} all"), f"| coin {((y.R + y.Ropp) / 2).mean():+.2f}")
        print(summary(z, f"{m} {hz} {per} H1 agrees"), f"| coin {((z.R + z.Ropp) / 2).mean():+.2f}")
