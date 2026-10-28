"""phase.py by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_phase.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase import efficiency, features, way, width  # noqa: E402


def test_efficiency_by_hand():
    straight = 100.0 + np.arange(10)
    assert efficiency(straight, 4)[-1] == 1.0 and np.isnan(efficiency(straight, 4)[3])
    zig = np.array([100.0, 101, 100, 101, 100, 101])  # 4 bars: moves 1+1+1+1 = 4, back where it was: net 0
    e = efficiency(zig, 4)
    assert e[4] == 0.0 and e[5] == 0.0
    assert efficiency(np.array([100.0, 101, 100, 101, 102]), 4)[4] == pytest.approx(0.5)  # net 2 over a path of 4
    assert efficiency(100.0 - np.arange(10), 4)[-1] == 1.0  # a straight fall is as efficient as a straight rise
    assert efficiency(np.full(6, 5.0), 4)[-1] != efficiency(np.full(6, 5.0), 4)[-1]  # no move at all: NaN


def test_way_and_width():
    c = np.array([100.0, 102, 101, 99, 98])
    assert way(c, 3).tolist()[3:] == [-1.0, -1.0]
    n = 30
    c = 100.0 + np.arange(n)
    w = width(c + 0.5, c - 0.5, c, 10)
    # the last 10 bars span 29.5 - 19.5 = 10 ... highs 120.5..129.5, lows 119.5..128.5 -> 129.5 - 119.5 = 10; ATR 1.5
    assert w[-1] == pytest.approx(10 / 1.5)


def test_only_days_complete_by_the_moment():
    # 25 server days of steady rises, then a moment inside day 26: D1 readings from day 25's bar
    idx = pd.date_range("2026-03-01 22:00", periods=26 * 1440, freq="1min", tz="UTC")  # Athens winter: days start 22:00 UTC
    c = 2000 + np.arange(len(idx)) * 0.01
    c[-1440:] = c[-1441] - np.arange(1, 1441) * 0.05  # day 26 falls hard: still forming at the moment, it must not count
    m = pd.DataFrame({"open": c, "high": c + 0.005, "low": c - 0.005, "close": c}, index=idx)
    t = pd.DatetimeIndex([idx[-1] - pd.Timedelta(hours=3)])
    X = features(m, t)
    assert X["D1_er20"].iloc[0] == pytest.approx(1.0) and X["D1_way20"].iloc[0] == 1.0
