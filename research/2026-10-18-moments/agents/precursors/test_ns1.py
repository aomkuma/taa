"""Hand tests of ns1.straddle_m1 (bars written here; spread 2 points -> s = 0.02 + 0.08 = 0.10)."""

import pandas as pd
import pytest

from ns1 import straddle_m1

T0 = pd.Timestamp("2026-01-07 13:30", tz="UTC")


def bars(rows):
    idx = [T0 + pd.Timedelta(minutes=k) for k in range(-1, len(rows) - 1)]
    return pd.DataFrame([dict(open=o, high=h, low=lo, close=c, spread=2) for o, h, lo, c in rows], index=idx)


def flat(n, p=100.0):
    return [(p, p, p, p)] * n


def test_buy_held_to_the_time_exit():
    # ref close 100 -> buy stop 100 + 0.1 + 2 = 102.1; the 08:30 ask high 103.1 -> fill 102.1; out at 09:00 open bid 105
    rows = [(100, 100, 100, 100), (100, 103, 99.5, 102.5)] + flat(29, 103) + [(105, 105, 105, 105)]
    r = straddle_m1(bars(rows), T0)
    assert r["side"] == 1 and r["entry"] == pytest.approx(102.1) and r["exit"] == "time"
    assert r["pnl"] == pytest.approx(105 - 102.1) and not r["both"]


def test_sell_stopped_on_the_ask():
    # sell stop 98: low 97 -> fill 98, stop 106; a later ask high 105.95 + 0.1 = 106.05 >= 106 -> out at 106
    rows = [(100, 100, 100, 100), (100, 100, 97, 97)] + flat(5, 97) + [(97, 105.95, 97, 105)] + flat(23, 105) + [(105,) * 4]
    r = straddle_m1(bars(rows), T0)
    assert r["side"] == -1 and r["entry"] == 98 and r["exit"] == "stop" and r["R"] == pytest.approx(-1.0)


def test_sell_exits_on_the_ask_at_the_time():
    rows = [(100, 100, 100, 100), (100, 100, 97, 97)] + flat(29, 95) + [(95, 95, 95, 95)]
    r = straddle_m1(bars(rows), T0)
    assert r["exit"] == "time" and r["pnl"] == pytest.approx(98 - 95.1)


def test_gap_fill_at_the_open():
    rows = [(100, 100, 100, 100), (104, 105, 104, 105)] + flat(29, 105) + [(105,) * 4]
    r = straddle_m1(bars(rows), T0)
    assert r["entry"] == pytest.approx(104.1)  # the open's ask, past the 102.1 trigger


def test_gap_through_the_stop_fills_at_the_open():
    rows = [(100, 100, 100, 100), (100, 102.5, 100, 102.2)] + [(90, 91, 89, 90)] + flat(28, 90) + [(90,) * 4]
    r = straddle_m1(bars(rows), T0)
    assert r["exit"] == "stop" and r["exit_px"] == 90  # the stop 94.1 was gapped: out at the bar's open


def test_both_reached_counts_the_worse_side():
    # both stops in the 08:30 bar; price ends at 99: the buy (102.1) loses 3.1, the sell (98) loses 1.1 -> the buy
    rows = [(100, 100, 100, 100), (100, 103, 97, 100)] + flat(29, 99) + [(99,) * 4]
    r = straddle_m1(bars(rows), T0)
    assert r["both"] and r["side"] == 1 and r["pnl"] == pytest.approx(99 - 102.1)


def test_target_and_stop_in_one_bar_is_the_stop():
    rows = [(100, 100, 100, 100), (100, 102.5, 100, 102.2)] + [(102.2, 111, 94, 100)] + flat(28, 100) + [(100,) * 4]
    r = straddle_m1(bars(rows), T0, target_r=1.0)
    assert r["exit"] == "stop"


def test_target_hit():
    rows = [(100, 100, 100, 100), (100, 102.5, 100, 102.2)] + [(102.2, 110.2, 102, 110)] + flat(28, 110) + [(110,) * 4]
    r = straddle_m1(bars(rows), T0, target_r=1.0)
    assert r["exit"] == "target" and r["R"] == pytest.approx(1.0)


def test_stop_in_the_trigger_bar_counts():
    # the 08:30 bar reaches the buy stop 102.1 and later (conservatively) its low 94 < the stop 94.1
    rows = [(100, 100, 100, 100), (100, 102.5, 94, 95)] + flat(29, 95) + [(95,) * 4]
    r = straddle_m1(bars(rows), T0)
    assert r["both"]  # the low 94 also reached the sell stop 98
    rows = [(100, 100, 100, 100), (100, 102.5, 98.5, 99)] + flat(29, 99) + [(99,) * 4]
    r = straddle_m1(bars(rows), T0)
    assert r["side"] == 1 and r["exit"] == "time"


def test_no_trigger_no_trade():
    rows = [(100, 100, 100, 100), (100, 101.9, 98.1, 100)] + flat(30)
    assert straddle_m1(bars(rows), T0) is None
