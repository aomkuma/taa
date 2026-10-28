"""W5 on design: F1 relaxed (gold M1, 00-20 UTC) - (a) PA only, (b) 2 of 3 only, (c) neither; C4 + C5 + the level
stop (3-10 U + the floor), 8 U, BE 0.6, 60 min. Trades on days / minutes without F1 reported apart.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w5_design.py
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
h = pd.DatetimeIndex(D.t).hour
days = w.days_in(*w.DESIGN)
f1 = w.run(w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60), P)
print(w.summary(f1, days, "F1 reference"))
fd = set(f1.t.dt.date)
for name, pa, ind in (("W5a PA only", True, 0), ("W5b 2/3 only", False, 2), ("W5c neither", False, 0),
                      ("F1 all-day (ref)", True, 2)):
    X = D.copy()
    if not pa:
        X["pa"] = True
    X["n_ind"] = np.where(X.n_ind >= ind, 2, 0)
    S = w.signals(X, 3, 10, 8, 0.6, 60)
    z = w.run(S, P)
    print(w.summary(z, days, name))
    zd = z.t.dt.date
    add = z[~zd.isin(fd)]
    print(f"      trades on days without F1: {len(add)} ({len(add) / days:.2f}/d) R {add.R.mean():+.3f};"
          f" exits {z.exit.value_counts().to_dict()}")
    if name.startswith("W5"):
        print(w.coin_line(S, P, z))
