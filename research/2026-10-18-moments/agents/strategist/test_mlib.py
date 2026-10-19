"""Hand-worked tests of the strategist's M1 simulator (mlib.trade)."""

import numpy as np

import mlib

# 4 bars, spread 0.2 everywhere
o = np.array([100.0, 101.0, 102.0, 103.0])
h = np.array([100.5, 101.5, 104.5, 103.5])
lo = np.array([99.5, 100.5, 101.5, 102.5])
c = np.array([100.2, 101.2, 104.0, 103.0])
spr = np.full(4, 0.2)


def test_buy_reaches_target():
    # entry at bar 1 open ask: 101 + 0.2 + 0.07 = 101.27; stop 100.0 -> risk 1.27; target 103.0 hit in bar 2 (high 104.5)
    pnl, risk, ex, k = mlib.trade(o, h, lo, c, spr, 1, 1, 100.0, 103.0, 3)
    assert ex == "target" and k == 2
    assert abs(risk - 1.27) < 1e-9 and abs(pnl - 1.73) < 1e-9


def test_buy_stop_in_entry_bar_with_slippage():
    # stop 100.6 inside bar 1's low 100.5 -> filled at 100.6 - 0.15 = 100.45
    pnl, risk, ex, k = mlib.trade(o, h, lo, c, spr, 1, 1, 100.6, 110.0, 3)
    assert ex == "stop" and k == 1 and abs(pnl - (100.45 - 101.27)) < 1e-9


def test_both_in_one_bar_is_a_stop():
    # bar 2 reaches the stop 101.6 (low 101.5) and the target 104 (high 104.5): the stop
    pnl, risk, ex, k = mlib.trade(o, h, lo, c, spr, 2, 1, 101.6, 104.0, 3)
    assert ex == "stop" and k == 2


def test_sell_on_the_ask_and_gap():
    # sell at bar 1 open bid 101 - 0.07 = 100.93; stop 101.9; bar 2's ask high 104.7 >= stop, its ask open 102.2 gapped
    # past the stop -> filled at the open ask 102.2 + 0.15
    pnl, risk, ex, k = mlib.trade(o, h, lo, c, spr, 1, -1, 101.9, 90.0, 3)
    assert ex == "stop" and k == 2 and abs(pnl - (100.93 - 102.35)) < 1e-9


def test_time_exit_on_the_close():
    # a sell with a far stop and target: out at bar 3's close ask 103.2
    pnl, risk, ex, k = mlib.trade(o, h, lo, c, spr, 1, -1, 120.0, 50.0, 3)
    assert ex == "time" and k == 3 and abs(pnl - (100.93 - 103.2)) < 1e-9
