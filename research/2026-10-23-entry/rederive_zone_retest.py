"""Independent re-derivation (SPEC.md 4.4) of app/strategy/zone_retest.py: the same rules written as one pass over
the bars with a state per grid line (no shared code), compared on M15 2025-01 .. 2025-12.

    .venv/Scripts/python research/2026-10-23-entry/rederive_zone_retest.py
"""

import math
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


def plain(h, lo, c, anchor, step):
    states = {}  # (anchor, k) -> dict(line, d, start, extreme, end)
    events = []
    for j in range(1, len(c)):
        # first the breaks already running (their bars after the break)
        for key, s0 in list(states.items()):
            if s0["done"] or j <= s0["start"]:
                continue
            if j > s0["start"] + 96:
                s0["done"] = True
                continue
            d, line, band = s0["d"], s0["line"], s0["band"]
            s0["extreme"] = max(s0["extreme"], h[j]) if d < 0 else min(s0["extreme"], lo[j])
            if (c[j] - line) * d < -band:
                s0["done"] = True
                s0["ended"] = j
                continue
            touch = (h[j] >= line - band) if d < 0 else (lo[j] <= line + band)
            prev = (h[j - 1] >= line - band) if d < 0 else (lo[j - 1] <= line + band)
            if touch and not prev and (c[j] - line) * d > 0:
                stop = s0["extreme"] + 0.05 * s0["s"] if d < 0 else s0["extreme"] - 0.05 * s0["s"]
                events.append((s0["start"], j, d, round(stop, 6)))
        a, s = anchor[j], step[j]
        if not (math.isfinite(a) and math.isfinite(s) and s > 0):
            continue
        half, band = s / 2, 0.15 * s
        lo_p, hi_p = min(c[j - 1], c[j]) - band, max(c[j - 1], c[j]) + band
        for k in range(math.floor((lo_p - a) / half), math.ceil((hi_p - a) / half) + 1):
            line = a + k * half
            d = 1 if c[j] - line > band else -1 if line - c[j] > band else 0
            if d == 0:
                continue
            key = (round(a, 2), k)
            s0 = states.get(key)
            if s0 is not None and not s0["done"]:
                continue
            if s0 is not None and s0.get("ended") is None and j <= s0["start"] + 96:
                continue
            past = c[max(0, j - 32) : j]
            if not np.any((past - line) * d < 0):
                continue
            states[key] = dict(line=line, d=d, start=j, extreme=c[j], band=band, s=s, done=False, ended=None)
    return events


m, d1 = load("M15"), load("D1")
m = m[(m.index >= "2025-01-01") & (m.index < "2026-01-01")]
G = zg.grid_rows(d1.index.as_unit("ns").asi8, d1.open.to_numpy(float), d1.high.to_numpy(float), d1.low.to_numpy(float),
                 d1.close.to_numpy(float))
k = np.searchsorted(G.known, m.index.as_unit("ns").asi8 + 15 * 60 * 10**9, side="right") - 1
h, lo, c = m.high.to_numpy(float), m.low.to_numpy(float), m.close.to_numpy(float)
app = sorted((e.break_bar, e.entry_bar, e.side, round(e.stop, 6)) for e in zr.zone_retests(h, lo, c, G.anchor[k], G.step[k]))
ref = sorted(plain(h, lo, c, G.anchor[k], G.step[k]))
print(f"M15 2025: app {len(app)} events, plain {len(ref)}, equal {app == ref}")
if app != ref:
    sa, sr = set(app), set(ref)
    print("only app", sorted(sa - sr)[:5], "only plain", sorted(sr - sa)[:5])
print("RE-DERIVATION", "OK" if app == ref else "FAILED")
