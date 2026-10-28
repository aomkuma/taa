"""The round-number frame without C4 (design): what separates its winners from its losers? Same buckets as
w5_losers.py plus the 72-h position; net / gross, halves, kinds.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/r_losers.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402
from gross_check import gross_run  # noqa: E402
from w5_losers import feats  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
D = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design_round0", kinds=["round"], round_offset=0.0)
S = feats(w.signals(D, 3, 10, 8, 0.6, 60, c4=None), P)
lo72 = pd.Series(P.lo).rolling(4305).min().to_numpy()
hi72 = pd.Series(P.h).rolling(4305).max().to_numpy()
p = S.e.to_numpy() - 1
far = np.where(S.side > 0, lo72[p - 16], hi72[p - 16])
S["pos72"] = (S.c_dec - far) / (S.front72 - far)
S["xx00"] = (S.level % 100).round(6) == 0
z = w.run(S, P)
zg = gross_run(S, P)
z = z.merge(S, on=["t", "side"], suffixes=("", "_s"))
z = z.merge(zg[["t", "side", "R"]].rename(columns={"R": "Rg"}), on=["t", "side"], how="left")
z["half"] = w.plib.half_of(z.t)
HN = [x[0] for x in w.HALVES]
print(f"round no-C4 design: {len(z)} trades, net {z.R.mean():+.3f}, gross {z.Rg.mean():+.3f}; kinds {w.plib.kinds(z)}")


def table(col, bins):
    b = pd.cut(z[col], bins) if bins is not None else z[col]
    print(f"\n  by {col}")
    for k, g in z.groupby(b, observed=True):
        hr = g.R.groupby(g.half).mean().reindex(HN)
        st = g[g.exit == "stop"]
        print(f"    {str(k):16} {len(g):4} win {100 * (g.exit == 'win').mean():3.0f}% net {g.R.mean():+.3f} gross {g.Rg.mean():+.3f}"
              f" halves+ {(hr > 0).sum()}/{hr.notna().sum()} [{' '.join(f'{v:+.2f}' for v in hr.to_numpy())}]"
              f" stops {len(st)} kinds {w.plib.kinds(g) if len(st) else '-'}")


table("c4u", [-1e9, 0, 4, 8, 16, 32, 1e9])
table("pos72", [-1, 0.5, 0.7, 0.8, 0.9, 1.0, 9])
table("side", None)
table("xx00", None)
table("hour", [-1, 1.99, 6.99, 11.99, 16.99, 20])
table("n_ind", [-1, 0, 1, 3])
table("sl_u", [0, 4, 5.5, 7.5, 20])
table("ret15", [-99, 0, 1, 2, 4, 99])
table("ret60", [-99, -3, -1, 1, 3, 99])
table("hrs_ext", [-1, 0.5, 2, 6, 24, 99])
table("h1_ce50", [-99, 1, 2, 3, 4.5, 99])
table("atr_ratio", [0, 0.8, 1.2, 1.6, 2])
table("dist_atr", [-1, 0.5, 1, 2, 3])
table("room_u", [-1, 4, 8, 15, 1e9])
