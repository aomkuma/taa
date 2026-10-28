"""News agent, step 2 (design only, periods A and B): after each release, does the move since the release
continue or reverse, by event, entry delay and impulse size? Forward moves from the next bar's open, in units of
the pre-release hour's mean 1-minute range (scale-free across 2021-2026) and in USD.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/explore.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import Gold, events  # noqa: E402


def panel(G: Gold, ev: pd.DataFrame) -> pd.DataFrame:
    rng = G.h - G.lo
    rows = []
    for r in ev.itertuples():
        i = G.pos.get(r.t)
        if i is None or i < 61 or i + 200 >= len(G.o):
            continue
        pre = rng[i - 60 : i].mean()
        for k in (1, 2, 3, 5, 10, 15):
            imp = G.c[i + k - 1] - G.o[i]
            s = 1 if imp > 0 else -1
            e = i + k
            base = G.o[e]
            rec = dict(t=r.t, main=r.main, all=r.all, per=r.per, k=k, pre=pre, imp=abs(imp), x=abs(imp) / pre,
                       hi=G.h[i : e].max() - G.o[i], lo=G.o[i] - G.lo[i : e].min(), px=G.c[i - 1])
            for hz in (15, 30, 60, 120):
                rec[f"f{hz}"] = (G.c[e + hz - 1] - base) * s
            rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    G = Gold()
    ev = events(extra=True)
    ev = ev[ev.per != "T"]
    d = panel(G, ev)
    d.to_parquet("research/2026-10-18-moments/agents/news/panel_design.parquet")
    pd.set_option("display.width", 250)
    for k in (1, 2, 5, 15):
        x = d[d.k == k].copy()
        x["big"] = np.where(x.x >= 3, "big", "small")
        print(f"\n== entry after {k} min: follow-side forward move, USD mean (share > 0) by event / period / size")
        g = x.groupby(["main", "big", "per"]).agg(
            n=("f30", "size"), imp=("imp", "median"),
            f15=("f15", "mean"), f30=("f30", "mean"), f60=("f60", "mean"), f120=("f120", "mean"),
            c30=("f30", lambda v: (v > 0).mean()), c60=("f60", lambda v: (v > 0).mean()))
        print(g.round(2).to_string())


if __name__ == "__main__":
    main()
