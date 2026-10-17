"""After the RF test (so: a NEW rule, designed after seeing the test; design data only here, no test run):
RF2 = RF, but confirm the stall through the 10:00 ET slot: skip if 10:00-10:15 ET makes a new extreme beyond the
08-10 extreme (the move resumed, e.g. a 10:00 release); otherwise decide at the 10:15 close (stop from there).
Also: RF on days with a 10:00 JOLTS release (news agent's calendar) vs others.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/next1.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import cand  # noqa: E402
import fxlib as fx  # noqa: E402
import lab  # noqa: E402
import reltrades as rt  # noqa: E402

fx.below_normal_priority()
H = cand.H
WAIT = 15


def rf2(Ps, period):
    out = []
    for p in cand.PAIRS:
        P = Ps[p]
        ev = rt.build(P, 10, 14)
        ev = ev[ev.half.isin(period) & ev.rel].reset_index(drop=True)
        atr = ev.h1_atr.to_numpy()
        mv = ev.move.to_numpy()
        side = -np.sign(mv).astype(int)
        side[np.abs(mv) / atr < 1.0] = 0
        ext = np.where(side < 0, ev.whi.to_numpy(), ev.wlo.to_numpy())
        back = np.abs(ext - ev.px.to_numpy()) / (ev.whi - ev.wlo).to_numpy()
        side[back <= 0.10] = 0
        pre_share = (ev.pre.to_numpy() - P.o[ev.a.to_numpy()]) / np.where(mv == 0, np.nan, mv)
        side[~(pre_share <= 0.25)] = 0
        d = ev.d.to_numpy()
        d2 = d + WAIT
        ok = (d2 < P.n) & (P.tmin[np.minimum(d2, P.n - 1)] - P.tmin[d] == WAIT)
        newx = np.array([(P.h[a + 1:b + 1].max() > e) if s < 0 else (P.lo[a + 1:b + 1].min() < e) if s > 0 else False
                         for a, b, e, s in zip(d, np.minimum(d2, P.n - 1), ext, side)])
        side[~ok | newx] = 0
        e2 = ev.copy()
        e2["d"] = np.where(ok, d2, d)
        e2["hz"] = ev.hz - WAIT
        e2["px"] = P.c[e2.d.to_numpy()]
        sl = np.maximum(np.abs(ext - e2.px.to_numpy()) + 1.0 * atr, atr)
        side[sl * P.usd_pip[e2.d.to_numpy()] > 4.0] = 0
        z = lab.simulate(P, e2, side, sl, None)
        if len(z):
            z["pair"], z["day"] = p, ev.day.to_numpy()[z.ev]
            out.append(z)
    z = pd.concat(out, ignore_index=True)
    z["prio"] = z.pair.map({p: i for i, p in enumerate(cand.PAIRS)})
    return z.sort_values(["day", "prio"]).groupby("day").head(3).sort_values("t").reset_index(drop=True)


def main() -> None:
    Ps = {p: fx.Pair(p) for p in cand.PAIRS}
    rf = pd.read_parquet("research/2026-10-18-moments/agents/fx/rf_design.parquet")
    cand.line("RF (design)", rf)
    jol = pd.read_csv("research/2026-10-18-moments/agents/news/extra_releases.csv")
    jdays = set(pd.to_datetime(jol[jol.event == "JOL"].date))
    rf["jol"] = pd.to_datetime(rf.day).isin(jdays)
    print("  RF on JOLTS days:", rf[rf.jol].R.agg(["size", "mean"]).round(3).to_dict(), " other:",
          rf[~rf.jol].R.agg(["size", "mean"]).round(3).to_dict())
    cand.line("RF2 confirm through 10:15 (design)", rf2(Ps, H))


if __name__ == "__main__":
    main()
