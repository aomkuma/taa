"""Trend days (design data only): at a checkpoint hour, the day's move so far (from 00:00 UTC, in ADR units) and
where the price sits in the day's range; does the next 2-3 hours continue in that direction?

Signed continuation in ADR units, per checkpoint hour and |move| bin, by half-year.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/trendday.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    s = pd.DataFrame({"o": B.o, "h": B.h, "l": B.lo, "c": B.c}, index=B.ot)
    s = s[s.index < lab.DESIGN_END]
    h1 = s.resample("60min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    d1 = s.resample("1D").agg({"h": "max", "l": "min"}).dropna()
    d1 = d1[d1.index.dayofweek < 5]
    adr = (d1.h - d1.l).rolling(20).mean().shift(1)
    h1["day"] = h1.index.normalize()
    h1 = h1[h1.index.dayofweek < 5]
    h1["adr"] = h1.day.map(adr)
    g = h1.groupby("day")
    h1["dopen"] = g.o.transform("first")
    h1["dhi"] = g.h.cummax()
    h1["dlo"] = g.l.cummin()
    h1["hr"] = h1.index.hour
    rows = []
    for k in (2, 3):
        fut = h1.c.shift(-k)
        same = (h1.index.to_series().shift(-k) - h1.index.to_series()) == pd.Timedelta(hours=k)
        x = h1.assign(m=(h1.c - h1.dopen) / h1.adr, pos=(h1.c - h1.dlo) / (h1.dhi - h1.dlo),
                      nxt=(fut - h1.c) / h1.adr, k=k)[same.to_numpy()]
        rows.append(x.dropna())
    d = pd.concat(rows)
    d["half"] = d.index.map(lab.half_of)
    d["sgn"] = np.sign(d.m)
    d["cont"] = d.sgn * d.nxt
    d["mb"] = pd.cut(d.m.abs(), [0, 0.15, 0.3, 0.5, 0.8, 9])
    # "at the extreme": pos >= 0.8 for an up day, <= 0.2 for a down day
    d["ext"] = np.where(d.sgn > 0, d.pos >= 0.8, d.pos <= 0.2)
    hn = [h[0] for h in lab.HALVES]
    pd.set_option("display.width", 220)
    for k in (2, 3):
        x = d[d.k == k]
        print(f"\n=== next {k} hours: signed continuation (ADR units x 100) by checkpoint hour (UTC) and |move so far|")
        print((100 * x.pivot_table(index="hr", columns="mb", values="cont", aggfunc="mean", observed=True)).round(1).to_string())
        print("\nhalves positive (of 9) for |m| > 0.3:")
        y = x[x.m.abs() > 0.3]
        t = y.groupby(["hr", "half"]).cont.mean().unstack().reindex(columns=hn)
        print(pd.DataFrame({"N": y.groupby("hr").size(), "mean": 100 * y.groupby("hr").cont.mean(), "halves+": (t > 0).sum(1)}).round(2).to_string())
        print("\n|m| > 0.3 and at the day's extreme:")
        y = x[(x.m.abs() > 0.3) & x.ext]
        t = y.groupby(["hr", "half"]).cont.mean().unstack().reindex(columns=hn)
        print(pd.DataFrame({"N": y.groupby("hr").size(), "mean": 100 * y.groupby("hr").cont.mean(), "halves+": (t > 0).sum(1)}).round(2).to_string())


if __name__ == "__main__":
    main()
