"""Grid for New York continuation on the design data (nine half-years, 2021-10 .. 2026-02).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/nycont_grid.py
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402
import nycont  # noqa: E402


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    d = pd.read_parquet(nycont.OUT)
    d = d[d.t < lab.DESIGN_END].reset_index(drop=True)
    hn = [h[0] for h in lab.HALVES]
    res = []
    for stopk, ex, hz in itertools.product((0.1, 0.15, 0.2), ("trail1/1", "tp2", "tp99"), (120, 180)):
        r = nycont.evaluate(B, d, d.side.to_numpy(), stopk, ex, hz)
        R = r.R.to_numpy()
        for ck, thr, h1, ext, orb in itertools.product(nycont.CHECKS, (0.0, 0.2, 0.3, 0.5), ("any", "with", "notAgainst"),
                                                    (0.0, 0.7), ("any", "orb")):
            m = (d.ck == ck) & (d.absm >= thr)
            if h1 == "with":
                m &= d.h1w
            elif h1 == "notAgainst":
                m &= ~d.h1a
            if ext:
                m &= d.ext >= ext
            if orb == "orb":
                if ck == "09:30":
                    continue
                m &= d.orb
            m = m.to_numpy()
            if m.sum() < 120:
                continue
            hs = pd.Series(R[m]).groupby(d.half.to_numpy()[m]).mean().reindex(hn)
            res.append(dict(ck=ck, thr=thr, h1=h1, ext=ext, orb=orb, stop=stopk, exit=ex, hz=hz, N=int(m.sum()),
                            R=R[m].mean(), win=100 * (r.usd.to_numpy()[m] > 0).mean(), pos=int((hs > 0).sum()),
                            worst=hs.min(), last=hs.iloc[-1]))
    res = pd.DataFrame(res)
    res.to_parquet("research/2026-10-18-moments/agents/trend/nycont_grid.parquet")
    pd.set_option("display.width", 220)
    print(f"{len(res)} cells; mean R by checkpoint / thr / h1 / ext / orb:")
    for c in ("ck", "thr", "h1", "ext", "orb", "stop", "exit", "hz"):
        print(res.groupby(c).agg(R=("R", "mean"), pos=("pos", "mean")).round(3).T.to_string())
    print("\nbaseline (every day, no filter) by checkpoint, stop 0.15 ADR, trail1/1, 180:")
    print(res[(res.thr == 0) & (res.h1 == "any") & (res.ext == 0) & (res.orb == "any") & (res.stop == 0.15)
              & (res.exit == "trail1/1") & (res.hz == 180)].round(3).to_string(index=False))
    print("\ntop 40 by halves positive then R (N >= 200):")
    print(res[res.N >= 200].sort_values(["pos", "R"], ascending=False).head(40).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
