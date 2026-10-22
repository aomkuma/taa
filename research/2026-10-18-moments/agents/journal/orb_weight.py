"""Owner 2026-10-22: "is the trade-count target forcing trades?" - try it before any principle: the frozen rules' trades
(sizing_trades.parquet: learning + exam, the exam already read once) re-sized with the London ORB at full / half / no
risk; the other pieces unchanged. Equity-based sizing, at least 0.01 lot (a half-risk ORB still takes the 0.01 lot).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/orb_weight.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

T = pd.read_parquet(Path(__file__).resolve().parent / "sizing_trades.parquet")


def run(X: pd.DataFrame, eq0: float, pct: float, w_orb: float) -> dict:
    eq, peak, mdd, n, R = eq0, eq0, 0.0, 0, 0.0
    for p, r, rk in zip(X.piece, X.rules_R, X.rules_risk):
        w = w_orb if p == "London ORB" else 1.0
        if w == 0:
            continue
        lots = max(0.01, np.floor(eq * pct * w / 100 / (rk * 100) * 100) / 100)
        eq += r * rk * lots * 100
        peak = max(peak, eq)
        mdd = min(mdd, (eq - peak) / peak)
        n += 1
        R += r * w
    return dict(trades=n, R_weighted=round(R, 2), end=round(eq, 2), gain_pct=round(100 * (eq / eq0 - 1)), mdd_pct=round(100 * mdd))


rows = []
for part in ("learn", "exam"):
    X = T[T.part == part]
    for eq0, pct in ((1066.0, 7.5), (1000.0, 3.0)):
        for w in (1.0, 0.5, 0.0):
            rows.append(dict(part=part, start=eq0, risk=pct, orb=w, **run(X, eq0, pct, w)))
print(pd.DataFrame(rows).to_string(index=False))
