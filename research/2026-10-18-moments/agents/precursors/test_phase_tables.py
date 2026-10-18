"""phase_tables.turned and phase_tables.by_days by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_phase_tables.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase_tables import by_days, turned  # noqa: E402


def test_turned_to_the_d1_way():
    X = pd.DataFrame({"H4_pos": [0.9, 0.9, 0.2], "H1_ema50": [2.0, 2.0, -1.0], "H1_rsi": [70.0, 70.0, 40.0], "H1_struct": [1, 9, -1],
                      "vol_rel": [1.5, 1.5, 0.5]})
    way = np.array([1.0, -1.0, -1.0])
    # D1 up: as it is; D1 down: the place mirrored, signed readings flipped, RSI centred and flipped, 9 unknown
    assert turned(X, "H4_pos", way).tolist() == pytest.approx([0.9, 0.1, 0.8])
    assert turned(X, "H1_ema50", way).tolist() == [2.0, -2.0, 1.0] and turned(X, "H1_rsi", way).tolist() == [20.0, -20.0, 10.0]
    s = turned(X, "H1_struct", way)
    assert s[0] == 1.0 and np.isnan(s[1]) and s[2] == 1.0 and turned(X, "vol_rel", way).tolist() == [1.5, 1.5, 0.5]


def test_by_days_takes_each_days_first_moment():
    t = pd.to_datetime(["2026-05-04 02:00", "2026-05-04 03:00", "2026-05-04 04:00", "2026-05-05 02:00"], utc=True)  # Thai 09:00 .. 11:00
    D = pd.DataFrame({"t": t})
    out = by_days(D, np.array([0, 0, 0, 0]), np.array([-1.0, 1.0, 1.0, 1.0]))
    # moments: 2 / 4 = 0.5; the days' first moments: day 1 -1, day 2 +1 -> 0 (a day mean would give (1/3 + 1) / 2)
    assert out.loc[0, "n"] == 4 and out.loc[0, "mean"] == 0.5 and out.loc[0, "days"] == 2 and out.loc[0, "day_mean"] == 0.0
    # the first by time, whatever the row order
    out2 = by_days(D.iloc[::-1].reset_index(drop=True), np.array([0, 0, 0, 0]), np.array([1.0, 1.0, 1.0, -1.0]))
    assert out2.loc[0, "day_mean"] == 0.0
