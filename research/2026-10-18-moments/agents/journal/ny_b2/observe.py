"""My own observations from weeks 18-19, measured on every NY-B2 trade up to END (nothing after):
1. the 10:00 New York data hour (22:00 Thai in winter, 21:00 in summer): entries before it whose 120-minute hold
   spans it, entries in its first 30 minutes, and entries after it
2. the stop width: USD and in H1 ATR(14) (at the 0.01 lot floor a wide stop weighs more in USD)

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/observe.py 2026-02-28
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
    X["r_real_all"] = W.realistic(X)
    h1 = W.Z.bars("H1")
    a = W._atr14(h1)
    X["h1atr"] = [float(a[a.index[a.index + pd.Timedelta(hours=1) <= t][-1]]) for t in X.t]
    X["stop"] = (X.entry_price - X.sl_initial).abs()
    X["stop_atr"] = X.stop / X.h1atr
    ny = X.t.dt.tz_convert("America/New_York")
    X["min_to_10et"] = (ny.dt.hour * 60 + ny.dt.minute) - 600  # negative = before 10:00 New York
    X["usd_real"] = X.r_real_all * X.stop  # one 0.01 lot: 1 USD of price = 1 USD

    def split(col: str, edges: list[float]) -> None:
        b = pd.cut(X[col], [-np.inf, *edges, np.inf])
        g = X.groupby(b, observed=True).agg(n=("r_multiple", "size"), base=("r_multiple", "sum"), real=("r_real_all", "sum"),
                                            win=("r_real_all", lambda s: (s > 0).mean() * 100), usd_real_001=("usd_real", "sum"))
        print(f"\n{col}\n{g.round(2).to_string()}")

    split("min_to_10et", [-120, -60, 0, 30])
    split("stop", [10, 15, 25, 40])
    split("stop_atr", [0.6, 0.9, 1.3, 2.0])
    print(f"\nall: {len(X)} trades base {X.r_multiple.sum():+.2f} real {X.r_real_all.sum():+.2f} real USD at 0.01 {X.usd_real.sum():+.2f}")


if __name__ == "__main__":
    main()
