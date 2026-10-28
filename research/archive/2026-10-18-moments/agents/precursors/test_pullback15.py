"""pullback15.structure and pullback15.active by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_pullback15.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pullback15 import active, structure  # noqa: E402


def zigzag_minutes(points, per_leg=150, start="2026-05-04 00:00"):
    """M1 bars walking straight between the given prices, per_leg minutes a leg (M15: 10 bars a leg)."""
    path = []
    for a, b in zip(points[:-1], points[1:]):
        path += list(np.linspace(a, b, per_leg, endpoint=False))
    path.append(points[-1])
    c = np.array(path)
    idx = pd.date_range(start, periods=len(c), freq="1min", tz="UTC")
    return pd.DataFrame({"open": c, "high": c + 0.2, "low": c - 0.2, "close": c, "tick_volume": 1.0, "spread": 20.0}, index=idx)


def test_up_and_down_structure_on_m15():
    # higher highs and higher lows (legs of 40-60 USD with an ATR of a few USD): up; the mirror: down
    up = zigzag_minutes([100, 160, 130, 200, 170, 240, 210, 280])
    t = np.array([(up.index[-1] + pd.Timedelta(minutes=1)).value])
    assert structure(up, t).tolist() == [1]
    dn = zigzag_minutes([280, 220, 250, 180, 210, 140, 170, 100])
    t = np.array([(dn.index[-1] + pd.Timedelta(minutes=1)).value])
    assert structure(dn, t).tolist() == [-1]


def test_the_active_hours_in_their_zones():
    # summer: the NY open 09:30 = 13:30 UTC; the PM fix 15:00 London = 14:00 UTC; the US data 08:30 = 12:30 UTC
    t = pd.DatetimeIndex(["2026-06-15 13:30", "2026-06-15 11:31", "2026-06-15 11:19", "2026-06-15 14:59", "2026-06-15 15:01", "2026-06-15 06:00"], tz="UTC")
    # 11:31: 59 min before the US data (12:30 UTC); 11:19: 61 min before the COMEX open (12:20 UTC) - out; 14:59: 59 min
    # after the PM fix (14:00 UTC); 15:01: 61 min after it and 91 after the NY open - out
    assert active(t).tolist() == [True, True, False, True, False, False]
    # winter: the PM fix 15:00 London = 15:00 UTC, the NY open 09:30 = 14:30 UTC
    w = pd.DatetimeIndex(["2026-01-15 15:59", "2026-01-15 16:01"], tz="UTC")
    assert active(w).tolist() == [True, False]


def test_nothing_after_the_moment_changes_the_structure():
    m = zigzag_minutes([100, 160, 130, 200, 170, 240, 210, 280, 250, 300])
    for k in range(400, len(m) - 1, 37):
        t = m.index[k] + pd.Timedelta(minutes=1)
        full = structure(m, np.array([t.value]))
        cut = structure(m[m.index < t], np.array([t.value]))
        # the cut data holds the forming M15 bar too; it must not be read in either
        assert full.tolist() == cut.tolist(), str(t)
