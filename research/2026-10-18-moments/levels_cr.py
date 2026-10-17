"""The nearest H1 and M15 chart-read levels (the bot's ZigZag) above and below the close at every candidate minute
of own_ml_long (round 9, docs/OWN_SETUP.md).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/levels_cr.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, ".")
import gold  # noqa: E402

from app.indicators.chart_read import ChartReadFrame  # noqa: E402

OUT = "data/research/own_ml_cr_levels.parquet"


def main() -> None:
    gold.below_normal_priority()
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= pd.Timestamp("2025-09-01", tz="UTC")) & (m1.index < pd.Timestamp("2026-10-15", tz="UTC"))]
    d = pd.read_parquet("data/research/own_ml_long.parquet", columns=["t", "e"])
    d["t"] = pd.to_datetime(d.t, utc=True)
    d = d[d.t >= pd.Timestamp("2025-12-01", tz="UTC")].drop_duplicates("t")
    times = pd.DatetimeIndex(d.t.sort_values())
    close = m1.close.reindex(times - pd.Timedelta(minutes=1)).to_numpy()  # the decision bar's close
    out = pd.DataFrame({"t": times})
    ohlc = {"open": "first", "high": "max", "low": "min", "close": "last"}
    for name, mins in (("M15", 15), ("H1", 60)):
        b = m1.resample(f"{mins}min", label="left", closed="left").agg(ohlc).dropna()
        b.index = b.index + pd.Timedelta(minutes=mins)
        fr = ChartReadFrame(name, b, 0.01)
        pos = b.index.searchsorted(times, side="right") - 1
        cache: dict[int, list[float]] = {}
        above, below = [], []
        for p, x in zip(pos, close, strict=True):
            if p not in cache:
                r = fr.at(int(p)) if p >= 0 else None
                cache[p] = [lv.price for lv in r.levels] if r is not None else []
            lv = np.array(cache[p])
            a, bl = lv[lv > x], lv[lv < x]
            above.append(a.min() - x if len(a) else np.nan)
            below.append(x - bl.max() if len(bl) else np.nan)
        out[f"cr_{name}_res"], out[f"cr_{name}_sup"] = above, below
        print(name, "done", flush=True)
    out.to_parquet(OUT)
    print(out.describe().round(2).to_string())


if __name__ == "__main__":
    main()
