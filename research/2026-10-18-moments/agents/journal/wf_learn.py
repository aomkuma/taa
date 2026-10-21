"""The learning walk-forward (owner 2026-10-21: "learning must change the numbers"): every week each lever takes the
option that made the most R over the previous N weeks (default 8; a tie keeps the current option), applied to the next
week only. Levers: the London ORB (target 1.0 / 1.5 / 2.0 R / none x the pool rule on / off), the NY straddle's stop
(6 / 8 / 10 / 12 USD), Asia B2 (every trade / only with the previous week's direction / only with the D1 trend).
Inputs: variants.parquet (each trade under each option), context_learn / context_exam.parquet (known at the decision).
The account: 300 USD, 3 % a trade, at least 0.01 lot, from exam week 1.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/wf_learn.py [N] [LAST_WEEK]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AG = HERE.parents[0]
ORB = [(t, p) for t in ("orb_1.0", "orb_1.5", "orb_2.0", "orb_none") for p in (True, False)]
NY = ["ny_6", "ny_8", "ny_10", "ny_12"]
B2 = ["all", "prev_week", "d1_trend"]
EXAM_W1 = pd.Timestamp("2026-04-20")
# from exam week 6 (decided after week 5: the levers switched on margins as small as 0.02 R): switch only when the new
# option beats the current one by at least MARGIN R over the window
MARGIN, MARGIN_FROM = 1.0, 6
# from exam week 8 (decided after week 7: the 6-USD straddle stop led in R and trailed in USD): options are scored in
# USD at one 0.01 lot (R x the option's risk), the switch margin 10 USD
USD_FROM, USD_MARGIN = 8, 10.0


def load() -> pd.DataFrame:
    V = pd.read_parquet(HERE / "variants.parquet")
    T = pd.concat([pd.read_parquet(AG / "dev" / f"plan1_trades_{p}_s0_x0.parquet") for p in ("learn", "exam")])
    for c in ("t_in",):
        if not np.issubdtype(T[c].dtype, np.integer):
            T[c] = pd.to_datetime(T[c], utc=True).astype("int64")
    C = pd.concat([pd.read_parquet(HERE / f"context_{p}.parquet") for p in ("learn", "exam")])
    X = V.merge(T[["t_in", "side", "risk"]], on="t_in").merge(C, on="t_in")
    X["t"] = pd.to_datetime(X.t_in, utc=True)
    X["wk"] = X.t.dt.tz_convert("Asia/Bangkok").dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    X["pool_skip"] = (X.H4chg <= 0) & (X.broke == "-")
    return X.sort_values("t_in").reset_index(drop=True)


def r_orb(X: pd.DataFrame, opt) -> pd.Series:
    t, pool = opt
    return X[t].where(~(pool & X.pool_skip))


def r_ny(X: pd.DataFrame, opt) -> pd.Series:
    return X[opt]


def r_b2(X: pd.DataFrame, opt) -> pd.Series:
    if opt == "all":
        return X.base
    col = "prev_week" if opt == "prev_week" else "d1_trend"
    return X.base.where(X.side == X[col])


LEVERS = {"London ORB": (ORB, r_orb, ("orb_1.5", True)), "NY straddle": (NY, r_ny, "ny_8"), "Asia B2": (B2, r_b2, "all")}


def main(N: int, last: int) -> None:
    X = load()
    weeks = sorted(X.wk.unique())
    exam_weeks = [w for w in weeks if w >= EXAM_W1][:last]
    cur = {p: v[2] for p, v in LEVERS.items()}
    eq, rows, log = 300.0, [], []
    for i, w in enumerate(exam_weeks, start=1):
        window = [x for x in weeks if x < w][-N:]
        changes = []
        for p, (opts, f, _) in LEVERS.items():
            P = X[(X.piece == p) & X.wk.isin(window)]
            if i >= USD_FROM:
                risk = (lambda o: float(o[3:])) if p == "NY straddle" else (lambda o: P.risk)
                score = {str(o): float(np.nansum(f(P, o) * risk(o))) for o in opts}
            else:
                score = {str(o): float(np.nansum(f(P, o))) for o in opts}
            best = max(opts, key=lambda o: score[str(o)])
            need = USD_MARGIN if i >= USD_FROM else MARGIN if i >= MARGIN_FROM else 1e-9
            if score[str(best)] > score[str(cur[p])] + need:
                changes.append(f"{p}: {cur[p]} -> {best} ({score[str(cur[p])]:+.2f} -> {score[str(best)]:+.2f} over {N} weeks{', USD at 0.01 lot' if i >= USD_FROM else ''})")
                cur[p] = best
        Wk = X[X.wk == w]
        wk_R, wk_usd, n = 0.0, 0.0, 0
        for r in Wk.itertuples():
            p = r.piece
            R = LEVERS[p][1](Wk.loc[[r.Index]], cur[p]).iloc[0]
            if np.isnan(R):
                continue
            risk = float(cur[p][3:]) if p == "NY straddle" else r.risk
            lots = max(0.01, np.floor(eq * 3 / 100 / (risk * 100) * 100) / 100)
            usd = R * risk * lots * 100
            eq += usd
            wk_R += R
            wk_usd += usd
            n += 1
            rows.append(dict(week=i, t=r.t, piece=p, side=r.side, R=R, usd=usd, equity=eq))
        log.append(dict(week=i, start=w.date(), trades=n, R=round(wk_R, 2), usd=round(wk_usd, 2), equity=round(eq, 2),
                        settings=f"ORB {cur['London ORB']}, NY {cur['NY straddle']}, B2 {cur['Asia B2']}",
                        changes="; ".join(changes) or "-"))
    L = pd.DataFrame(log)
    pd.set_option("display.width", 250, "display.max_colwidth", 200)
    print(L.to_string(index=False))
    T = pd.DataFrame(rows)
    T.to_parquet(HERE / f"wf_learn_trades_N{N}.parquet")
    print(f"total: {len(T)} trades {T.R.sum():+.2f} R ({T.R.mean():+.3f} a trade); 300 -> {eq:.2f} USD")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8, int(sys.argv[2]) if len(sys.argv) > 2 else 26)
