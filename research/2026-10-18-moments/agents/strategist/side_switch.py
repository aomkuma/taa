"""A side switch for the break-and-retest events, written before computing (2026-10-20 ~13:25 Thai, after rt_old.py
showed the side flips by period: the continuation ~ +0.03 R in O1 / O2, the reclaim side +0.26 in P1 / P2): at each
event, take the side ('same' = with the break, 'opp' = back into the range) whose mean R over the last N events
(N = 20 / 40; only events entered before this one - their 120-minute trades are over within the 2 h hold, a lag of
at most one event is ignored here and named) was higher; target 1 R (x0.5), M1, mlib costs. Per period O1 / O2 / P1 / P2.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/side_switch.py > .../out_side_switch.txt
"""
import numpy as np
import pandas as pd

import slib

T = pd.read_parquet(slib.HERE / "rt_old_trades.parquet")
T = T[T.tgt == "x0.5 1R"]
S = T[T.side_v == "same"].reset_index(drop=True)
O = T[T.side_v == "opp"].reset_index(drop=True)
assert (S.t.values == O.t.values).all()
for N in (20, 40):
    rs, ro = S.R.to_numpy(), O.R.to_numpy()
    pick = np.full(len(S), "", dtype=object)
    for i in range(len(S)):
        if i < N + 1:
            continue
        a, b = rs[i - N - 1:i - 1].mean(), ro[i - N - 1:i - 1].mean()  # the last N events, skipping the one just before
        pick[i] = "same" if a > b else "opp"
    R = np.where(pick == "same", rs, np.where(pick == "opp", ro, np.nan))
    D = pd.DataFrame(dict(part=S.part, R=R, pick=pick)).dropna()
    print(f"N {N}: " + " | ".join(f"{p} n {len(D[D.part == p])} R {D[D.part == p].R.mean():+.3f} (opp picked {np.mean(D[D.part == p].pick == 'opp'):.2f})"
                               for p in ("O1", "O2", "P1", "P2")))
