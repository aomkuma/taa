"""SW-20 on PLAN-1's pieces over P1 .. exam (notes.md, written before computing; a description only - the exam was read
for PLAN-1 already). Each piece's paper trades = dev1's runner's every-trade files (slippage 0); a trade is taken for
real when >= 20 earlier paper trades of the piece exited before its entry and their last 20 mean R > 0.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/sw20_plan1.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DEV = Path(__file__).parents[1] / "dev"
N = 20


def switch(g: pd.DataFrame, n: int = N) -> np.ndarray:
    """keep[k]: >= n earlier trades exited strictly before g's k-th entry and their last n mean R > 0."""
    ti, te, r = g.t_in.to_numpy(np.int64), g.t_out.to_numpy(np.int64), g.R.to_numpy(float)
    order = np.argsort(te, kind="stable")
    te_s, r_s = te[order], r[order]
    keep = np.zeros(len(g), bool)
    for k in range(len(g)):
        m = int(np.searchsorted(te_s, ti[k], side="left"))
        keep[k] = m >= n and r_s[m - n:m].mean() > 0
    return keep


def main() -> None:
    A = pd.concat([pd.read_parquet(DEV / "plan1_every_learn_s0_x0.parquet"), pd.read_parquet(DEV / "plan1_every_exam_s0_x0.parquet")])
    for c in ("t_in", "t_out"):
        A[c] = pd.to_datetime(A[c], utc=True).astype("int64") if not np.issubdtype(A[c].dtype, np.integer) else A[c]
    A = A.sort_values("t_in").reset_index(drop=True)
    rows = []
    for piece, g in A.groupby("piece"):
        g = g.sort_values("t_in")
        rows.append(g.assign(keep=switch(g)))
    K = pd.concat(rows)
    for piece, g in list(K.groupby("piece")) + [("PLAN-1 (pieces together, no overlap rule)", K)]:
        print(piece)
        for p in ("P1", "P2", "exam"):
            x = g[g.part == p]
            k = x[x.keep]
            print(f"  {p:4s} always {len(x):3d} R {x.R.mean():+.3f} sum {x.R.sum():+6.1f} | SW-20 kept {len(k):3d} "
                  f"({len(k) / max(1, len(x)):.0%}) R {k.R.mean() if len(k) else float('nan'):+.3f} sum {k.R.sum():+6.1f}")


if __name__ == "__main__":
    main()
