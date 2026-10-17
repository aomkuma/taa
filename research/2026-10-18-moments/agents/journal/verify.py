"""Check build.py against confluence.py's own inputs (own_ml_long + own_ml_cr_levels) on design minutes where both
exist (2025-12-01 .. 2026-02-28): the same (minute, side) signals before the stop-size filter.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/journal/verify.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jlib  # noqa: E402

A, B = pd.Timestamp("2025-12-01", tz="UTC"), jlib.DESIGN_END


def main() -> None:
    mine = jlib.cands("XAUUSD", "design")
    mine = mine[(mine.t >= A) & (mine.t < B)]
    pa = mine.pa_m1 | mine.pa_m5 | mine.engulf | mine.reclaim
    ind = (mine.rsi_ok.astype(int) + mine.macd_ok.astype(int) + mine.stoch_ok.astype(int)) >= 2
    sm = mine[mine.tide & mine.at_level & pa & ind]
    # the original inputs
    d = pd.read_parquet(jlib.ROOT / "data/research/own_ml_long.parquet")
    d["t"] = pd.to_datetime(d.t, utc=True)
    d = d[(d.t >= A) & (d.t < B)]
    print("rows mine", len(mine), "orig", len(d))
    cr = pd.read_parquet(jlib.ROOT / "data/research/own_ml_cr_levels.parquet")
    cr["t"] = pd.to_datetime(cr.t, utc=True)
    d = d.merge(cr, on="t", how="left")
    m = mine.merge(d[["t", "side", "atr1", "h1_e20_slope", "h1_c_e50", "cr_M15_sup", "cr_M15_res", "cr_H1_sup", "cr_H1_res"]],
                   on=["t", "side"], suffixes=("", "_o"))
    print("matched rows", len(m))
    for a, b in (("atr1", "atr1_o"), ("h1_e20_slope", "h1_e20_slope_o"), ("h1_c_e50", "h1_c_e50_o"),
                 ("cr_M15_sup", "cr_M15_sup_o"), ("cr_M15_res", "cr_M15_res_o"), ("cr_H1_sup", "cr_H1_sup_o"), ("cr_H1_res", "cr_H1_res_o")):
        x, y = m[a].to_numpy(float), m[b].to_numpy(float)
        both = np.isfinite(x) & np.isfinite(y)
        print(f"  {a:14} max|diff| {np.nanmax(np.abs(x[both] - y[both])):.4f}  nan mismatch {(np.isfinite(x) != np.isfinite(y)).sum()}")
    print("signals mine (tide+level+pa+ind):", len(sm), "per side", sm.side.value_counts().to_dict())


if __name__ == "__main__":
    main()
