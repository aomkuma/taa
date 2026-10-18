"""Round 2, step 3 (notes.md): RUN-A's own levers on design data - A6/A7's filters (H1 tide with the run, no chase,
age <= 120 min) and the step-1 strength markers (a big run >= 3.7 M15 ATR, the 72-hour extreme broken), against
the stop (A7's pullback stop / beyond the run's start) and the exit (8 U with BE 0.6 / a trailing stop), each
turn signal on its own. Design only.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/levers.py [R15|A25]
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

HL = ["H1", "H2", "H3", "H4", "H5"]


def main() -> None:
    rules.gold.below_normal_priority()
    tag = sys.argv[1] if len(sys.argv) > 1 else "R15"
    P = rules.jlib.Instr("XAUUSD")
    AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_atr_usd"]).ad_atr_usd.reindex(P.ot).to_numpy()
    z = pd.read_parquet(HERE / f"study_{tag}_design.parquet")
    rows = []
    for r in z.itertuples():
        s, e, u = int(r.side), int(r.e), r.u
        entry = simlib.market_entry(P, e, s)
        ss = P.stop_slip_ny if r.t.hour >= 12 else P.stop_slip
        ad = float(AD[r.d])
        size = (r.ext - r.start) * s
        slP = max((entry - (r.pl - s * 0.3 * u)) * s, 0.5 * ad)
        slS = max((entry - (r.start - s * 0.3 * u)) * s, 0.5 * ad, 3.0)
        base = dict(t=r.t, half=r.half, tide=r.h1_tide == 1, nochase=r.m15_e20 <= 1.75, fresh=r.age <= 120,
                    big=r.size_atr >= 3.7, brk=bool(np.isfinite(r.lvl_h72) and r.lvl_h72 > 0), slP=slP, slS=slS)
        res = {}
        if 3.0 <= slP <= 10.0:
            x = simlib.trade(P, e, s, entry, slP, 8 * u, 0.6, 120, ss)
            res["P_T8"] = x["pnl"] / (slP + ss), x["pnl"], x["exit"], x["kind"]
            x = simlib.trade_trail(P, e, s, entry, slP, slP, 8 * u, 240, ss)
            res["P_trail"] = x["pnl"] / (slP + ss), x["pnl"], x["exit"], ""
        x = simlib.trade(P, e, s, entry, slS, 8 * u, 0.6, 120, ss)
        res["S_T8"] = x["pnl"] / (slS + ss), x["pnl"], x["exit"], x["kind"]
        x = simlib.trade(P, e, s, entry, slS, max((r.ext - entry) * s, 5.0), None, 120, ss)
        res["S_X_noBE"] = x["pnl"] / (slS + ss), x["pnl"], x["exit"], x["kind"]
        x = simlib.trade_trail(P, e, s, entry, slS, 0.3 * size, 0.3 * size, 240, ss)
        res["S_trail"] = x["pnl"] / (slS + ss), x["pnl"], x["exit"], ""
        x = simlib.trade_trail(P, e, s, entry, slS, 0.5 * size, 0.5 * size, 240, ss)
        res["S_trail50"] = x["pnl"] / (slS + ss), x["pnl"], x["exit"], ""
        for k, (R, pnl, ex, kind) in res.items():
            rows.append(base | dict(c=k, R=R, pnl=pnl, exit=ex, kind=kind))
    L = pd.DataFrame(rows)
    L.to_parquet(HERE / f"levers_{tag}_design.parquet")
    filt = {"all": L.index == L.index, "A6 (tide, nochase, fresh)": L.tide & L.nochase & L.fresh,
            "strong (big | brk72)": L.big | L.brk, "big & brk72": L.big & L.brk,
            "A6 & strong": L.tide & L.nochase & L.fresh & (L.big | L.brk), "fresh & strong": L.fresh & (L.big | L.brk),
            "fresh & big & brk72": L.fresh & L.big & L.brk}
    pd.set_option("display.width", 250)
    out = []
    for fn, sel in filt.items():
        for c, g in L[sel].groupby("c", sort=False):
            per = [g[g.half == h].R.mean() for h in HL]
            out.append(dict(filter=fn, c=c, n=len(g), win=(g.exit == "win").mean(), R=g.R.mean(), usd=g.pnl.sum(),
                            hpos=sum(v > 0 for v in per), **dict(zip(HL, per))))
    print(pd.DataFrame(out).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
