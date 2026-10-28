"""Audit 2: indicators.bars by hand - the server day in winter and on both DST-change nights, and `avail`.

Synthetic continuous M1 (every minute, weekends included, so the bucketing rule shows on its own).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "precursors"))
from indicators import at, bars  # noqa: E402


def m1(start: str, end: str) -> pd.DataFrame:
    """Every minute in [start, end); open = the minute's number, high = open + 0.5, low = open - 0.5, close = open + 0.25."""
    idx = pd.date_range(start, end, freq="1min", tz="UTC", inclusive="left")
    o = np.arange(len(idx), dtype=float)
    return pd.DataFrame({"open": o, "high": o + 0.5, "low": o - 0.5, "close": o + 0.25, "tick_volume": 1.0,
                         "spread": 20.0}, index=idx)


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def test_d1_in_winter_starts_at_22_utc() -> None:
    m = m1("2026-01-13 20:00", "2026-01-15 00:00")  # Athens UTC+2
    d = bars(m, "1D")
    assert d["last"].tolist() == [ts("2026-01-13 21:59"), ts("2026-01-14 21:59"), ts("2026-01-14 23:59")]
    assert d["open"].iloc[1] == 120.0  # 2026-01-13 22:00 is minute 120 of the series
    assert d["high"].iloc[1] == 120 + 24 * 60 - 1 + 0.5


def test_spring_forward_night_2026_03_29() -> None:
    """Athens jumps 03:00 -> 04:00 at 01:00 UTC: the server day of Sunday 29 March is 23 h (22:00 .. 21:00 UTC)
    and its first H4 bar (00:00 local) is 3 h (22:00 .. 01:00 UTC)."""
    m = m1("2026-03-28 21:00", "2026-03-30 00:00")
    d = bars(m, "1D")
    assert d["last"].tolist() == [ts("2026-03-28 21:59"), ts("2026-03-29 20:59"), ts("2026-03-29 23:59")]
    assert d["avail"].iloc[1] == ts("2026-03-29 21:00")
    h4 = bars(m, "4h")
    first_of_day = h4[h4["last"] > ts("2026-03-28 22:00")].iloc[0]
    assert first_of_day["last"] == ts("2026-03-29 00:59")  # 3 hours: 22:00 .. 00:59 UTC
    assert first_of_day["open"] == 60.0  # 2026-03-28 22:00 is minute 60


def test_fall_back_night_2025_10_26() -> None:
    """Athens goes 04:00 -> 03:00 at 01:00 UTC: the local hour 03:xx happens twice, so the first H4 bar (00:00 local) is
    5 h (21:00 .. 02:00 UTC) and the server day of Sunday 26 October is 25 h (21:00 .. 22:00 UTC)."""
    m = m1("2025-10-25 20:00", "2025-10-27 00:00")
    h4 = bars(m, "4h")
    first_of_day = h4[h4["last"] > ts("2025-10-25 21:00")].iloc[0]
    assert first_of_day["last"] == ts("2025-10-26 01:59") and first_of_day["open"] == 60.0
    d = bars(m, "1D")
    assert d["last"].tolist() == [ts("2025-10-25 20:59"), ts("2025-10-26 21:59"), ts("2025-10-26 23:59")]


def test_avail_after_a_quiet_last_minute_is_the_last_minute_plus_one() -> None:
    """The rule as written: an M5 bar with no 06:03 / 06:04 minutes is available at 06:03 - before it ends at 06:05.
    Its prices then equal the forming bar's at 06:03 (nothing came after), so no price from the future is used; only
    the "complete" flag is early (5 such M5 bars in the learning parts, 0 for M15 / H1 / H4 / D1: check_bars.py)."""
    m = m1("2025-11-10 06:00", "2025-11-10 06:10").drop([ts("2025-11-10 06:03"), ts("2025-11-10 06:04")])
    b = bars(m, "5min")
    assert b["avail"].tolist() == [ts("2025-11-10 06:03"), ts("2025-11-10 06:10")]
    assert at(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, np.array([ts("2025-11-10 06:03").value]))[0] == 0


def test_clock_bars_and_their_prices() -> None:
    m = m1("2026-01-14 10:00", "2026-01-14 11:00")
    b = bars(m, "15min")
    assert len(b) == 4
    assert b.iloc[1][["open", "high", "low", "close"]].tolist() == [15.0, 29.5, 14.5, 29.25]
    assert b["avail"].iloc[1] == ts("2026-01-14 10:30")
