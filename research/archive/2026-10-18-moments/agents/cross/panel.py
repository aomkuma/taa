"""Agent "cross": one aligned M1 panel of gold and the other markets (2023-09-01 .. 2026-10-15, UTC minute index).

Columns: gold o/h/l/c/spread (USD) and the M1 close of every other market, forward-filled at most 3 minutes
(a stale value beyond that is NaN). Synthetic: AUDJPY = AUDUSD x USDJPY; DXY-like composite = mean of the six
majors' log prices signed so that up = a stronger dollar.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/panel.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

OUT = "research/2026-10-18-moments/agents/cross/panel.parquet"
LO, HI = pd.Timestamp("2023-09-01", tz="UTC"), pd.Timestamp("2026-10-15", tz="UTC")
OTHERS = ["US500", "US100", "US30", "JP225", "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "XAUAUD"]
USD_SIGN = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1, "USDCHF": 1, "USDCAD": 1}


def main() -> None:
    gold.below_normal_priority()
    g = gold.bars("M1")
    g = g[(g.index >= LO) & (g.index < HI)]
    idx = g.index
    p = pd.DataFrame(index=idx)
    p["go"], p["gh"], p["gl"], p["gc"] = (g[k].astype(float) for k in ("open", "high", "low", "close"))
    p["gsp"] = g["spread"].astype(float) * 0.01
    for s in OTHERS:
        d = pd.read_parquet(f"data/history/FBS-Demo/{s}/M1.parquet", columns=["open_time", "close"])
        d.index = pd.DatetimeIndex(pd.to_datetime(d.open_time, utc=True))
        c = d["close"].astype(float)
        c = c[~c.index.duplicated()].sort_index()
        full = c.reindex(c.index.union(idx)).ffill(limit=3)
        p[s] = full.reindex(idx)
    p["AUDJPY"] = p.AUDUSD * p.USDJPY
    p["USD"] = sum(sgn * np.log(p[k]) for k, sgn in USD_SIGN.items()) / len(USD_SIGN)
    p.to_parquet(OUT)
    print(p.notna().mean().round(3).to_dict())
    print(len(p), p.index.min(), p.index.max())


if __name__ == "__main__":
    main()
