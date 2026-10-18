"""W0: does w4lib's F1 frame (gold M1) reproduce F1's design trades inside F1's wide windows? Builds the gold M1
candidate table for 00-20 UTC on design (cached; reused by W1 / W4).

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w0_check.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402
from portfolio import family_signals  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
D = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
h = pd.DatetimeIndex(D.t).hour
Dw = D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))]
S = w.signals(Dw, 3, 10, 8, 0.6, 60)
z = w.run(S, P)
# the reference: F1 + C4 + C5 + the floor from the portfolio agent's signal table
R = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, "wdesign").reset_index(drop=True)
R["t"] = pd.to_datetime(R.t, utc=True)
m15 = w.resample(P.m, 15)
a15 = w.true_atr(m15)
R["sl"] = np.maximum(family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, "wdesign").sl.to_numpy(),
                     0.5 * w.at_time(m15.index + pd.Timedelta(minutes=15), a15.to_numpy(), pd.DatetimeIndex(R.t)))
zr = w.run(R, P)
days = w.days_in(*w.DESIGN)
print(w.summary(z, days, "w4lib F1 (windows)"))
print(w.summary(zr, days, "reference F1"))
ks = set(zip(S.t, S.side))
kr = set(zip(R.t, R.side))
print(f"signal rows: w4lib {len(ks)}, reference {len(kr)}, common {len(ks & kr)}")
zt, rt = set(zip(z.t, z.side)), set(zip(zr.t, zr.side))
print(f"trades: w4lib {len(zt)}, reference {len(rt)}, common {len(zt & rt)}")
only_r = sorted(kr - ks)[:10]
only_w = sorted(ks - kr)[:10]
print("only reference:", only_r)
print("only w4lib:", only_w)
