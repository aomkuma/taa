"""Per-trade context known at the decision, for the learning walk-forward (wf_learn.py): the pool break and the H4 ATR
change (liq_journal, the ORB pool rule's inputs), the H1 ATR, and two trend readings for Asia B2 - the previous
completed week's direction (close vs open, Mon-Fri) and the D1 trend (the last closed D1 close vs 5 closes earlier).

    PLAN1_TRADES=<file> .venv/Scripts/python research/2026-10-18-moments/agents/journal/context.py START END OUT
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_journal as L  # noqa: E402

if __name__ == "__main__":
    s, e, out = sys.argv[1:4]
    J = L.journal(s, e)
    A = pd.read_parquet(L.TRADES)
    for c in ("t_in", "t_dec"):
        if not np.issubdtype(A[c].dtype, np.integer):
            A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    A = A[(A.t_in >= pd.Timestamp(s, tz="UTC").value) & (A.t_in < pd.Timestamp(e, tz="UTC").value)].sort_values("t_in")
    d = L.gold.bars("D1", before=pd.Timestamp(e, tz="UTC") + pd.Timedelta(days=2))
    closed = d.index + pd.Timedelta(days=1)
    wk = d.close.groupby(d.index.tz_convert(None).to_period("W-SUN")).agg(["first", "last"])
    wk_dir = np.sign(wk["last"] - wk["first"])
    rows = []
    for r in A.itertuples():
        t = pd.Timestamp(int(r.t_dec), tz="UTC")
        k = int(np.searchsorted(closed, t, side="right")) - 1
        d1 = float(np.sign(d.close.iloc[k] - d.close.iloc[k - 5])) if k >= 5 else 0.0
        prev = t.tz_convert(None).to_period("W-SUN") - 1
        rows.append(dict(t_in=r.t_in, d1_trend=d1, prev_week=float(wk_dir.get(prev, 0.0))))
    C = pd.DataFrame(rows)
    C["H4chg"], C["broke"], C["H1atr"] = J.H4chg.values, J.broke.values, J.H1atr.values
    C.to_parquet(out)
    print(len(C))
