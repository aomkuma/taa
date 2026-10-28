"""level_power.first_passage by hand: which barrier the bars after the touch reach first.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_level_power.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from level_power import first_passage  # noqa: E402


def bars(highs, lows):
    return np.array(highs, float), np.array(lows, float)


def test_the_upper_barrier_first():
    h, lo = bars([100, 100.5, 101.2, 99.0], [99.5, 99.8, 100.4, 98.0])
    assert first_passage(h, lo, 0, 101.0, 99.0, 10) == 1  # bar 2 reaches 101 before any low reaches 99


def test_the_lower_barrier_first():
    h, lo = bars([100, 100.5, 100.2, 101.5], [99.5, 99.2, 98.9, 100.0])
    assert first_passage(h, lo, 0, 101.0, 99.0, 10) == -1  # bar 2's low 98.9


def test_the_touch_bar_itself_does_not_count():
    h, lo = bars([101.5, 100.2, 100.1], [98.5, 99.5, 99.6])  # bar 0 spans both barriers; nothing after reaches either
    assert first_passage(h, lo, 0, 101.0, 99.0, 10) == 0


def test_both_in_one_bar_and_the_horizon():
    h, lo = bars([100, 101.2, 100], [99.5, 98.8, 99.5])
    assert first_passage(h, lo, 0, 101.0, 99.0, 10) == 0  # bar 1 reaches both: dropped
    h, lo = bars([100, 100.2, 100.3, 101.5], [99.5, 99.6, 99.7, 99.8])
    assert first_passage(h, lo, 0, 101.0, 99.0, 2) == 0  # bar 3 is beyond a 2-bar horizon
    assert first_passage(h, lo, 0, 101.0, 99.0, 3) == 1
