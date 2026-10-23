"""Per-trade facts for the solo exam, computed once for the learning trades (../trades.csv) and the exam trades
(../exam/trades.csv): the base R, the exit variants, and the context at the entry (closed bars before the entry only;
an exit variant's outcome uses the ticks of the trade's own 120 minutes). Every consumer filters by time - nothing
here is read beyond the week being decided.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/solo/cache.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import retest_week as RT  # noqa: E402
import week as W  # noqa: E402

W.C.EXAM = pd.Timestamp("2026-10-23", tz="UTC")  # the owner's go-ahead to read the exam (2026-10-22)
BASE = W.HERE


def facts(folder: Path) -> pd.DataFrame:
    W.HERE = folder
    X = W.load().sort_values("t").reset_index(drop=True)
    X["exit"] = W.realistic(X, band=0.1)
    X["exit_nobe"] = W.realistic(X, be=False, band=0.1)
    X["exit_noband"] = W.realistic(X, band=1e-9)
    X["exit_h90"] = W.realistic(X, band=0.1, hold=90)
    X = X.join(W.pressure(X)).join(W.context(X))
    ny = X.t.dt.tz_convert("America/New_York")
    X["m10"] = ny.dt.hour * 60 + ny.dt.minute - 600
    X["run3"] = [W.run3(t) for t in X.t]
    X["tf"] = np.where(X.strategy.str.endswith("m5"), "M5", "M1")
    X["risk"] = (X.entry_price - X.sl_initial).abs()
    X["zone_share"] = np.minimum(X.zone_pos, 1 - X.zone_pos)
    g = W.Z.daily_grid(W.Z.bars("D1"))
    k = g.index.searchsorted(X.t, side="right") - 1
    sh = g["shift"].values
    last = [next((sh[j] for j in range(i, -1, -1) if sh[j]), "") for i in k]
    X["with_trend"] = [(v == "up") == (sd == "BUY") for v, sd in zip(last, X.side)]
    keep = ["signal_id", "t", "side", "entry_price", "sl_initial", "risk", "tf", "r_multiple", "exit", "exit_nobe", "exit_noband",
            "exit_h90", "vol", "push3d", "zone_line_dist", "zone_share", "m10", "score", "run3", "day_run", "day_rng", "touches",
            "worn", "h1_structure", "with_trend", "pattern", "level"]
    return X[keep]


if __name__ == "__main__":
    F = pd.concat([facts(BASE), facts(BASE / "exam")]).sort_values("t").reset_index(drop=True)
    F["bounces"] = None
    F.drop(columns=["bounces"]).to_parquet(HERE / "b2_facts.parquet")
    R = RT.trades(pd.Timestamp("2025-10-20", tz="UTC"), pd.Timestamp("2026-10-22", tz="UTC"))
    R.to_parquet(HERE / "retest_facts.parquet")
    print(len(F), "B2 trades,", len(R), "re-test trades")
