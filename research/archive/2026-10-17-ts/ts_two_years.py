"""TS rules judged on both years at once (in-sample 2025-10..2026-09 and OOS 2024-10..2025-09), split into four
half-years: a rule must keep a positive R per trade in every half. One-feature table, then 1-2 condition rules.

usage: python ts_two_years.py <outcomes.csv year 1> <outcomes.csv year 2> [plan]
"""

import itertools
import sys

import numpy as np
import pandas as pd

plan = sys.argv[3] if len(sys.argv) > 3 else "b0.25_k3.0"
d = pd.concat([pd.read_csv(p, parse_dates=["time"]) for p in sys.argv[1:3]], ignore_index=True)
edges = [pd.Timestamp(x, tz="UTC") for x in ("2024-10-01", "2025-04-01", "2025-10-01", "2026-04-01", "2026-10-01")]
d["q"] = pd.cut(d.time, edges, labels=["24H2", "25H1", "25H2", "26H1"], right=False)
d["loc"] = pd.cut(d[["H1_pivot_dist", "H4_pivot_dist"]].min(axis=1), [-1, 0.25, 0.5, 1.0, 99],
                  labels=["<=0.25", "0.25-0.5", "0.5-1", ">1"]).astype(str)
d["h4_room"] = d["h4_room"].astype(str)
FEATURES = ["side", "kind", "h4_map", "h4_swings", "h1_map", "h1_swings", "session", "stop_bin", "loc", "h4_room"]


def halves(mask: pd.Series) -> tuple[int, float, list[float]]:
    s = d.loc[mask]
    return len(s), s[plan].mean(), [s.loc[s.q == q, plan].mean() for q in ["24H2", "25H1", "25H2", "26H1"]]


print(f"{len(d)} triggers, plan {plan}; halves 24H2 (Oct-Mar) 25H1 (Apr-Sep) 25H2 26H1")
n, r, h = halves(pd.Series(True, index=d.index))
print(f"all: n {n} R {r:+.3f}  " + " ".join(f"{x:+.3f}" for x in h))
print("\none feature (n >= 60): value n R | the four halves")
for f in FEATURES:
    for v in sorted(d[f].dropna().unique(), key=str):
        n, r, h = halves(d[f] == v)
        if n >= 60:
            mark = "  all 4 > 0" if all(x > 0 for x in h) else ""
            print(f"  {f:10} {str(v):14} {n:5d} {r:+.3f} | " + " ".join(f"{x:+.3f}" for x in h) + mark)
print("\nrules of 1-2 conditions with every half > +0.05 and n >= 80 (by the weakest half):")
values = [(f, v) for f in FEATURES for v in d[f].dropna().unique()]
found = []
for size in (1, 2):
    for combo in itertools.combinations(values, size):
        if len({f for f, _ in combo}) < size:
            continue
        mask = pd.Series(np.logical_and.reduce([d[f] == v for f, v in combo]), index=d.index)
        n, r, h = halves(mask)
        if n >= 80 and all(x > 0.05 for x in h):
            found.append((min(h), n, r, h, combo))
found.sort(key=lambda x: -x[0])
for weak, n, r, h, combo in found[:20]:
    print(f"  {r:+.3f} n {n:4d} ({n / 24:.1f}/month) halves " + " ".join(f"{x:+.3f}" for x in h) + "  " +
          " & ".join(f"{f}={v}" for f, v in combo))
print(f"({len(found)} rules)")
