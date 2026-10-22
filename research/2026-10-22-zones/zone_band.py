"""How wide is a zone line's band (owner 2026-10-22: "a zone line is a price level with a +- range; price may stop short
of it or overshoot it")? Every confirmed H4 turn (a 3-bar fractal high / low) of the learning period, its distance to
the nearest line of the grid in force at that bar, in USD and in steps. Learning period only.

    .venv/Scripts/python research/2026-10-22-zones/zone_band.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zone_grid_v1 as Z  # noqa: E402

h4 = Z.bars("H4")
g = Z.daily_grid(Z.bars("D1"))
x = h4[(h4.index >= "2025-10-20") & (h4.index < "2026-04-18")]
hi, lo = x.high.values, x.low.values
rows = []
for i in range(1, len(x) - 1):
    for kind, p, ok in (("high", hi[i], hi[i] > hi[i - 1] and hi[i] > hi[i + 1]), ("low", lo[i], lo[i] < lo[i - 1] and lo[i] < lo[i + 1])):
        if not ok:
            continue
        k = g.index.searchsorted(x.index[i], side="right") - 1
        anc, stp = g.anchor.values[k], g.step.values[k]
        pos = (p - anc) / stp
        near = np.round(pos)
        d = (pos - near) * stp  # + above the line, - below it
        # for a high, "overshoot" = above the line it turned at; for a low, below
        over = d if kind == "high" else -d
        rows.append(dict(kind=kind, dist=abs(d), over=over, step=stp, frac=abs(pos - near)))
R = pd.DataFrame(rows)
print("turns:", len(R), "| median step", round(R.step.median(), 1))
print("distance to the nearest line, USD: median", round(R.dist.median(), 1), "| p70", round(R.dist.quantile(0.7), 1), "| p80", round(R.dist.quantile(0.8), 1))
print("in steps: median", round(R.frac.median(), 3), "| p70", round(R.frac.quantile(0.7), 3), "| a random price would give median 0.25")
for b in (0.05, 0.10, 0.15, 0.20):
    print(f"turns within +-{b:.2f} step of a line: {100 * (R.frac <= b).mean():.0f} % (random {200 * b:.0f} %)")
print("overshoot (turn beyond the line) vs short (turn before it), within 0.2 step:", (R[R.frac <= 0.2].over > 0).mean().round(2))

# observe closer: by the market's size and by which line (the anchor line k = 0 vs lines further away)
rows2 = []
for i in range(1, len(x) - 1):
    for kind, p, ok in (("high", hi[i], hi[i] > hi[i - 1] and hi[i] > hi[i + 1]), ("low", lo[i], lo[i] < lo[i - 1] and lo[i] < lo[i + 1])):
        if not ok:
            continue
        k = g.index.searchsorted(x.index[i], side="right") - 1
        anc, stp = g.anchor.values[k], g.step.values[k]
        pos = (p - anc) / stp
        rows2.append(dict(frac=abs(pos - np.round(pos)), line=int(abs(np.round(pos))), step=stp, month=x.index[i].strftime("%Y-%m")))
Q = pd.DataFrame(rows2)
Q["size"] = pd.cut(Q.step, [0, 80, 120, 1000], labels=["step < 80", "80-120", "> 120"])
print("\nshare of turns within +-0.10 step, by market size:")
print(Q.groupby("size", observed=True).frac.agg(n="size", within=lambda s: round(100 * (s <= 0.10).mean())).to_string())
print("\nby line (0 = the anchor line):")
print(Q.assign(line=Q.line.clip(upper=4)).groupby("line").frac.agg(n="size", within=lambda s: round(100 * (s <= 0.10).mean())).to_string())
print("\nby month:")
print(Q.groupby("month").frac.agg(n="size", within=lambda s: round(100 * (s <= 0.10).mean())).to_string())
