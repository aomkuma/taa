"""Prediction 2 of HYPOTHESIS.md, measured directly: how often the fixed 5.00 USD take-profit floor rejected a
signal that was otherwise complete, in each period.

If the absolute floor is what drifted, it must reject far more in 2023 (where 5 USD is 0.95 x the H1 ATR) than
in 2026 (0.23 x). If it rejects about the same share everywhere, the floor was never the thing that changed
and the hypothesis is wrong.

    .venv/Scripts/python research/2026-10-26-three-bots/gate_bite.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bots  # noqa: E402
from audit import BEST  # noqa: E402
from relative import PERIODS, h1_atr  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.zigzag import zigzag  # noqa: E402


def count(f: dict, start: pd.Timestamp, end: pd.Timestamp) -> tuple[int, int, float]:
    """(signals whose geometry was complete, of those how many the 5 USD floor rejected, the mean 5/ATR)."""
    m1, h1 = f[Timeframe.M1], f[Timeframe.H1]
    h4 = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    m1 = m1[(m1.index >= start - pd.Timedelta(days=3)) & (m1.index < end + pd.Timedelta(days=2))]
    m5 = m1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    whole, blocked, ratios = 0, 0, []
    for day in pd.date_range(start, end, freq="D"):
        if day.weekday() >= 5:
            continue
        for w0, w1 in bots.windows(day):
            bars = m5[(m5.index >= w0 - pd.Timedelta(hours=2)) & (m5.index < w1)]
            seen, sw, sw4, atr = None, [], [], 0.0
            for i in range(len(bars)):
                t = bars.index[i] + pd.Timedelta(minutes=5)
                if t <= w0 or t > w1:
                    continue
                hx = h1[h1.index + pd.Timedelta(hours=1) <= t].iloc[-400:]
                if seen != len(hx):
                    seen = len(hx)
                    atr = h1_atr(h1, t)
                    sw, _ = zigzag(hx.high.to_numpy(float), hx.low.to_numpy(float))
                    h4x = h4[h4.index + pd.Timedelta(hours=4) <= t].iloc[-300:]
                    sw4, _ = zigzag(h4x.high.to_numpy(float), h4x.low.to_numpy(float))
                if len(sw) < 3 or atr <= 0:
                    continue
                past = bars.iloc[: i + 1]
                for name, p in BEST.items():
                    # the same signal twice: once with the floor at 0 (geometry only), once at 5.00 USD
                    free = bots.signal(name, sw, sw4, past, replace(p, min_tp=0.0), t)
                    if free is None:
                        continue
                    whole += 1
                    ratios.append(5.0 / atr)
                    if bots.signal(name, sw, sw4, past, p, t) is None:
                        blocked += 1
    return whole, blocked, (sum(ratios) / len(ratios) if ratios else 0.0)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in (Timeframe.M1, Timeframe.H1)}
    print("| period | complete signals | rejected by the 5 USD floor | share | 5 USD in H1 ATRs |")
    print("|---|---|---|---|---|")
    for name, (s, e) in PERIODS.items():
        whole, blocked, ratio = count(f, pd.Timestamp(s, tz="UTC"), pd.Timestamp(e, tz="UTC"))
        share = f"{blocked / whole:.0%}" if whole else "-"
        print(f"| {name} | {whole} | {blocked} | {share} | {ratio:.2f} |")


if __name__ == "__main__":
    main()
