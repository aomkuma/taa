"""Hand-worked tests of sw20.switch_ok (the SW-20 switch): the warm-up, exits strictly before the entry, the last n."""

import numpy as np

import sw20


def test_warm_up_needs_n_exits():
    te = np.array([10, 20, 30])
    R = np.array([1.0, 1.0, 1.0])
    # n = 3: at t = 31 three exits (10, 20, 30) -> mean 1 > 0 -> real; at t = 25 only two -> paper only
    assert sw20.switch_ok(te, R, np.array([25, 31]), n=3).tolist() == [False, True]


def test_exit_at_the_entry_moment_is_not_counted():
    te = np.array([10, 20, 30])
    R = np.array([1.0, 1.0, 1.0])
    # t = 30: the exit at 30 is not strictly before -> two exits -> not enough for n = 3
    assert sw20.switch_ok(te, R, np.array([30]), n=3).tolist() == [False]


def test_last_n_by_exit_time():
    # given out of order: exits 40 (R -5), 10 (+1), 30 (+1), 20 (+1)
    te = np.array([40, 10, 30, 20])
    R = np.array([-5.0, 1.0, 1.0, 1.0])
    # t = 41, n = 2: the last two by exit time are 30 (+1) and 40 (-5) -> mean -2 -> not real
    # t = 35, n = 2: the last two are 20 (+1), 30 (+1) -> real
    assert sw20.switch_ok(te, R, np.array([41, 35]), n=2).tolist() == [False, True]
    # t = 41, n = 4: all four -> mean -0.5 -> not real
    assert sw20.switch_ok(te, R, np.array([41]), n=4).tolist() == [False]


def test_mean_must_be_strictly_positive_and_missing_trades_skipped():
    te = np.array([10, 20, 25, -1])
    R = np.array([1.0, -1.0, np.nan, 9.0])
    # t = 30, n = 2: the NaN (25) and the missing exit (-1) are not in the record -> 10 (+1), 20 (-1) -> mean 0 -> not real
    assert sw20.switch_ok(te, R, np.array([30]), n=2).tolist() == [False]
    # if the NaN were counted as an exit the record would differ; with n = 3 there are only two valid exits
    assert sw20.switch_ok(te, R, np.array([30]), n=3).tolist() == [False]


def test_fewer_records_than_n_never_trade():
    # two exits (+1, +1), n = 3: never real, whatever their mean (guards a negative slice start)
    assert sw20.switch_ok(np.array([10, 20]), np.array([1.0, 1.0]), np.array([25]), n=3).tolist() == [False]


def test_a_missing_result_does_not_take_a_place_in_the_last_n():
    # exits 10 (+1), 20 (+1), 25 (no result), n = 2, t = 30: the last two valid are 10, 20 -> mean +1 -> real
    assert sw20.switch_ok(np.array([10, 20, 25]), np.array([1.0, 1.0, np.nan]), np.array([30]), n=2).tolist() == [True]


def test_only_the_last_n_count():
    # exits 10 (-5), 20 (+1), 30 (+1), n = 2, t = 35: the last two are +1, +1 -> real (all three: -1 -> not)
    assert sw20.switch_ok(np.array([10, 20, 30]), np.array([-5.0, 1.0, 1.0]), np.array([35]), n=2).tolist() == [True]
