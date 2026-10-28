"""Runs come in clusters (the catalogue: 45-87 % start within 60 min of another run's extreme). From the moments a
trader can see - the run has just reached R (its target bar's close) and the leg's first 40 % pullback (its end bar's
close) - which side gets +X first (the run's way or back), and the next run's side against the previous one's.
Design half-years and the window (the window only as a description here; no rule is chosen on it).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/after_run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import gold  # noqa: E402
from catalogue import load  # noqa: E402
from frame_a import first_hit  # noqa: E402


def main() -> None:
    gold.below_normal_priority()
    m = load()
    o, h, lo = (m[k].to_numpy(float) for k in ("open", "high", "low"))
    sp = m.spread.to_numpy(float) * 0.01
    C = pd.read_parquet(HERE / "catalogue.parquet")
    C = C[(C.t.dt.hour <= 20) & (C.t.dt.dayofweek < 5)]
    for R, g in C.groupby("R"):
        g = g.sort_values("t").reset_index(drop=True)
        print(f"\n=== R = {R} U ===")
        print(f"{'half':10} {'n':>5} | at R: {'+5 run way':>10} {'+10':>6} | at leg end: {'+5':>6} {'+10':>6} |"
              f" next run (<=60 min after the extreme) same side")
        for hl, x in g.groupby("half", observed=True):
            s = x.side.to_numpy()
            d1 = x.tgt.to_numpy()
            d2 = x.endj.to_numpy()
            u1, u2 = o[d1] / 4100, o[np.minimum(d2, len(o) - 1)] / 4100
            r = {}
            for name, d, u in (("tgt", d1, u1), ("end", d2, u2)):
                for k in (5, 10):
                    f = first_hit(o, h, lo, sp, d, k * u) * s
                    r[(name, k)] = (f[f != 0] > 0).mean()
            # next run after this run's extreme
            nxt = []
            t_ext = x.t_ext.to_numpy()
            st, sd = g.t.to_numpy(), g.side.to_numpy()
            for te, si in zip(t_ext, s, strict=True):
                p = np.searchsorted(st, te, side="right")
                if p < len(st) and st[p] - te <= np.timedelta64(60, "m"):
                    nxt.append(sd[p] == si)
            print(f"{hl:10} {len(x):5} | {100 * r[('tgt', 5)]:16.1f} {100 * r[('tgt', 10)]:6.1f} |"
                  f" {100 * r[('end', 5)]:17.1f} {100 * r[('end', 10)]:6.1f} | {100 * np.mean(nxt):5.1f} % (n {len(nxt)})")


if __name__ == "__main__":
    main()
