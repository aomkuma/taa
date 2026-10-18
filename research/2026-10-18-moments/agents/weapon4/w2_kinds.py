"""W2 (gold M5 frame, T12 H180) design trades by level kind and C4 distance (does the round number hold on M5?).

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w2_kinds.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
D = w.build(P, 5, *w.DESIGN, [(0, 20)], "XAUUSD_M5_design")
HN = [x[0] for x in w.HALVES]
KIND = {0: "today", 1: "yesterday", 2: "asia", 3: "round", 4: "M15", 5: "H1"}
for T, H in ((8, 60), (12, 180)):
    for c4 in (4.0, None):
        S = w.signals(D, 4, 16, T, 0.6, H, c4=c4)
        z = w.run(S, P).merge(S[["t", "side", "level_kind", "front72", "c_dec", "unit"]], on=["t", "side"], suffixes=("", "_s"))
        z["half"] = w.plib.half_of(z.t)
        print(f"\n== M5 T{T} H{H} C4 {c4}: {len(z)} trades R {z.R.mean():+.3f}")
        for k, g in z.groupby("level_kind"):
            hr = g.R.groupby(g.half).mean().reindex(HN)
            print(f"   {KIND[k]:9} {len(g):4} R {g.R.mean():+.3f} win {100 * (g.exit == 'win').mean():3.0f}% [{' '.join(f'{v:+.2f}' for v in hr.to_numpy())}]")
