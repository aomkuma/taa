"""Hand-worked tests of tsim.grid (the transformations' tick simulator). Times in minutes, spread 0.2 unless stated."""

import numpy as np
import pandas as pd
import pytest

import tsim

M = tsim.NS_MIN


def ticks(rows):
    t = np.array([int(r[0] * M) for r in rows], dtype=np.int64)
    bid = np.array([r[1] for r in rows], float)
    ask = np.array([r[2] for r in rows], float)
    return t, bid, ask


def cells(rows):
    return {(r["side_v"], r["stop_m"], r["tgt"]): r for r in rows}


# minute, bid, ask
A = ticks([(0, 100.0, 100.2), (1, 99.5, 99.7), (2, 98.9, 99.1), (3, 101.0, 101.2)])


def test_buy_stop_wider_stop_target_and_the_mirror():
    # a buy fills at the ask 100.2; the rule's stop 99.0 -> d_s0 1.2; the target 101.0 -> d_t0 0.8; ticks end at 3 ('end')
    c = cells(tsim.grid(*A, 0, 1, 99.0, 101.0, 10 * M))
    x = c[("same", 1.0, "orig")]
    assert x["exit"] == "stop" and abs(x["pnl"] - (98.9 - 100.2)) < 1e-9 and abs(x["R"] - (-1.3 / 1.2)) < 1e-9
    # stop x 1.5 = 1.8 below: the worst bid 98.9 is 1.3 below -> no stop; the bid 101.0 reaches the target (limit 0.8)
    x = c[("same", 1.5, "orig")]
    assert x["exit"] == "target" and abs(x["pnl"] - 0.8) < 1e-9 and abs(x["R"] - 0.8 / 1.8) < 1e-9
    # the opposite side: a sell at the bid 100.0, exits on the ask: 99.7 (+0.3), 99.1 (+0.9) -> target 0.8 at minute 2
    x = c[("opp", 1.0, "orig")]
    assert x["side"] == -1 and x["exit"] == "target" and abs(x["entry"] - 100.0) < 1e-9 and abs(x["R"] - 0.8 / 1.2) < 1e-9
    # x 0.5 target: 0.4; the opposite reaches it at minute 2 (0.9 >= 0.4; minute 1 gives only 0.3)
    x = c[("opp", 1.0, "0.5")]
    assert x["exit"] == "target" and abs(x["pnl"] - 0.4) < 1e-9 and x["exit_t"] == 2 * M
    # opp, stop x 1: the ask 101.2 is 1.2 above 100.0 -> the stop, but the target came first (minute 2)
    # opp with no target ('1R0' = 1.2 our way): 0.9 is the best -> the stop at minute 3, pnl -1.2
    x = c[("opp", 1.0, "1R0")]
    assert x["exit"] == "stop" and abs(x["pnl"] + 1.2) < 1e-9 and x["exit_t"] == 3 * M


def test_stop_at_exact_distance_fills():
    # a sell at the bid 100.0, stop 1.0 above: the ask 101.0 is exactly 1.0 against -> stopped there
    T = ticks([(0, 100.0, 100.2), (1, 100.5, 100.7), (2, 100.8, 101.0), (3, 99.0, 99.2)])
    x = cells(tsim.grid(*T, 0, -1, 101.0, np.nan, 10 * M, sides=("same",)))[("same", 1.0, "orig")]
    assert x["exit"] == "stop" and x["exit_t"] == 2 * M and abs(x["pnl"] + 1.0) < 1e-9


def test_time_exit_first_tick_at_or_after():
    T = ticks([(0, 100.0, 100.2), (1, 100.1, 100.3), (2, 100.2, 100.4), (3, 100.6, 100.8), (4, 101.0, 101.2)])
    x = cells(tsim.grid(*T, 0, 1, 90.0, np.nan, int(2.5 * M), sides=("same",)))[("same", 1.0, "orig")]
    assert x["exit"] == "time" and x["exit_t"] == 3 * M and abs(x["pnl"] - (100.6 - 100.2)) < 1e-9


def test_gap_breaks_at_the_last_tick_before_it():
    T = ticks([(0, 100.0, 100.2), (1, 100.1, 100.3), (2, 100.4, 100.6), (40, 90.0, 90.2), (41, 90.0, 90.2)])
    x = cells(tsim.grid(*T, 0, 1, 95.0, np.nan, 60 * M, sides=("same",)))[("same", 1.0, "orig")]
    assert x["exit"] == "break" and x["exit_t"] == 2 * M and abs(x["pnl"] - 0.2) < 1e-9


def test_surrender_out_at_k_unless_it_ran_y_before():
    T = ticks([(0, 100.0, 100.2), (1, 100.9, 101.1), (2, 101.0, 101.2), (3, 100.0, 100.2), (9, 100.5, 100.7)])
    # a buy at 100.2; Y = 1.0 within K = 2 minutes: before minute 2 the best is 100.9 - 100.2 = 0.7 -> out at minute 2's
    # tick (bid 101.0: +0.8, although that tick itself is 0.8 - it is the exit, not a reason to stay)
    x = cells(tsim.grid(*T, 0, 1, 95.0, np.nan, 10 * M, surr=(2, 1.0), sides=("same",)))[("same", 1.0, "orig")]
    assert x["exit"] == "surrender" and x["exit_t"] == 2 * M and abs(x["pnl"] - 0.8) < 1e-9
    # Y = 0.7 was reached at minute 1 -> no surrender; out on time at minute 9
    x = cells(tsim.grid(*T, 0, 1, 95.0, np.nan, 9 * M, surr=(2, 0.7), sides=("same",)))[("same", 1.0, "orig")]
    assert x["exit"] == "time" and x["exit_t"] == 9 * M


