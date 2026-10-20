"""PLAN-1's stopped losers, one by one (owner 2026-10-20: "have we learned from the losing trades?"). Learning parts
P1 / P2 only (dev/plan1_every_learn_s0_x0.parquet). For each London ORB / NY straddle trade stopped at -1 R: its path
from the fill to the end of its original window (ORB fill + 60 min, straddle 08:30 + 30 min) WITHOUT the stop, on the
ticks (the bid for a buy, the ask for a sell), in R of its own risk:
  - when the stop came (minutes after the fill);
  - the R at the window's end without the stop (end_R), the worst (MAE) and the best (MFE) without the stop;
  - the class: SWEPT (end_R > 0: the stop was taken, then price came back its way), FAKE (end_R <= -1.5: it ran on
    the other way - the reverse side paid), SLOW (between).
And for every trade of the piece, the same no-stop path, so a rule found on the losers is judged on all trades.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/plan1_losers.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import check_plan1 as C

DEV = Path(__file__).parents[1] / "dev"
MIN = 60 * 10**9


def window_end(r) -> int:
    return int(r.t_in) + 60 * MIN if r.piece == "London ORB" else int(r.t_dec) + 30 * MIN


def path(r) -> dict:
    t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
    f = int(np.searchsorted(t, int(r.t_in), side="left"))
    e = int(np.searchsorted(t, window_end(r), side="left"))
    px = (bid if r.side > 0 else ask)[f + 1:e + 1]
    tt = t[f + 1:e + 1]
    Rp = (px - r.entry) * r.side / r.risk
    stop_i = np.flatnonzero(Rp <= (r.stop - r.entry) * r.side / r.risk)
    return dict(end_R=float(Rp[-1]), MAE=float(Rp.min()), MFE=float(Rp.max()),
                stop_min=float((tt[stop_i[0]] - int(r.t_in)) / MIN) if len(stop_i) else np.nan,
                MFE_before_stop=float(Rp[:stop_i[0] + 1].max()) if len(stop_i) else float(Rp.max()))


def main() -> None:
    A = pd.read_parquet(DEV / "plan1_every_learn_s0_x0.parquet")
    for c in ("t_in", "t_out", "t_dec"):
        if not np.issubdtype(A[c].dtype, np.integer):
            A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    A = A[A.piece.isin(["London ORB", "NY straddle"])].reset_index(drop=True)
    A = pd.concat([A, pd.DataFrame([path(r) for r in A.itertuples()])], axis=1)
    A["cls"] = np.where(A.end_R > 0, "SWEPT", np.where(A.end_R <= -1.5, "FAKE", "SLOW"))
    S = A[A.exit == "stop"]
    for p, g in S.groupby("piece"):
        print(f"\n== {p}: {len(g)} stopped (of {(A.piece == p).sum()} trades)")
        print(f"   class: {g.cls.value_counts().to_dict()}")
        print(f"   minutes to the stop: median {g.stop_min.median():.1f}, <= 5 min {np.mean(g.stop_min <= 5):.0%}")
        print(f"   best R before the stop: median {g.MFE_before_stop.median():+.2f}, reached +0.5 R first {np.mean(g.MFE_before_stop >= 0.5):.0%}")
        for k, x in g.groupby("cls"):
            print(f"   {k:5s} {len(x):2d}: end_R without the stop median {x.end_R.median():+.2f}, MAE median {x.MAE.median():+.2f}, "
                  f"parts {x.part.value_counts().to_dict()}")
    print("\n== every trade, no stop (the window's end) vs the real result, R per trade (P1 / P2)")
    for p, g in A.groupby("piece"):
        for part in ("P1", "P2"):
            x = g[g.part == part]
            print(f"   {p:12s} {part}: real {x.R.mean():+.3f} | no stop {x.end_R.mean():+.3f} | stop x1.5 "
                  f"{np.where(x.MAE <= -1.5, -1.5, x.end_R).mean() / 1.5:+.3f} | stop x2 {np.where(x.MAE <= -2, -2, x.end_R).mean() / 2:+.3f}")
    A.to_parquet(Path(__file__).with_name("plan1_losers.parquet"))


if __name__ == "__main__":
    main()
