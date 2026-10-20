"""Row 45, step 4 - written before computing, AFTER step 2 / 3 were seen (a follow-up, not an independent test):
the quarter table shows the leads paying in a time block (2025-Q4 .. 2026-Q1) rather than at a value of any reading.
The plainest present-detector is the stream's own shadow result: trade the stream only while the mean R of its last N
shadow trades (every event is simulated whether traded or not; exits before the entry only) is > 0. N = 20 / 40 / 60,
at least N / 2 earlier trades. 3 settings x 4 streams, nothing chosen: every cell printed. Per part: trades R (kept),
and the share of the part's events kept.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/states_switch.py > .../out_states_switch.txt
"""

import numpy as np
import pandas as pd

import readings
import slib

E = pd.read_parquet(slib.HERE / "states_readings.parquet")
PARTS = ("O1", "O2", "P1", "P2")
tot = {}


def total(k: pd.DataFrame) -> str:
    return " | ".join(f"{p} {k[k.part == p].R.sum():+6.1f}" for p in PARTS)


print("per part: kept trades, mean R, the share of the part's events kept; then the summed R per part")
for st in ("ORB", "RC_win", "RC_all", "RT_opp"):
    S = E[E.stream == st]
    te, rr = S.t_exit.to_numpy(np.int64), S.R.to_numpy(float)
    print(f"{st:7s} always    summed R: {total(S)}")
    tot.setdefault("always", []).append(S) if st != "RC_all" else None
    for n in (20, 40, 60):
        own = np.array([readings.own_trailing(te, rr, int(t), n=n, min_n=n // 2) for t in S.t_in])
        keep = own > 0
        k = S[keep]
        tot.setdefault(f"own{n}", []).append(k) if st != "RC_all" else None
        print(f"{st:7s} own{n:<3d} > 0: " + " | ".join(
            f"{p} {len(k[k.part == p]):3d} {k[k.part == p].R.mean() if len(k[k.part == p]) else float('nan'):+.3f} "
            f"({len(k[k.part == p]) / max(1, (S.part == p).sum()):.0%})" for p in PARTS))
        print(f"{'':17s} summed R: {total(k)}")
print("\nthe three leads together (ORB + RC_win + RT_opp), summed R per part:")
for key, ks in tot.items():
    print(f"  {key:7s} {total(pd.concat(ks))}")
