"""no_sl.hold and no_sl.wiped by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_no_sl.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from no_sl import hold, wiped  # noqa: E402


def test_a_buy_goes_deep_then_reaches_the_target():
    # in at 100 + 0.3 + 0.07 = 100.37; down to a low of 80 (20.37 against), then up to 110.4 >= 110.37
    o = np.array([100.0, 95, 85, 90, 105, 109])
    h = np.array([100.5, 96, 88, 95, 108, 110.4])
    lo = np.array([99.0, 90, 80, 86, 100, 106])
    x = hold(o, h, lo, np.full(6, 0.3), 0, 1, chunk=2)
    assert x["xj"] == 5 and x["pnl"] == 10.0 and x["mae"] == pytest.approx(20.37)


def test_a_sell_reads_the_ask_and_the_end_of_the_data():
    # a sell at 99.93; the ask high 104.0 + 0.3 = 104.3 -> 4.37 against; never 10 down: open at the end
    o = np.array([100.0, 101, 103])
    h = np.array([100.5, 102, 104.0])
    lo = np.array([99.5, 100, 102])
    x = hold(o, h, lo, np.full(3, 0.3), 0, -1)
    assert x["xj"] == -1 and x["mae"] == pytest.approx(4.37)


def test_wiped_by_the_balance_at_the_trade_start():
    # balance 22: trades +10, +10, then one going 45 against (balance 42 then) -> wiped on the third
    assert wiped(np.array([10.0, 10, 10]), np.array([5.0, 15, 45]), 22.0) == 2
    assert wiped(np.array([10.0, 10, 10]), np.array([5.0, 15, 41]), 22.0) == -1
    assert wiped(np.array([10.0]), np.array([22.0]), 22.0) == 0
