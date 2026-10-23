"""Independent re-derivation (SPEC.md 4.4) of app/strategy/strong_levels.py: the swings, the merge and the strong
levels written again with plain loops on DataFrames (no shared helper), compared at 120 decision times over
2026-09-01 .. 10-22 on the stored XAUUSD H4 / D1 bars; then the strong levels on 2026-10-21 18:00 Thai (the owner's
chart) printed next to the owner's lines.

    .venv/Scripts/python research/2026-10-23-entry/rederive_strong_levels.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.strategy import strong_levels as sl  # noqa: E402
from app.strategy import zone_grid as zg  # noqa: E402
from app.strategy.plan1_b2 import Bars  # noqa: E402


def load(tf: str, hours: int) -> pd.DataFrame:
    d = pd.read_parquet(ROOT / f"data/history/FBS-Demo/XAUUSD/{tf}.parquet")
    d["t"] = pd.to_datetime(d.open_time, utc=True)
    d = d.drop_duplicates("t", keep="last").set_index("t").sort_index()
    d["avail"] = d.index + pd.Timedelta(hours=hours)
    return d


def to_bars(d: pd.DataFrame) -> Bars:
    t = d.index.as_unit("ns").asi8
    return Bars(t, d.avail.dt.as_unit("ns").astype("int64").to_numpy(), d.open.to_numpy(float), d.high.to_numpy(float),
                d.low.to_numpy(float), d.close.to_numpy(float))


def swings_plain(d: pd.DataFrame, t: pd.Timestamp, last: int) -> list[tuple[float, int, float]]:
    x = d[d.avail <= t]
    rows = list(x.itertuples())
    out = []
    first = max(2, len(rows) - last)
    for j in range(first, len(rows) - 2):
        hj, lj = rows[j].high, rows[j].low
        nb = [rows[i] for i in (j - 2, j - 1, j + 1, j + 2)]
        after = rows[j + 1 : j + 13]
        if all(hj > r.high for r in nb):
            out.append((hj, 1, hj - min(r.low for r in after)))
        if all(lj < r.low for r in nb):
            out.append((lj, -1, max(r.high for r in after) - lj))
    return out


def strong_plain(h4: pd.DataFrame, d1: pd.DataFrame, t: pd.Timestamp, step: float) -> list[float]:
    items = sorted(swings_plain(h4, t, 500) + swings_plain(d1, t, 250))
    levels, group = [], []
    for p, k, turn in items:
        if group and p - sum(g[0] for g in group) / len(group) > 0.15 * step:
            levels.append(group)
            group = []
        group.append((p, k, turn))
    if group:
        levels.append(group)
    out = [sum(g[0] for g in grp) / len(grp) for grp in levels if len(grp) >= 2 or max(g[2] for g in grp) >= step]
    x = h4[h4.avail <= t].iloc[-500:]
    return sorted(out + [x.high.max(), x.low.min()])


h4, d1 = load("H4", 4), load("D1", 24)
B4, B1 = to_bars(h4), to_bars(d1)
G = zg.grid_rows(B1.t_open, B1.o, B1.h, B1.lo, B1.c)
times = pd.date_range("2026-09-01", "2026-10-22", periods=120, tz="UTC")
bad = 0
for t in times:
    st = zg.grid_at(G, t.value)
    app = sorted(lv.price for lv in sl.strong_levels(B4, B1, t.value, st.step) if lv.source != "shift")
    plain = strong_plain(h4, d1, t, st.step)
    if len(app) != len(plain) or not np.allclose(app, plain):
        bad += 1
        if bad <= 3:
            print("MISMATCH", t, len(app), len(plain))
print(f"re-derivation: {len(times) - bad} / {len(times)} decision times equal")

t = pd.Timestamp("2026-10-21 11:00", tz="UTC")
st = zg.grid_at(G, t.value)
anchors = [float(G.anchor[i]) for i in np.flatnonzero(G.shift[: st.row + 1])[-6:]]
lv = sl.strong_levels(B4, B1, t.value, st.step, anchors)
print(f"\n2026-10-21 18:00 Thai: step {st.step:.1f}; strong levels between 3,900 and 4,450 (owner's lines 4,369 / 4,293 / 4,217 / 4,141 / 4,066 / 3,990):")
for x in lv:
    if 3900 < x.price < 4450:
        print(f"  {x.price:8.1f}  touches {x.touches}  turn {x.turn:6.1f}  kinds {x.kinds:+d}  {x.source}")
