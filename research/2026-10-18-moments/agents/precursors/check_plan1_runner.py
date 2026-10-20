"""The measurer's check of dev1's PLAN-1 runner at slippage 0: London / NY against check_plan1's own derivation, Asia B2
against the ticks (check_plan1.check_b2), and the weighted summaries recomputed from the trade table a second way.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_plan1_runner.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import check_plan1 as C

D = pd.read_parquet(Path(__file__).parents[1] / "dev" / "plan1_trades_learn_s0_x0.parquet")
for name, mine in (("London ORB", C.london(0.0)), ("NY straddle", C.ny(0.0))):
    C.compare(mine, D[D.piece == name], name)
B = D[D.piece == "Asia B2"].rename(columns={"t_in": "entry_t", "t_out": "exit_t"})
B = B.assign(entry_t=pd.to_datetime(B.entry_t, utc=True).astype("int64"), exit_t=pd.to_datetime(B.exit_t, utc=True).astype("int64"),
             exit_px=B.entry + B.pnl * B.side, target=np.nan)
bad = C.check_b2(B, 0.0)
print(f"  Asia B2: {len(bad)} trades on the ticks, faults in {(bad.faults != '').sum()}: {bad[bad.faults != ''].faults.head(5).tolist()}")
for p in ("P1", "P2"):
    g = D[D.part == p]
    for col in (None, "w_mech", "w_p1"):
        w = np.ones(len(g)) if col is None else g[col].to_numpy(float)
        print(f"  {p} {col or 'unweighted'}: {len(g)} trades, R {np.sum(w * g.R) / np.sum(w):+.3f}  (sum w R / sum w)")
