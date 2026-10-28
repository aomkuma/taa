"""W8 / W7 / W7b on design (notes.md): W5a's entries and the round frames with F1 v1 and v2 exits.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w8_design.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalw as ev  # noqa: E402
import w4lib as w  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
D = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
h = pd.DatetimeIndex(D.t).hour
f1w = ((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))
S1 = w.signals(D[f1w], 3, 10, 8, 0.6, 60)
f1_v1 = w.run(S1, P)
f1_v2 = w.run_v2(S1, P)
print("== F1 reference")
ev.report("F1 v1", S1, P)
ev.report("F1 v2", S1, P, v2=True)
X = D.copy()
X["n_ind"] = 2
S5 = w.signals(X, 3, 10, 8, 0.6, 60)
print("== W5a entries (F1 without the 2-of-3 vote, 00-20 UTC)")
ev.report("W5a v1", S5, P, f1=f1_v1)
ev.report("W8 = W5a v2", S5, P, v2=True, f1=f1_v2)
R = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design_round0", kinds=["round"], round_offset=0.0)
S7 = w.signals(R, 3, 10, 8, 0.6, 60, c4=4.0)
S7b = w.signals(R, 3, 10, 8, 0.6, 60, c4=0.0)
print("== round frames")
ev.report("W7 round C4<4 v1", S7, P, f1=f1_v1)
ev.report("W7 round C4<4 v2", S7, P, v2=True, f1=f1_v2)
ev.report("W7b round behind v1", S7b, P, f1=f1_v1)
ev.report("W7b round behind v2", S7b, P, v2=True, f1=f1_v2)
