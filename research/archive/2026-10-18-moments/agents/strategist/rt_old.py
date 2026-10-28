"""The lead RT_25 opp (the break-and-retest entries traded the other way, back into the range) on the older years, as a
regime label only (never to choose a setting): retest.py's events exactly (its functions and loop copied, M1, the
mlib costs - 0.07 USD entry, 0.15 / 0.20 stop slippage, heavier than the spread-only ticks), with the side flipped, the
stop at the rule's distance on the other side, targets 2 R (orig) and 1 R (x0.5), out after 120 minutes. P1 / P2 are
re-run the same way so the M1 numbers can be compared with the ticks. O1 = 2023-10-18 .. 2024-10-17, O2 = .. 2025-10-17.
Written after seeing the P1 / P2 lead (a label, not a test).

    STRAT_START=2023-09-15 .venv/Scripts/python research/2026-10-18-moments/agents/strategist/rt_old.py > .../out_rt_old.txt
"""

from __future__ import annotations

import os

os.environ.setdefault("STRAT_START", "2023-09-15")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import mlib  # noqa: E402
import slib  # noqa: E402
from retest import C5, D, H5, L5, MIN, atr, c, h, h_av, idx_of_day, in_window, indicators, lo, m5_av, o, spr, ti  # noqa: E402


def label(t: pd.Timestamp) -> str:
    if t < pd.Timestamp("2023-10-18", tz="UTC"):
        return ""
    if t < pd.Timestamp("2024-10-18", tz="UTC"):
        return "O1"
    if t < pd.Timestamp("2025-10-18", tz="UTC"):
        return "O2"
    return slib.part_of(pd.DatetimeIndex([t]))[0]


rows = []
for d in D.index[(D.index >= pd.Timestamp("2023-10-18")) & (D.index < pd.Timestamp("2026-04-18"))]:
    got = idx_of_day(d)
    if got is None:
        continue
    idx, levels = got
    for kind, L, top, known in levels:
        side = 1 if top == 1 else -1
        cand = idx[m5_av[idx] > known]
        if len(cand) < 3:
            continue
        b = None
        for q in range(1, len(cand)):
            k, kp = cand[q], cand[q - 1]
            Hk = atr[indicators.at(h_av, np.array([m5_av[k]]))[0]]
            if side < 0 and C5[k] < L - 0.1 * Hk and C5[kp] >= L:
                b = (q, Hk)
                break
            if side > 0 and C5[k] > L + 0.1 * Hk and C5[kp] <= L:
                b = (q, Hk)
                break
        if b is None:
            continue
        q0, Hk = b
        r = None
        for q in range(q0 + 1, min(q0 + 37, len(cand))):
            k = cand[q]
            if (C5[k] - L) * side < -0.75 * Hk:
                break
            if (side < 0 and H5[k] >= L - 0.15 * Hk) or (side > 0 and L5[k] <= L + 0.15 * Hk):
                r = q
                break
        if r is None:
            continue
        ext = H5[cand[r]] if side < 0 else L5[cand[r]]
        lowest = L5[cand[r]] if side < 0 else H5[cand[r]]
        for q in range(r + 1, min(r + 13, len(cand))):
            k = cand[q]
            if (C5[k] - L) * side < -0.75 * Hk:
                break
            turned = (C5[k] < lowest) if side < 0 else (C5[k] > lowest)
            if turned and (C5[k] - L) * side > -0.5 * Hk:
                i_in = np.searchsorted(ti, m5_av[k])
                if i_in >= len(ti):
                    break
                stop = ext + 0.25 * Hk if side < 0 else ext - 0.25 * Hk
                e = o[i_in] + spr[i_in] + 0.07 if side > 0 else o[i_in] - 0.07
                risk = (e - stop) * side
                if risk > 0:
                    t_in = pd.Timestamp(ti[i_in], tz="UTC")
                    i_last = np.searchsorted(ti, ti[i_in] + 120 * MIN) - 1
                    s2 = -side  # the other way
                    e2 = o[i_in] + spr[i_in] + 0.07 if s2 > 0 else o[i_in] - 0.07
                    st2 = e2 - s2 * risk
                    ss = 0.20 if in_window(t_in) == "NY" else 0.15
                    for tg, k_r in (("orig 2R", 2.0), ("x0.5 1R", 1.0)):
                        for sname, sd, en, sp_ in (("same", side, e, stop), ("opp", s2, e2, st2)):
                            res = mlib.trade(o, h, lo, c, spr, i_in, sd, sp_, en + sd * k_r * risk, i_last, ss)
                            if res:
                                rows.append(dict(part=label(t_in), kind=kind, win=in_window(t_in), tgt=tg, side_v=sname,
                                                 R=res[0] / res[1], pnl=res[0], H=Hk, t=t_in))
                break
            ext = max(ext, H5[k]) if side < 0 else min(ext, L5[k])
            lowest = min(lowest, L5[k]) if side < 0 else max(lowest, H5[k])

T = pd.DataFrame(rows)
T = T[T.part != ""]
for (sv, tg), g in T.groupby(["side_v", "tgt"]):
    print(f"{sv:4s} {tg:8s} " + " | ".join(f"{p} n {len(g[g.part == p]):3d} R {g[g.part == p].R.mean():+.3f} win "
                                          f"{(g[g.part == p].pnl > 0).mean():.2f}" for p in ("O1", "O2", "P1", "P2")))
print("\nopp x0.5 1R by the owner's windows / other hours:")
g = T[(T.side_v == "opp") & (T.tgt == "x0.5 1R")]
for w, y in g.groupby(g.win.eq("other").map({True: "other", False: "windows"})):
    print(f"  {w:8s} " + " | ".join(f"{p} n {len(y[y.part == p]):3d} R {y[y.part == p].R.mean():+.3f}" for p in ("O1", "O2", "P1", "P2")))
T.to_parquet(slib.HERE / "rt_old_trades.parquet")
print("\nopp x0.5 1R by the H1 ATR at the event (USD; fixed bins, a label written after the lead):")
g = T[(T.side_v == "opp") & (T.tgt == "x0.5 1R")].copy()
g["Hb"] = pd.cut(g.H, [0, 6, 10, 15, 25, 1000])
print(g.groupby(["Hb", "part"], observed=True).R.agg(["mean", "size"]).unstack("part").round(3).to_string())
