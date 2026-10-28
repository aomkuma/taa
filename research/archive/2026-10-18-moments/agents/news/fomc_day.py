"""FOMC day in detail (design only, A and B): decide at 14:00 + k ET, side = the move since 14:00 (S) or since
14:30 (P); the forward move to +60/+120/+180 minutes from the next open, in pre units (the 13:00-14:00 hour's
mean 1-minute range) and USD. Also the per-event share continuing.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/fomc_day.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import Gold, events  # noqa: E402

G = Gold()
ev = events(extra=True)
ev = ev[(ev.main == "FOMC") & (ev.per != "T")]
rng = G.h - G.lo
rows = []
for r in ev.itertuples():
    i = int(G.pos[r.t])
    pre = rng[i - 60 : i].mean()
    for k in (1, 2, 3, 5, 10, 15, 20, 25, 30, 32, 35, 40, 45, 50, 60, 75, 90):
        e = i + k
        for ref, r0 in (("S", i), ("P", i + 30)):
            if e <= r0:
                continue
            mv = G.c[e - 1] - G.o[r0]
            s = 1 if mv > 0 else -1
            rec = dict(t=r.t, per=r.per, k=k, ref=ref, x=abs(mv) / pre, pre=pre)
            for hz in (30, 60, 120, 180):
                rec[f"f{hz}"] = (G.c[e + hz - 1] - G.o[e]) * s / pre
            rows.append(rec)
d = pd.DataFrame(rows)
pd.set_option("display.width", 250)
g = d.groupby(["ref", "k", "per"]).agg(n=("f60", "size"), f30=("f30", "mean"), f60=("f60", "mean"),
                                       f120=("f120", "mean"), f180=("f180", "mean"),
                                       med120=("f120", "median"), c120=("f120", lambda v: (v > 0).mean()))
print(g.unstack("per").round(2).to_string())
