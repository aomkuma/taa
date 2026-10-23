"""Where gold runs, by Thai hour, on the old years only (2023-08 .. 2025-10-17; the exam months are spent): per H1
bar, the body and the range in D1 ATR(20) of the days before, and how often the hour continues the previous hour's
direction. Descriptive - which hours a piece should be designed for, not a trade.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/hours_old.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "2026-10-22-zones"))
import zone_grid_v1 as Z  # noqa: E402

d1, h1 = Z.bars("D1"), Z.bars("H1")
h1 = h1[(h1.index >= "2023-08-01") & (h1.index < "2025-10-18")].copy()
pc = d1.close.shift(1)
atr = pd.concat([d1.high - d1.low, (d1.high - pc).abs(), (d1.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean().shift(1)
h1["atr"] = atr.reindex(h1.index, method="ffill").values
h1["body"] = (h1.close - h1.open).abs() / h1.atr
h1["rng"] = (h1.high - h1.low) / h1.atr
s = np.sign(h1.close - h1.open)
h1["cont"] = (s == s.shift(1)).astype(float)
h1["th"] = h1.index.tz_convert("Asia/Bangkok").hour
g = h1.groupby("th").agg(n=("body", "size"), body=("body", "mean"), rng=("rng", "mean"), big=("body", lambda b: (b > 0.25).mean() * 100),
                         cont=("cont", lambda c: c.mean() * 100))
print("Thai hour: mean |body| and range in D1 ATR, % of hours with a body > 0.25 ATR, % continuing the previous hour")
print(g.round(3).to_string())
