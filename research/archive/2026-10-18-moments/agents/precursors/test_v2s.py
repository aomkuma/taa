"""v2s.py by hand: the side from (days, lean), and the trigger situation's lean from a five-moment library.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_v2s.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from picture import KEYS  # noqa: E402
from v2s import situation_leans, side_of  # noqa: E402


def test_side_of_by_hand():
    assert side_of(5, 0.2, 5, 0.2) == 1  # exactly the minimum days and the threshold
    assert side_of(5, -0.2, 5, 0.2) == -1
    assert side_of(4, 0.9, 5, 0.2) == 0  # too few days
    assert side_of(9, 0.19, 5, 0.2) == 0  # a lean too weak
    assert side_of(9, float("nan"), 5, 0.2) == 0


def test_situation_leans_by_hand():
    # the evaluated moment (row 4, day 10) on M5 and M1: smoothness 0.3, pullback 0.5 ATR, close above its last top,
    # the 120 bars up, size 5 ATR, at 0.8 of the range
    me = dict(size=5.0, pos=0.8, edge=0, leg_way=1, leg=1.0, net_way=1, struct=1, brk=1, retr=0.5, er=0.3,
              seg0=1, seg1=0, seg2=1)
    rows = [(dict(me), dict(me)),  # row 0, day 0: the same situation in every part on both - ran up
            (dict(me, net_way=-1), dict(me)),  # row 1, day 1: the same L3 situation, M5's 120 bars down (not L6) - ran down
            (dict(me), dict(me, brk=0)),  # row 2, day 3: M5 the same, M1 between its last top and bottom (neither) - ran up
            (dict(me), dict(me)),  # row 3, day 5: the same in every part but within 7 days of row 4 - ran down
            (dict(me), dict(me))]  # row 4, day 10: the moment evaluated
    T = pd.DataFrame({f"{tf}_{k}": [r[j][k] for r in rows] for j, tf in enumerate(("M5", "M1")) for k in KEYS})
    cls = np.array(["ran_up", "ran_dn", "ran_up", "ran_dn", "flat"])
    day = np.array([0, 1, 3, 5, 10])
    SH = np.zeros((5, 6, 40))
    out = situation_leans(T, SH, day, cls, np.array([4, 2]), [4, 5])
    # L3: rows 0 and 1 (two days: one up, one down) -> lean 0; L6: row 0 only -> one day, lean +1
    assert tuple(out["L3"][0]) == (2.0, 0.0)
    assert tuple(out["L6"][0]) == (1.0, 1.0)
    # row 2 (day 3): nothing 7 days before it
    assert out["L3"][1][0] == 0 and math.isnan(out["L3"][1][1])
