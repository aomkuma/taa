"""tick_straddle.trade by hand, tick by tick.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_tick_straddle.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tick_straddle import trade  # noqa: E402

S = 10**9  # one second


def ticks(rows):
    t, b = zip(*rows)
    b = np.array(b, float)
    return np.array(t, np.int64) * S, b, b + 0.3  # the spread 0.3


def test_the_dip_before_the_trigger_does_not_stop_the_buy():
    # c0 100, b 3: the bid dips to 98.0 first - below the stop the buy will have (98.17), above the sell trigger (97)
    t, bid, ask = ticks([(1, 100.0), (2, 98.0), (3, 102.8), (4, 103.0), (5, 113.5)])
    # tick 3: ask 103.1 >= 103 -> a buy at 103.1 + 0.07 = 103.17; s 5 -> stop 98.17; tick 5 bid 113.5 >= 113.17: the target
    x = trade(t, bid, ask, 0, 100.0, 3.0, 5.0)
    assert x["side"] == 1 and x["exit"] == "win" and x["entry"] == pytest.approx(103.17) and x["pnl"] == 10.0


def test_the_first_trigger_wins_and_the_stop_takes_the_gap():
    # the bid falls to 96.9 first: a sell at 96.83; the ask jumps to 102.5 (bid 102.2): beyond the stop 101.83 -> out at 102.5
    t, bid, ask = ticks([(1, 99.0), (2, 96.9), (3, 99.0), (4, 102.2), (5, 104.0)])
    x = trade(t, bid, ask, 0, 100.0, 3.0, 5.0)
    assert x["side"] == -1 and x["exit"] == "stop" and x["entry"] == pytest.approx(96.83) and x["pnl"] == pytest.approx(96.83 - 102.5)


def test_nothing_within_the_wait_and_out_on_time():
    t, bid, ask = ticks([(1, 100.5), (2, 99.5)])
    assert trade(t, bid, ask, 0, 100.0, 3.0, 5.0) is None
    # a buy at 103.47 (tick 1), then quiet for the hold (here 10 s): out at the last tick's bid 104.0
    t, bid, ask = ticks([(1, 103.4), (5, 104.0), (20, 120.0)])
    x = trade(t, bid, ask, 0, 100.0, 3.0, 5.0, wait_ns=60 * S, hold_ns=10 * S)
    assert x["exit"] == "time" and x["pnl"] == pytest.approx(104.0 - (103.7 + 0.07))


def test_ticks_before_the_moment_are_not_used():
    t, bid, ask = ticks([(-5, 110.0), (1, 100.0), (2, 100.2)])
    assert trade(t, bid, ask, 0, 100.0, 3.0, 5.0) is None
