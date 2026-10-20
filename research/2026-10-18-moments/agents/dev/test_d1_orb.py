"""d1_orb by hand: the range and its decision (edges of time, width and the close), the tick trade, the M1 trade, the
level in the way, the readings by time (H, ADR20).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_d1_orb.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d1_orb as D  # noqa: E402

MN = 60 * 10**9
S = 10**9
T0 = pd.Timestamp("2026-01-14 06:00", tz="UTC").value


def day_bars(first: int = 0, n: int = 90):
    """M1 bars from 06:00 + first minutes: range bars high 101 / low 99, close 100; bar 06:07 high 101.5, bar 06:03 low
    98.5 -> the 15-minute range 101.5 / 98.5 (3.0)."""
    t = T0 + np.arange(first, first + n) * MN
    h, lo, c = np.full(n, 101.0), np.full(n, 99.0), np.full(n, 100.0)
    for i, minute in enumerate(range(first, first + n)):
        if minute == 7:
            h[i] = 101.5
        if minute == 3:
            lo[i] = 98.5
    return t, h, lo, c


def test_the_range_and_the_decision():
    t, h, lo, c = day_bars()
    c[18] = 101.5  # exactly at the range high: not beyond
    c[20] = 101.6  # 06:20 closes above: buy, the decision at 06:21
    d = D.decide(t, h, lo, c, T0, 2.0, 15)
    assert d["status"] == "trade" and (d["side"], d["stop"], d["k"], d["rh"], d["rl"]) == (1, 98.5, 20, 101.5, 98.5)
    assert d["t_dec"] == T0 + 21 * MN and d["close"] == 101.6
    assert D.decide(t, h, lo, c, T0, 1.9, 15)["status"] == "wide"  # 3.0 > 1.5 x 1.9 = 2.85
    assert D.decide(t, h, lo, c, T0, 2.0, 15)["status"] == "trade"  # 3.0 = 1.5 x 2.0: not wider
    assert D.decide(t, h, lo, c, T0, np.nan, 15)["status"] == "wide"  # no H
    c2 = c.copy()
    c2[20], c2[16] = 100.0, 98.4  # 06:16 closes below: sell, the stop the range high
    d = D.decide(t, h, lo, c2, T0, 2.0, 15)
    assert (d["side"], d["stop"], d["k"]) == (-1, 101.5, 16)
    d10 = D.decide(t, h, lo, c, T0, 2.0, 10)  # the first 10 minutes: 101.5 / 98.5 too; the window 06:10 - 07:09
    assert d10["status"] == "trade" and d10["k"] == 20
    h2 = h.copy()
    h2[14] = 101.55  # the range's last bar (06:14) sets the high: a close at 101.52 is inside
    c3 = c.copy()
    c3[20] = 101.52
    assert D.decide(t, h2, lo, c3, T0, 2.1, 15)["status"] == "no break"  # H 2.1: 3.05 is not wide


def test_the_entry_window_and_the_open():
    t, h, lo, c = day_bars()
    c[75] = 101.6  # 07:15: outside the window (06:15 - 07:14)
    assert D.decide(t, h, lo, c, T0, 2.0, 15)["status"] == "no break"
    c[74] = 101.6  # 07:14: inside
    assert D.decide(t, h, lo, c, T0, 2.0, 15)["k"] == 74
    t5, h5, lo5, c5 = day_bars(first=5)  # the first bar at 06:05: counts (the range = bars 06:05 - 06:14)
    c5[20 - 5] = 101.6
    d = D.decide(t5, h5, lo5, c5, T0, 2.0, 15)
    assert d["status"] == "trade" and (d["rh"], d["rl"]) == (101.5, 99.0)
    t6, h6, lo6, c6 = day_bars(first=6)
    assert D.decide(t6, h6, lo6, c6, T0, 2.0, 15)["status"] == "late open"


def ticks(path):
    t = np.array([p[0] for p in path], np.int64)
    bid = np.array([p[1] for p in path], float)
    return t, bid, bid + 0.1


def test_the_tick_trade():
    td = T0 + 21 * MN
    # the fill 1 s after the decision: ask 101.8 + 0.07 = 101.87; the stop 98.5 -> risk 3.37; the target 101.87 + 6.74
    path = [(td + 1 * S, 101.7), (td + 60 * S, 104.0), (td + 120 * S, 108.61), (td + 180 * S, 109.0)]
    x = D.tick_trade(*ticks(path), td, 1, 98.5, 2.0, 60)
    assert x["entry"] == pytest.approx(101.87) and x["risk"] == pytest.approx(3.37) and x["target"] == pytest.approx(108.61)
    assert x["exit"] == "target" and x["R"] == pytest.approx(2.0) and x["exit_t"] == td + 120 * S
    stop = [(td + 1 * S, 101.7), (td + 60 * S, 100.0), (td + 90 * S, 98.0)]  # a gap through the stop: filled at 98.0
    x = D.tick_trade(*ticks(stop), td, 1, 98.5, 2.0, 60)
    assert x["exit"] == "stop" and x["exit_px"] == 98.0 and x["pnl"] == pytest.approx(98.0 - 101.87)
    tm = [(td + 1 * S, 101.7)] + [(td + k * 10 * MN, 101.9) for k in range(1, 6)] + [(td + 59 * MN, 102.0), (td + 60 * MN + S // 2, 102.2),
                                                                         (td + S + 60 * MN, 102.5), (td + 61 * MN, 103.0)]
    x = D.tick_trade(*ticks(tm), td, 1, 98.5, 2.0, 60)  # out at the first tick at / after the fill + 60 min (not the decision's)
    assert x["exit"] == "time" and x["exit_px"] == 102.5 and x["exit_t"] == td + S + 60 * MN
    assert D.tick_trade(*ticks([(td + 61 * S, 101.7), (td + 120 * S, 103)]), td, 1, 98.5, 2.0, 60) is None  # 61 s late
    sell = [(td + 1 * S, 98.6), (td + 60 * S, 101.5)]  # a sell: bid 98.6 - 0.07; the stop 101.5 on the ask (101.6)
    x = D.tick_trade(*ticks(sell), td, -1, 101.5, 2.0, 60)
    assert x["entry"] == pytest.approx(98.53) and x["exit"] == "stop" and x["exit_px"] == pytest.approx(101.6)


def m1(path_o, path_h, path_l, path_c, spr=0.1, start=21):
    n = len(path_o)
    t = T0 + (start + np.arange(n)) * MN
    return t, np.array(path_o, float), np.array(path_h, float), np.array(path_l, float), np.array(path_c, float), np.full(n, spr)


def test_the_m1_trade():
    # bar 0 = the decision bar (06:21 open? no: its index k_dec = 0); bar 1 opens at the decision: buy at 101.7 + 0.1 +
    # 0.07 = 101.87; the stop 98.8 (risk 3.07), the target 108.01
    t, o, h, lo, c, spr = m1([101, 101.7, 103, 106], [101.7, 102, 104, 108.01], [100, 101, 102, 105], [101.6, 101.9, 103.5, 107])
    x = D.m1_trade(t, o, h, lo, c, spr, 0, 1, 98.8, 2.0, 60)
    assert x["entry"] == pytest.approx(101.87) and x["exit"] == "target" and x["R"] == pytest.approx(2.0)
    t, o, h, lo, c, spr = m1([101, 101.7, 103, 106], [101.7, 102, 104, 108.5], [100, 101, 102, 98.8], [101.6, 101.9, 103.5, 107])
    x = D.m1_trade(t, o, h, lo, c, spr, 0, 1, 98.8, 2.0, 60)  # both in one bar: the stop, at the stop
    assert x["exit"] == "stop" and x["exit_px"] == 98.8
    t, o, h, lo, c, spr = m1([101, 101.7, 98.0], [101.7, 102, 99], [100, 101, 97.5], [101.6, 101.9, 98.5])
    x = D.m1_trade(t, o, h, lo, c, spr, 0, 1, 98.8, 2.0, 60)  # the bar opens past the stop: filled at its open
    assert x["exit"] == "stop" and x["exit_px"] == 98.0
    # a sell on the ask: the decision bar, then fill at 98.6 - 0.07 = 98.53; the stop 101.5 hit when the high + 0.1 >= it
    t, o, h, lo, c, spr = m1([99, 98.6, 99, 100], [99, 98.9, 99.5, 101.4], [98.5, 98.2, 98.5, 99.5], [98.7, 98.8, 99.2, 100.5])
    x = D.m1_trade(t, o, h, lo, c, spr, 0, -1, 101.5, 2.0, 60)
    assert x["entry"] == pytest.approx(98.53) and x["exit"] == "stop" and x["exit_px"] == 101.5
    # the time exit at the open of the first bar at / after the fill + 60 min, a buy at the bid
    n = 63
    t, o, h, lo, c, spr = m1([101.7] * n, [102.0] * n, [101.5] * n, [101.8] * n)
    o[61] = 101.9
    x = D.m1_trade(t, o, h, lo, c, spr, 0, 1, 98.8, 2.0, 60)
    assert x["exit"] == "time" and x["exit_t"] == t[61] and x["exit_px"] == 101.9
    t2 = t.copy()
    t2[1:] += MN  # the bar after the decision opens a minute late: no trade
    assert D.m1_trade(t2, o, h, lo, c, spr, 0, 1, 98.8, 2.0, 60) is None


def test_the_level_in_the_way():
    assert D.level_in_way(np.array([105.0, 99.0, 101.9]), 101.6, 1, 2.8) == pytest.approx(101.9)  # the nearest ahead
    assert np.isnan(D.level_in_way(np.array([108.0, 95.0]), 101.6, 1, 2.8))  # 6.4 > 2 x 2.8; 95 behind
    assert np.isnan(D.level_in_way(np.array([105.0]), 100.0, 1, 2.5))  # exactly 2 R: not closer
    assert np.isnan(D.level_in_way(np.array([100.0]), 100.0, 1, 2.5))  # at the close: not ahead
    assert D.level_in_way(np.array([97.0, 103.0]), 100.0, -1, 2.0) == 97.0  # a sell: below, 3 < 4


def test_the_readings_by_time():
    assert D.at_time(np.array([10, 20]), np.array([1.0, 2.0]), 19) == 1.0
    assert D.at_time(np.array([10, 20]), np.array([1.0, 2.0]), 20) == 2.0  # complete exactly at t counts
    assert np.isnan(D.at_time(np.array([10, 20]), np.array([1.0, 2.0]), 9))
    # ADR20: 25 weekdays, bars 12:00 - 12:59 UTC with high - low = the day's number (1 .. 25); at 06:00 on day 22 the
    # last complete D1 bar is day 21 -> the mean of days 2 .. 21 = 11.5; H: every H1 bar 12:00 - 12:59 has the range of
    # its day and the close 100 -> MT5's ATR(14) of the last H1 bar (day 21) = the mean of the true ranges of days 8 .. 21
    # = 14.5 (bar 0 has no true range)
    days = pd.bdate_range("2026-01-05", periods=25, tz="UTC")
    idx, hi, lw = [], [], []
    for n, d in enumerate(days, 1):
        for mnt in range(60):
            idx.append(d + pd.Timedelta(hours=12, minutes=mnt))
            hi.append(100.0 + n / 2)
            lw.append(100.0 - n / 2)
    m = pd.DataFrame(dict(open=100.0, high=hi, low=lw, close=100.0, spread=10.0), index=pd.DatetimeIndex(idx))
    mk = D.Market(m)
    t = (days[21] + pd.Timedelta(hours=6)).value
    assert mk.adr20(t) == pytest.approx(11.5)
    assert mk.adr20((days[20] + pd.Timedelta(hours=12, minutes=59, seconds=59)).value) == pytest.approx(10.5)  # day 21 not yet
    assert mk.H(t) == pytest.approx(14.5)
    assert np.isnan(mk.H((days[13] + pd.Timedelta(hours=13)).value))  # day 14's bar: only 13 true ranges


def test_the_times_stay_exact():
    t = 1_760_000_000_000_000_064  # not a multiple of 256 ns: a float would round it
    T = D.with_times([dict(day=1, t_dec=t, exit_t=t + 1), dict(day=2)])
    assert int(T.t_dec[0]) == t and int(T.exit_t[0]) == t + 1 and T.t_dec.isna()[1] and str(T.t_dec.dtype) == "Int64"
