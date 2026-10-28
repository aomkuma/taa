"""The largest loser group of RUN-A (A4): the run was the end of the swing (its start broken within 120 min). Can
the pullback tell it before the entry? For each trade: the pullback's depth (share of the run given back), its
speed against the run's (minutes per U), the tick volume in the pullback against the run's, the pullback's largest
M1 bar against the run's largest. Design (to choose) and window (described only).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/pullback.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402

HL = ["H1", "H2", "H3", "H4", "H5"]


def main() -> None:
    P = rules.jlib.Instr("XAUUSD")
    C = pd.read_parquet(HERE / "catalogue.parquet")
    C = C[C.R == 15].set_index(["t", "side"])
    for part in ("design", "window"):
        z = pd.read_parquet(HERE / f"trades_A4_{part}.parquet")
        key = pd.MultiIndex.from_arrays([pd.DatetimeIndex(z.run_t), z.side.to_numpy()])
        cat = C.reindex(key)
        rows = []
        for r, (_, c) in zip(z.itertuples(), cat.iterrows(), strict=True):
            s = r.side
            i0 = P.ot.searchsorted(r.run_t)
            ix = P.ot.searchsorted(c.t_ext)
            d = r.e - 1
            run_bars = slice(i0, ix + 1)
            pb_bars = slice(ix + 1, d + 1)
            pl = P.lo[pb_bars].min() if s > 0 else P.h[pb_bars].max()
            depth = (c.start_px + s * c["size"] - pl) * s / c["size"]
            run_min = max(ix - i0 + 1, 1)
            pb_min = max(d - ix, 1)
            speed = (c["size"] * depth / pb_min) / (c["size"] / run_min)  # U per minute, pullback / run
            tv = P.v[pb_bars].mean() / P.v[run_bars].mean()
            rng = P.h - P.lo
            big = rng[pb_bars].max() / rng[run_bars].max()
            seg = slice(r.e, min(r.e + 120, len(P.o)))
            vrev = bool((P.lo[seg] < r.start).any()) if s > 0 else bool((P.h[seg] > r.start).any())
            rows.append(dict(depth=depth, speed=speed, tv=tv, big=big, vrev=vrev, run_atr=c.size_atr))
        X = pd.DataFrame(rows)
        z = pd.concat([z.reset_index(drop=True), X], axis=1)
        z["half"] = pd.cut(z.t, rules.HALVES, labels=HL, right=False)
        z.to_parquet(HERE / f"pullback_A4_{part}.parquet")
        los, win = z.exit == "stop", z.exit == "win"
        print(f"\n== A4 {part}: {len(z)} trades; V-losers {int((los & z.vrev).sum())} of {int(los.sum())} losers")
        for f in ("depth", "speed", "tv", "big", "run_atr"):
            q = np.nanquantile(z[f], [0.2, 0.4, 0.6, 0.8]) if part == "design" else qs[f]
            if part == "design":
                qs = qs if "qs" in dir() else {}
                qs[f] = q
            b = np.digitize(z[f], q)
            line = []
            for k in range(5):
                g = z[b == k]
                per = "" if part == "window" else " h+" + str(int(sum(g[g.half == h].R.mean() > 0 for h in HL)))
                line.append(f"[{g[f].min():.2f},{g[f].max():.2f}] n{len(g)} R{g.R.mean():+.2f} V{100 * g.vrev.mean():.0f}%{per}")
            print(f"  {f:8} " + " | ".join(line))


if __name__ == "__main__":
    main()
