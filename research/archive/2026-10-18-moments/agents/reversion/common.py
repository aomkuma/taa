"""Shared arrays and helpers for the reversion agent (research only).

Bars: gold M1 from 2023-09-01 (bid OHLC, spread in USD). Decide at bar i's close (features use bars <= i);
orders act from bar i + 1. Development half-years are before 2026-03-01; the test window 2026-03-01 .. 10-14.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")  # run from the repo root (gold.py reads data/ relative)
import gold  # noqa: E402

SLIP, REF = 0.07, 4100.0
DEV = [
    ("H1 2023-11..2024-04", "2023-11-01", "2024-05-01"),
    ("H2 2024-05..2024-10", "2024-05-01", "2024-11-01"),
    ("H3 2024-11..2025-04", "2024-11-01", "2025-05-01"),
    ("H4 2025-05..2025-10", "2025-05-01", "2025-11-01"),
    ("H5 2025-11..2026-02", "2025-11-01", "2026-03-01"),
]
TEST = [("TEST 2026-03..10-14", "2026-03-01", "2026-10-15")]


class Bars:
    def __init__(self, start: str = "2023-09-01") -> None:
        m = gold.bars("M1")
        m = m[(m.index >= pd.Timestamp(start, tz="UTC")) & (m.index < pd.Timestamp("2026-10-15", tz="UTC"))]
        self.ot = m.index
        self.t64 = m.index.as_unit("ns").asi8
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * 0.01
        self.n = len(self.o)
        # minutes since the previous bar (gaps: weekends, breaks)
        self.gap = np.r_[999, np.diff(self.t64) // 60_000_000_000]
        utc = self.ot
        self.hour = utc.hour.to_numpy()
        ny = utc.tz_convert("America/New_York")
        self.ny_min = (ny.hour * 60 + ny.minute).to_numpy()
        ldn = utc.tz_convert("Europe/London")
        self.ldn_min = (ldn.hour * 60 + ldn.minute).to_numpy()
        self.utc_min = (utc.hour * 60 + utc.minute).to_numpy()

    def idx(self, a: str) -> int:
        return int(self.ot.searchsorted(pd.Timestamp(a, tz="UTC")))

    def session(self) -> np.ndarray:
        """0 Asia 00:00-07:00 UTC, 1 London 07:00 London .. 08:00 ET, 2 New York 08:00-12:00 ET, 3 other."""
        s = np.full(self.n, 3, np.int8)
        s[(self.utc_min >= 0) & (self.utc_min < 420)] = 0
        s[(self.ldn_min >= 420) & (self.ny_min < 480)] = 1
        s[(self.ny_min >= 480) & (self.ny_min < 720)] = 2
        return s

    def contiguous(self, k: int) -> np.ndarray:
        """True where bars i-k .. i are consecutive minutes (no gap > 1 min)."""
        g = (self.gap > 1).astype(np.int64)
        cs = np.cumsum(g)
        ok = np.zeros(self.n, bool)
        ok[k:] = cs[k:] == cs[:-k]
        return ok


def ema(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def rstd(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).std().to_numpy()


def h1_trend(B: Bars) -> np.ndarray:
    """H1 trend at each M1 bar from H1 bars closed before it: +1 when EMA20 rises and close > EMA50, -1 the
    mirror, else 0 (the earlier rounds' tide)."""
    s = pd.Series(B.c, index=B.ot)
    h1 = s.resample("1h", label="left", closed="left").last().dropna()
    e20, e50 = h1.ewm(span=20, adjust=False).mean(), h1.ewm(span=50, adjust=False).mean()
    tr = np.where((e20.diff() > 0) & (h1 > e50), 1, np.where((e20.diff() < 0) & (h1 < e50), -1, 0))
    # the H1 bar opening at T closes at T+1h; an M1 bar at t sees H1 bars whose close <= t's close (t + 1 min)
    avail = h1.index + pd.Timedelta(hours=1)
    pos = np.searchsorted(avail.as_unit("ns").asi8, B.t64 + 60_000_000_000, side="right") - 1
    out = np.where(pos >= 0, tr[np.clip(pos, 0, None)], 0)
    return out.astype(np.int8)
