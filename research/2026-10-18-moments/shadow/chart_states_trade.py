"""Round 14: trade the chosen chart states (docs/OWN_SETUP.md) - the side that reached 5 USD first in >= 4 of 5
design half-years (here: the M15 side when H1 and M15 disagree on a pullback), TP 5 / SL 5 (price-scaled), entry at
the M1 open after the M5 close, real costs, 60 minutes, one position at a time.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/chart_states_trade.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/shadow")
import chart_states as cs  # noqa: E402

P = cs.jlib.Instr("XAUUSD")
d = pd.read_parquet("data/research/own_chart_states.parquet")
CHOSEN = [(1, -1, "pullback", "squeeze", "NY"), (-1, 1, "pullback", "squeeze", "Asia"), (1, -1, "pullback", "normal", "Asia")]
m = np.zeros(len(d), bool)
for h1, m15, pos, sq, ses in CHOSEN:
    m |= ((d.h1 == h1) & (d.m15 == m15) & (d.pos == pos) & (d["squeeze"] == sq) & (d.session == ses)).to_numpy()
x = d[m].copy()
x["side"] = -x.h1  # the M15 side (the tide's side reached 5 first in only 36-42 %)
for part, a, b in (("design", "2023-11-01", "2026-03-01"), ("window 2026-03..10-16", "2026-03-01", "2026-10-17")):
    y = x[(x.index >= pd.Timestamp(a, tz="UTC")) & (x.index < pd.Timestamp(b, tz="UTC"))]
    out, free = [], pd.Timestamp(0, tz="UTC")
    for t, r in y.iterrows():
        if t < free:
            continue
        tr = P.trade(int(r.e), int(r.side), r.k, r.k, None, 60, P.stop_slip)
        tr |= dict(t=t, R=tr["pnl"] / (r.k + P.stop_slip))
        out.append(tr)
        free = t + pd.Timedelta(minutes=int(tr["mins"]))
    z = pd.DataFrame(out)
    eq = z.pnl.cumsum()
    per = z.groupby(z.t.dt.strftime("%Y-%m") if part.startswith("window") else pd.cut(z.t, cs.HALVES, right=False), observed=True).R.mean()
    print(f"{part}: {len(z)} trades, win {100 * (z.exit == 'win').mean():.0f}%, R {z.R.mean():+.3f}, {z.pnl.sum():+.1f} USD at 0.01 lot,"
          f" max DD {(eq.cummax() - eq).max():.1f} | " + " ".join(f"{v:+.2f}" for v in per))
