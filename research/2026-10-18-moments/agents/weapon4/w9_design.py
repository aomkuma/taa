"""W9 on design: W5a (F1 without the 2-of-3 vote) at 00-17 UTC.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w9_design.py
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
f1 = w.run(w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60), P)
X = D[h < 17].copy()
X["n_ind"] = 2
S9 = w.signals(X, 3, 10, 8, 0.6, 60)
z = ev.report("W9 W5a 00-17 UTC", S9, P, f1=f1)
print("    " + w.account(z) + f"; exits {z.exit.value_counts().to_dict()}")
