"""framework by hand: the D1 bias, the pullback depth, the efficiency.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_framework.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from framework import d1_bias, efficiency, pullback  # noqa: E402


def test_the_bias_needs_the_close_beyond_a_rising_or_falling_average():
    up = np.arange(1.0, 41.0)            # a steady climb: the close above a rising EMA20 from bar 24 (EMA ready at 19, slope at 24)
    b = d1_bias(up, 20, 5)
    assert (b[:24] == 0).all() and (b[24:] == 1).all()
    assert (d1_bias(-up, 20, 5)[24:] == -1).all()
    dip = np.r_[up, [25.0]]  # one close under the average (about 30) while it still rises over 5 bars: no bias
    assert d1_bias(dip, 20, 5)[-1] == 0


def test_the_deepest_pullback_from_the_running_extreme():
    h = np.array([10.0, 14, 12, 18, 17]); lo = np.array([9.0, 11, 8, 15, 12])
    assert pullback(h, lo, 1) == pytest.approx(6.0)   # running high 14 -> low 8 (6), later 18 -> 12 (6)
    assert pullback(h, lo, -1) == pytest.approx(10.0)  # running low 8 -> high 18


def test_efficiency():
    assert efficiency(np.array([1.0, 2, 3]), 0.0) == pytest.approx(1.0)
    assert efficiency(np.array([2.0, 0, 2]), 0.0) == pytest.approx(2 / 6)
