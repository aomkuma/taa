"""Probe (design only): W5a's trades by level kind - is the round-number effect real? Sides, the coin on the same
minutes, F1's own trades by kind, the distance to the round number.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/round_probe.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
D = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
KIND = {0: "today", 1: "yesterday", 2: "asia", 3: "round", 4: "M15", 5: "H1"}
HN = [x[0] for x in w.HALVES]
X = D.copy()
X["n_ind"] = 2
S = w.signals(X, 3, 10, 8, 0.6, 60)
z = w.run(S, P).merge(S[["t", "side", "level_kind", "level", "c_dec", "unit", "dist_atr"]], on=["t", "side"], suffixes=("", "_s"))
z["half"] = w.plib.half_of(z.t)
for k, g in z.groupby("level_kind"):
    hr = g.R.groupby(g.half).mean().reindex(HN)
    print(f"  {KIND[k]:9} {len(g):4} net {g.R.mean():+.3f} buys {g[g.side > 0].R.mean():+.3f} ({(g.side > 0).sum()}) sells"
          f" {g[g.side < 0].R.mean():+.3f} ({(g.side < 0).sum()}) halves [{' '.join(f'{v:+.2f}' for v in hr.to_numpy())}]")
# the coin on each kind's own minutes (the kind's signal rows only, run alone)
for k in (3, 4, 5):
    Sk = S[S.level_kind == k]
    zk = w.run(Sk, P)
    c = w.plib.coin(Sk, P, seeds=20)
    print(f"  alone {KIND[k]:6} {len(zk)} R {zk.R.mean():+.3f} win {100 * (zk.exit == 'win').mean():.0f}% | coin R {c['R']:+.3f} win {100 * c['win']:.0f}%")
# F1's own trades by kind
h = pd.DatetimeIndex(D.t).hour
S1 = w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60)
f1 = w.run(S1, P).merge(S1[["t", "side", "level_kind"]], on=["t", "side"])
print("F1 by kind: " + ", ".join(f"{KIND[k]} {len(g)} {g.R.mean():+.3f}" for k, g in f1.groupby("level_kind")))
r = z[z.level_kind == 3]
print("round trades: level mod 100 =", (r.level % 100).value_counts().to_dict())
print("round: distance close-level in U  p25/50/75", np.percentile((r.c_dec - r.level) * r.side / r.unit, [25, 50, 75]).round(2))
o = z[z.level_kind != 3]
print("others: distance in U p25/50/75", np.percentile((o.c_dec - o.level) * o.side / o.unit, [25, 50, 75]).round(2))
