"""Round 4: resting limits at round numbers vs placebo levels (notes.md, round 4). Development only."""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

from common import DEV, SLIP
from sim import one_at_a_time, simulate
import r2

warnings.filterwarnings("ignore")
L = r2.L
B, F = L.B, L.F
atr = F.atr.to_numpy(float)
hi_roll = pd.Series(B.h).rolling(30).max().to_numpy()
lo_roll = pd.Series(B.lo).rolling(30).min().to_numpy()
window = (B.ldn_min >= 420) & (B.ny_min < 930) & F.ok60.to_numpy() & np.isfinite(atr)


def orders(S: float, shift: float, D: float):
    c = B.c
    below = np.floor((c - shift) / S) * S + shift
    above = below + S
    db, da = (c - below) / atr, (above - c) / atr
    okb = (db >= 0.5) & (db <= D) & (lo_roll > below)  # not traded in the last 30 bars
    oka = (da >= 0.5) & (da <= D) & (hi_roll < above)
    buy = okb & (~oka | (db <= da))
    sell = oka & ~buy
    m = window & (buy | sell)
    i = np.flatnonzero(m)
    i = i[i < B.n - 400]
    side = np.where(buy[i], 1, -1)
    off = np.where(side > 0, c[i] - below[i], above[i] - c[i])
    return i, side, off


def run(S, shift, D, k, m_, hold=120, valid=15):
    i, side, off = orders(S, shift, D)
    d = simulate(B, i, side, k * atr[i], m_ * atr[i], hold, off, valid)
    rows = []
    for name, a, b in DEV:
        ia, ib = B.idx(a), B.idx(b)
        t = one_at_a_time(d[(d.i >= ia) & (d.i < ib)])
        f = t[t.filled]
        rows.append(dict(half=name[:2], n=len(f), R=(f.usd / (f.sl + SLIP)).mean(), usd=f.usd.sum(),
                         win=(f.exit == "win").mean()))
    return pd.DataFrame(rows).set_index("half")


if __name__ == "__main__":
    for S in (5.0, 10.0, 50.0):
        for D in (2.0, 4.0):
            for k, m_ in ((3, 3), (4, 6), (6, 6)):
                res = {nm: run(S, S * sh, D, k, m_) for nm, sh in (("round", 0.0), ("p37", 0.37), ("p63", 0.63))}
                r = res["round"]
                pl = (res["p37"].R + res["p63"].R) / 2
                print(f"S {S:>4} D {D} {k}/{m_}: round R " + " ".join(f"{v:+.3f}" for v in r.R)
                      + f" | mean {r.R.mean():+.3f} placebo {pl.mean():+.3f} beats {int((r.R > res['p37'].R).sum() + (r.R > res['p63'].R).sum())}/10"
                      + f" | n {int(r.n.sum())} win {r.win.mean():.2f} USD {r.usd.sum():+.0f}", flush=True)
    _ = sys