def test_structure_exit_same_side_only_and_stop_first_on_one_tick():
    T = ticks([(0, 100.0, 100.2), (1, 100.3, 100.5), (2, 99.0, 99.2), (3, 100.0, 100.2)])
    rows = cells(tsim.grid(*T, 0, 1, 99.1, np.nan, 10 * M, t_struct=int(1.5 * M)))
    x = rows[("same", 1.0, "orig")]  # the structure time 1.5 -> the tick at minute 2, where the bid 99.0 also stops it
    assert x["exit"] == "stop" and x["exit_t"] == 2 * M
    x = rows[("same", 2.0, "orig")]  # stop 2.2 below: not hit -> the structure exit at minute 2
    assert x["exit"] == "structure" and abs(x["pnl"] - (99.0 - 100.2)) < 1e-9
    x = rows[("opp", 2.0, "orig")]  # no structure exit for the other side: out at the data's end
    assert x["exit"] == "end" and x["exit_t"] == 3 * M


def test_targets_without_a_rule_target():
    c = cells(tsim.grid(*A, 0, -1, 101.4, np.nan, 10 * M))  # a sell at 100.0, stop 1.4 above -> d_s0 1.4
    assert c[("same", 1.0, "orig")]["has_tgt"] is False
    for tg in ("orig", "0.75", "0.5"):
        assert c[("same", 1.0, tg)]["exit"] == "end"  # no target: out at the last tick (ask 101.2: -1.2)
    x = c[("same", 2.0, "1R0")]  # 1R0 = 1.4 (the rule's distance, not 2.8): the ask 99.1 gives 0.9 only -> no target
    assert x["exit"] == "end" and abs(x["R"] - (-1.2 / 2.8)) < 1e-9


def test_slippage_parameter_and_default():
    x = cells(tsim.grid(*A, 0, 1, 99.0, np.nan, 10 * M, sides=("same",)))[("same", 2.0, "orig")]
    assert abs(x["entry"] - 100.2) < 1e-9
    x = cells(tsim.grid(*A, 0, 1, 99.0, np.nan, 10 * M, slip=0.07, sides=("same",)))[("same", 2.0, "orig")]
    assert abs(x["entry"] - 100.27) < 1e-9 and abs(x["risk"] - 2 * 1.27) < 1e-9


def test_refusals():
    assert tsim.grid(*A, 0, 1, 100.5, np.nan, 10 * M) is None  # the fill 100.2 is already below a buy's stop 100.5
    T = ticks([(0, 100.0, 100.2), (10, 100.0, 100.2), (11, 100.0, 100.2)])
    assert tsim.grid(*T, 4 * M, 1, 99.0, np.nan, 20 * M) is None  # the first tick after t_in is 6 minutes later


def test_exam_days_are_never_loaded():
    with pytest.raises(RuntimeError):
        tsim.day_ticks(pd.Timestamp("2026-04-18"))
    assert tsim.Ticks().day(pd.Timestamp("2026-04-20", tz="UTC")) is None


def test_one_at_a_time():
    T = pd.DataFrame(dict(entry_t=[0, 5, 12, 13], exit_t=[10, 8, 20, 14]))
    assert list(tsim.one_at_a_time(T).entry_t) == [0, 12]


def test_surrender_ignores_the_tick_at_k_itself():
    # Y = 0.75: before minute 2 the best is 0.7 -> out at minute 2 tick, although that tick is +0.8
    T = ticks([(0, 100.0, 100.2), (1, 100.9, 101.1), (2, 101.0, 101.2), (3, 100.0, 100.2), (9, 100.5, 100.7)])
    x = cells(tsim.grid(*T, 0, 1, 95.0, np.nan, 9 * M, surr=(2, 0.75), sides=("same",)))[("same", 1.0, "orig")]
    assert x["exit"] == "surrender" and x["exit_t"] == 2 * M


def test_1r0_is_the_rules_distance_in_every_stop_cell():
    # a sell at 100.0, the rule's stop 101.4 (d_s0 1.4); the ask falls to 98.5 (+1.5): 1R0 = 1.4 is reached even with
    # the stop x 2 (risk 2.8) -> pnl 1.4, R 0.5
    T = ticks([(0, 100.0, 100.2), (1, 99.5, 99.7), (2, 98.3, 98.5), (3, 98.6, 98.8)])
    x = cells(tsim.grid(*T, 0, -1, 101.4, np.nan, 10 * M, sides=("same",)))[("same", 2.0, "1R0")]
    assert x["exit"] == "target" and abs(x["pnl"] - 1.4) < 1e-9 and abs(x["R"] - 0.5) < 1e-9


def test_stop_and_target_given_as_distance_and_multiple():
    # stop_d 1.2 from the fill 100.2 = the price 99.0; tgt_r 2 -> 2.4 our way (not reached) - the same as the prices
    a = cells(tsim.grid(*A, 0, 1, np.nan, np.nan, 10 * M, stop_d=1.2, tgt_r=2.0))
    b = cells(tsim.grid(*A, 0, 1, 99.0, 102.6, 10 * M))
    for k in b:
        assert abs(a[k]["pnl"] - b[k]["pnl"]) < 1e-9 and a[k]["exit"] == b[k]["exit"]
