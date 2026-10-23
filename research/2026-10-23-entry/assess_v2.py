"""The assessment, version 2 - written after v1 failed its judge (out_assess_v1.txt), before running this:

v1 kept only the components whose FIXED direction held in both FIT halves (2 of 20) and lost on its judge (-0.157 R
taken vs -0.111 all). Several components were stable in BOTH halves in the direction opposite to my prior (the H1
structure with the trade, room >= 2 R, yesterday's bar with the trade, the day's run). "The market is always right":
v2 lets the FIT data set each component's direction, keeping a component when its effect has the same sign in
both FIT halves, |effect| >= 0.03 R in each, at least 30 candidates on each side in each half; score = the sum of
the kept components times their sign; trade when > 0. The v1 judge (2025-04 .. 09) is now spent - v2's judge is
2025-10 .. 2026-04-17 (the NY-B2 journal's weeks: other triggers, never these readings), read once. The exam
months stay information only.

    .venv/Scripts/python research/2026-10-23-entry/assess_v2.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from assess import FIT, HALF, MAPS, T, effect

HERE = Path(__file__).resolve().parent
PERIODS = [("v1 judge 2025-04 .. 09 (spent)", T("2025-04-01"), T("2025-10-01")), ("JUDGE v2 2025-10 .. 2026-04-17", T("2025-10-01"), T("2026-04-18")),
           ("2026-04-18 .. 10-16 (seen)", T("2026-04-18"), T("2026-10-17"))]


def main() -> None:
    X = pd.read_parquet(HERE / "candidates.parquet").dropna(subset=["r"])
    F = {name: np.asarray(fn(X), float) for name, fn in MAPS.items()}
    fit = (X.t >= FIT[0]) & (X.t < FIT[1])
    h1, h2 = fit & (X.t < HALF), fit & (X.t >= HALF)
    kept = {}
    for name, f in F.items():
        e1, p1, n1 = effect(X[h1], f[h1])
        e2, p2, n2 = effect(X[h2], f[h2])
        if np.sign(e1) == np.sign(e2) and min(abs(e1), abs(e2)) >= 0.03 and min(p1, n1, p2, n2) >= 30:
            kept[name] = float(np.sign(e1))
    print("kept (direction set by FIT):")
    for name, sgn in kept.items():
        print(f"  {'+' if sgn > 0 else '-'} {name}")
    X["score"] = sum(sgn * F[n] for n, sgn in kept.items())
    take = X.score > 0
    print(f"\n{'period':34s} {'all R':>8s} {'n':>6s} {'taken R':>8s} {'n':>6s} {'won':>5s}  by trigger (taken R / n)")
    for name, a, b in [("FIT 2023-09 .. 2025-03", *FIT), *PERIODS]:
        p = (X.t >= a) & (X.t < b)
        tk = X[p & take]
        by = "  ".join(f"{g}: {d.r.mean():+.3f}/{len(d)}" for g, d in tk.groupby("trig"))
        print(f"{name:34s} {X.r[p].mean():+8.3f} {p.sum():6d} {tk.r.mean():+8.3f} {len(tk):6d} {(tk.r > 0).mean() * 100:4.0f}%  {by}")


if __name__ == "__main__":
    main()
