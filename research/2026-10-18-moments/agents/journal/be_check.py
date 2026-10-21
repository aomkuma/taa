"""Break-even check (journal phase 2, owner 2026-10-21 "learning should change the numbers"): many losers first ran
+1 R or more, then hit the full stop. For each piece: once the trade has run `trig` R in its favour (on the exit side
of the quote), the stop moves to the entry. Everything else as the base trade (the same entry, stop, target / exits,
the trade's own end). Prior weeks (1-26 learn) and weeks 27-32 (exam, journaled forward) separately.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/be_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_journal as L  # noqa: E402

C = L.C
C.EXAM = pd.Timestamp("2026-10-19", tz="UTC")
TRIGS = (None, 0.5, 0.75, 1.0, 1.5)


def path_R(r) -> np.ndarray:
    t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
    f = int(np.searchsorted(t, int(r.t_in)))
    g = int(np.searchsorted(t, int(r.t_out), side="right"))
    px = (bid if r.side > 0 else ask)[f:g]
    return (px - r.entry) * r.side / r.risk


def with_be(r, Rp: np.ndarray, trig: float | None) -> float:
    if trig is None or not len(Rp):
        return r.R
    hit = np.flatnonzero(Rp >= trig)
    if not len(hit):
        return r.R
    after = Rp[hit[0]:]
    back = np.flatnonzero(after <= 0)
    if not len(back):
        return r.R  # never came back to the entry: the base exit stands
    return float(min(after[back[0]], 0.0)) if r.exit == "stop" or r.R < 0 or back[0] < len(after) - 1 else r.R


def run(file: str, s: str, e: str) -> pd.DataFrame:
    A = pd.read_parquet(L.AG / "dev" / file)
    for c in ("t_in", "t_out"):
        if not np.issubdtype(A[c].dtype, np.integer):
            A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    A = A[(A.t_in >= pd.Timestamp(s, tz="UTC").value) & (A.t_in < pd.Timestamp(e, tz="UTC").value)]
    rows = []
    for r in A.itertuples():
        Rp = path_R(r)
        rows.append({"piece": r.piece, **{str(k): with_be(r, Rp, k) for k in TRIGS}})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    for name, f, s, e in (("weeks 1-26", "plan1_trades_learn_s0_x0.parquet", "2025-10-20", "2026-04-18"),
                          ("weeks 27-32", "plan1_trades_exam_s0_x0.parquet", "2026-04-18", "2026-05-30")):
        X = run(f, s, e)
        print(name)
        print(X.groupby("piece")[[str(k) for k in TRIGS]].sum().round(2).to_string())
        print("all", X[[str(k) for k in TRIGS]].sum().round(2).to_dict())
