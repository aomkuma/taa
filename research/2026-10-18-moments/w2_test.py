"""Round 11's one test (docs/OWN_SETUP.md): W2 (and the declared W3) on 2026-03-01 .. 10-13 - the journal agent's B0
with the losers' filters applied to the signals before the selection loop. Also re-runs them on the design data
the same way (the check that the filters on signals reproduce the trade-level step table).

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/w2_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

J = Path("research/2026-10-18-moments/agents/journal")
sys.path.insert(0, str(J))
import jlib  # noqa: E402
from rules import RULES, signals  # noqa: E402

FILTERS = {
    "B0": lambda s: np.ones(len(s), dtype=bool),
    "W2": lambda s: (s.cr_H1_leg_dir >= 0) & (s.h1_c_e50.abs() >= 0.85) & (s.pos240 >= 0.5),
    "W3": lambda s: (s.cr_H1_leg_dir >= 0) & (s.h1_c_e50.abs() >= 0.85) & (s.pos240 >= 0.75),
}


def main() -> None:
    jlib.gold.below_normal_priority()
    P = jlib.Instr("XAUUSD")
    rule = RULES["B0"]
    for part in ("design", "test"):
        D = jlib.cands("XAUUSD", part)
        D["e"] = P.e_of(D.t)
        sig = signals(D, rule, P)
        print(f"\n== {part}: B0 signal rows {len(sig)}")
        for name, f in FILTERS.items():
            s = sig[np.asarray(f(sig), dtype=bool)]
            r = jlib.run(s, P, rule["tp"], rule["be"], rule["hz"])
            if not len(r):
                print(f"  {name}: 0 trades")
                continue
            r["t"] = pd.to_datetime(r.t, utc=True)
            days = 520 if part == "design" else pd.bdate_range("2026-03-01", "2026-10-13").size
            by_m = r.pnl.groupby(r.t.dt.strftime("%Y-%m")).sum()
            eq = r.pnl.cumsum()
            streak = mx = 0
            for v in r.pnl:
                streak = streak + 1 if v < 0 else 0
                mx = max(mx, streak)
            print(f"  {name}: {len(r)} trades ({len(r) / days:.2f}/day), win {100 * (r.exit == 'win').mean():.0f}%, R {r.R.mean():+.3f}, "
                  f"{r.pnl.sum():+.1f} USD at 0.01 lot, months+ {(by_m > 0).sum()}/{len(by_m)}, worst {r.pnl.min():.2f}, "
                  f"max DD {(eq.cummax() - eq).max():.1f}, longest losing streak {mx}")
            if part == "test":
                print("     by month: " + "  ".join(f"{m} {v:+.1f}({int((r.t.dt.strftime('%Y-%m') == m).sum())})" for m, v in by_m.items()))
                for sname, g in r.groupby("session"):
                    print(f"     {['Asia', 'London', 'New York'][int(sname)]}: {len(g)} trades, R {g.R.mean():+.3f}, {g.pnl.sum():+.1f} USD")
                los = r[(r.exit == "stop") & (r.pnl < 0)]
                print(f"     stopped losers {len(los)}: kinds {los.kind.value_counts(normalize=True).round(2).to_dict()}")
                r.to_parquet(f"data/research/own_{name}_test.parquet")


if __name__ == "__main__":
    main()
