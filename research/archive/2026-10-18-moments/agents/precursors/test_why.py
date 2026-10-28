"""why.lean by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_why.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from why import lean  # noqa: E402


def test_lean_by_hand():
    # L1: values 0..9 (two per bin at its quintiles); up first only at the top two values, down first only at the bottom two
    v1 = np.arange(10.0)
    up1, dn1 = v1 >= 8, v1 <= 1
    # L2: values 100..109 - all in L1's top bin by L1's edges; tilt there +1 for half of them
    v2 = 100 + np.arange(10.0)
    up2, dn2 = np.arange(10) % 2 == 0, np.zeros(10, bool)
    X = pd.DataFrame({"r": np.r_[v1, v2], "half": ["L1"] * 10 + ["L2"] * 10, "up5": np.r_[up1, up2], "dn5": np.r_[dn1, dn2]})
    out = lean(X, "r", 5)
    assert out["lo_L1"] == -1.0 and out["hi_L1"] == 1.0 and out["move_L1"] == 2.0
    # L2 lands in one bin only (edges from L1): lowest = highest = that bin, no move -> not steady
    assert out["lo_L2"] == pytest.approx(0.5) and out["move_L2"] == 0.0 and out["strength"] == 0.0


def test_a_reading_that_leans_down_in_both_halves():
    v = np.tile(np.arange(10.0), 2)
    up, dn = v <= 1, v >= 8
    X = pd.DataFrame({"r": v, "half": ["L1"] * 10 + ["L2"] * 10, "up10": up, "dn10": dn})
    out = lean(X, "r", 10)
    assert out["move_L1"] == -2.0 and out["move_L2"] == -2.0 and out["steady"] and out["strength"] == 2.0
