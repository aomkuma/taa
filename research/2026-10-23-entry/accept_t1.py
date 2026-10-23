"""Acceptance (SPEC.md 4.5): trigger T1 on the owner's chart (XAUUSD 2026-10-16 .. 23): does it find the sell
re-test of the broken 4,141 line, the stop above the swept 4,155.5, and what the grid's lines were each day.

    .venv/Scripts/python research/2026-10-23-entry/accept_t1.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from app.strategy import zone_grid as zg  # noqa: E402
from app.strategy import zone_retest as zr  # noqa: E402


def load(tf: str) -> pd.DataFrame:
    d = pd.read_parquet(ROOT / f"data/history/FBS-Demo/XAUUSD/{tf}.parquet")
    d["t"] = pd.to_datetime(d.open_time, utc=True)
    return d.drop_duplicates("t", keep="last").set_index("t").sort_index()


d1 = load("D1")
G = zg.grid_rows(d1.index.as_unit("ns").asi8, d1.open.to_numpy(float), d1.high.to_numpy(float), d1.low.to_numpy(float),
                 d1.close.to_numpy(float))
for day in pd.date_range("2026-10-16", "2026-10-23", freq="D", tz="UTC"):
    st = zg.grid_at(G, (day + pd.Timedelta(hours=12)).value)
    if np.isfinite(st.anchor):
        lines = [st.anchor + k * st.step for k in range(-3, 1)]
        print(f"{day.date()} grid: anchor {st.anchor:.2f} step {st.step:.2f} -> lines {', '.join(f'{x:.1f}' for x in sorted(lines, reverse=True))}")
print("owner's lines: 4369.19, 4293.24, 4217.25, 4141.83, 4066.41, 3989.57\n")
for tf, minutes in (("H4", 240), ("H1", 60), ("M15", 15)):
    b = load(tf)
    b = b[(b.index >= "2026-09-01") & (b.index < "2026-10-24")]
    avail = b.index.as_unit("ns").asi8 + minutes * 60 * 10**9
    k = np.searchsorted(G.known, avail, side="right") - 1
    ev = zr.zone_retests(b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float), G.anchor[k], G.step[k])
    print(f"{tf}: re-tests from 2026-10-19 (Thai time = the bar's close):")
    for e in ev:
        t = b.index[e.entry_bar] + pd.Timedelta(minutes=minutes)
        if t >= pd.Timestamp("2026-10-19", tz="UTC"):
            print(f"  {t.tz_convert('Asia/Bangkok'):%a %d %H:%M}  {'SELL' if e.side < 0 else 'BUY'} line {e.line:.1f} broke "
                  f"{(b.index[e.break_bar] + pd.Timedelta(minutes=minutes)).tz_convert('Asia/Bangkok'):%a %d %H:%M}, entry {e.entry:.1f}, "
                  f"stop {e.stop:.1f} (extreme {e.extreme:.1f}), risk {abs(e.entry - e.stop):.1f}")
