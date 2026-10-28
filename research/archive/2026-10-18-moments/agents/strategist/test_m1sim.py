"""Hand-worked tests of m1sim.trade (row 45). Each number below is worked by hand from the bars written in the test."""

import numpy as np
import pytest

import m1sim

#            bar:  0      1      2      3
O = np.array([100.0, 101.0, 102.0, 99.0])
H = np.array([100.5, 102.5, 103.0, 99.5])
L = np.array([99.5, 100.5, 101.0, 97.0])
C = np.array([100.2, 102.0, 102.5, 98.0])
S = np.array([0.3, 0.3, 0.3, 0.3])


def test_buy_target():
    # buy at bar 1's open ask 101.3; stop 100.0 (risk 1.3); target 102.6 -> bar 2's high 103.0 reaches it
    pnl, risk, ex, k = m1sim.trade(O, H, L, C, S, 1, 1, 100.0, 102.6, 3)
    assert ex == "target" and k == 2
    assert pnl == pytest.approx(1.3) and risk == pytest.approx(1.3)


def test_buy_stop_on_gap():
    # buy at bar 2's open ask 102.3; stop 100.0; bar 3 opens at 99.0 < stop -> filled at the open 99.0
    pnl, risk, ex, k = m1sim.trade(O, H, L, C, S, 2, 1, 100.0, None, 3)
    assert ex == "stop" and k == 3 and pnl == pytest.approx(99.0 - 102.3)


def test_sell_uses_ask_for_stop_and_target():
    # sell at bar 1's open bid 101.0; stop 103.2: bar 1 ask high 102.8 no, bar 2 ask high 103.3 >= 103.2 -> stop
    pnl, risk, ex, k = m1sim.trade(O, H, L, C, S, 1, -1, 103.2, 99.0, 3)
    assert ex == "stop" and k == 2 and pnl == pytest.approx(101.0 - 103.2) and risk == pytest.approx(2.2)


def test_sell_target_on_ask():
    # sell at bar 2's open 102.0; stop 104; target 97.4: bar 3's ask low 97.3 <= 97.4 -> target (not the bid low)
    pnl, risk, ex, k = m1sim.trade(O, H, L, C, S, 2, -1, 104.0, 97.4, 3)
    assert ex == "target" and k == 3 and pnl == pytest.approx(4.6)
    # target 97.2 is below the ask low 97.3 -> not reached, time exit at bar 3's close ask 98.3
    pnl, _, ex, _ = m1sim.trade(O, H, L, C, S, 2, -1, 104.0, 97.2, 3)
    assert ex == "time" and pnl == pytest.approx(102.0 - 98.3)


def test_both_in_one_bar_is_the_stop_and_slip():
    # buy at bar 1's open ask 101.3 + slip 0.1 = 101.4; stop 100.6 and target 102.4 both inside bar 1 -> stop 100.6 - 0.05
    pnl, risk, ex, k = m1sim.trade(O, H, L, C, S, 1, 1, 100.6, 102.4, 3, slip=0.1, slip_stop=0.05)
    assert ex == "stop" and k == 1 and pnl == pytest.approx(100.55 - 101.4) and risk == pytest.approx(0.8)


def test_time_exit_and_refusals():
    pnl, _, ex, k = m1sim.trade(O, H, L, C, S, 0, 1, 99.0, None, 1)
    assert ex == "time" and k == 1 and pnl == pytest.approx(102.0 - 100.3)
    assert m1sim.trade(O, H, L, C, S, 1, 1, 101.5, None, 3) is None  # stop above the ask fill
    assert m1sim.trade(O, H, L, C, S, 4, 1, 99.0, None, 4) is None
