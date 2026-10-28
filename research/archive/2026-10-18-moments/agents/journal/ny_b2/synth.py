"""The observation ledger of the NY-B2 journal (owner 2026-10-22: "do you turn the weekly observations into anything?"):
every field the journal records, measured on all trades up to END with the realistic variant unfiltered, and each
in-force rule's record before and after it took effect.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/synth.py 2026-03-07
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
    X = X.join(W.pressure(X)).join(W.context(X))
    ny = X.t.dt.tz_convert("America/New_York")
    X["m10"] = ny.dt.hour * 60 + ny.dt.minute - 600

    def split(col: str, edges: list[float]) -> None:
        b = pd.cut(X[col], [-np.inf, *edges, np.inf])
        g = X.groupby(b, observed=True).agg(n=("r", "size"), base=("r_multiple", "sum"), real=("r", "sum"),
                                            win=("r", lambda s: (s > 0).mean() * 100))
        print(f"\n{col}\n{g.round(2).to_string()}")

    for col, e in (("score", [-0.5, 3.5]), ("touches", [2.5, 4.5]), ("worn", [0.5, 1.5]), ("day_run", [-0.25, 0.25, 0.75]),
                   ("day_rng", [0.5, 1.0]), ("push3d", [-1.0, 0.0, 1.0])):
        split(col, e)
    rules = (("near line < 10 USD", W.NEAR_FROM, X.zone_line_dist < W.NEAR_USD),
             ("H1 vol > 1.1x", W.VOL_FROM, X.vol > W.VOL_MAX),
             ("10:00-10:30 New York", W.NEWS_FROM, (X.m10 > 0) & (X.m10 <= 30)))
    print("\nrule: the skipped trades' realistic R before / after the rule took effect (negative = the rule saved it)")
    for name, t0, m in rules:
        b, a = X[m & (X.t < t0)].r, X[m & (X.t >= t0)].r
        print(f"  {name}: before {b.sum():+.2f} on {len(b)} | after {a.sum():+.2f} on {len(a)}")
    print(f"\nall: {len(X)} trades base {X.r_multiple.sum():+.2f} real unfiltered {X.r.sum():+.2f}")


if __name__ == "__main__":
    main()
