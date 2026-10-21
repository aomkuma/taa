import os, sys; sys.path.insert(0, "research/2026-10-18-moments/agents/journal")
import numpy as np, pandas as pd, liq_journal as L
C = L.C; C.EXAM = pd.Timestamp("2026-10-19", tz="UTC")
def b2_targets(file, s, e):
    A = pd.read_parquet(L.AG / "dev" / file)
    for c in ("t_in", "t_out"):
        if not np.issubdtype(A[c].dtype, np.integer): A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    A = A[(A.piece == "Asia B2") & (A.t_in >= pd.Timestamp(s, tz="UTC").value) & (A.t_in < pd.Timestamp(e, tz="UTC").value)]
    out = {k: [] for k in ("base", 1.0, 1.5, 2.0)}
    for r in A.itertuples():
        t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
        f = int(np.searchsorted(t, int(r.t_in))); g = int(np.searchsorted(t, int(r.t_out), side="right"))
        px = (bid if r.side > 0 else ask)[f:g]
        Rp = (px - r.entry) * r.side / r.risk
        out["base"].append(r.R)
        for k in (1.0, 1.5, 2.0):
            out[k].append(k if (len(Rp) and Rp.max() >= k) and r.exit != "target" or (r.exit == "target" and r.R >= k) else (k if len(Rp) and Rp.max() >= k else r.R))
    return {k: (len(v), round(float(np.sum(v)), 2)) for k, v in out.items()}
print("weeks 1-26 :", b2_targets("plan1_trades_learn_s0_x0.parquet", "2025-10-20", "2026-04-18"))
print("week 27    :", b2_targets("plan1_trades_exam_s0_x0.parquet", "2026-04-20", "2026-04-25"))
