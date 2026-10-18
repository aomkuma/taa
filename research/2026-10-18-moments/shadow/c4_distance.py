"""How early can F1 come? C4's distance (the 72-h extreme in front closer than X U, or behind) from 2 to 20 U, the
rest of F1 as frozen (+ the 0.5 M15-ATR floor, C5), one position at a time, real costs. Chosen on design only.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/c4_distance.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402
from portfolio import family_signals  # noqa: E402

P = plib.jlib.Instr("XAUUSD")
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15.index = a15.index + pd.Timedelta(minutes=15)
for part in ("wdesign", "wtest"):
    S = family_signals("F1", ["C5 not a fast tape"], 2, part).reset_index(drop=True)  # F1 without C4
    S["t"] = pd.to_datetime(S.t, utc=True)
    S["sl"] = np.maximum(S.sl, 0.5 * a15.reindex(S.t, method="ffill").to_numpy())
    room = ((S.front72 - S.c_dec) * S.side / S.unit).to_numpy()
    days = pd.bdate_range(*(("2023-11-01", "2026-02-28") if part == "wdesign" else ("2026-03-01", "2026-10-13"))).size
    print(f"\n== {'DESIGN' if part == 'wdesign' else 'WINDOW'}")
    for x in (2, 4, 6, 8, 10, 15, 20, 1000):
        z = plib.run(S[room < x], P)
        z["t"] = pd.to_datetime(z.t, utc=True)
        per = plib.by_half(z) if part == "wdesign" else " ".join(
            f"{k[5:]} {v:+.0f}" for k, v in z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum().items())
        print(f"  C4 < {x:4} U: {len(z):4} ({len(z) / days:.2f}/d) win {100 * (z.exit == 'win').mean():3.0f}% R {z.R.mean():+.3f}"
              f" USD {z.pnl.sum():+7.1f} | {per}")
