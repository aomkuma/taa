"""Hand tests of sw20_plan1.switch (the warm-up, exits strictly before the entry, the last 20 only)."""

import numpy as np
import pandas as pd

from sw20_plan1 import switch


def frame(t_in, t_out, r):
    return pd.DataFrame({"t_in": np.array(t_in, np.int64), "t_out": np.array(t_out, np.int64), "R": np.array(r, float)})


def test_warm_up_and_sign():
    # trades 0..3 exit at 10k+5; with n = 2: trade 2 sees trades 0, 1 (R +1, -3 -> mean -1 -> out); trade 3 sees 1, 2
    g = frame([0, 10, 20, 30], [5, 15, 25, 35], [1, -3, 4, 9])
    assert switch(g, n=2).tolist() == [False, False, False, True]


def test_exit_at_the_entry_is_not_known():
    g = frame([0, 10, 20], [5, 20, 30], [1, 1, 1])  # trade 1 exits exactly at trade 2's entry: not counted
    assert switch(g, n=2).tolist() == [False, False, False]


def test_only_the_last_n():
    g = frame([0, 10, 20, 30], [5, 15, 25, 35], [-100, 1, 1, 0])  # trade 3 sees the last 2 (1, 1): in, despite -100
    assert switch(g, n=2).tolist() == [False, False, False, True]


def test_exit_order_not_entry_order():
    # trade 0 enters first but exits last (40); at trade 2's entry (30) only trade 1 (exit 12) is known -> warm-up
    g = frame([0, 10, 30], [40, 12, 50], [5, 5, 5])
    assert switch(g, n=2).tolist() == [False, False, False]


def test_a_mean_of_zero_stays_out():
    g = frame([0, 10, 20], [5, 15, 25], [1, -1, 7])  # trade 2 sees +1, -1: mean 0 -> not > 0
    assert switch(g, n=2).tolist() == [False, False, False]
