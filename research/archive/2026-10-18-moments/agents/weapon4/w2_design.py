"""W2 on design: the F1 frame on M5 (00-20 UTC), stop the level - 1 M5 ATR (floor 0.5 M15 ATR) within 4-16 U, C4 < 4
U, C5; the grid T in {8, 12, 16} U x H in {120, 180} min, BE 0.6 of T. Plus the trades / days it adds to F1-M1.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w2_design.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
D1 = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
h = pd.DatetimeIndex(D1.t).hour
f1 = w.run(w.signals(D1[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60), P)
D = w.build(P, 5, *w.DESIGN, [(0, 20)], "XAUUSD_M5_design")
days = w.days_in(*w.DESIGN)
print(w.summary(f1, days, "F1-M1 reference"))
fd = set(f1.t.dt.date)
f1_busy = [(a, a + pd.Timedelta(minutes=int(m))) for a, m in zip(f1.t, f1.mins)]
for T in (8, 12, 16):
    for H in (120, 180):
        S = w.signals(D, 4, 16, T, 0.6, H)
        z = w.run(S, P)
        print(w.summary(z, days, f"W2 T{T} H{H}"))
        zd = z.t.dt.date
        print(f"      on days without F1: {(~zd.isin(fd)).sum()} of {len(z)}; W2 days {zd.nunique()}; exits {z.exit.value_counts().to_dict()}")
S = w.signals(D, 4, 16, 12, 0.6, 180)
z = w.run(S, P)
print(w.coin_line(S, P, z))
print("    " + w.account(z))
print(f"    signal rows {len(S)}, minutes {S.t.nunique()}")
