"""Agent "cross": why the London rule's losers lost (design trades of a steps.py config), concretely.
Adds the context of refine.py to each trade and compares stopped losers, time-exit losers and winners.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/losers.py s4 [design|test_NAME]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from fxlab import Inst  # noqa: E402
from measure import PANEL  # noqa: E402
from refine import context  # noqa: E402


def main() -> None:
    gold.below_normal_priority()
    tag = sys.argv[1]
    path = f"research/2026-10-18-moments/agents/cross/trades_{'design_' + tag if len(sys.argv) < 3 else sys.argv[2]}.csv"
    r = pd.read_csv(path, parse_dates=["t"])
    panel = pd.read_parquet(PANEL)
    parts = []
    for sym, g in r.groupby("sym"):
        inst = Inst(sym)
        ctx = context(inst, sym, panel, g.e.to_numpy() - 1, g.side.to_numpy())
        ctx["atr_ratio"] = ctx.rng60 / ctx.atr
        parts.append(pd.concat([g.reset_index(drop=True), ctx.reset_index(drop=True)], axis=1))
    x = pd.concat(parts, ignore_index=True)
    x["grp"] = np.where(x.exit == "win", "win", np.where(x.pnl < 0, np.where(x.exit == "stop", "stopped", "time-loss"), "time-gain"))
    x["dow"] = x.t.dt.dayofweek
    x["h1_against"] = x.h1 < 0
    x["slope_against"] = x.h1slope < 0
    x["at_extreme"] = x.pos > 0.85
    x["stretched"] = x.atr_ratio > 1.5
    x["own_moved"] = x.own30 > 0.5
    pd.set_option("display.width", 250)
    cols = ["h1_against", "slope_against", "at_extreme", "stretched", "own_moved", "rel"]
    print(x.groupby("grp")[cols + ["atr", "rng60", "own30", "usd30", "pos"]].mean().round(2).to_string())
    print(x.groupby("grp").size().to_dict())
    print("\nR by condition (True / False), n:")
    for c in cols:
        a, b = x[x[c]], x[~x[c]]
        print(f"  {c:14} {a.R.mean():+.3f} ({len(a)})  vs  {b.R.mean():+.3f} ({len(b)})")
    print("\nby hour:", x.groupby(x.t.dt.hour).R.agg(["mean", "size"]).round(3).T.to_string())
    print("by pair:", x.groupby("sym").R.agg(["mean", "size"]).round(3).T.to_string())
    print("by side:", x.groupby("side").R.agg(["mean", "size"]).round(3).T.to_string())
    x.to_csv(path.replace(".csv", "_ctx.csv"), index=False)


if __name__ == "__main__":
    main()
