"""Audit 5: the first developer's dev/p2_trades.py::simulate (imported read only) on hand-worked ticks.

Ticks are (seconds, bid), the ask is bid + 0.30. simulate(t, bid, ask, t_entry, side, stop, target, t_struct, t_limit).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dev"))
from p2_trades import simulate  # noqa: E402

S = 10**9
NAN = float("nan")


def ticks(rows: list[tuple[float, float]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t, b = zip(*rows, strict=True)
    b = np.array(b, float)
    return (np.array(t, float) * S).astype(np.int64), b, b + 0.3


def test_a_buy_stop_on_the_bid_through_its_gap_and_r_over_the_fills_risk() -> None:
    # buy at the ask 100.3 + 0.07 = 100.37, stop 95 -> risk 5.37; the bid 96 holds, 93 is past: out at 93, -7.37,
    # R -7.37 / 5.37
    t, bid, ask = ticks([(0, 100), (60, 96), (120, 93), (180, 120)])
    x = simulate(t, bid, ask, 0, 1, 95.0, NAN, None, 3600 * S)
    assert x["exit"] == "stop" and x["pnl"] == pytest.approx(93 - 100.37)
    assert x["risk"] == pytest.approx(5.37) and x["R"] == pytest.approx(-7.37 / 5.37)


def test_a_sell_target_is_a_limit_on_the_ask() -> None:
    # sell at the bid 100 - 0.07 = 99.93, target 90: the ask 85.3 is past it -> filled at 90, +9.93
    t, bid, ask = ticks([(0, 100), (60, 85)])
    x = simulate(t, bid, ask, 0, -1, 105.0, 90.0, None, 3600 * S)
    assert x["exit"] == "target" and x["pnl"] == pytest.approx(9.93)


def test_the_stop_and_the_structure_exit_on_one_tick_is_the_stop() -> None:
    t, bid, ask = ticks([(0, 100), (60, 99), (120, 94)])
    x = simulate(t, bid, ask, 0, 1, 95.0, NAN, 120 * S, 3600 * S)
    assert x["exit"] == "stop" and x["pnl"] == pytest.approx(94 - 100.37)


def test_a_tick_gap_over_30_minutes_exits_at_the_last_tick_before_it() -> None:
    # the daily break: ticks stop at 299 s and resume 70 minutes later at 150: out at 299 s at the bid 101 -> +0.63
    t, bid, ask = ticks([(0, 100), (299, 101), (299 + 70 * 60, 150)])
    x = simulate(t, bid, ask, 0, 1, 95.0, NAN, None, 3 * 3600 * S)
    assert x["exit"] == "break" and x["exit_t"] == 299 * S and x["pnl"] == pytest.approx(101 - 100.37)


def test_no_trade_when_the_fill_is_already_past_the_stop() -> None:
    t, bid, ask = ticks([(0, 100), (60, 101)])
    assert simulate(t, bid, ask, 0, 1, 100.5, NAN, None, 3600 * S) is None  # the fill 100.37 is below the stop 100.5


def test_the_time_exit_is_the_first_tick_at_or_after_the_limit() -> None:
    t, bid, ask = ticks([(0, 100), (100, 100.5), (200, 100.8), (400, 101)])
    x = simulate(t, bid, ask, 0, 1, 95.0, NAN, None, 200 * S)
    assert x["exit"] == "time" and x["exit_t"] == 200 * S and x["pnl"] == pytest.approx(100.8 - 100.37)
