"""Step 3b: the release-day New York reversal, design halves only. Own-pair sign vs the dollar basket's sign, by
event type, by half, against non-release days. Units: H1 ATR. Gross (bid closes).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/relfade.py > .../out_relfade.txt
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
sys.path.insert(0, "research/2026-10-18-moments")
import fxlib as fx  # noqa: E402
import gold  # noqa: E402
import lab  # noqa: E402

fx.below_normal_priority()
H = [h for h, _, _ in fx.HALVES]
UD = {p: (1 if p in fx.USD_BASE else -1) for p in fx.PAIRS}
rel = gold.releases()
r830 = rel[rel.time_et == "08:30"].copy()
r830["day"] = pd.to_datetime(r830.date)
ev_of_day = r830.groupby("day").event.agg(lambda s: "+".join(sorted(s)))
Ts = [11, 12, 13, 14, 15, 16]


def f(v, p=3):
    return " ".join(f"{x:+6.{p}f}" if np.isfinite(x) else "     -" for x in v)


def main() -> None:
    rows = []
    for p in fx.PAIRS:
        P = fx.Pair(p, costs=False)
        ev = lab.events(P, fx.NYC, 8, 10, 16)
        ev = ev[ev.half.isin(H) & np.isfinite(ev.h1_atr)].copy()
        pre = lab.local_index(P, fx.NYC, 8.5)  # the bar closing 08:30 ET = the price just before the release
        ev["pre"] = pd.Series(P.c[pre.to_numpy()], index=pre.index).reindex(ev.day).to_numpy()
        for T in Ts:
            ix = lab.local_index(P, fx.NYC, T)
            ev[f"p{T}"] = pd.Series(P.c[ix.to_numpy()], index=ix.index).reindex(ev.day).to_numpy()
        ev["pair"] = p
        rows.append(ev)
    a = pd.concat(rows, ignore_index=True)
    a["qm"] = a.move / a.h1_atr
    a["qr"] = (a.px - a.pre) / a.h1_atr  # release reaction 08:30 -> 10:00
    a["usd_qm"] = a.qm * a.pair.map(UD)
    basket = a.groupby("day").usd_qm.mean().rename("basket")
    a = a.join(basket, on="day")
    a["rel"] = a.day.isin(ev_of_day.index)
    a["etype"] = a.day.map(ev_of_day).fillna("none")
    for T in Ts:
        a[f"f{T}"] = (a[f"p{T}"] - a.px) / a.h1_atr  # forward move from 10:00 ET to T, price direction
    a.to_parquet("research/2026-10-18-moments/agents/fx/relfade_design.parquet")
    print("days:", a.day.nunique(), " release days:", a[a.rel].day.nunique())

    def table(name, m, sidecol):
        x = a[m]
        print(f"-- {name} (n events {len(x)}, days {x.day.nunique()})   fade path to ET hours {Ts}")
        side = -np.sign(x[sidecol])
        print(f"   pooled          {f([np.nanmean(side * x[f'f{T}']) for T in Ts])}")
        for h in H:
            y, s = x[x.half == h], side[x.half == h]
            print(f"   {h}            {f([np.nanmean(s * y[f'f{T}']) for T in Ts])}  n={len(y)}")
        for p in fx.PAIRS:
            y, s = x[x.pair == p], side[x.pair == p]
            print(f"   {p}          {f([np.nanmean(s * y[f'f{T}']) for T in Ts])}")

    a["basket_px"] = a.basket * a.pair.map(UD)  # the basket's USD move expressed in this pair's price direction
    print("\n=== fade the own move 08:00->10:00 ET ===")
    table("release days, own", a.rel, "qm")
    table("non-release days, own", ~a.rel, "qm")
    print("\n=== fade the basket (USD) move 08:00->10:00 ET ===")
    table("release days, basket", a.rel, "basket_px")
    table("non-release days, basket", ~a.rel, "basket_px")
    print("\n=== release days by size of the basket move |basket| (ATR) and by event: fade-basket to 14 ET ===")
    x = a[a.rel].copy()
    x["s"] = -np.sign(x.basket_px) * x.f14
    x["bq"] = pd.cut(x.basket.abs(), [0, 0.5, 1, 1.5, 2, 9])
    print(x.groupby("bq", observed=True).s.agg(["mean", "size"]).round(3))
    print(x.groupby(["bq", "half"], observed=True).s.mean().unstack().round(3))
    for e in ("CPI", "NFP", "PPI", "PCE", "GDP"):
        y = x[x.etype.str.contains(e)]
        print(f"  {e:4s} days {y.day.nunique():3d}  fade14 {y.s.mean():+.3f}  by half "
              f"{f([y[y.half == h].s.mean() for h in H])}")
    print("\n=== same day: the release reaction 08:30->10:00 vs the pre-release drift 08:00->08:30 ===")
    x["pre_q"] = (x.pre - x.px + x.move) / x.h1_atr
    x["s_r"] = -np.sign(x.qr) * x.f14
    print("  fade the reaction only (08:30->10:00) to 14 ET:", round(x.s_r.mean(), 3),
          f([x[x.half == h].s_r.mean() for h in H]))


if __name__ == "__main__":
    main()
