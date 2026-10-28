"""Agent "cross": timestamp alignment check. A lagged clock in another market's data would show up as a fake lead.
Cross-correlation of 1-minute log returns gold vs X at lags -3..+3 minutes and of 5-minute returns at lags
-120..+120 minutes (multiples of 60), by half-year incl. summer/winter months (DST).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/align_check.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

PANEL = "research/2026-10-18-moments/agents/cross/panel.parquet"


def main() -> None:
    gold.below_normal_priority()
    p = pd.read_parquet(PANEL)
    p = p[p.index < pd.Timestamp("2026-03-01", tz="UTC")]
    full = p.reindex(pd.date_range(p.index[0], p.index[-1], freq="min"))
    g = np.log(full.gc).diff()
    months = full.index.month
    for k in ["US500", "JP225", "USDJPY", "EURUSD", "AUDJPY"]:
        x = np.log(full[k]).diff()
        for name, m in (("winter", np.isin(months, [12, 1, 2])), ("summer", np.isin(months, [6, 7, 8]))):
            gs, xs = g.where(m), x.where(m)
            row = [100 * gs.corr(xs.shift(lag)) for lag in (-3, -2, -1, 0, 1, 2, 3)]
            print(f"{k:7} {name}  1-min lags -3..+3 (X shifted +lag = X earlier): " + " ".join(f"{v:+5.1f}" for v in row))
        g5 = np.log(full.gc).diff(5)
        x5 = np.log(full[k]).diff(5)
        row = [100 * g5.corr(x5.shift(lag)) for lag in (-120, -60, 0, 60, 120)]
        print(f"{k:7} 5-min returns, lags -120,-60,0,+60,+120 min: " + " ".join(f"{v:+5.1f}" for v in row))


if __name__ == "__main__":
    main()
