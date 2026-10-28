"""The reclaim of reclaim_2025.py split by the BIG regime - owner 2026-10-25: "2025 was asked for because it was a
bull market". Does the winning side follow the big trend (bull: buys, bear: sells)?

Big regime at the sweep, from D1 closes known then (the day before the sweep's day):
- bull: the close over its 50-day mean AND the 50-day mean higher than 20 days earlier;
- bear: under its 50-day mean AND the mean lower than 20 days earlier; else mixed.
D1 is built from M1 (UTC days). Trades: buffer 1.0 ATR, target 0.7 R (the AI's day-4 values) and buffer 1.8.

    .venv/Scripts/python research/2026-10-24-replay/reclaim_regime.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reclaim_2025 import ROOT, m5_from_m1, signals, trade  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

MEAN, SLOPE = 50, 20


def regime_by_day(m5: pd.DataFrame) -> pd.Series:
    d1 = m5.close.resample("1D").last().dropna()
    mean = d1.rolling(MEAN).mean()
    bull = (d1 > mean) & (mean > mean.shift(SLOPE))
    bear = (d1 < mean) & (mean < mean.shift(SLOPE))
    lab = pd.Series(np.where(bull, "bull", np.where(bear, "bear", "mixed")), index=d1.index)
    lab[mean.shift(SLOPE).isna()] = "?"
    return lab.shift(1)  # known at the start of the next day


def main() -> None:
    m1 = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M1, None, None)
    m5 = m5_from_m1(m1)
    lab = regime_by_day(m5)
    d1 = m5.close.resample("1D").last().dropna()
    for y in ("2024", "2025"):
        part = d1[d1.index.year == int(y)]
        print(
            f"gold {y}: {part.iloc[0]:.0f} -> {part.iloc[-1]:.0f} ({part.iloc[-1] / part.iloc[0] - 1:+.0%})"
        )
    part = d1[d1.index >= "2026-07-01"]
    print(
        f"gold 2026-07 ..: {part.iloc[0]:.0f} -> {part.iloc[-1]:.0f} ({part.iloc[-1] / part.iloc[0] - 1:+.0%})"
    )
    for title, lo, hi in (
        ("2024 (before the exam)", "2023-12-31", "2025-01-01"),
        ("2025 (before the exam)", "2024-12-31", "2026-01-01"),
        ("2026-07-01 .. (replay months, information only)", "2026-06-30", "2100-01-01"),
    ):
        part = m5[(m5.index >= lo) & (m5.index < hi)]
        sig = signals(part)
        t = part.index[sig.j.to_numpy()]
        sig = sig.assign(t=t, regime=lab.reindex(t.normalize()).to_numpy())
        days = lab[(lab.index >= lo) & (lab.index < hi)].value_counts().to_dict()
        print(f"\n== {title}: {len(sig)} reclaims; days by regime {days} ==")
        print("regime | side | trades | buffer 1.0 / 0.7 R: win %, avg R | buffer 1.8 / 0.7 R: win %, avg R")
        for reg in ("bull", "mixed", "bear"):
            for up in (True, False):
                e = sig[(sig.regime == reg) & (sig.up == up)]
                if not len(e):
                    continue
                out = []
                for buf in (1.0, 1.8):
                    r = np.array([trade(part, s, buf, 0.7) for s in e.itertuples()])
                    r = r[~np.isnan(r)]
                    out.append(f"{(r > 0).mean():4.0%}, {r.mean():+.3f}")
                print(f"{reg:6s} | {'SELL' if up else 'BUY ':4s} | {len(e):6d} | {out[0]:22s} | {out[1]}")


if __name__ == "__main__":
    main()
