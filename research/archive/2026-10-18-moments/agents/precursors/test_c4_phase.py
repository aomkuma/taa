"""c4_phase.efficiency_ratio by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_c4_phase.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c4_phase import efficiency_ratio  # noqa: E402


def test_a_straight_line_is_one_and_back_and_forth_is_low():
    er = efficiency_ratio(np.array([1.0, 2, 3, 4, 5]), 3)
    assert np.isnan(er[:3]).all() and er[3] == pytest.approx(1.0) and er[4] == pytest.approx(1.0)
    # 10, 12, 10, 12: net 2 over a path of 2 + 2 + 2 = 6 -> 1/3
    er = efficiency_ratio(np.array([10.0, 12, 10, 12]), 3)
    assert er[3] == pytest.approx(2 / 6)
    assert np.isnan(efficiency_ratio(np.array([1.0, 1, 1, 1]), 3)[3])  # no movement at all: undefined
