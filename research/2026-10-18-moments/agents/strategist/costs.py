"""Q8 - how much of R do the costs take, and what if the owner's real account spreads were wider than the demo ticks?

Written before computing: for the developer's W (P4) and B2 (P3) trades (news cost 0) and the strategist's ORB at
13:00 Thai (L15 k2 X60), the round-trip cost of one trade = the spread at the entry minute (M1 spread column x 0.01,
the demo tick spread) + 0.07 slippage, in R (/ the trade's risk); median and mean per part. Then the R lost if the real
spread were 1.5 / 2 / 3 x the demo's (the extra spread / risk). The owner's real-account spread is not known here:
a question for the owner, not a number.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/costs.py > .../strategist/out_costs.txt
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import slib

m = slib.m1("2025-10-18")
sp = (m.spread * 0.01)
print("demo M1 spread (USD), median by the owner's windows, P1 | P2:")
th = m.index.tz_convert(slib.TH)
mins = th.hour * 60 + th.minute
ny = m.index.tz_convert("America/New_York")
nm = ny.hour * 60 + ny.minute
win = np.where((mins >= 420) & (mins < 540), "Asia", np.where((mins >= 780) & (mins < 840), "London",
               np.where((nm >= 570) & (nm < 690), "NY", "other")))
part = slib.part_of(m.index)
for w in ("Asia", "London", "NY", "other"):
    print(f"  {w:7s} " + " | ".join(f"{p} {sp[(win == w) & (part == p)].median():.3f} (90 % {sp[(win == w) & (part == p)].quantile(0.9):.3f})"
                                      for p in ("P1", "P2")))


def cost_r(d: pd.DataFrame, label: str) -> None:
    i = np.searchsorted(m.index.asi8, pd.DatetimeIndex(d.t).as_unit("ns").asi8, side="right") - 1
    s = sp.to_numpy()[np.clip(i, 0, None)]
    cr = (s + 0.07) / d.risk.to_numpy()
    extra = s / d.risk.to_numpy()
    for p in ("P1", "P2"):
        k = (d.part == p).to_numpy()
        print(f"  {label:22s} {p}: cost / risk median {np.median(cr[k]):.3f}, mean {cr[k].mean():.3f}; R lost if the real "
              f"spread were 1.5 / 2 / 3 x: {0.5 * extra[k].mean():.3f} / {1.0 * extra[k].mean():.3f} / {2.0 * extra[k].mean():.3f}"
              f"  (median risk {d.risk[k].median():.1f} USD)")


print("\ncost in R:")
cost_r(slib.dev_trades("p4_trades_W_WL.parquet", "W"), "W (P4)")
cost_r(slib.dev_trades("p3_trades_all.parquet", "B2"), "B2 (P3)")
O = pd.read_parquet(slib.HERE / "orb_sens_trades.parquet")
O = O[(O.open == "13 Thai") & (O.L == 15) & (O.k == 2.0) & (O.X == 60) & O.per.isin(["P1", "P2"])].rename(columns={"per": "part"})
O["t"] = O.t0
cost_r(O, "ORB 13 Thai (at open)")
R = pd.read_parquet(slib.HERE / "reclaim_trades.parquet")
cost_r(R, "reclaim (Q7b)")
