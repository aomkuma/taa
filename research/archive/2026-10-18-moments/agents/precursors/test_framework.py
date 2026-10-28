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


def test_the_first_passage_counts_a_bar_with_both_against():
    from framework2 import first_passage, trend_sign
    h = np.array([102.0, 106, 111]); lo = np.array([99.0, 98, 104])
    assert first_passage(100.0, h, lo, 1, 10.0, 3.0) == 1     # 111 (+11) before 97 (-3): the lows 99, 98 stay above 97
    assert first_passage(100.0, h, lo, 1, 10.0, 2.0) == -1    # 98 is -2: against first
    assert first_passage(100.0, np.array([112.0]), np.array([95.0]), 1, 10.0, 3.0) == -1  # one bar with both: against
    assert first_passage(100.0, h, lo, -1, 10.0, 3.0) == -1   # a sell: 102 is +2 against, 106 is +6 -> against at bar 1
    assert first_passage(100.0, np.array([101.0]), np.array([99.0]), 1, 10.0, 3.0) == 0
    up = np.arange(1.0, 81.0)
    assert trend_sign(up)[-1] == 1 and trend_sign(-up)[-1] == -1 and trend_sign(up)[40] == 0  # EMA50 not ready at 40


def test_a_sell_reaches_its_target_on_the_lows():
    from framework2 import first_passage
    # a sell from 100: lows 95 then 89 (+11 our way), highs never 3 above: the target first
    assert first_passage(100.0, np.array([101.0, 100.0]), np.array([95.0, 89.0]), -1, 10.0, 3.0) == 1
