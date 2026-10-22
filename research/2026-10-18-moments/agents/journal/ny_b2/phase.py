"""Week 21's question: is the market in a one-way run or swinging? The score rule (enter at multi-TF score <= -1) lost
in week 21's steady fall, the deleted zone-trend filter lost in week 12's grinding rally. Per NY-B2 entry up to END,
from closed D1 bars only:

- er5: the efficiency ratio of the last 5 closed days, |close - close 5 days ago| / the sum of the daily |changes|
  (1 = one way, 0 = back and forth)
- same: how many of the last 3 closed days closed the same way as the last one (1-3)
- since_shift: closed days since the owner's zone grid last shifted
and the score rule's split inside each phase (realistic variant, unfiltered).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/phase.py 2026-03-21
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import week as W


def main() -> None:
    end = pd.Timestamp(sys.argv[1], tz="UTC")
    X = W.load()
    X = X[X.t < end].sort_values("t").copy()
    X["r"] = W.realistic(X)
    X = X.join(W.context(X))
    d1 = W.Z.bars("D1")
    g = W.Z.daily_grid(d1)
    er, same, since = [], [], []
    for t in X.t:
        c = d1[d1.index + pd.Timedelta(days=1) <= t].close
        ch = c.diff().iloc[-5:]
        er.append(abs(c.iloc[-1] - c.iloc[-6]) / ch.abs().sum())
        s = np.sign(c.diff().iloc[-3:].values)
        same.append(int((s == s[-1]).sum()))
        k = g.index.searchsorted(t, side="right") - 1
        sh = np.flatnonzero(g["shift"].values[: k + 1] != "")
        since.append(k - sh[-1] if len(sh) else 99)
    X["er5"], X["same"], X["since_shift"] = er, same, since
    X["low_score"] = X.score <= W.SCORE_MAX

    def by(col: str, edges: list[float]) -> None:
        key = pd.cut(X[col], [-np.inf, *edges, np.inf])
        g = X.groupby([key, "low_score"], observed=True).r.agg(n="size", real="sum", win=lambda s: (s > 0).mean() * 100)
        print(f"\n{col} x score <= -1\n{g.round(2).to_string()}")

    by("er5", [0.3, 0.6])
    by("same", [1.5, 2.5])
    by("since_shift", [3, 10])
    print(f"\nall: {len(X)} trades real unfiltered {X.r.sum():+.2f}; score <= -1 {X.r[X.low_score].sum():+.2f} on {X.low_score.sum()}")


if __name__ == "__main__":
    main()
