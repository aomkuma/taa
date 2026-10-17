"""The release-minute straddle on M1 history (A and B), worst-case ordering: a buy stop at open + D, a sell stop at
open - D, exit at the release minute's close, stop S beyond the fill. One M1 bar cannot show the order inside it,
so: if both triggers lie inside the bar, the trade is counted as the wrong side first, stopped at -S (or, when the
range cannot reach S, closed at the close on the losing side); if one trigger, the bar's adverse extreme is
assumed to come after the fill. Fill gap: GAP USD beyond the trigger (ticks 2025-10 .. 2026-02: median ~0.4,
mean ~1.7). D, S in USD at a gold price of 4000, scaled by price.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/straddle_m1.py [--test]
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import SLIP, Gold, events  # noqa: E402

TEST = "--test" in sys.argv
GAP = float(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else 1.0
MAINS = ("CPI", "NFP", "PPI", "FOMC", "RET")


def one(o, h, lo, c, sp, D, S, G=None, i=None, hold=1):
    up, dn = o + sp + D, o - D  # the buy trigger on the ask, the sell trigger on the bid
    hit_up, hit_dn = h + sp >= up, lo <= dn
    if not (hit_up or hit_dn):
        return None
    if hit_up and hit_dn:  # whipsaw: the wrong side first, worst case
        s = 1 if c < o else -1
        entry = (up + GAP + SLIP) if s > 0 else (dn - GAP - SLIP)
        adv = (lo - entry) if s > 0 else (entry - h - sp)
        how = "whip"
    else:
        s = 1 if hit_up else -1
        entry = (up + GAP + SLIP) if s > 0 else (dn - GAP - SLIP)
        adv = (lo - entry) if s > 0 else (entry - h - sp)
        how = "time"
    if adv <= -S:
        return s, -S - SLIP, "stop" if how == "time" else "whip"
    for j in range(i + 1, i + hold):  # later bars: the stop on each bar's extreme
        a2 = (G.lo[j] - entry) if s > 0 else (entry - G.h[j] - G.sp[j])
        if a2 <= -S:
            return s, -S - SLIP, "stop"
    x = i + hold - 1
    ex = (G.c[x] - SLIP) if s > 0 else (G.c[x] + G.sp[x] + SLIP)
    return s, (ex - entry) * s, how


def main() -> None:
    G = Gold()
    ev = events(extra=True)
    ev = ev[ev.per == "T"] if TEST else ev[ev.per != "T"]
    rows = []
    for r in ev.itertuples():
        i = G.pos.get(r.t)
        if i is None:
            continue
        i = int(i)
        k = G.c[i - 1] / 4000
        if r.main not in MAINS:
            continue
        for D, S, hold in itertools.product((0.5, 1, 2), (5, 8, 12), (1, 2, 5, 15)):
                out = one(G.o[i], G.h[i], G.lo[i], G.c[i], G.sp[i], D * k, S * k, G, i, hold)
                if out:
                    rows.append(dict(t=r.t, main=r.main, per=r.per, D=D, S=S, hold=hold, side=out[0], usd=out[1] / k,
                                     how=out[2], R=out[1] / (S * k + SLIP)))
    d = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    g = d.groupby(["main", "D", "S", "hold", "per"]).R.agg(["size", "mean"]).unstack("per").round(2)
    print(g.to_string())
    print(d.groupby(["main", "per"]).how.value_counts(normalize=True).unstack().round(2).to_string())
    d.to_parquet(f"research/2026-10-18-moments/agents/news/straddle_m1_{'test' if TEST else 'design'}_gap{GAP:g}.parquet")


if __name__ == "__main__":
    main()
