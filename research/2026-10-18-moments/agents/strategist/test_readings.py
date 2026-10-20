"""Hand-worked tests of the row-45 readings (readings.py). Every expected number is worked out by hand in the comment."""

import numpy as np
import pytest

import readings as R

H = 3600 * 10**9


def test_pct_rank_recent():
    rng = np.arange(1.0, 11.0)  # 1 .. 10
    # j = 9, recent 2 -> mean(9, 10) = 9.5; hist 10 -> values <= 9.5 are 1..9 = 9 of 10
    assert R.pct_rank_recent(rng, 9, recent=2, hist=10) == pytest.approx(0.9)
    # j = 4, recent 2 -> mean(4, 5) = 4.5; hist 5 = 1..5 -> 4 of 5
    assert R.pct_rank_recent(rng, 4, recent=2, hist=5) == pytest.approx(0.8)
    assert np.isnan(R.pct_rank_recent(rng, 3, recent=2, hist=5))  # not enough history


def test_season():
    rng = np.array([1.0, 2, 3, 4, 10, 10])
    # j = 5, n = 2 -> mean(10, 10) = 10; base 6 -> median(1,2,3,4,10,10) = 3.5 -> 2.857...
    assert R.season(rng, 5, n=2, base=6) == pytest.approx(10 / 3.5)
    assert np.isnan(R.season(rng, 4, n=2, base=6))


def test_efficiency():
    c = np.array([10.0, 12, 11, 13, 13])
    # j = 3, n = 3: |13 - 10| / (2 + 1 + 2) = 0.6
    assert R.efficiency(c, 3, 3) == pytest.approx(0.6)
    # j = 4, n = 1: no move -> 0
    assert R.efficiency(c, 4, 1) == 0.0
    assert np.isnan(R.efficiency(c, 2, 3))


def test_fail_share_counts_only_settled_breaks():
    tb = np.array([0, 10, 20, 30, 40])
    ts = np.array([5, 15, 25, 35, 100])
    fl = np.array([1.0, 0, 1, 1, 0])
    # t = 35: breaks 0..3 settled; from t_from = 10 -> breaks 1, 2, 3 -> failed 2 of 3
    assert R.fail_share(tb, ts, fl, 10, 35, min_n=3) == pytest.approx(2 / 3)
    # break 4 (settled at 100) is not counted at t = 99 -> still 2 / 3 from t_from 10
    assert R.fail_share(tb, ts, fl, 10, 99, min_n=3) == pytest.approx(2 / 3)
    # at t = 100 it counts -> 2 of 4
    assert R.fail_share(tb, ts, fl, 10, 100, min_n=3) == pytest.approx(0.5)
    assert np.isnan(R.fail_share(tb, ts, fl, 10, 35, min_n=4))


def test_big_bars_and_since_big():
    h = np.array([10.0, 10, 10, 20])
    lo = np.array([9.0, 9, 9, 10])
    atr = np.array([np.nan, 1.0, 1.0, 1.0])
    big = R.big_bars(h, lo, atr, 2.5)
    # bar 3: range 10 >= 2.5 x the ATR before it (1.0) -> big; bar 0 has no ATR before it
    assert big.tolist() == [False, False, False, True]
    avail = np.array([1, 2, 3, 4]) * H
    # t = 7 h: the last big bar (3) became available at 4 h -> 3 hours
    assert R.since_big(avail, big, 3, 7 * H) == pytest.approx(3.0)
    # j = 2: bar 3 not yet complete -> none -> the cap
    assert R.since_big(avail, big, 2, 7 * H) == 999.0


def test_own_trailing_uses_only_earlier_exits():
    te = np.array([10, 20, 30, 40, -1])
    rr = np.array([1.0, -1.0, 2.0, 5.0, 9.0])
    # t = 30: exits 10, 20, 30 -> mean(1, -1, 2) = 0.667 (n 3, min_n 3); exit 40 and the missing (-1) one excluded
    assert R.own_trailing(te, rr, 30, n=20, min_n=3) == pytest.approx(2 / 3)
    # n = 2 -> the last two by exit: -1, 2 -> 0.5
    assert R.own_trailing(te, rr, 30, n=2, min_n=2) == pytest.approx(0.5)
    assert np.isnan(R.own_trailing(te, rr, 15, n=20, min_n=3))


def test_pct_rank_counts_ties():
    rng = np.array([1.0, 2, 2, 2, 5])
    # j = 4, recent 3 -> mean(2, 2, 5) = 3.0 -> values <= 3: 1, 2, 2, 2 = 4 of 5; recent 1 at j = 3 -> 2 -> ties count: 4 of 4
    assert R.pct_rank_recent(rng, 3, recent=1, hist=4) == pytest.approx(1.0)
    assert R.pct_rank_recent(rng, 4, recent=3, hist=5) == pytest.approx(0.8)


def test_big_bar_uses_the_atr_before_it_and_the_last_big_bar():
    h = np.array([10.0, 13, 10, 13])
    lo = np.array([9.0, 10, 9, 10])
    atr = np.array([1.0, 2.0, 1.0, 2.0])
    # bar 1: range 3 >= 2.5 x 1.0 (bar 0's ATR) -> big; with its own ATR 2.0 it would not be (5.0)
    # bar 3: range 3 >= 2.5 x 1.0 (bar 2's) -> big
    big = R.big_bars(h, lo, atr, 2.5)
    assert big.tolist() == [False, True, False, True]
    avail = np.array([1, 2, 3, 4]) * H
    # t = 10 h: the LAST big bar (3, avail 4 h) -> 6 h, not the first (8 h)
    assert R.since_big(avail, big, 3, 10 * H) == pytest.approx(6.0)
