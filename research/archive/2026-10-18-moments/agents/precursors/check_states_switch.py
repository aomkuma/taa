"""The measurer's recomputation of the strategist's shadow-result switch (row 45) from states_events.parquet: a stream
trades an event only while the mean R of its last N events that exited before the entry is > 0. Streams: ORB, RC in
the owner's windows (win), RT_opp. Two readings of the start (fewer than N past events): trade / stand aside.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_states_switch.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

E = pd.read_parquet(Path(__file__).parents[1] / "strategist" / "states_events.parquet").dropna(subset=["R"])
S = {"ORB": E[E.stream == "ORB"], "RC_win": E[(E.stream == "RC") & (E.win != "other")], "RT_opp": E[E.stream == "RT_opp"]}
for n in (None, 20, 40, 60):
    for start in ("trade", "aside"):
        if n is None and start == "aside":
            continue
        tot = {p: 0.0 for p in ("O1", "O2", "P1", "P2")}
        for g in S.values():
            g = g.sort_values("t_in")
            ti, te, r = g.t_in.to_numpy(), g.t_exit.to_numpy(), g.R.to_numpy(float)
            for k in range(len(g)):
                if n is not None:
                    past = r[te < ti[k]]
                    if len(past) < n and start == "aside":
                        continue
                    if len(past) and past[-n:].mean() <= 0:
                        continue
                tot[g.part.iloc[k]] += r[k]
        print(f"N {n or 'always'} ({start}): " + "  ".join(f"{p} {v:+.1f}" for p, v in tot.items()))
