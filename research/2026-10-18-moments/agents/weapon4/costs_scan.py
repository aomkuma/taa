"""weapon4: spread vs the M1 / M5 / M15 range per market (design 2025-09 .. 2026-02 and 2024-03 .. 2024-08), by UTC
hour: is a 72-h-extreme scalp affordable there? Spread = the M1 column (the minute's minimum) x point.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/costs_scan.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research/2026-10-18-moments"))
import gold  # noqa: E402

gold.below_normal_priority()
SYMS = ["XAUUSD", "XAUAUD", "US100", "US30", "US500", "JP225", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
for sym in SYMS:
    H = ROOT / f"data/history/FBS-Demo/{sym}"
    point = json.load(open(H / "spec.json"))["spec"]["point"]
    m = pd.read_parquet(H / "M1.parquet")
    m.index = pd.DatetimeIndex(pd.to_datetime(m.open_time, utc=True))
    for a, b in (("2024-03-01", "2024-09-01"), ("2025-09-01", "2026-03-01")):
        x = m[(m.index >= a) & (m.index < b)]
        sp = x.spread * point
        r1 = x.high - x.low
        m15 = x.resample("15min").agg({"high": "max", "low": "min"}).dropna()
        r15 = (m15.high - m15.low)
        h = x.index.hour
        hs = pd.DataFrame({"sp": sp, "r1": r1, "h": h}).groupby("h").median()
        r15h = r15.groupby(r15.index.hour).median()
        hs["r15"] = r15h
        hs["sp/r1"] = hs.sp / hs.r1
        hs["sp/r15"] = hs.sp / hs.r15
        act = hs[hs.r1 > 0]
        print(f"{sym} {a[:7]}..{b[:7]} price {x.close.median():.5g} spread med {sp.median():.5g} M1 range {r1.median():.5g}"
              f" ({sp.median() / r1.median():.2f}) M15 range {r15.median():.5g} ({sp.median() / r15.median():.3f})")
        print("   sp/M15 range by UTC hour: " + " ".join(f"{k}:{v:.2f}" for k, v in act["sp/r15"].items()))
