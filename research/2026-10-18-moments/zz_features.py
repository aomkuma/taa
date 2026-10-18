"""ZigZag structure features (the bot's chart read) on M5 / M15 / H1 at every candidate minute of own_ml_long, and
the 52 indicator votes of round 6, for round 8's all-in model (docs/OWN_SETUP_ROUNDS.md).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/zz_features.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, ".")
import gold  # noqa: E402
from indicator_score import TFS, votes  # noqa: E402

from app.indicators.chart_read import ChartReadFrame  # noqa: E402

STRUCT = {"UP": 1.0, "DOWN": -1.0}
OUT = "data/research/own_ml_zz_votes.parquet"


def main() -> None:
    gold.below_normal_priority()
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= pd.Timestamp("2023-06-01", tz="UTC")) & (m1.index < pd.Timestamp("2026-10-15", tz="UTC"))]
    d = pd.read_parquet("data/research/own_ml_long.parquet", columns=["t"])
    times = pd.DatetimeIndex(pd.to_datetime(d.t, utc=True).drop_duplicates().sort_values())
    F = pd.DataFrame(index=times)
    ohlc = {"open": "first", "high": "max", "low": "min", "close": "last"}
    for name, mins in (("M5", 5), ("M15", 15), ("H1", 60)):
        b = m1.resample(f"{mins}min", label="left", closed="left").agg(ohlc).dropna()
        b.index = b.index + pd.Timedelta(minutes=mins)  # close-time index
        fr = ChartReadFrame(name, b, 0.01)
        pos = b.index.searchsorted(times, side="right") - 1
        cache: dict[int, tuple] = {}
        rows = []
        for p in pos:
            if p not in cache:
                r = fr.at(int(p)) if p >= 0 else None
                if r is None:
                    cache[p] = (np.nan,) * 5
                else:
                    leg = r.leg
                    cache[p] = (
                        STRUCT.get(str(r.structure_now.value if r.structure_now else r.structure.value), 0.0),
                        STRUCT.get(str(r.structure.value), 0.0),
                        (leg.direction * leg.leg_atr) if leg else np.nan,
                        (leg.retrace if leg and leg.retrace is not None else np.nan),
                        float(r.age_legs),
                    )
            rows.append(cache[p])
        part = pd.DataFrame(rows, index=times, columns=[f"zz_{name}_{k}" for k in ("now", "conf", "leg", "retrace", "age")])
        F = F.join(part)
        print(name, "done", flush=True)
    for name, mins in TFS.items():
        b = m1[["open", "high", "low", "close"]] if mins == 1 else m1.resample(f"{mins}min", label="left", closed="left").agg(ohlc).dropna()
        v = votes(b, name)
        ends = b.index + pd.Timedelta(minutes=mins)
        k = ends.searchsorted(times, side="right") - 1
        part = v.iloc[np.clip(k, 0, None)].set_axis(times)
        part[k < 0] = 0
        F = F.join(part.add_prefix("v_"))
    F.index.name = "t"
    F.reset_index().to_parquet(OUT)
    print(F.shape)


if __name__ == "__main__":
    main()
