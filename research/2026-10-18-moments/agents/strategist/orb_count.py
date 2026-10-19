"""Count the opening-range grid cells (orb_sens_trades.parquet) with a positive mean R, per open and period.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/orb_count.py > .../strategist/out_orb_count.txt
"""
import pandas as pd

import slib

T = pd.read_parquet(slib.HERE / "orb_sens_trades.parquet")
g = T.groupby(["open", "L", "k", "X", "per"]).R.mean().unstack("per")
for o in g.index.get_level_values(0).unique():
    x = g.loc[o]
    print(o, {p: int((x[p] > 0).sum()) for p in ["O1", "O2", "P1", "P2"]}, "of", len(x), " min/max P1",
          round(x.P1.min(), 3), round(x.P1.max(), 3), "P2", round(x.P2.min(), 3), round(x.P2.max(), 3))
