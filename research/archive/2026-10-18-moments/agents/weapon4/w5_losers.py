"""W5a's design trades: why the losers lost. Buckets of features with a prior reason (F1's findings), R net / gross,
win %, the stopped losers' kinds, halves positive (net); design only.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w5_losers.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402
from gross_check import gross_run  # noqa: E402

P = w.instr("XAUUSD") if __name__ == "__main__" else None


def w5a(D):
    X = D.copy()
    X["n_ind"] = 2
    return w.signals(X, 3, 10, 8, 0.6, 60)


def feats(S, P):
    S = S.copy()
    p = S.e.to_numpy() - 1
    a = S.atr.to_numpy()
    s = S.side.to_numpy()
    for k in (15, 60):
        S[f"ret{k}"] = (P.c[p] - P.c[p - k]) * s / a
    S["c4u"] = ((S.front72 - S.c_dec) * S.side / S.unit)
    S["sl_u"] = S.sl / S.unit
    S["room_u"] = S.room / S.unit
    S["hour"] = pd.DatetimeIndex(S.t).hour
    # hours since the 72-h extreme in the trade's way was made (the latest bar at it, bars p-4320 .. p)
    W = 4320
    hs = np.empty(len(S))
    for i, (q, sd) in enumerate(zip(p, s)):
        seg = P.h[q - W + 1: q + 1] if sd > 0 else -P.lo[q - W + 1: q + 1]
        hs[i] = np.argmax(seg[::-1])  # bars since the latest bar at the extreme
    S["hrs_ext"] = hs / 60
    S["spr_atr"] = S.spread / S.atr
    return S


def main():
    global z
    D = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
    S = feats(w5a(D), P)
    z = w.run(S, P)
    zg = gross_run(S, P)
    key = ["t", "side"]
    z = z.merge(S, on=["t", "side"], suffixes=("", "_s"))
    z = z.merge(zg[["t", "side", "R"]].rename(columns={"R": "Rg"}), on=["t", "side"], how="left")
    z["half"] = w.plib.half_of(z.t)
    HN = [x[0] for x in w.HALVES]
    print(f"W5a design: {len(z)} trades, net {z.R.mean():+.3f}, gross {z.Rg.mean():+.3f}; kinds {w.plib.kinds(z)}")


    def table(col, bins, labels=None):
        b = pd.cut(z[col], bins, labels=labels) if bins is not None else z[col]
        print(f"\n  by {col}")
        for k, g in z.groupby(b, observed=True):
            hr = g.R.groupby(g.half).mean().reindex(HN)
            st = g[g.exit == "stop"]
            print(f"    {str(k):16} {len(g):4} win {100 * (g.exit == 'win').mean():3.0f}% net {g.R.mean():+.3f} gross {g.Rg.mean():+.3f}"
                  f" halves+ {(hr > 0).sum()}/{hr.notna().sum()} [{' '.join(f'{v:+.2f}' for v in hr.to_numpy())}]"
                  f" stops {len(st)} kinds {w.plib.kinds(g) if len(st) else '-'}")


    table("c4u", [-1e9, -4, 0, 2, 4])
    table("hour", [-1, 1.99, 6.99, 11.99, 16.99, 20])
    table("n_ind", [-1, 0, 1, 3])
    table("sl_u", [0, 4, 5.5, 7.5, 20])
    table("ret15", [-99, -1, 0, 1, 2, 99])
    table("ret60", [-99, -3, -1, 1, 3, 99])
    table("hrs_ext", [-1, 0.5, 2, 6, 24, 99])
    table("level_kind", None)
    table("h1_ce50", [-99, 1, 2, 3, 4.5, 99])
    table("atr_ratio", [0, 0.8, 1.2, 1.6, 2])
    table("spr_atr", [0, 0.1, 0.15, 0.2, 0.3, 9])
    table("dist_atr", [-1, 0.5, 1, 2, 3])
    table("room_u", [-1, 2, 5, 8, 15, 1e9])


if __name__ == "__main__":
    main()
