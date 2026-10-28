"""Audit 4: the ZigZag swings (precursors/fingerprint.py::zigzag) by hand.

The owner's rule (2026-10-19): one bar's high and low are never two turns - the order inside a bar is unknown, so a
turn needs a later bar. Every pivot is confirmed by a bar after it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "precursors"))
import fingerprint  # noqa: E402

FIVE = np.full(8, 5.0)  # ATR 5, k = 2 -> the threshold is 10


def zz(h: list[float], lo: list[float], atr: np.ndarray = FIVE, k: float = 2.0) -> list[tuple[int, float, int, int]]:
    b, p, t, c = fingerprint.zigzag(np.array(h, float), np.array(lo, float), atr[: len(h)], k)
    return list(zip(b.tolist(), p.tolist(), t.tolist(), c.tolist(), strict=True))


def test_one_wide_bar_at_the_start_is_never_two_turns() -> None:
    # bar 1 (30 / 0) holds both the highest high and the lowest low; bars 2-3 stay inside it. Which came first in
    # bar 1 is unknown, so no turn can be confirmed yet. (Before the fix: a peak at bar 1 confirmed BY bar 1 itself,
    # then a trough at bar 1 confirmed by bar 2 - one bar, two turns.)
    assert zz([10, 30, 25, 26], [9, 0, 20, 25]) == []


def test_after_a_wide_bar_the_first_turn_waits_for_a_bar_that_takes_an_extreme_out() -> None:
    # bar 4 makes a new high (31): bar 1's low (0) is the first turn, a trough confirmed by bar 4; the peak is tracked
    # from bar 4; bar 5's low 20 is 11 below 31 -> the peak at 4 confirmed by 5
    assert zz([10, 30, 25, 26, 31, 24], [9, 0, 20, 25, 28, 20]) == [(1, 0.0, -1, 4), (4, 31.0, 1, 5)]


def test_an_outside_bar_in_an_up_leg_extends_it_and_is_one_turn() -> None:
    # trough 9 (bar 0) confirmed by bar 2 (19 - 9 = 10); bar 3 makes a new high 25 AND a low 14 (11 below the old peak
    # 19 and below its own high by 11): the new high extends the peak, nothing confirmed on that bar; bar 4 (low 15,
    # 10 below 25) confirms the peak at 3; then the trough is tracked from 4
    assert zz([10, 15, 19, 25, 20], [9, 12, 16, 14, 15]) == [(0, 9.0, -1, 2), (3, 25.0, 1, 4)]


def test_an_outside_bar_in_a_down_leg_is_mirrored() -> None:
    # the mirror of the previous case (prices negated): peak -9 at 0 ... -> the same bars, kinds flipped
    out = zz([-9, -12, -16, -14, -15], [-10, -15, -19, -25, -20])
    assert out == [(0, -9.0, 1, 2), (3, -25.0, -1, 4)]


@pytest.mark.parametrize("seed", range(20))
def test_every_pivot_is_confirmed_by_a_later_bar_and_no_bar_turns_twice(seed: int) -> None:
    rng = np.random.default_rng(seed)
    n = 400
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    wide = rng.random(n) < 0.05  # some very wide bars, the first bar after the warm-up among them
    wide[14] = True
    span = np.where(wide, 15.0, rng.random(n))
    h, lo = c + span, c - span
    atr = np.r_[np.full(14, np.nan), np.full(n - 14, 1.5)]
    b, _, t, conf = fingerprint.zigzag(h, lo, atr, 3.0)
    assert (conf > b).all()
    assert len(np.unique(b)) == len(b)
    assert (np.diff(t) != 0).all()  # peaks and troughs alternate


def test_an_equal_high_moves_the_peak_later_and_exactly_the_threshold_confirms() -> None:
    # trough 9 at 0 confirmed by bar 1 (19 - 9 = 10, exactly the threshold); an equal high 19 on bar 2 moves the peak to
    # bar 2; bar 3's low 9 is exactly 10 below it -> the peak at 2 confirmed by 3
    assert zz([10, 19, 19, 12], [9, 15, 16, 9]) == [(0, 9.0, -1, 1), (2, 19.0, 1, 3)]


def test_just_under_the_threshold_confirms_nothing() -> None:
    assert zz([10, 18.99, 17], [9, 15, 16]) == []


def test_an_equal_low_moves_the_trough_later() -> None:
    # the mirror of the equal-high case: peak -9 at 0 confirmed by bar 1, an equal low -19 on bar 2 moves the trough
    # to bar 2, bar 3's high -9 confirms it
    assert zz([-9, -15, -16, -9], [-10, -19, -19, -12]) == [(0, -9.0, 1, 1), (2, -19.0, -1, 3)]
