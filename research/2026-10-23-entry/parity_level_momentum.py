"""Parity (SPEC.md 4.4): app/strategy/level_momentum.py against the research original (the touches and bounces in
research/2026-10-18-moments/agents/journal/ny_b2/week.py ``context``: H1 bars of the last 5 days, the level's band
+-0.1 D1 ATR, the trade's side) on all 98 NY-B2 learning trades.

    .venv/Scripts/python research/2026-10-23-entry/parity_level_momentum.py
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/2026-10-18-moments/agents/journal/ny_b2"))
import week as W  # noqa: E402

from app.strategy import level_momentum as lm  # noqa: E402
from app.strategy.plan1_b2 import Bars  # noqa: E402

X = W.load().sort_values("t").reset_index(drop=True)
ref = W.context(X)
h1 = W.Z.bars("H1")
t = h1.index.as_unit("ns").asi8
B = Bars(t, t + 3600 * 10**9, h1.open.to_numpy(float), h1.high.to_numpy(float), h1.low.to_numpy(float), h1.close.to_numpy(float))
g = W.Z.daily_grid(W.Z.bars("D1"))
bad = 0
for r, c in zip(X.itertuples(), ref.itertuples(), strict=True):
    lv = float(re.match(r"\s*([0-9.]+)", str(r.level)).group(1))
    k = g.index.searchsorted(r.t, side="right") - 1
    band = 0.1 * g.step.values[k]
    m = lm.level_momentum(B, r.t.value, lv, band, 1 if r.side == "BUY" else -1, (r.t - pd.Timedelta(days=5)).value)
    # the research rounded each bounce to 0.1 USD
    if m.touches != c.touches or not np.allclose(np.round(m.bounces[-4:], 1), c.bounces):
        bad += 1
        if bad <= 3:
            print("MISMATCH", r.t, m.touches, c.touches, m.bounces[-4:], c.bounces)
print(f"touches and bounces equal on {len(X) - bad} / {len(X)} trades")
print("PARITY", "OK" if bad == 0 else "FAILED")
