"""Hand-worked tests of the row-50 helpers (regime50.py)."""

import numpy as np
import pytest

import regime50 as G


def test_release_jump():
    t = np.array([90, 99, 100, 130, 159, 160])
    bid = np.array([10.0, 11.0, 13.0, 8.0, 12.0, 30.0])
    ask = bid + 0.2
    # the last mid before t0 = 100 is tick 99: 11.1; ticks in [100, 160): mids 13.1, 8.1, 12.1 -> the largest |diff| = 3.0
    # (8.1 - 11.1); the tick at 160 is outside the 60-unit span
    assert G.release_jump(t, bid, ask, 100, span_ns=60) == pytest.approx(3.0)
    assert np.isnan(G.release_jump(t, bid, ask, 90, span_ns=60))  # no tick before t0
    assert np.isnan(G.release_jump(t, bid, ask, 161, span_ns=60))  # no tick in the span


def test_choose_threshold_higher():
    x = np.array([1.0, 2.0, 3.0, 4.0, np.nan])
    r = np.array([-2.0, 1.0, -0.5, 3.0, 9.0])
    # thr 1 -> on x in {2,3,4}: 3.5; thr 2 -> {3,4}: 2.5; thr 3 -> {4}: 3.0; thr 4 -> none: 0; NaN never on -> (1, 3.5)
    assert G.choose_threshold(x, r) == (1.0, pytest.approx(3.5))


def test_choose_threshold_lower_and_ties():
    x = np.array([1.0, 2.0, 3.0])
    r = np.array([1.0, 0.0, -1.0])
    # lower: thr 2 -> {1}: 1; thr 3 -> {1,2}: 1 (a tie -> the highest threshold, 3); thr 1 -> none: 0
    assert G.choose_threshold(x, r, lower=True) == (3.0, pytest.approx(1.0))
    # higher with a tie: r = [0, 1, 0]: thr 1 -> {2,3}: 1; thr 2 -> {3}: 0 ... thr 1 wins; ties at 1 go to the lowest
    x2, r2 = np.array([1.0, 2.0, 3.0, 0.5]), np.array([0.0, 1.0, 0.0, 0.0])
    # thr 0.5 -> {1,2,3}: 1 (tie with thr 1) -> the lowest, 0.5
    assert G.choose_threshold(x2, r2) == (0.5, pytest.approx(1.0))


def test_rolling_before_is_strict():
    dates = np.array(["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06"], dtype="datetime64[D]")
    vals = np.array([1.0, np.nan, 5.0, 100.0])
    # before 2026-01-06: values 1, 5 (the NaN skipped; the day itself excluded) -> median 3
    assert G.rolling_before(dates, vals, np.datetime64("2026-01-06"), 2) == pytest.approx(3.0)
    # n = 1 -> the last one, 5; mean
    assert G.rolling_before(dates, vals, np.datetime64("2026-01-06"), 1, "mean") == pytest.approx(5.0)
    # too few: before 2026-01-02 there is 1 value; n = 4 needs >= 2
    assert np.isnan(G.rolling_before(dates, vals, np.datetime64("2026-01-02"), 4))
