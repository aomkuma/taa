"""touches by hand: the outcome after a touch, how far past the level, the approach, the next level.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_touches.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from touches import approach, next_level, outcome  # noqa: E402


def arr(*v):
    return np.array(v, float)


def test_a_support_holds_without_a_pierce():
    # the level 100; bar 0 (the touch) low 100.5 high 112 (it came from above: its own high does not count);
    # bar 1 low 101, bar 2 high 110.2 -> 10 back first, never past 100
    h, lo = arr(112, 104, 110.2), arr(100.5, 101, 105)
    x = outcome(h, lo, 0, 100.0, 1)
    assert x["outcome"] == "reversed" and x["over"] == 0.0 and x["bars"] == 2


def test_a_wick_past_the_support_then_the_reversal():
    # past by 4.5 (low 95.5 on bar 1), then a high 110.5 on bar 3 -> reversed, over 4.5, the extreme 95.5
    h, lo = arr(103, 99, 104, 110.5), arr(99.8, 95.5, 97, 104)
    x = outcome(h, lo, 0, 100.0, 1)
    assert x["outcome"] == "reversed" and x["over"] == pytest.approx(4.5) and x["extreme"] == 95.5


def test_a_resistance_breaks_and_a_bar_reaching_both_is_left_out():
    # a resistance test at 100 (price came from below): a high 110 first -> broke
    h, lo = arr(100.2, 106, 110.0, 101), arr(95, 99, 104, 89)
    assert outcome(h, lo, 0, 100.0, -1)["outcome"] == "broke"
    h, lo = arr(100.2, 111, 101), arr(95, 89, 95)
    assert outcome(h, lo, 0, 100.0, -1)["outcome"] == "ambiguous"  # bar 1: 110+ and 90- in one bar


def test_the_touch_bar_can_break_but_not_reverse():
    # a support test: the touch bar itself falls to 89.5 (10.5 past) -> broke on bar 0; its high 111 is where it came from
    h, lo = arr(111, 95), arr(89.5, 88)
    assert outcome(h, lo, 0, 100.0, 1)["outcome"] == "broke"


def test_neither_within_the_window():
    h, lo = arr(103, 104, 108), arr(99, 97, 96)
    x = outcome(h, lo, 0, 100.0, 1, ahead=3)
    assert x["outcome"] == "neither" and x["over"] == pytest.approx(4.0)


def test_the_approach_is_the_first_touch_after_price_was_away():
    # atr 10: away = 5 from the level 100, the touch distance 1.0
    c = arr(108, 107, 106, 103, 102, 100.5, 104, 100.8)
    h, lo = c + 0.3, c - 0.3
    assert approach(c, h, lo, 5, 100.0, 10.0) == 1  # bar 2 (106) was the last close 5+ away, above; bars 3-4 did not touch
    assert approach(c, h, lo, 7, 100.0, 10.0) == 0  # bar 5 touched after the last far bar (2): not a new approach
    c2 = arr(92, 94, 96, 99.5)
    assert approach(c2, c2 + 0.3, c2 - 0.3, 3, 100.0, 10.0) == -1  # from below


def test_the_next_level_past_this_one():
    lv = arr(80.0, 90.0, 99.8, 100.0, 110.0)
    assert next_level(lv, 100.0, 1, 4.0) == 90.0  # below a support test; 99.8 is within 0.4 (the touch distance 0.1 x 4): the same place
    assert next_level(lv, 100.0, -1, 4.0) == 110.0
    assert np.isnan(next_level(lv, 80.0, 1, 4.0))


def test_how_far_past_counts_only_up_to_the_reversal():
    # past 4.5 (bar 1), reversed at bar 3 (110.5), then 8 past on bar 4 (after the reversal - not the turn's wick)
    h, lo = arr(103, 99, 104, 110.5, 105), arr(99.8, 95.5, 97, 104, 92)
    assert outcome(h, lo, 0, 100.0, 1)["over"] == pytest.approx(4.5)


def test_the_approach_uses_the_latest_bar_away():
    # bar 1 touched (100.2) but bar 2 (107) went away again: the touch at bar 4 is a new approach from above
    c = arr(108, 100.2, 107, 103, 100.5)
    assert approach(c, c + 0.3, c - 0.3, 4, 100.0, 10.0) == 1
