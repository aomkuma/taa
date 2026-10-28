"""d2_straddle by hand: the reference tick, the two stop orders and their 60 s, the fill with the release slippage, the
stop 8 U, the time exit, the gap, U from the price.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_d2_straddle.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d2_straddle as D  # noqa: E402

S = 10**9
MN = 60 * S
T0 = 1_768_000_000 * S


def tk(rows):
    """rows: (seconds from T0, bid, ask)."""
    t = np.array([T0 + int(r[0] * S) for r in rows], np.int64)
    return t, np.array([r[1] for r in rows], float), np.array([r[2] for r in rows], float)


def test_the_reference_tick():
    assert D.reference(*tk([(-40, 1, 2), (-20, 3999.0, 3999.4), (0, 5, 6)]), T0) == (3999.0, 3999.4)  # the one before T0
    assert D.reference(*tk([(-30, 3999.0, 3999.4), (1, 5, 6)]), T0) == (3999.0, 3999.4)  # 30 s: still armed
    assert D.reference(*tk([(-31, 3999.0, 3999.4), (1, 5, 6)]), T0) is None  # 31 s old
    assert D.reference(*tk([(0, 3999.0, 3999.4)]), T0) is None  # no tick before


def test_the_stop_orders():
    # U = 4000 / 4000 = 1: the buy stop 4000.4 + 2 = 4002.4, the sell stop 4000 - 2 = 3998
    rows = [(-5, 4000.0, 4000.4), (5, 4001.9, 4002.3), (10, 4002.1, 4002.5), (12, 3990, 3990.4)]
    assert D.triggered(*tk(rows), T0, 4002.4, 3998.0) == (2, 1)  # 4002.3 < 4002.4; 4002.5 >= it
    rows = [(-5, 4000.0, 4000.4), (5, 3998.0, 3998.4)]
    assert D.triggered(*tk(rows), T0, 4002.4, 3998.0) == (1, -1)  # the bid at the sell stop
    rows = [(-5, 4000.0, 4000.4), (60, 3990.0, 3990.4)]
    assert D.triggered(*tk(rows), T0, 4002.4, 3998.0) is None  # at T0 + 60 s: no longer live
    rows = [(-5, 4000.0, 4000.4), (-1, 3990.0, 4010.0), (59.9, 3997.9, 4002.5)]
    assert D.triggered(*tk(rows), T0, 4002.4, 3998.0) == (2, 1)  # before T0 not live; both on one tick: the buy


def test_a_straddle_trade():
    # the buy at the tick's ask 4002.5 + 0.07 + 0.5 = 4003.07; the stop 4003.07 - 8 = 3995.07; held 15 minutes: out at
    # the first tick at / after T0 + 15 min, on the bid 4010 -> +6.93 USD, R 6.93 / 8
    rows = [(-5, 4000.0, 4000.4), (10, 4002.1, 4002.5), (300, 4005.0, 4005.4), (899, 4006, 4006.4), (900, 4010.0, 4010.4),
            (960, 3000.0, 3000.4)]
    x = D.straddle(*tk(rows), T0, 2.0, 8.0, 15, 0.5)
    assert (x["side"], x["exit"], x["exit_t"]) == (1, "time", T0 + 900 * S)
    assert x["entry"] == pytest.approx(4003.07) and x["stop"] == pytest.approx(3995.07) and x["R"] == pytest.approx(6.93 / 8)
    rows2 = [(-5, 4000.0, 4000.4), (5, 4001.9, 4002.3)] + rows[1:]  # the ask 4002.3 is below the buy stop 4002.4
    x2 = D.straddle(*tk(rows2), T0, 2.0, 8.0, 15, 0.5)
    assert x2["up"] == pytest.approx(4002.4) and x2["entry_t"] == T0 + 10 * S
    rows = [(-5, 4000.0, 4000.4), (10, 4002.1, 4002.5), (300, 3995.07, 3995.47), (400, 4100, 4100.4), (900, 4010.0, 4010.4)]
    x = D.straddle(*tk(rows), T0, 2.0, 8.0, 15, 0.5)
    assert x["exit"] == "stop" and x["exit_px"] == pytest.approx(3995.07)  # the bid exactly at the stop
    rows = [(-5, 4000.0, 4000.4), (10, 4002.1, 4002.5), (300, 3990.0, 3990.4), (900, 4010.0, 4010.4)]
    x = D.straddle(*tk(rows), T0, 2.0, 8.0, 15, 0.0)
    assert x["exit"] == "stop" and x["pnl"] == pytest.approx(3990.0 - 4002.57)  # a gap through: the tick's bid


def test_a_sell_and_the_unit():
    # U = 4400 / 4000 = 1.1: the sell stop 4400 - 2.2 = 4397.8; the fill at the bid 4397.5 - 0.07 - 1 = 4396.43; the stop
    # 4396.43 + 8.8 = 4405.23 on the ask; out at T0 + 30 min on the ask
    rows = [(-5, 4400.0, 4400.4), (3, 4397.5, 4397.9), (600, 4390.0, 4390.4), (1800, 4380.0, 4380.4)]
    x = D.straddle(*tk(rows), T0, 2.0, 8.0, 30, 1.0)
    assert (x["side"], x["exit"]) == (-1, "time") and x["unit"] == pytest.approx(1.1) and x["dn"] == pytest.approx(4397.8)
    assert x["entry"] == pytest.approx(4396.43) and x["stop"] == pytest.approx(4405.23) and x["risk"] == pytest.approx(8.8)
    assert x["pnl"] == pytest.approx(4396.43 - 4380.4)
    rows = [(-5, 4400.0, 4400.4), (3, 4397.5, 4397.9), (600, 4404.9, 4405.3), (1800, 4380.0, 4380.4)]
    assert D.straddle(*tk(rows), T0, 2.0, 8.0, 30, 1.0)["exit"] == "stop"  # the ask 4405.3 >= 4405.23


def test_the_gap_and_no_trade():
    rows = [(-5, 4000.0, 4000.4), (10, 4002.1, 4002.5), (100, 4003.0, 4003.4), (100 + 31 * 60, 4020, 4020.4)]
    x = D.straddle(*tk(rows), T0, 2.0, 8.0, 30, 0.0)  # no tick for 31 minutes: out at the last tick before the gap
    assert x["exit"] == "break" and x["exit_t"] == T0 + 100 * S
    assert D.straddle(*tk([(-5, 4000.0, 4000.4), (10, 4001.0, 4001.4)]), T0, 2.0, 8.0, 30, 0.0) is None  # no trigger
    assert D.straddle(*tk([(-40, 4000.0, 4000.4), (10, 4010.0, 4010.4)]), T0, 2.0, 8.0, 30, 0.0) is None  # no reference
