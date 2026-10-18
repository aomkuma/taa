"""loc.location by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_loc.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loc import location  # noqa: E402


def test_location_by_hand():
    # a larger timeframe of 6 bars completing at 10, 20, .. 60; its swings: a bottom 100 (bar 1, known at bar 2), a top
    # 120 (bar 3, known at bar 4), a bottom 105 (bar 4, known at bar 5)
    Y = dict(avail=np.array([10, 20, 30, 40, 50, 60]), h=np.array([110.0, 104.0, 112.0, 120.0, 114.0, 113.0]),
             lo=np.array([102.0, 100.0, 103.0, 108.0, 105.0, 107.0]), atr=np.full(6, 2.0),
             piv=(np.array([1, 3, 4]), np.array([100.0, 120.0, 105.0]), np.array([-1, 1, -1]), np.array([2, 4, 5])))
    # at t = 55 the last closed bar is bar 4 (completed at 50): range 100 .. 120; the swings known: bottom 100, top 120
    # (the bottom 105 is known only at bar 5); a price 106: pos 0.3, 3 ATRs above 100, 7 ATRs below 120
    L = location(np.array([55]), np.array([106.0]), Y)
    assert np.allclose(L.iloc[0].to_numpy(), [0.3, 3.0, 7.0])
    # at t = 60 bar 5 is closed: the bottom 105 is known and nearer: 0.5 ATR
    L = location(np.array([60]), np.array([106.0]), Y)
    assert np.allclose(L.iloc[0].to_numpy(), [0.3, 0.5, 7.0])
    # a price above every top: no top above
    L = location(np.array([60]), np.array([121.0]), Y)
    assert math.isnan(L.d_top.iloc[0]) and math.isclose(L.pos.iloc[0], 1.05)
    # before any bar is closed: nothing
    assert math.isnan(location(np.array([5]), np.array([106.0]), Y).pos.iloc[0])


def test_location_keeps_to_the_window(monkeypatch):
    import loc  # noqa: PLC0415

    monkeypatch.setattr(loc, "WIN", 3)  # a window of the last 3 bars
    Y = dict(avail=np.array([10, 20, 30, 40, 50, 60]), h=np.array([110.0, 104.0, 112.0, 120.0, 114.0, 113.0]),
             lo=np.array([102.0, 100.0, 103.0, 108.0, 105.0, 107.0]), atr=np.full(6, 2.0),
             piv=(np.array([1, 3, 4]), np.array([100.0, 120.0, 105.0]), np.array([-1, 1, -1]), np.array([2, 4, 5])))
    # at t = 60 the window is bars 3..5 (range 105 .. 120); a price 103 is below it; the bottom 100 (bar 1) is outside
    # the window and 105 is above the price: no bottom below
    L = loc.location(np.array([60]), np.array([103.0]), Y)
    assert math.isnan(L.d_bot.iloc[0]) and math.isclose(L.pos.iloc[0], -2 / 15)
