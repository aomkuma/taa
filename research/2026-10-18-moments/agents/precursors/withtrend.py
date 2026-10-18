"""Check (design only): do the runs that come go with the larger timeframe's structure? The side of the FIRST run
to start after the decision, by half-year, against the time the structure points each way (drift), and the
adverse move an early entry sits through before it.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/withtrend.py [10|5]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from plib import HERE

X = int(sys.argv[1]) if len(sys.argv) > 1 else 10
P = f"x{X}"
DH = ["H1", "H2", "H3", "H4", "H5"]

D = pd.read_parquet(HERE / "decisions.parquet")
D = D[D.half.isin(DH)].copy()
lu, ld = D[f"{P}_lead_up"], D[f"{P}_lead_dn"]
# the first run to start (ties: both -> dropped)
side = np.where(lu.notna() & (ld.isna() | (lu < ld)), 1, np.where(ld.notna() & (lu.isna() | (ld < lu)), -1, 0))
D["rside"] = side
D["rmae"] = np.where(side > 0, D[f"{P}_mae_up"], np.where(side < 0, D[f"{P}_mae_dn"], np.nan))
D["rlead"] = np.where(side > 0, lu, np.where(side < 0, ld, np.nan))
D["rsize"] = np.where(side > 0, D[f"{P}_size_up"], np.where(side < 0, D[f"{P}_size_dn"], np.nan))

print(f"=== X = {X} U: the first run's side vs each timeframe's structure / tide (design) ===")
print("with = share of the runs going the state's way; drift = the same share if runs ignored the state "
      "(the half's up-run share applied to the state's mix)")
rows = []
for tf in ("M1", "M5", "M15", "M30", "H1", "H4"):
    for kind in ("struct", "tide", "leg", "phase"):
        if kind == "phase":
            ref = D[f"{tf}_struct"].where(D[f"{tf}_struct"].isin([1, -1])) * 1.0
            ref = ref.where(D[f"{tf}_phase"] == -1)  # correction now: is the next run back with the structure?
            name = f"{tf} correction -> run with structure"
        else:
            col = D[f"{tf}_{kind}"]
            ref = col.where(col.isin([1, -1])) * 1.0
            name = f"{tf} {kind}"
        g = D[ref.notna() & (D.rside != 0)]
        r = ref.loc[g.index]
        w = (g.rside * r) > 0
        per = w.groupby(g.half).mean()
        upshare = (D[D.rside != 0].rside > 0).groupby(D.half).mean()
        drift = (np.where(r > 0, upshare.reindex(g.half).to_numpy(), 1 - upshare.reindex(g.half).to_numpy())).mean()
        mae_w = g.rmae[w].median()
        mae_a = g.rmae[~w].median()
        rows.append(dict(state=name, runs=len(g), with_=w.mean(), drift=drift,
                         halves=" ".join(f"{per.get(h, np.nan):.2f}" for h in DH), n_ge_056=int((per >= 0.56).sum()),
                         mae_with=mae_w, mae_against=mae_a, lead_with=g.rlead[w].median(),
                         size_with=g.rsize[w].median(), size_against=g.rsize[~w].median()))
print(pd.DataFrame(rows).round(3).to_string(index=False))

# runs per minute with / against the H4 and H1 structure: are the with-trend moves faster and the counter-trend
# moves slower (fewer 10 U-in-15-min runs) for the same total distance?
print("\n-- the up-runs vs down-runs per 1,000 decision minutes, by the H4 / H1 structure, and the net drift over the"
      " next 60 min (U) --")
o = D
for tf in ("H4", "H1", "M15"):
    for s in (1, -1):
        g = o[o[f"{tf}_struct"] == s]
        up = (g.rside > 0).mean() * 1000
        dn = (g.rside < 0).mean() * 1000
        print(f"{tf} {'up  ' if s > 0 else 'down'}: minutes {len(g):6d}  up-runs {up:6.1f}  down-runs {dn:6.1f}  "
              f"first +X {((g[f'{P}_first'] > 0).mean()):.3f}  first -X {((g[f'{P}_first'] < 0).mean()):.3f}")

print("\n-- the adverse move before a with-H4 run (U) - what an early entry must survive: quantiles --")
ref = D.H4_struct.where(D.H4_struct.isin([1, -1]))
g = D[ref.notna() & (D.rside != 0)]
w = (g.rside * ref.loc[g.index]) > 0
q = g.rmae[w].quantile([0.25, 0.5, 0.75, 0.9]).round(2)
print("with H4:", q.to_dict(), " against H4:", g.rmae[~w].quantile([0.25, 0.5, 0.75, 0.9]).round(2).to_dict())
print("by window, with-H4 share of the first run:")
print((w.groupby(g.win).mean()).round(3).to_string())
