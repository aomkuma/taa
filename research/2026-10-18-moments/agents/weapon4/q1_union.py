"""Q1 union (design): W11 = the round 50 frame with any passing anchor (A72, A24, AW, AS) within 4 U / behind;
halves, coin, the trades beyond F1, count by half.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/q1_union.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalw as ev  # noqa: E402
import w4lib as w  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
T = w.build_round_multi(P, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design_rgrid", 50.0, [0.0])
D = w.add_anchors(T[0.0], P)
S = w.signals(D, 3, 10, 8, 0.6, 60, c4=None)
near = np.zeros(len(S), bool)
for a in ("A72", "A24", "AW", "AS"):
    near |= (S[f"d_{a}"] < 4).to_numpy()
S11 = S[near].reset_index(drop=True)
Dd = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
h = pd.DatetimeIndex(Dd.t).hour
f1 = w.run(w.signals(Dd[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60), P)
z = ev.report("W11 round50 x (A72|A24|AW|AS)", S11, P, f1=f1)
c = w.plib.coin(S11, P, seeds=20)
print(f"    kinds ours {w.plib.kinds(z)} / coin {c['kinds']}; longs {100 * (z.side > 0).mean():.0f}%; " + w.account(z))
z["half"] = w.plib.half_of(z.t)
hd = {hn: w.days_in(a, b) for hn, a, b in w.HALVES}
print("    per day by half: " + " ".join(f"{k} {len(g) / hd[k]:.2f}" for k, g in z.groupby("half")))
zv2 = ev.report("W11 with v2 exits", S11, P, v2=True, f1=f1)
