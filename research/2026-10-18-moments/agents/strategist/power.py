"""Q1 - can the pass bar ("+0.15 R or more in BOTH P1 and P2") tell a real +0.15 R rule from a rule with none?

Written before computing: take the real R distributions of the developer's trades (B2 of P3 and W of P4, news cost
0, P1 + P2 pooled), shift each to a true mean mu, draw n trades per part (bootstrap), and count how often both parts
reach >= +0.15 R. n = 60 (W in the windows today), 125 (2 a weekday), 190 (3 a weekday), 350. mu = 0, 0.10, 0.15,
0.20, 0.30. Then: the expected number of false passes among K settings tried with mu = 0, and the trades needed per
part for the 95 % range of the mean to exclude 0 at mu = 0.15.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/power.py > .../strategist/out_power.txt
"""

from __future__ import annotations

import numpy as np

import slib

rng = np.random.default_rng(11)
SETS = {"B2 (P3)": slib.dev_trades("p3_trades_all.parquet", "B2"), "W (P4)": slib.dev_trades("p4_trades_W_WL.parquet", "W")}
NS = [60, 125, 190, 350]
MUS = [0.0, 0.10, 0.15, 0.20, 0.30]
SIMS = 20000

for name, d in SETS.items():
    r = d.R.to_numpy(float)
    sd = r.std(ddof=1)
    print(f"{name}: {len(r)} trades, mean R {r.mean():+.3f}, SD {sd:.3f}; per part SD "
          + ", ".join(f"{p} {d[d.part == p].R.std(ddof=1):.3f}" for p in ("P1", "P2")))
    base = r - r.mean()
    print("  P(both parts >= +0.15 R)   " + "  ".join(f"n={n:<4d}" for n in NS))
    for mu in MUS:
        cells = []
        for n in NS:
            a = rng.choice(base, size=(SIMS, n)).mean(1) + mu
            b = rng.choice(base, size=(SIMS, n)).mean(1) + mu
            cells.append(np.mean((a >= 0.15) & (b >= 0.15)))
        print(f"  true mu {mu:+.2f}               " + "  ".join(f"{c:6.3f}" for c in cells))
    # false passes among K settings at mu = 0 (independent settings: an upper bound on how many look good)
    for n in (60, 125):
        a = rng.choice(base, size=(SIMS, n)).mean(1)
        b = rng.choice(base, size=(SIMS, n)).mean(1)
        p0 = np.mean((a >= 0.15) & (b >= 0.15))
        print(f"  n={n}: false pass per setting {p0:.4f}; among K = 25 / 100 / 300 settings, expected "
              f"{25 * p0:.2f} / {100 * p0:.2f} / {300 * p0:.2f}; P(at least one) "
              f"{1 - (1 - p0) ** 25:.2f} / {1 - (1 - p0) ** 100:.2f} / {1 - (1 - p0) ** 300:.2f}")
    need = (1.96 * sd / 0.15) ** 2
    need80 = ((1.96 + 0.84) * sd / 0.15) ** 2
    print(f"  trades per part for the 95 % range to exclude 0 at a true +0.15: {need:.0f} (at 80 % power: {need80:.0f});"
          f" pooled P1 + P2 halves that.")
    print()
