"""The journal's rules in force, applied to one week of PLAN-1 trades, trade by trade against the base.
Rules (each added forward only, journal PLAN1_JOURNAL.md):
- weeks 4-5 only: Asia B2 takes at most one trade a morning (deleted after week 5: it cost 1.01 R net);
- weeks 6-28: Asia B2's second trade of a morning only in the first trade's direction (no flip) - deleted after week 28
  (it cost 0.83 + 1.08 in weeks 27-28; weeks 1-28 net -0.98 R);
- from week 5: the London ORB's target is 1.5 R (re-simulated on the ticks: same entry, stop and 60-minute exit);
- from week 10: when the H4 ATR contracted over the last 24 h, the London ORB enters only if its 15 minutes before the
  decision broke a pool in its direction (liq_journal's "broke"); otherwise skipped;
- week 16 only: the NY straddle's stop was max(8 USD, 0.25 x H1 ATR) from the fill (re-simulated on the ticks, out at
  the decision + 30 minutes; R on the new risk) - deleted after week 16 (it cost 3.10 R that week, net -1.43 R on weeks
  1-16).
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
NY_STOP, NY_K = 8.0, 0.25


def apply(start: str, end: str) -> pd.DataFrame:
    A = pd.read_parquet(L.TRADES)
    for c in ("t_in", "t_out", "t_dec"):
        if not np.issubdtype(A[c].dtype, np.integer):
            A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    W = A[(A.t_in >= pd.Timestamp(start, tz="UTC").value) & (A.t_in < pd.Timestamp(end, tz="UTC").value)].sort_values("t_in")
    J = L.journal(start, end)  # same trades, same order: the pool break and the H4 ATR change per trade
    rows = []
    first_b2: dict = {}
    week10 = pd.Timestamp("2025-12-22", tz="UTC").value
    week16 = pd.Timestamp("2026-02-02", tz="UTC").value
    week17 = pd.Timestamp("2026-02-09", tz="UTC").value
    week29 = pd.Timestamp("2026-05-04", tz="UTC").value
    week6 = pd.Timestamp("2025-11-24", tz="UTC").value
    for r, j in zip(W.itertuples(), J.itertuples()):
        day = pd.Timestamp(int(r.t_in), tz="UTC").tz_convert(L.TH).date()
        R2, note, rk = r.R, "", r.risk
        if r.piece == "Asia B2":
            if day in first_b2:
                if pd.Timestamp("2025-11-10", tz="UTC").value <= r.t_in < week6:
                    R2, note = np.nan, "skipped: second B2 of the morning (weeks 4-5 rule)"
                elif week6 <= r.t_in < week29 and r.side != first_b2[day]:
                    R2, note = np.nan, "skipped: a flip against the morning's first B2"
            else:
                first_b2[day] = r.side
        elif r.piece == "London ORB" and r.t_in >= week10 and j.H4chg <= 0 and j.broke == "-":
            R2, note = np.nan, f"skipped: H4 ATR contracting ({j.H4chg:+d}%) and no pool broken"
        elif r.piece == "London ORB" and r.t_in >= pd.Timestamp("2025-11-17", tz="UTC").value:
            t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
            f = int(np.searchsorted(t, int(r.t_in)))
            px, _, kind = C.manage(t, bid, ask, f, r.entry, r.side, r.stop, r.entry + r.side * ORB_TP * r.risk, int(t[f]) + 60 * MIN)
            R2, note = (px - r.entry) * r.side / r.risk, f"TP {ORB_TP} R: {kind}"
        elif r.piece == "NY straddle" and week16 <= r.t_in < week17 and NY_K * j.H1atr > NY_STOP:
            risk = NY_K * j.H1atr
            t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
            f = int(np.searchsorted(t, int(r.t_in)))
            px, _, kind = C.manage(t, bid, ask, f, r.entry, r.side, r.entry - r.side * risk, None, int(r.t_dec) + 30 * MIN)
            rk = risk
            R2, note = (px - r.entry) * r.side / risk, f"stop {risk:.1f} (0.25 x H1 ATR {j.H1atr}): {kind}"
        rows.append(dict(t=L.th(r.t_in), piece=r.piece, side="BUY" if r.side > 0 else "SELL", base_R=r.R, rules_R=R2, note=note, rules_risk=rk))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    D = apply(sys.argv[1], sys.argv[2])
    for r in D.itertuples():
        print(f"{r.t} {r.piece:11s} {r.side:4s} base {r.base_R:+.2f} | rules {r.rules_R:+.2f} {r.note}")
    print(f"week: base {len(D)} trades {D.base_R.sum():+.2f} R | rules {D.rules_R.notna().sum()} trades {D.rules_R.sum():+.2f} R")
