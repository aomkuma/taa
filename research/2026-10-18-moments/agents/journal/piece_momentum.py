"""Piece on / off by its own recent result (journal phase 2): a piece trades in a week only if its base trades of the
previous N weeks summed > 0 (its trades keep being recorded while it is off, as in a paper ledger, so it can come back).
Decided on prior weeks only. Learning weeks 1-26 and the exam weeks 27-32 in one chain.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/piece_momentum.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

AG = __import__("pathlib").Path(__file__).resolve().parents[1]


def load() -> pd.DataFrame:
    parts = []
    for f in ("plan1_trades_learn_s0_x0.parquet", "plan1_trades_exam_s0_x0.parquet"):
        A = pd.read_parquet(AG / "dev" / f)
        A["t"] = pd.to_datetime(A.t_in, utc=True)
        parts.append(A[["piece", "t", "R"]])
    X = pd.concat(parts, ignore_index=True)
    X = X[(X.t >= "2025-10-20") & (X.t < "2026-05-30")]
    X["wk"] = (X.t.dt.tz_convert("Asia/Bangkok").dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time)
    return X


if __name__ == "__main__":
    X = load()
    weeks = sorted(X.wk.unique())
    W = X.groupby(["piece", "wk"]).R.sum().unstack(0).reindex(weeks).fillna(0.0)
    split = pd.Timestamp("2026-04-20")
    for N in (2, 3, 4, 6, 8):
        on = (W.rolling(N).sum().shift(1) > 0) | (W.rolling(N).sum().shift(1).isna())
        res = (W * on)
        a, b = res[res.index < split], res[res.index >= split]
        print(f"N={N}: weeks 1-26 {a.values.sum():+.2f} (base {W[W.index < split].values.sum():+.2f}) | weeks 27-32 "
              f"{b.values.sum():+.2f} (base {W[W.index >= split].values.sum():+.2f}) | by piece 1-26 {a.sum().round(2).to_dict()}")
