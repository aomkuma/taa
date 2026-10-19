"""persist.carry_on by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_persist.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persist import carry_on  # noqa: E402


def bars(h, lo):
    h, lo = np.array(h, float), np.array(lo, float)
    return (h + lo) / 2, h, lo


def test_up_then_on_to_twice():
    # start = bar 0's open 100; X 5: bar 1 high 105.5 (up first); then bar 3 high 110.2 >= 110 before a low <= 100
    o, h, lo = bars([100.5, 105.5, 106, 110.2], [99.5, 101, 102, 106])
    way, car = carry_on(o, h, lo, np.array([0]), 5.0, horizon=10)
    assert way.tolist() == [1] and car.tolist() == [1.0]


def test_up_then_back_to_the_start():
    o, h, lo = bars([100.5, 105.5, 104, 103], [99.5, 101, 99.8, 98])
    way, car = carry_on(o, h, lo, np.array([0]), 5.0, horizon=10)
    assert way.tolist() == [1] and car.tolist() == [0.0]


def test_down_then_on():
    o, h, lo = bars([100.5, 99, 96, 93], [99.5, 94.5, 92, 89.5])
    way, car = carry_on(o, h, lo, np.array([0]), 5.0, horizon=10)
    assert way.tolist() == [-1] and car.tolist() == [1.0]


def test_both_ways_in_one_bar_or_nothing():
    o, h, lo = bars([100.5, 106, 107], [99.5, 94, 95])
    way, car = carry_on(o, h, lo, np.array([0]), 5.0, horizon=10)
    assert way.tolist() == [0] and np.isnan(car[0])
    o, h, lo = bars([100.5, 101, 102], [99.5, 99, 98])
    way, car = carry_on(o, h, lo, np.array([0]), 5.0, horizon=10)
    assert way.tolist() == [0] and np.isnan(car[0])


def test_the_touch_bar_is_not_raced():
    # bar 1 touches 105 and also 110.5 (its order unknown): the race starts at bar 2 - back to 100 at bar 2 -> 0
    o, h, lo = bars([100.5, 110.5, 103], [99.5, 101, 99.9])
    way, car = carry_on(o, h, lo, np.array([0]), 5.0, horizon=10)
    assert way.tolist() == [1] and car.tolist() == [0.0]
