"""The measurer's re-derivation of exam43's trades from the raw ticks with its own loop (check_plan1.manage):
the fill = the first tick at / after t_in (a buy at the ask, a sell at the bid); the stop at the trade's risk; the
target 1 R (RT_opp) or 2 R (RC_win); out at the first tick at / after the fill + 120 min.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_exam43.py [trades.parquet] [exam]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import check_plan1 as C

f = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[1] / "strategist" / "exam43_trades_learn.parquet"
if "exam" in sys.argv[2:]:
    C.EXAM = pd.Timestamp("2026-10-18", tz="UTC")
T = pd.read_parquet(f)
rows = []
for r in T.itertuples():
    t0 = pd.Timestamp(int(r.t_in), tz="UTC")
    t, bid, ask = C.day_ticks(t0.normalize())
    nxt = t0.normalize() + pd.Timedelta(days=1)
    if int(r.t_in) + 125 * 60 * 10**9 > nxt.value and nxt < C.EXAM:
        n2 = C.day_ticks(nxt)
        if n2 is not None:
            t, bid, ask = np.r_[t, n2[0]], np.r_[bid, n2[1]], np.r_[ask, n2[2]]
    i = int(np.searchsorted(t, int(r.t_in), side="left"))
    e = ask[i] if r.side > 0 else bid[i]
    k = 1.0 if r.stream == "RT_opp" else 2.0
    out = C.manage(t, bid, ask, i, e, r.side, e - r.side * r.risk, e + r.side * k * r.risk, int(t[i]) + 120 * 60 * 10**9)
    px, tx, kind = out
    rows.append(dict(stream=r.stream, part=r.part, d_entry=e - r.entry, mine_R=(px - e) * r.side / r.risk, R=r.R,
                     same_exit=kind == r.exit))
D = pd.DataFrame(rows)
D["dR"] = (D.mine_R - D.R).abs()
for (s, p), g in D.groupby(["stream", "part"]):
    print(f"{s:6s} {p:4s}: {len(g)} trades, entry |diff| max {g.d_entry.abs().max():.3f}, same exit {g.same_exit.mean():.2f}, "
          f"|dR| max {g.dR.max():.4f} (> 0.01: {(g.dR > 0.01).sum()}), mine R {g.mine_R.mean():+.3f} vs {g.R.mean():+.3f}")
