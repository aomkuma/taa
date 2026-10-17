"""The one test of a frozen journal rule on 2026-03-01 .. 2026-10-14 (month by month, sessions, losers' kinds vs the
coin, the owner's account check). The window was already SEEN by the lead's W2/W3 run (round 11); every line says so.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/journal/test.py SYM RULE [RULE ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jlib  # noqa: E402
from rules import RULES, signals  # noqa: E402


def main() -> None:
    sym, names = sys.argv[1], sys.argv[2:]
    jlib.gold.below_normal_priority()
    P = jlib.Instr(sym)
    D = jlib.cands(sym, "test")
    D = D[(D.t >= jlib.TEST_START) & (D.t < jlib.TEST_END)]
    D["e"] = P.e_of(D.t)
    days = pd.bdate_range(jlib.TEST_START, jlib.TEST_END, inclusive="left").size
    unit = "USD" if sym == "XAUUSD" else "pips"
    k = 1.0 if sym == "XAUUSD" else 1.0 / P.pip
    for name in names:
        rule = RULES[name]
        sig = signals(D, rule, P)
        r = jlib.run(sig, P, rule["tp"], rule["be"], rule["hz"])
        cs = [jlib.run(sig, P, rule["tp"], rule["be"], rule["hz"], coin=np.random.default_rng(500 + s)) for s in range(20)]
        print(f"\n{sym} {name} - TEST 2026-03-01 .. 10-14 (window already SEEN in round 11): {rule['doc']}")
        if not len(r):
            print("  0 trades")
            continue
        by_m = r.groupby(r.t.dt.strftime("%Y-%m"))
        print(f"  {len(r)} trades ({len(r) / days:.2f}/day), win {100 * (r.exit == 'win').mean():.0f}%, {r.R.mean():+.3f} R/trade, "
              f"{k * r.pnl.sum():+.1f} {unit} at 0.01 lot, months+ {(by_m.pnl.sum() > 0).sum()}/{by_m.ngroups}; exits {r.exit.value_counts().to_dict()}")
        print("  account: " + jlib.account(r, P))
        print("  month     trades  win%   R/trade   P&L")
        for m, g in by_m:
            print(f"  {m}   {len(g):4}  {100 * (g.exit == 'win').mean():4.0f}  {g.R.mean():+.3f}  {k * g.pnl.sum():+8.1f}")
        for s, g in r.groupby("session"):
            print(f"  {jlib.SESS[int(s)]:8} {len(g):3} trades, win {100 * (g.exit == 'win').mean():3.0f}%, {g.R.mean():+.3f} R, {k * g.pnl.sum():+.1f} {unit}")
        cr = np.mean([c.R.mean() for c in cs])
        cw = np.mean([(c.exit == "win").mean() for c in cs])
        kc = np.mean([c.kind[c.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0).to_numpy() for c in cs], 0)
        print(f"  losers' kinds ours (1/2/3): {jlib.kinds(r)} %  | coin (20 seeds): {100 * kc[0]:.0f}/{100 * kc[1]:.0f}/{100 * kc[2]:.0f} %,"
              f" coin R {cr:+.3f}, coin win {100 * cw:.0f}%")
        extra = sig.loc[r.idx.to_numpy()].reset_index(drop=True)
        r = r.reset_index(drop=True)
        for col in extra.columns:
            if col not in r.columns:
                r[col] = extra[col].to_numpy()
        r.to_parquet(HERE / f"test_{sym}_{name}.parquet")


if __name__ == "__main__":
    main()
