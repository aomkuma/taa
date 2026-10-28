"""Round 2, step 2c (notes.md): the deep-limit family on design data - a trailing limit at the f retracement of an
R15 run, the stop beyond the run's start, the target at a fib extension of the run - over a small grid (f, the
target, break-even, the horizon), each run on its own, with the run's size in M15 ATRs and the 72-hour break known
at the fill. Design only.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/deep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402
import simlib  # noqa: E402

REF = 4100.0
SPLIT = pd.Timestamp("2026-03-01", tz="UTC")
HL = ["H1", "H2", "H3", "H4", "H5"]
FS = (0.5, 0.618, 0.786)
KS = (1.0, 1.272, 1.618, 2.0)


def main() -> None:
    rules.gold.below_normal_priority()
    P = rules.jlib.Instr("XAUUSD")
    AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_atr_usd"]).ad_atr_usd.reindex(P.ot).to_numpy()
    C = pd.read_parquet(HERE / "catalogue.parquet")
    C = C[(C.R == 15) & (C.t < SPLIT)].sort_values("t")
    C["half"] = pd.cut(C.t, rules.HALVES, labels=HL, right=False)
    h72 = pd.Series(P.h, index=P.ot).rolling("72h").max().to_numpy()
    l72 = pd.Series(P.lo, index=P.ot).rolling("72h").min().to_numpy()
    ot = P.ot
    rows = []
    for r in C.itertuples():
        s = int(r.side)
        i_s = ot.searchsorted(r.t)
        a = ot.searchsorted(r.t_tgt) + 1
        k0 = ot.searchsorted(r.t_end)
        b = min(i_s + 121, k0 + 60, len(ot) - 300)
        if a >= b:
            continue
        x0 = simlib.run_x0(P, i_s, a, s)  # fixed 2026-10-18: the start bar gives only its close
        lvl72 = h72[i_s - 1] if s > 0 else l72[i_s - 1]
        for f in FS:
            got = simlib.limit_fill(P, a, b, s, r.start_px, f, x0)
            if got is None:
                continue
            jf, entry, x = got
            t = ot[jf]
            if t.hour >= 20 or t.dayofweek >= 5:
                continue
            u = P.o[jf] / REF
            ss = P.stop_slip_ny if t.hour >= 12 else P.stop_slip
            size = (x - r.start_px) * s
            sl = max((entry - (r.start_px - s * 0.3 * u)) * s, 0.5 * float(AD[jf - 1]), 3.0)
            base = dict(t=t, half=r.half, side=s, f=f, size_atr=size / r.atr15, brk72=float((x - lvl72) * s > 0),
                        sl=sl, age=(t - r.t).total_seconds() / 60, run_t=r.t, mins_to_R=r.mins_to_R)
            for k in KS:
                tp = max((r.start_px + s * k * size - entry) * s, 5.0)
                for be in (0.6, None):
                    for hz in (120, 240):
                        x_ = simlib.trade(P, jf, s, entry, sl, tp, be, hz, ss, fill_bar=True)
                        rows.append(base | dict(k=k, be=be or 0.0, hz=hz, tp=tp, exit=x_["exit"], pnl=x_["pnl"],
                                                R=x_["pnl"] / (sl + ss), kind=x_["kind"], mins=x_["mins"]))
    L = pd.DataFrame(rows)
    L.to_parquet(HERE / "deep_long_design.parquet")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    out = []
    for thr in (0.0, 3.0, 3.7, 4.5, 5.5):
        for (f, k, be, hz), g in L[L.size_atr >= thr].groupby(["f", "k", "be", "hz"]):
            per = [g[g.half == h].R.mean() for h in HL]
            out.append(dict(thr=thr, f=f, k=k, be=be, hz=hz, n=len(g), win=(g.exit == "win").mean(), R=g.R.mean(),
                            usd=g.pnl.sum(), sl=g.sl.median(), tp=g.tp.median(), hpos=sum(v > 0 for v in per),
                            hmin=min(per), **dict(zip(HL, per))))
    T = pd.DataFrame(out)
    T.to_csv(HERE / "deep_design.csv", index=False)
    print(T.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
