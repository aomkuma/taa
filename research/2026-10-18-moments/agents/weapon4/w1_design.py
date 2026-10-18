"""W1 on design: F1 as frozen (8 U, BE 0.6, 60 min, stop 3-10 U + the 0.5 M15-ATR floor) at 02-07 and 17-20 UTC; by
hour block; the coin; days / overlap with F1's own design trades.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w1_design.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
D = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
h = pd.DatetimeIndex(D.t).hour
f1w = ((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))
days = w.days_in(*w.DESIGN)
f1 = w.run(w.signals(D[f1w], 3, 10, 8, 0.6, 60), P)
print(w.summary(f1, days, "F1 (its windows)"))
for name, m in (("W1 02-07 + 17-20", ((h >= 2) & (h < 7)) | ((h >= 17) & (h < 20))),
                ("  02-07", (h >= 2) & (h < 7)), ("  17-20", (h >= 17) & (h < 20)),
                ("  02-04", (h >= 2) & (h < 4)), ("  04-07", (h >= 4) & (h < 7)),
                ("all 00-20 (F1 + W1)", h < 20)):
    S = w.signals(D[m], 3, 10, 8, 0.6, 60)
    z = w.run(S, P)
    print(w.summary(z, days, name))
    if name.startswith("W1"):
        print(w.coin_line(S, P, z))
        print("    " + w.account(z))
        fd = set(f1.t.dt.date)
        zd = z.t.dt.date
        print(f"    W1 trades on days without an F1 trade: {(~zd.isin(fd)).sum()} of {len(z)}; W1 days {zd.nunique()},"
              f" F1 days {len(fd)}, union {len(fd | set(zd))} of {days}")
        print("    exits " + str(z.exit.value_counts().to_dict()))
