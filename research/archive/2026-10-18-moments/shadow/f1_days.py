"""Days with an entry (owner, 2026-10-18: "how can a day have no M5 entry at all?"): per weekday of the window,
whether the confluence base (B0 + stop 3-10 U) and F1 (+ C4 + C5) had at least one signal, by session.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_days.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402

P, D = plib.load("wtest")
D = D.reset_index(drop=True)
side = D.side.to_numpy()
sl0 = (P.fill(D.e.to_numpy(), side) - (D.level.to_numpy() - side * D.atr1.to_numpy())) * side
pa = (D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim).to_numpy()
ind = ((D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2).to_numpy()
base = D.tide.to_numpy(bool) & D.at_level.to_numpy(bool) & pa & ind & (sl0 >= 3 * D.unit) & (sl0 <= 10 * D.unit)
f1 = base & plib.MENU["C4 72-h extreme near/behind"](D).to_numpy(bool) & plib.MENU["C5 not a fast tape"](D).to_numpy(bool)
day = pd.to_datetime(D.t, utc=True).dt.normalize()
days = pd.bdate_range("2026-03-02", "2026-10-13", tz="UTC")
for name, m in (("base (tide + level + PA + 2/3 M5 + stop)", base), ("F1 (+ C4 72-h extreme + C5)", f1)):
    per = pd.Series(m).groupby(day).sum().reindex(days, fill_value=0)
    print(f"{name}: days with a signal {(per > 0).sum()} of {len(days)} ({(per > 0).mean():.0%})")
    for s, sn in plib.jlib.SESS.items():
        ps = pd.Series(m & (D.session == s).to_numpy()).groupby(day).sum().reindex(days, fill_value=0)
        print(f"    {sn:9} days with a signal {(ps > 0).mean():.0%}")
# where was price vs the 72-h extreme when the base fired? (C4 needs the close within 4 U of it, or beyond)
gap = ((D.front72 - D.c_dec) * D.side / D.unit)[base]
print("base signals: distance to the 72-h extreme in front (U):", " ".join(f"p{q}={np.nanpercentile(gap, q):.0f}" for q in (10, 25, 50, 75, 90)))
up = (D.side > 0).to_numpy()
print(f"base signals BUY {np.mean(up[base]):.0%}; F1 BUY {np.mean(up[f1]):.0%}")
