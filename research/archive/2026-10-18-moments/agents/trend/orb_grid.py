"""Opening-range breakout grid on the design data only (2021-10 .. 2026-02, nine half-years).

Every (session, range length, stop, exit, hold, context filter) is scored in R a trade (net of the spread and the
slippage) per half-year; the table keeps the cells positive in most half-years.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/orb_grid.py
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402
import sim  # noqa: E402

EV = "research/2026-10-18-moments/agents/trend/orb_events.parquet"


def stops(d: pd.DataFrame, entry_signed: np.ndarray) -> dict[str, np.ndarray]:
    side = d.side.to_numpy()
    mid = ((d.hi + d.lo) / 2).to_numpy()
    opp = np.where(side > 0, d.lo, d.hi)
    fill = entry_signed * side  # the real fill price
    out = {
        "mid": (fill - mid) * side,
        "opp": (fill - opp) * side,
        "adr10": 0.10 * d.adr.to_numpy(),
        "adr15": 0.15 * d.adr.to_numpy(),
    }
    return out


def filters(d: pd.DataFrame) -> dict[str, np.ndarray]:
    s = d.side.to_numpy()
    with_h1 = np.where(s > 0, d.h1_up, d.h1_dn)
    against = np.where(s > 0, d.h1_dn, d.h1_up)
    pre = d.pre.to_numpy() * s
    return {
        "all": np.ones(len(d), bool),
        "withH1": with_h1,
        "notAgainstH1": ~against,
        "againstH1": against,
        "withPre": pre > 0,
        "withH1&pre": with_h1 & (pre > 0),
        "orRel<0.8": (d.or_rel < 0.8).to_numpy(),
        "orRel>1.25": (d.or_rel > 1.25).to_numpy(),
        "delay<=15": (d.delay <= 15).to_numpy(),
        "withH1&delay<=15": with_h1 & (d.delay <= 15).to_numpy(),
    }


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    ev = pd.read_parquet(EV)
    ev = ev[ev.t < lab.DESIGN_END].reset_index(drop=True)
    P = sim.paths(B, ev.e.to_numpy(), ev.side.to_numpy(), 200)
    ST = stops(ev, P["entry"])
    FI = filters(ev)
    halves = ev.half.to_numpy()
    hnames = [h[0] for h in lab.HALVES]
    exits = [("tp1", 1.0, None), ("tp1.5", 1.5, None), ("tp2", 2.0, None), ("tp3", 3.0, None),
             ("tp2be1", 2.0, "be"), ("trail1", None, "trail"), ("trail0.5", None, "trail05")]
    res = []
    for (sname, risk), (xname, tpm, mg), hz in itertools.product(ST.items(), exits, (120, 180)):
        ok = risk > 0.3
        rk = np.where(ok, risk, 1.0)
        kw = {}
        if mg == "be":
            kw = dict(be=1.0)
        elif mg == "trail":
            kw = dict(trail=rk, trail_start=rk)
        elif mg == "trail05":
            kw = dict(trail=rk, trail_start=0.5 * rk)
        tp = rk * tpm if tpm else None
        o = sim.run(P, rk, tp, hz, **kw)
        R = o["R"]
        for (sess, f), g in ev.groupby(["sess", "f"]).groups.items():
            gi = np.zeros(len(ev), bool)
            gi[np.asarray(g)] = True
            for fname, fm in FI.items():
                m = gi & fm & ok
                if m.sum() < 100:
                    continue
                hs = pd.Series(R[m]).groupby(halves[m]).mean().reindex(hnames)
                res.append(dict(sess=sess, f=f, stop=sname, exit=xname, hz=hz, filt=fname, N=int(m.sum()),
                                R=R[m].mean(), win=100 * (o["usd"][m] > 0).mean(), usd=o["usd"][m].mean(),
                                pos=int((hs > 0).sum()), worst=hs.min(), last=hs.iloc[-1], risk=rk[m].mean()))
    r = pd.DataFrame(res)
    r.to_parquet("research/2026-10-18-moments/agents/trend/orb_grid.parquet")
    pd.set_option("display.width", 220)
    print(f"{len(r)} cells")
    print("\nBaseline: every breakout, stop at the range mid, target 2R, 180 min, no filter")
    print(r[(r.filt == "all") & (r.stop == "mid") & (r.exit == "tp2") & (r.hz == 180)].round(3).to_string(index=False))
    print("\nMean R by filter (over all sessions/stops/exits):")
    print(r.groupby(["sess", "filt"]).R.mean().unstack().round(3).to_string())
    print("\nMean R by exit / stop:")
    print(r.groupby(["exit"]).R.mean().round(3).to_string())
    print(r.groupby(["stop"]).R.mean().round(3).to_string())
    print("\nTop 40 cells by halves positive, then R (N >= 150):")
    top = r[r.N >= 150].sort_values(["pos", "R"], ascending=False).head(40)
    print(top.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
