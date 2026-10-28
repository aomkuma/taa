"""Auditor check 1c: own_ml_cr_levels (levels_cr.py, ChartReadFrame on the full series) against ChartReadFrame on M1
truncated at the decision bar, for a random sample of minutes (look-ahead test of the chart-read levels).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/cr_check.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, ".")
import gold  # noqa: E402

from app.indicators.chart_read import ChartReadFrame  # noqa: E402


def main() -> None:
    gold.below_normal_priority()
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= pd.Timestamp("2025-09-01", tz="UTC")) & (m1.index < pd.Timestamp("2026-10-15", tz="UTC"))]
    cr = pd.read_parquet("data/research/own_ml_cr_levels.parquet")
    cr["t"] = pd.to_datetime(cr.t, utc=True)
    rng = np.random.default_rng(5)
    sub = cr.iloc[rng.choice(len(cr), 25, replace=False)]
    ohlc = {"open": "first", "high": "max", "low": "min", "close": "last"}
    worst = {}
    for r in sub.itertuples():
        cut = m1[m1.index < r.t]  # bars opened before t = closed by t
        x = float(cut.close.iloc[-1])
        for name, mins in (("M15", 15), ("H1", 60)):
            b = cut.resample(f"{mins}min", label="left", closed="left").agg(ohlc).dropna()
            b.index = b.index + pd.Timedelta(minutes=mins)
            b = b[b.index <= r.t]
            rd = ChartReadFrame(name, b, 0.01).at(len(b) - 1)
            lv = np.array([v.price for v in rd.levels]) if rd is not None else np.array([])
            a, bl = lv[lv > x], lv[lv < x]
            res = a.min() - x if len(a) else np.nan
            sup = x - bl.max() if len(bl) else np.nan
            for k, v in ((f"cr_{name}_res", res), (f"cr_{name}_sup", sup)):
                s = getattr(r, k)
                dv = 0.0 if (np.isnan(v) and np.isnan(s)) else abs(v - s)
                worst[k] = max(worst.get(k, 0.0), dv)
                if not dv < 1e-6:
                    print(f"  differs {r.t} {k}: stored {s} truncated {v}")
    print("largest differences:", worst)


if __name__ == "__main__":
    main()
