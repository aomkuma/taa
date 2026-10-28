"""The journal's account (owner 2026-10-21: "start from 100 USD plus the profit we have made"): the rules-in-force
trades from week 1, sized at 7.5 % of the current equity (the owner's preset), at least 0.01 lot, in 0.01 steps.
Gold: 0.01 lot = 1 oz, so a 1-USD move is 1 USD; P&L = R x risk (USD per oz) x lots x 100. Costs are in R (spread).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/account.py 2025-12-27 [2026-01-03]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_journal as L  # noqa: E402
import rules_week as RW  # noqa: E402

START, START_EQ, RISK_PCT = "2025-10-20", 100.0, 7.5
if os.environ.get("PLAN1_ACCOUNT"):  # "start,equity,risk %" - the exam weeks: 2026-04-18,300,3 (owner 2026-10-21)
    _s, _e, _r = os.environ["PLAN1_ACCOUNT"].split(",")
    START, START_EQ, RISK_PCT = _s, float(_e), float(_r)


def run(end: str) -> pd.DataFrame:
    D = RW.apply(START, end)
    A = pd.read_parquet(L.TRADES)
    A["t"] = pd.to_datetime(A.t_in, utc=True)
    W = A[(A.t >= pd.Timestamp(START, tz="UTC")) & (A.t < pd.Timestamp(end, tz="UTC"))].sort_values("t").reset_index(drop=True)
    D["risk"], D["t_utc"] = D.rules_risk.values, W.t.values  # the rules' risk (week 16: the straddle's wider stop)
    eq, rows = START_EQ, []
    for r in D.itertuples():
        if np.isnan(r.rules_R):
            continue
        lots = max(0.01, np.floor(eq * RISK_PCT / 100 / (r.risk * 100) * 100) / 100)
        usd = r.rules_R * r.risk * lots * 100
        eq += usd
        rows.append(dict(t=r.t, t_utc=r.t_utc, piece=r.piece, side=r.side, R=r.rules_R, risk=r.risk, lots=lots,
                         risk_pct=100 * r.risk * lots * 100 / (eq - usd), usd=usd, equity=eq))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    X = run(sys.argv[1])
    X["wk"] = pd.to_datetime(X.t_utc, utc=True).dt.tz_convert(L.TH).dt.strftime("%G-W%V")
    g = X.groupby("wk").agg(trades=("R", "size"), R=("R", "sum"), usd=("usd", "sum"), end=("equity", "last"))
    print(g.round(2).to_string())
    peak = np.maximum.accumulate(np.r_[START_EQ, X.equity.values])[1:]
    print(f"start {START_EQ:.2f} USD -> {X.equity.iloc[-1]:.2f} USD | worst trade {X.usd.min():.2f} | max drawdown {((X.equity - peak) / peak).min() * 100:.0f}%")
    if len(sys.argv) > 2:
        wk = X[X.t_utc >= np.datetime64(pd.Timestamp(sys.argv[2]).to_datetime64())]
        for r in wk.itertuples():
            print(f"{r.t} {r.piece:11s} {r.side:4s} R {r.R:+.2f} lots {r.lots:.2f} (risk {r.risk_pct:.1f}%) {r.usd:+.2f} USD -> {r.equity:.2f}")
