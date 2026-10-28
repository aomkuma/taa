"""Round 2: RUN-A's side against its mirror (the same trades, the other side) by half-year, old sample + design +
window, for A10 / A11 - is the side's edge a regime (volatility) effect? Descriptive.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/regime.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oldcheck  # noqa: E402
import rules  # noqa: E402
import rules2  # noqa: E402

CUTS = pd.to_datetime(["2021-10-01", "2022-05-01", "2022-11-01", "2023-05-01", "2023-11-01", "2024-05-01", "2024-11-01",
                       "2025-05-01", "2025-09-01", "2026-03-01", "2026-10-17"], utc=True)


def mirror(P, z, cfg, AD):
    out = []
    for r in z.itertuples():
        row = pd.Series(dict(t=r.t, e=r.e, d=r.e - 1, side=r.side, start=r.start, u=P.o[r.e] / 4100.0, size=r.size,
                             run_t=r.run_t, ext=r.lvl, entry=r.entry))
        x = rules2.one(P, row, cfg, AD, side=-int(r.side))
        out.append(x["R"])
    return np.array(out)


def main() -> None:
    rules.gold.below_normal_priority()
    for period in ("old", "new"):
        if period == "old":
            rules.jlib.m1_frame = oldcheck._m1_old
            P = rules.jlib.Instr("XAUUSD")
            AD = oldcheck.adaptive_old(P)
        else:
            rules.jlib.m1_frame = rules._m1
            P = rules.jlib.Instr("XAUUSD")
            AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_atr_usd"]).ad_atr_usd.reindex(P.ot).to_numpy()
        for name in ("A10", "A11"):
            cfg = rules2.RULES2[name]
            parts = ["old"] if period == "old" else ["design", "window"]
            z = pd.concat([pd.read_parquet(HERE / f"trades_{name}_{p}.parquet") for p in parts], ignore_index=True)
            z["mR"] = mirror(P, z, cfg, AD)
            g = z.groupby(pd.cut(z.t, CUTS, right=False), observed=True)
            for k, v in g:
                print(f"{name} {str(k.left)[:7]}: n {len(v):3}  R {v.R.mean():+.3f}  mirror {v.mR.mean():+.3f}  side - mirror"
                      f" {v.R.mean() - v.mR.mean():+.3f}  stop median {v.sl.median():5.1f} USD")


if __name__ == "__main__":
    main()
