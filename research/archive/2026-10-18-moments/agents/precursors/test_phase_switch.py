"""phase_switch.side by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_phase_switch.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase_switch import side  # noqa: E402


def test_the_side_by_the_phase():
    X = pd.DataFrame({"D1_er20": [0.30, 0.30, 0.10, 0.10, 0.10, 0.20], "aligned": [True, False, False, True, False, True],
                      "D1_way20": [-1, 1, 1, 1, -1, 1], "M30_pos": [0.5, 0.5, 0.9, 0.5, 0.1, 0.05]})
    # running + aligned: the D1 way (-1); running not aligned: none; back and forth at the high edge: sell; mid-range: none;
    # at the low edge: buy (whatever the D1 way); between the phases: none
    assert side(X).tolist() == [-1, 0, -1, 0, 1, 0]


def test_the_pullback_variant():
    X = pd.DataFrame({"D1_er20": [0.30, 0.30, 0.30, 0.10], "aligned": [True, True, True, False], "D1_way20": [1, 1, 1, 1],
                      "M30_pos": [0.5, 0.5, 0.5, 0.9], "M15_leg_way": [-1, 1, -1, 1], "D1_atr_rel": [1.0, 1.0, 1.5, 1.0]})
    # a pullback while calm: the D1 way; the leg with D1: none; a pullback while D1 is busy: none; the fade unchanged
    assert side(X, pull=True).tolist() == [1, 0, 0, -1] and side(X).tolist() == [1, 1, 1, -1]
