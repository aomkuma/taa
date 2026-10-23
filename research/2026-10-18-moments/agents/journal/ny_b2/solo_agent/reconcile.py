"""After the solo exam (2026-10-23): week 25's missing B2 trades (the stored bars had a hole 2026-10-05..12, refilled
and the bot re-run: ../exam_w25) added to the three lines, and the counterfactual the owner asked about - the realized
line had B2 not been stopped after week 1 (each signal under the exit and skip rules in force that week, from the
ledger), plus when a slower stop rule (below -3 R after at least 4 weeks and 10 trades) would have stopped B2.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/solo_agent/reconcile.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import week as W  # noqa: E402

W.C.EXAM = pd.Timestamp("2026-10-23", tz="UTC")


def main() -> None:
    L = pd.read_csv(HERE / "ledger.csv")
    L["t"] = pd.to_datetime(L.t, utc=True)
    W.HERE = HERE.parent / "exam_w25"
    X = W.load().sort_values("t").reset_index(drop=True)
    X["real"] = W.realistic(X, band=0.1)
    X["h90"] = W.realistic(X, band=0.1, hold=90)
    X = X.join(W.pressure(X))
    ny = X.t.dt.tz_convert("America/New_York")
    m10 = ny.dt.hour * 60 + ny.dt.minute - 600
    vol, near, news = X.vol > W.VOL_MAX, X.zone_line_dist < W.NEAR_USD, (m10 > 0) & (m10 <= 30)
    X["nolearn"] = X.real.where(~vol & ~near & ~news)  # the start state
    X["state25"] = X.h90.where(~vol & ~news)  # the agent's state in week 25: hold-90, rules vol + news
    print("week 25's B2 trades (after the refill):")
    print(X.assign(th=X.t.dt.tz_convert("Asia/Bangkok").dt.strftime("%m-%d %a %H:%M"))[["th", "side", "r_multiple", "real", "h90", "vol", "zone_line_dist", "nolearn", "state25"]].round(2).to_string())
    base = L[L.piece == "B2"].r_base.sum() + X.r_multiple.sum()
    nl = L.r_nolearn.sum() + X.nolearn.sum()
    print(f"\nwith week 25: base {base:+.2f} on {L[L.piece == 'B2'].r_base.notna().sum() + len(X)} | no-learning {nl:+.2f} on "
          f"{L.r_nolearn.notna().sum() + X.nolearn.notna().sum()} | realized {L.r_realized.sum():+.2f} on {L.r_realized.notna().sum()} (B2 stopped, unchanged)")
    # the counterfactual: B2 never stopped - every B2 signal under the exit and rules in force that week
    B = L[L.piece == "B2"].copy()
    rules = B.skipped_by.fillna("").str.replace("stopped", "").str.strip()
    B["cf"] = np.where(rules == "", B.r_cur, np.nan)
    cf = pd.concat([B[["week", "t", "side", "entry_price", "sl_initial", "cf"]],
                    X.assign(week=25, cf=X.state25)[["week", "t", "side", "entry_price", "sl_initial", "cf"]]])
    other = L[(L.piece != "B2") & L.r_realized.notna()][["week", "t", "side", "entry_price", "sl_initial", "r_realized"]].rename(columns={"r_realized": "cf"})
    A = pd.concat([cf, other]).sort_values("t").reset_index(drop=True)
    A = W.accounts(A, "cf", "x")
    g = A.groupby("week").agg(n=("cf", "count"), r=("cf", "sum"), b100=("balx_100", "last"), b300=("balx_300", "last"))
    print("\nB2 never stopped (plus the realized line's other pieces), by week:")
    print(g.round(2).T.to_string())
    print(f"total {A.cf.sum():+.2f} on {A.cf.notna().sum()} (B2 {cf.cf.sum():+.2f} on {cf.cf.notna().sum()}); 100 min {A.balx_100.min():.2f}, 300 end {A.balx_300.iloc[-1]:.2f}")
    # a slower stop: forward below -3 R after at least 4 weeks and 10 taken trades
    run, n = 0.0, 0
    for wk, s in cf.groupby("week").cf:
        run += s.sum()
        n += s.notna().sum()
        if wk >= 4 and n >= 10 and run < -3:
            print(f"slower stop rule: B2 would stop after week {wk} ({run:+.2f} R on {n})")
            break
    else:
        print(f"slower stop rule: B2 never stopped ({run:+.2f} R on {n})")


if __name__ == "__main__":
    main()
