"""present_wf.one_at_a_time by hand: one position - a pick is taken only after the previous trade's exit bar.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_present_wf.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from present_wf import one_at_a_time  # noqa: E402


def test_one_at_a_time_by_hand():
    # rows 0..5 enter at bars 10, 15, 20, 25, 30, 35; a buy exits at 22 (row 0), a sell at 30 (row 3)
    j0 = np.array([10, 15, 20, 25, 30, 35])
    xj = {1: np.array([22, 18, 26, 31, 33, 40]), -1: np.array([12, 17, 21, 30, 32, 38])}
    side = np.array([1, -1, 0, -1, 1, 1])
    # row 0 buys (busy to 22); row 1 enters at 15 <= 22: skipped; row 2 no pick; row 3 sells at 25 (busy to 30);
    # row 4 enters at 30 <= 30: skipped (its exit bar is still the old trade's); row 5 buys at 35
    assert one_at_a_time(np.arange(6), side, j0, xj) == [(0, 1), (3, -1), (5, 1)]
