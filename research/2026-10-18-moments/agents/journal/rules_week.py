"""The journal's rules in force, applied to one week of PLAN-1 trades, trade by trade against the base.
Rules (each added forward only, journal PLAN1_JOURNAL.md):
- weeks 4-5 only: Asia B2 takes at most one trade a morning (deleted after week 5: it cost 1.01 R net);
- from week 6: Asia B2's second trade of a morning only in the first trade's direction (no flip);
- from week 5: the London ORB's target is 1.5 R (re-simulated on the ticks: same entry, stop and 60-minute exit).
The base trades are dev/plan1_trades_learn_s0_x0.parquet (one position at a time already applied).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/rules_week.py 2025-11-17 2025-11-22
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_journal as L  # noqa: E402

C, MIN = L.C, L.MIN
ORB_TP = 1.5


def apply(start: str, end: str) -> pd.DataFrame:
    A = pd.read_parquet(L.AG / "dev" / "plan1_trades_learn_s0_x0.parquet")
    for c in ("t_in", "t_out", "t_dec"):
        if not np.issubdtype(A[c].dtype, np.integer):
            A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    W = A[(A.t_in >= pd.Timestamp(start, tz="UTC").value) & (A.t_in < pd.Timestamp(end, tz="UTC").value)].sort_values("t_in")
    rows = []
    first_b2: dict = {}
    week6 = pd.Timestamp("2025-11-24", tz="UTC").value
    for r in W.itertuples():
        day = pd.Timestamp(int(r.t_in), tz="UTC").tz_convert(L.TH).date()
        R2, note = r.R, ""
        if r.piece == "Asia B2":
            if day in first_b2:
                if r.t_in < week6:
                    R2, note = np.nan, "skipped: second B2 of the morning (weeks 4-5 rule)"
                elif r.side != first_b2[day]:
                    R2, note = np.nan, "skipped: a flip against the morning's first B2"
            else:
                first_b2[day] = r.side
        elif r.piece == "London ORB" and r.t_in >= pd.Timestamp("2025-11-17", tz="UTC").value:
            t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
            f = int(np.searchsorted(t, int(r.t_in)))
            px, _, kind = C.manage(t, bid, ask, f, r.entry, r.side, r.stop, r.entry + r.side * ORB_TP * r.risk, int(t[f]) + 60 * MIN)
            R2, note = (px - r.entry) * r.side / r.risk, f"TP {ORB_TP} R: {kind}"
        rows.append(dict(t=L.th(r.t_in), piece=r.piece, side="BUY" if r.side > 0 else "SELL", base_R=r.R, rules_R=R2, note=note))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    D = apply(sys.argv[1], sys.argv[2])
    for r in D.itertuples():
        print(f"{r.t} {r.piece:11s} {r.side:4s} base {r.base_R:+.2f} | rules {r.rules_R:+.2f} {r.note}")
    print(f"week: base {len(D)} trades {D.base_R.sum():+.2f} R | rules {D.rules_R.notna().sum()} trades {D.rules_R.sum():+.2f} R")
