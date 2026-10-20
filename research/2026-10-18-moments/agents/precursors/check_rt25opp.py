"""The measurer's re-derivation of the strategist's lead (RT_25 opposite side, stop x1, target 1 x the stop distance)
from the raw ticks with the measurer's own fill / exit loop (check_plan1.manage): the entry at the tick at entry_t
(a buy at the ask, a sell at the bid, slippage 0), the stop mirrored at the rule's distance, the 1 R target, the time exit at t_out.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_rt25opp.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import check_plan1 as C
from pathlib import Path

T = pd.read_parquet(Path(__file__).parents[1] / "strategist" / "transform_trades.parquet")
X = T[(T.family == "RT_25") & (T.side_v == "opp") & (T.stop_m == 1.0) & (T.tgt == "1R0")].reset_index(drop=True)
rows = []
for r in X.itertuples():
    t_in = pd.Timestamp(int(r.entry_t), tz="UTC")
    tk = C.day_ticks(t_in.normalize())
    t, bid, ask = tk
    nxt = t_in.normalize() + pd.Timedelta(days=1)
    if int(r.t_out) > nxt.value and nxt < C.EXAM:
        n2 = C.day_ticks(nxt)
        if n2 is not None:
            t, bid, ask = np.r_[t, n2[0]], np.r_[bid, n2[1]], np.r_[ask, n2[2]]
    f = int(np.searchsorted(t, t_in.value, side="left"))
    e = ask[f] if r.side > 0 else bid[f]
    risk = r.risk  # the opposite side: the stop mirrored at the rule's distance (stop_px is the rule's own side)
    px, tx, kind = C.manage(t, bid, ask, f, e, r.side, e - r.side * risk, e + r.side * risk, int(r.t_out))
    rows.append(dict(part=r.part, mine_R=(px - e) * r.side / risk, theirs_R=r.R, mine_exit=kind, theirs_exit=r.exit,
                     d_entry=e - r.entry))
D = pd.DataFrame(rows)
D["dR"] = (D.mine_R - D.theirs_R).abs()
print(f"{len(D)} trades; |dR| max {D.dR.max():.4f}; > 0.01 in {(D.dR > 0.01).sum()}; exit kind differs in "
      f"{(D.mine_exit != D.theirs_exit).sum()}; |entry diff| max {D.d_entry.abs().max():.3f}")
for p in ("P1", "P2"):
    g = D[D.part == p]
    print(f"  {p}: {len(g)} trades, mine R {g.mine_R.mean():+.3f} (win {(g.mine_R > 0).mean():.2f}), theirs {g.theirs_R.mean():+.3f}")
print(D[D.dR > 0.01].head(10).to_string())
