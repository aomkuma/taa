"""Account sizing on the frozen rules' trades (owner 2026-10-21: "300 USD at 3 % - safer?"): the learning parts and the
exam (the exam's trades were already read once; this only re-sizes them), each from its start equity, at least 0.01 lot.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/sizing.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "sizing_trades.parquet"


def trades() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_parquet(CACHE)
    code = (
        "import os,sys; sys.path.insert(0,r'%s'); import pandas as pd\n"
        "import liq_journal as L; L.C.EXAM=pd.Timestamp('2026-10-19',tz='UTC'); import rules_week as RW\n"
        "s,e,o=sys.argv[1:4]; D=RW.apply(s,e); D=D[D.rules_R.notna()]; D['part']=os.path.basename(o).replace('sizing_',''); D.to_parquet(o+'.parquet')\n" % HERE
    )
    parts = []
    for name, s, e, f in (("learn", "2025-10-20", "2026-04-18", "plan1_trades_learn_s0_x0.parquet"),
                          ("exam", "2026-04-18", "2026-10-18", "plan1_trades_exam_s0_x0.parquet")):
        env = dict(os.environ, PLAN1_TRADES=f)
        subprocess.run([sys.executable, "-c", code, s, e, str(HERE / f"sizing_{name}")], env=env, check=True)
        parts.append(pd.read_parquet(HERE / f"sizing_{name}.parquet"))
        (HERE / f"sizing_{name}.parquet").unlink()
    T = pd.concat(parts, ignore_index=True)[["part", "t", "piece", "rules_R", "rules_risk"]]
    T.to_parquet(CACHE)
    return T


def run(T: pd.DataFrame, eq0: float, pct: float) -> dict:
    eq, peak, mdd, low, over, worst, R_used = eq0, eq0, 0.0, eq0, 0, 0.0, []
    for R, rk in zip(T.rules_R, T.rules_risk):
        lots = max(0.01, np.floor(eq * pct / 100 / (rk * 100) * 100) / 100)
        risk_pct = 100 * rk * lots * 100 / eq
        over += risk_pct > pct * 1.5
        usd = R * rk * lots * 100
        worst = min(worst, usd / eq * 100)
        eq += usd
        peak, low = max(peak, eq), min(low, eq)
        mdd = min(mdd, (eq - peak) / peak)
        if eq <= 0:
            break
    return dict(end=eq, gain_pct=100 * (eq / eq0 - 1), low=low, mdd_pct=100 * mdd, worst_trade_pct=worst,
                over_share=100 * over / len(T))


if __name__ == "__main__":
    T = trades()
    print(T.groupby("part").rules_R.agg(["count", "sum", "mean"]).round(3))
    rows = []
    for part in ("learn", "exam"):
        X = T[T.part == part]
        for eq0, pct in ((100, 7.5), (300, 7.5), (300, 5), (300, 3), (300, 2), (500, 3), (1000, 3), (1000, 2)):
            rows.append(dict(part=part, start=eq0, risk=pct, **run(X, eq0, pct)))
    print(pd.DataFrame(rows).round(1).to_string(index=False))
