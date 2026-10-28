"""Gross R (no costs) and net R by half-year for every candidate so far (design only), with the coin by half.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/gross_check.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402

HN = [x[0] for x in w.HALVES]


def halves(z):
    h = w.plib.half_of(z.t)
    return z.R.groupby(h).mean().reindex(HN).to_numpy(), z.R.groupby(h).size().reindex(HN).fillna(0).astype(int).to_numpy()


def gross_run(S, P):
    keep = P.sp.copy(), P.slip, P.stop_slip, P.stop_slip_ny
    P.gross()
    z = w.run(S, P)
    P.sp, P.slip, P.stop_slip, P.stop_slip_ny = keep
    return z


def coin_halves(S, P, seeds=10):
    acc = []
    for s in range(seeds):
        z = w.plib.run(S, P, coin=np.random.default_rng(100 + s))
        z["t"] = pd.to_datetime(z.t, utc=True)
        acc.append(halves(z)[0])
    return np.nanmean(np.array(acc), 0)


def report(label, S, P):
    z = w.run(S, P)
    zg = gross_run(S, P)
    rn, n = halves(z)
    rg, _ = halves(zg)
    rc = coin_halves(S, P)
    d2 = (np.sum(rg >= 0.10) >= 4) and (rn[-1] >= 0.10)
    print(f"  {label:26} n {len(z):4} net {z.R.mean():+.3f} gross {zg.R.mean():+.3f} | D2 {'PASS' if d2 else 'fail'}")
    print("      net   " + " ".join(f"{v:+.2f}({k})" for v, k in zip(rn, n)))
    print("      gross " + " ".join(f"{v:+.2f}" for v in rg))
    print("      coin  " + " ".join(f"{v:+.2f}" for v in rc) + "   ours-coin " + " ".join(f"{a - b:+.2f}" for a, b in zip(rn, rc)))


def main():
    w.jlib.gold.below_normal_priority()
    P = w.instr("XAUUSD")
    D = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
    h = pd.DatetimeIndex(D.t).hour
    f1w = ((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))
    print("== gold M1")
    report("F1 (its windows)", w.signals(D[f1w], 3, 10, 8, 0.6, 60), P)
    report("W1 02-07 + 17-20", w.signals(D[~f1w], 3, 10, 8, 0.6, 60), P)
    for name, pa, ind in (("W5a PA only", True, 0), ("W5b 2/3 only", False, 2), ("W5c neither", False, 0)):
        X = D.copy()
        if not pa:
            X["pa"] = True
        X["n_ind"] = np.where(X.n_ind >= ind, 2, 0)
        report(name, w.signals(X, 3, 10, 8, 0.6, 60), P)
    print("== gold M5")
    D5 = w.build(P, 5, *w.DESIGN, [(0, 20)], "XAUUSD_M5_design")
    for T in (8, 12, 16):
        report(f"W2 T{T} H180", w.signals(D5, 4, 16, T, 0.6, 180), P)
    for sym in ("US100", "US30", "US500", "JP225", "XAUAUD"):
        Q = w.instr(sym)
        Dq = w.build(Q, 1, *w.DESIGN, [], f"{sym}_M1_design")
        print(f"== {sym} M1")
        report(f"W3a {sym}", w.signals(Dq, 3, 10, 8, 0.6, 60), Q)


if __name__ == "__main__":
    main()
