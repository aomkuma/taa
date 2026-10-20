"""Checks on transform.py's leads (seen after the run): per lead cell and part, R without the single best trade and
without the best three, the median R, the share of Thai weeks with a positive sum, the owner's windows against the
rest; for RT_25 opp, how many of its entries are the reclaim trades of reclaim.py (the same level kind and day,
entries within 60 minutes) - i.e. whether it is new information or #23 again.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/lead_checks.py > .../strategist/out_lead_checks.txt
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import slib

A = pd.read_parquet(slib.HERE / "transform_trades.parquet")
LEADS = [("RT_25", "opp", 1.0, "orig"), ("RT_25", "opp", 1.0, "0.5"), ("RT_25", "opp", 1.5, "orig"), ("D2_41", "same", 1.0, "orig"),
         ("D2_41", "same", 1.5, "orig")]


def week(t_ns: pd.Series) -> pd.Series:
    th = pd.to_datetime(t_ns, utc=True).dt.tz_convert(slib.TH).dt.tz_localize(None)
    return (th - pd.to_timedelta(th.dt.weekday, unit="D")).dt.normalize()


for fam, sv, sm, tg in LEADS:
    g = A[(A.family == fam) & (A.side_v == sv) & (A.stop_m == sm) & (A.tgt == tg)]
    print(f"\n== {fam} {sv} x{sm:g} {tg}")
    for p in ("P1", "P2"):
        x = g[g.part == p].sort_values("R")
        r = x.R.to_numpy()
        wk = x.groupby(week(x.entry_t)).pnl.sum()
        print(f"  {p}: n {len(r)} R {r.mean():+.3f} | without the best 1 {r[:-1].mean():+.3f}, best 3 {r[:-3].mean():+.3f} | "
              f"median {np.median(r):+.3f} | best trade {r[-1]:+.2f} R | weeks positive {int((wk > 0).sum())} of {len(wk)} | "
              f"USD {x.pnl.sum():+.1f}")
        if "win" in x and x.win.notna().any():
            for w, y in x.groupby(x.win.isin(["Asia", "London", "NY"]).map({True: "owner's windows", False: "other hours"})):
                print(f"      {w}: n {len(y)} R {y.R.mean():+.3f}")

# RT_25 opp against reclaim.py's trades
R = pd.read_parquet(slib.HERE / "retest_trades.parquet")
C = pd.read_parquet(slib.HERE / "reclaim_trades.parquet")
g = A[(A.family == "RT_25") & (A.side_v == "opp") & (A.stop_m == 1.0) & (A.tgt == "orig")].copy()
g["t"] = pd.to_datetime(g.t_in, utc=True)
g = g.merge(R[["t", "kind"]], on="t", how="left")
same = 0
for r in g.itertuples():
    c = C[(C.kind == r.kind) & ((C.t - r.t).abs() <= pd.Timedelta(minutes=60))]
    same += len(c) > 0
print(f"\nRT_25 opp x1 orig: {len(g)} trades, of which {same} have a reclaim.py trade on the same level kind within 60 min")
print("RT_25 opp x1 orig by level kind (P1 / P2):")
for k, y in g.groupby("kind"):
    print(f"   {k}: " + " | ".join(f"{p} n {len(y[y.part == p])} R {y[y.part == p].R.mean():+.3f}" for p in ("P1", "P2")))
print("exits:", g.groupby("part").exit.value_counts().to_dict())
