"""verify_p4's own clock by hand: the US summer-time rule and the three windows.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_verify_p4.py -q
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_p4 as V  # noqa: E402

U = lambda s: pd.Timestamp(s, tz="UTC").value  # noqa: E731


def test_us_summer_time_rule():
    # 2025: 9 Mar - 2 Nov; 2026: 8 Mar - 1 Nov (the second Sunday of March, the first Sunday of November)
    assert not V.us_summer(datetime(2026, 3, 7)) and V.us_summer(datetime(2026, 3, 8)) and V.us_summer(datetime(2025, 11, 1))
    assert not V.us_summer(datetime(2025, 11, 2)) and not V.us_summer(datetime(2026, 1, 9)) and V.us_summer(datetime(2025, 3, 9))
    assert not V.us_summer(datetime(2025, 3, 8))


def test_its_windows():
    assert V.window_of(U("2026-01-12 00:00")) == "Asia" and V.window_of(U("2026-01-12 02:00")) is None
    assert V.window_of(U("2026-01-12 06:59")) == "London" and V.window_of(U("2026-01-12 07:00")) is None
    assert V.window_of(U("2026-01-12 05:30"), 30) == "London" and V.window_of(U("2026-01-12 07:29"), 30) == "London"
    assert V.window_of(U("2026-01-12 14:30")) == "NY" and V.window_of(U("2026-01-12 14:29")) is None  # EST
    assert V.window_of(U("2026-01-12 16:29")) == "NY" and V.window_of(U("2026-01-12 16:30")) is None
    assert V.window_of(U("2026-03-09 13:30")) == "NY" and V.window_of(U("2026-03-09 15:30")) is None  # EDT
    assert V.window_of(U("2025-10-31 13:30")) == "NY" and V.window_of(U("2025-11-03 13:30")) is None  # EDT -> EST


def test_its_new_york_minute():
    assert V.ny_minute(U("2026-01-12 15:00")) == 600 and V.ny_minute(U("2026-03-09 14:00")) == 600
    assert V.ny_minute(U("2026-03-09 14:29")) == 629
