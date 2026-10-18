"""TP at 70 % of the way to the next level in front, the stop 10 % wider (owner, 2026-10-18). Step 0: only the
distribution of that distance on F1's design trades (no outcomes), to write the rule before computing.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/tp70_room.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/weapon4"))
import w4lib as w  # noqa: E402

P = w.instr("XAUUSD")
D = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
h = pd.DatetimeIndex(D.t).hour
S = w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60)
fill = P.o[S.e.to_numpy()] + np.where(S.side > 0, P.sp[S.e.to_numpy()] + P.slip, -P.slip)
room_f = S.room.to_numpy() - (fill - S.c_dec.to_numpy()) * S.side.to_numpy()
ru = room_f / S.unit.to_numpy()
print(f"F1 design signals {len(S)}; room missing {np.isnan(ru).sum()}")
print("room from the fill, U:", pd.Series(ru).describe(percentiles=[.1, .25, .5, .75, .9]).round(2).to_dict())
print("0.7 x room < 2 U:", np.mean(0.7 * ru < 2).round(3), "| < 3 U:", np.mean(0.7 * ru < 3).round(3),
      "| > 11.2 U (beyond 1.4 x 8 U):", np.mean(0.7 * ru > 11.2).round(3))
