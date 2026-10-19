"""Q7b - the mirror mechanism of Q7: the break of an everyone-sees level that FAILS (the close back inside), traded
back into the range - the owner's "fake break at the range edge" (dev2 entry 3) and the S1 / F1 fade of false breaks.

Written before computing (after reading Q7's result: the retest entries lost -0.22 / -0.39 R, 24 % / 23 % wins - the
broken level was mostly reclaimed; so this is a follow-up, not an independent test). Same levels, H and costs as
retest.py:
- the break as in retest.py (the first M5 close beyond the level by 0.1 H, from the other side);
- the reclaim: within 24 M5 bars (2 h) of the break, the first M5 close back inside by 0.1 H (a support: a close >
  L + 0.1 H) -> trade back into the range (a buy for a broken support) at the next M1 open;
- stop = the break's extreme since the break (the lowest low for a support) - 0.25 H; target 2 R; out after 120 min;
- reported all hours / the owner's windows / per level kind, P1 / P2.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/reclaim.py > .../strategist/out_reclaim.txt
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import mlib
import slib
from retest import (C5, D, H5, L5, MIN, atr, c, h, h_av, idx_of_day, in_window, indicators, lo, m5_av, o, spr, ti)

rows = []
OLD = len(sys.argv) > 1 and sys.argv[1] == "old"  # the older-years read: O1 2023-10-18 .. 2024-10-17, O2 .. 2025-10-17
FROM, TO = ("2023-10-18", "2025-10-18") if OLD else ("2025-10-18", "2026-04-18")
days = D.index[(D.index >= pd.Timestamp(FROM)) & (D.index < pd.Timestamp(TO))]
for d in days:
    got = idx_of_day(d)
    if got is None:
        continue
    idx, levels = got
    for kind, L, top, known in levels:
        brk_side = 1 if top == 1 else -1  # the way the level breaks: a top breaks up, a low breaks down
        cand = idx[m5_av[idx] > known]
        b = None
        for q in range(1, len(cand)):
            k, kp = cand[q], cand[q - 1]
            Hk = atr[indicators.at(h_av, np.array([m5_av[k]]))[0]]
            if (C5[k] - L) * brk_side > 0.1 * Hk and (C5[kp] - L) * brk_side <= 0:
                b = (q, Hk)
                break
        if b is None:
            continue
        q0, Hk = b
        ext = H5[cand[q0]] if brk_side > 0 else L5[cand[q0]]
        for q in range(q0 + 1, min(q0 + 25, len(cand))):
            k = cand[q]
            if (C5[k] - L) * brk_side < -0.1 * Hk:  # back inside: the break failed
                side = -brk_side
                i_in = np.searchsorted(ti, m5_av[k])
                if i_in >= len(ti):
                    break
                stop = ext - side * 0.25 * Hk
                e = o[i_in] + spr[i_in] + 0.07 if side > 0 else o[i_in] - 0.07
                risk = (e - stop) * side
                if risk > 0:
                    t_in = pd.Timestamp(ti[i_in], tz="UTC")
                    i_last = np.searchsorted(ti, ti[i_in] + 120 * MIN) - 1
                    res = mlib.trade(o, h, lo, c, spr, i_in, side, stop, e + side * 2 * risk, i_last,
                                     0.20 if in_window(t_in) == "NY" else 0.15)
                    if res:
                        rows.append(dict(day=d, kind=kind, side=side, t=t_in, part=(('O1' if t_in < pd.Timestamp('2024-10-18', tz='UTC') else 'O2') if OLD else slib.part_of(pd.DatetimeIndex([t_in]))[0]),
                                         win=in_window(t_in), pnl=res[0], risk=res[1], R=res[0] / res[1], exit=res[2], H=Hk))
                break
            ext = max(ext, H5[k]) if brk_side > 0 else min(ext, L5[k])

T = pd.DataFrame(rows)
T = T[T.part != ""]
T.to_parquet(slib.HERE / ("reclaim_trades_old.parquet" if OLD else "reclaim_trades.parquet"))
print(f"events (trades per part): {T.part.value_counts().to_dict()}; "
      f"median risk / H {np.median(T.risk / T.H):.2f}, median risk USD {T.risk.median():.1f}")
for p in (("O1", "O2") if OLD else ("P1", "P2")):
    x = T[T.part == p]
    print(f"{p} all hours   {slib.row(x)}  exits {x.exit.value_counts().to_dict()}")
    print(f"{p} in windows  {slib.row(x[x.win != 'other'])}")
    for w in ("Asia", "London", "NY", "other"):
        print(f"   {p} {w:7s} {slib.row(x[x.win == w])}")
    for k in ("PDH", "PDL", "ASH", "ASL"):
        print(f"   {p} {k}     {slib.row(x[x.kind == k])}")
