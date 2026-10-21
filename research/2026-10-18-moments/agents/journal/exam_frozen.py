"""The exam of the journal's frozen rules (PLAN1_JOURNAL.md "Frozen for the exam", 2026-10-21 19:15 Thai): the rules in
force after week 26 applied to PLAN-1's exam trades (dev/plan1_trades_exam_s0_x0.parquet, 2026-04-18 .. 2026-10-17), week by
week, with the account from 100 USD and continued from the learning parts' 1,710.98 USD. The measurer reads it ONCE.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/exam_frozen.py --exam
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if "--exam" not in sys.argv:
    sys.exit("the exam is read once, by the measurer: pass --exam")
os.environ["PLAN1_TRADES"] = "plan1_trades_exam_s0_x0.parquet"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_journal as L  # noqa: E402

L.C.EXAM = pd.Timestamp("2026-10-19", tz="UTC")  # the measurer's single exam reading lifts the tick guard
import account as ACC  # noqa: E402

START, END = "2026-04-18", "2026-10-18"


def sized(X: pd.DataFrame, eq0: float) -> pd.Series:
    eq, out = eq0, []
    for R, rk in zip(X.R, X.risk):
        lots = max(0.01, np.floor(eq * ACC.RISK_PCT / 100 / (rk * 100) * 100) / 100)
        eq += R * rk * lots * 100
        out.append(eq)
    return pd.Series(out, index=X.index)


if __name__ == "__main__":
    ACC.START, ACC.START_EQ = START, 100.0
    X = ACC.run(END)
    D = ACC.RW.apply(START, END)
    print(f"base {len(D)} trades {D.base_R.sum():+.2f} R ({D.base_R.mean():+.3f} a trade) | rules {D.rules_R.notna().sum()} trades "
          f"{D.rules_R.sum():+.2f} R ({D.rules_R.mean():+.3f} a trade)")
    for pc, g in D.groupby("piece"):
        print(f"  {pc:11s} base {len(g)} {g.base_R.sum():+.2f} | rules {g.rules_R.notna().sum()} {g.rules_R.sum():+.2f} ({g.rules_R.mean():+.3f})")
    for k in ("pool broken", "flip", "TP 1.5"):
        s = D[D.note.str.contains(k)]
        print(f"  rule '{k}': {len(s)} trades, rules minus base {(s.rules_R.fillna(0) - s.base_R).sum():+.2f} R")
    X["wk"] = pd.to_datetime(X.t_utc, utc=True).dt.tz_convert(L.TH).dt.strftime("%G-W%V")
    X["eq_cont"] = sized(X, 1710.98)
    g = X.groupby("wk").agg(trades=("R", "size"), R=("R", "sum"), usd=("usd", "sum"), end_100=("equity", "last"),
                            end_cont=("eq_cont", "last"))
    print(g.round(2).to_string())
    for col, s0 in (("equity", 100.0), ("eq_cont", 1710.98)):
        peak = np.maximum.accumulate(np.r_[s0, X[col].values])[1:]
        print(f"account from {s0:.2f}: -> {X[col].iloc[-1]:.2f} USD | deepest fall {((X[col] - peak) / peak).min() * 100:.0f}%")
    print(f"worst trade (from 100): {X.usd.min():.2f} USD")
