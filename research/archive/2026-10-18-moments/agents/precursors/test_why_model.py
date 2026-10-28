"""why_model.spaced and why_model.picks by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_why_model.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from why_model import picks, spaced  # noqa: E402


def test_spaced_one_an_hour():
    t = pd.Series(pd.to_datetime(["2026-05-04 08:00", "2026-05-04 08:30", "2026-05-04 09:00", "2026-05-04 09:05", "2026-05-04 10:10"], utc=True))
    keep = np.array([True, True, True, True, True])
    # 08:00 taken; 08:30 too soon; 09:00 exactly an hour later - taken; 09:05 too soon; 10:10 taken
    assert spaced(t, keep).tolist() == [True, False, True, False, True]
    assert spaced(t, np.array([False, True, False, True, True])).tolist() == [False, True, False, False, True]


def test_picks_sides_and_wins():
    t = pd.to_datetime(["2026-05-04 08:00", "2026-05-04 10:00", "2026-05-04 12:00", "2026-05-04 14:00"], utc=True)
    D = pd.DataFrame({"t": t, "up": [True, False, False, True], "dn": [False, True, True, False]})
    S = picks(D, np.array([0.70, 0.30, 0.50, 0.45]), 0.6)
    # 0.70 a buy (up first: a win); 0.30 a sell (down first: a win); 0.50 no pick; 0.45 is above 1 - 0.6: no pick
    assert S.side.tolist() == [1, -1] and S.win.tolist() == [True, True]
