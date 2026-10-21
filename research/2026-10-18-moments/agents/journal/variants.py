"""Every base trade of weeks 1-52 re-simulated under the journal's lever variants (phase 2, the walk-forward of the
levers): the London ORB's target (1.0 / 1.5 / 2.0 R / none, out after 60 minutes) and the NY straddle's stop (6 / 8 /
10 / 12 USD from the fill, R on that risk, out at the decision + 30 minutes). Asia B2 is kept as it is. Written to
variants.parquet for the weekly walk-forward in wf_levers.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/variants.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_journal as L  # noqa: E402

C, MIN = L.C, L.MIN
C.EXAM = pd.Timestamp("2026-10-19", tz="UTC")
ORB_T = {"orb_1.0": 1.0, "orb_1.5": 1.5, "orb_2.0": 2.0, "orb_none": None}
NY_S = {"ny_6": 6.0, "ny_8": 8.0, "ny_10": 10.0, "ny_12": 12.0}


def main() -> None:
    parts = []
    for f in ("plan1_trades_learn_s0_x0.parquet", "plan1_trades_exam_s0_x0.parquet"):
        A = pd.read_parquet(L.AG / "dev" / f)
        for c in ("t_in", "t_out", "t_dec"):
            if not np.issubdtype(A[c].dtype, np.integer):
                A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
        parts.append(A)
    A = pd.concat(parts, ignore_index=True).sort_values("t_in").reset_index(drop=True)
    A = A[A.t_in >= pd.Timestamp("2025-10-20", tz="UTC").value]
    rows = []
    for r in A.itertuples():
        row = {"t_in": r.t_in, "piece": r.piece, "base": r.R}
        if r.piece in ("London ORB", "NY straddle"):
            t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
            f = int(np.searchsorted(t, int(r.t_in)))
            if r.piece == "London ORB":
                for k, tp in ORB_T.items():
                    tg = None if tp is None else r.entry + r.side * tp * r.risk
                    px, _, _ = C.manage(t, bid, ask, f, r.entry, r.side, r.stop, tg, int(t[f]) + 60 * MIN)
                    row[k] = (px - r.entry) * r.side / r.risk
            else:
                for k, s in NY_S.items():
                    px, _, _ = C.manage(t, bid, ask, f, r.entry, r.side, r.entry - r.side * s, None, int(r.t_dec) + 30 * MIN)
                    row[k] = (px - r.entry) * r.side / s
        rows.append(row)
    V = pd.DataFrame(rows)
    V.to_parquet(Path(__file__).resolve().parent / "variants.parquet")
    print(len(V), V.groupby("piece").size().to_dict())


if __name__ == "__main__":
    main()
