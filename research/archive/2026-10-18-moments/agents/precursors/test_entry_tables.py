"""entry_tables.aligned and entry_tables.turn by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_entry_tables.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from entry_tables import aligned, turn  # noqa: E402


def test_aligned_phase_by_hand():
    X = pd.DataFrame({"D1_er20": [0.30, 0.30, 0.20, 0.30, 0.30, 0.30], "D1_way20": [1, -1, 1, 1, 1, 0],
                      "H1_struct": [1, -1, 1, -1, 9, 1], "H4_di": [5.0, -5.0, 5.0, 5.0, 5.0, 5.0]})
    # 0 aligned up; 1 aligned down; 2 D1 not running; 3 H1 against; 4 H1 unknown; 5 no D1 way
    assert aligned(X).tolist() == [True, True, False, False, False, False]
    X2 = X.assign(H4_di=[-5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
    assert aligned(X2).tolist()[:2] == [False, False]  # H4 against D1
    assert aligned(X.assign(D1_er20=[0.264] * 6)).tolist()[0]  # the threshold itself counts


def test_turn_to_the_d1_way():
    X = pd.DataFrame({"M15_pos": [0.2, 0.2], "M5_rsi": [30.0, 30.0], "M5_struct": [1, 9], "hour_utc": [8.0, 8.0]})
    way = np.array([1.0, -1.0])
    assert turn(X, "M15_pos", way).tolist() == [0.2, 0.8] and turn(X, "M5_rsi", way).tolist() == [-20.0, 20.0]
    s = turn(X, "M5_struct", way)
    assert s[0] == 1.0 and np.isnan(s[1]) and turn(X, "hour_utc", way).tolist() == [8.0, 8.0]
