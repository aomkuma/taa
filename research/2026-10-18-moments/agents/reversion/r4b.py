"""Round 4b: stop orders through round numbers vs placebo levels (notes.md). Development only."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from common import DEV, SLIP
from sim import one_at_a_time, simulate
import r4

warnings.filterwarnings("ignore")
B, atr = r4.B, r4.atr


def run(S, shift, D, k, m_, hold=120, valid=15):
    i, side, off = r4.orders(S, shift, D)
    side = -side  # through the level: below -> sell stop, above -> buy stop
    d = simulate(B, i, side, k * atr[i], m_ * atr[i], hold, off, valid, stop_entry=True)
    rows = []
    for name, a, b in DEV:
        ia, ib = B.idx(a), B.idx(b)
        t = one_at_a_time(d[(d.i >= ia) & (d.i < ib)])
        f = t[t.filled]
        rows.append(dict(half=name[:2], n=len(f), R=(f.usd / (f.sl + SLIP)).mean(), usd=f.usd.sum(),
                         win=(f.exit == "win").mean()))
    return pd.DataFrame(rows).set_index("half")


if __name__ == "__main__":
    for S in (5.0, 10.0):
        for D in (2.0, 4.0):
            for k, m_ in ((3, 3), (4, 6), (6, 6)):
                res = {nm: run(S, S * sh, D, k, m_) for nm, sh in (("round", 0.0), ("p37", 0.37), ("p63", 0.63))}
                r = res["round"]
                pl = (res["p37"].R + res["p63"].R) / 2
                print(f"S {S:>4} D {D} {k}/{m_}: round R " + " ".join(f"{v:+.3f}" for v in r.R)
                      + f" | mean {r.R.mean():+.3f} placebo {pl.mean():+.3f} beats {int((r.R > res['p37'].R).sum() + (r.R > res['p63'].R).sum())}/10"
                      + f" | n {int(r.n.sum())} win {r.win.mean():.2f} USD {r.usd.sum():+.0f}", flush=True)
    _ = np
