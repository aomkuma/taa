"""pullback.signals and pullback.manage by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_pullback.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pullback import manage, signals  # noqa: E402


def path(n_up=25, top=110.0, n_down=6, bottom=104.0):
    """A rise to `top`, a pullback to `bottom` over n_down bars, then one bar closing back up."""
    c = list(np.linspace(100, top, n_up)) + list(np.linspace(top - 1, bottom, n_down))
    h = [x + 0.3 for x in c]
    lo = [x - 0.3 for x in c]
    # the turn: a bar closing above the 3 bars before it
    c.append(bottom + 2.5)  # 106.5: above the 3 bars before it (highs 106.3, 105.3, 104.3)
    h.append(bottom + 2.7)
    lo.append(bottom - 0.1)
    return np.array(h), np.array(lo), np.array(c)


def test_a_pullback_in_an_up_trend_and_the_turn():
    h, lo, c = path()
    n = len(c)
    S = signals(h, lo, c, np.ones(n, int), np.full(n, 3.0))
    # the turn bar (the last) closes 106.5 > the 3 bars before (highs up to 106.3): a buy; the pullback low 103.7
    assert S.i.tolist() == [n - 1] and S.side.tolist() == [1] and S.extreme.iloc[0] == pytest.approx(103.7)


def test_no_signal_without_the_trend_or_a_deep_enough_pullback():
    h, lo, c = path()
    n = len(c)
    assert signals(h, lo, c, np.zeros(n, int), np.full(n, 3.0)).empty  # no trend
    assert signals(h, lo, c, np.ones(n, int), np.full(n, 10.0)).empty  # the drop (~6.6) is under 1 x 10
    # in a down trend the same path is a rally against it (100 -> 110) turning down: a sell, its extreme the high 110.3
    S = signals(h, lo, c, -np.ones(n, int), np.full(n, 3.0))
    assert S.side.tolist() == [-1] and S.extreme.iloc[0] == pytest.approx(110.3)


def bars(o, h, lo, c, sp=0.3):
    return [np.array(x, float) for x in (o, h, lo, c)] + [np.full(len(o), sp), np.zeros(len(o), bool)]


def test_manage_target_three_r():
    # in at 106 + 0.3 + 0.07 = 106.37; the stop 103.7 - 0.3 = 103.4 -> R0 2.97; the target 106.37 + 8.91 = 115.28
    o, h, lo, c, sp, ny = bars([106, 107, 109, 112, 116], [106.5, 108, 110, 113, 115.3], [105.8, 106.2, 108, 111, 114], [106, 108, 110, 112.5, 115])
    x = manage(o, h, lo, c, sp, ny, 0, 1, 103.7)
    assert x["exit"] == "win" and x["r0"] == pytest.approx(2.97) and x["pnl"] == pytest.approx(3 * 2.97) and x["xj"] == 4


def test_manage_surrender_and_stop():
    # never +1 R0 (109.34) in the first 5 bars: out at bar 4's close 107.0 - 0.07
    flat = [106.5] * 6
    o, h, lo, c, sp, ny = bars([106] * 6, [107.0] * 6, [105.5] * 6, [107.0] * 6)
    x = manage(o, h, lo, c, sp, ny, 0, 1, 103.7)
    assert x["exit"] == "surrender" and x["xj"] == 4 and x["pnl"] == pytest.approx(107.0 - 0.07 - 106.37)
    # bar 1 falls to 103.3 <= the stop 103.4: out at the stop less the stop slippage 0.15
    o, h, lo, c, sp, ny = bars([106, 105], [106.5, 105.5], [105.8, 103.3], [106, 104])
    x = manage(o, h, lo, c, sp, ny, 0, 1, 103.7)
    assert x["exit"] == "stop" and x["pnl"] == pytest.approx(103.4 - 106.37 - 0.15)
    assert flat  # (kept for readability)


def test_the_risk_outside_its_range_is_no_trade():
    o, h, lo, c, sp, ny = bars([106], [106.5], [105.8], [106])
    assert manage(o, h, lo, c, sp, ny, 0, 1, 105.5) is None  # R0 = 106.37 - 105.2 = 1.17 < 2
    assert manage(o, h, lo, c, sp, ny, 0, 1, 97.0) is None  # R0 = 9.67 > 8


def test_a_dip_before_the_high_is_not_a_pullback():
    # a rise, a dip to 98 nine bars ago, then new highs: the lowest low came BEFORE the highest high - no buy
    c = list(np.linspace(100, 104, 22)) + [98.0] + list(np.linspace(99, 106, 9))
    c = np.array(c)
    h, lo = c + 0.3, c - 0.3
    n = len(c)
    assert signals(h, lo, c, np.ones(n, int), np.full(n, 3.0)).empty


def test_the_turn_bar_must_close_above_the_three_before_it():
    h, lo, c = path()
    c[-1], h[-1] = 106.0, 106.4  # closes under 106.3 (the bar before): no turn yet, whatever its own high
    n = len(c)
    assert signals(h, lo, c, np.ones(n, int), np.full(n, 3.0)).empty


def test_one_bar_reaching_the_stop_and_the_target_is_a_stop():
    o, h, lo, c, sp, ny = bars([106, 106], [106.5, 116.0], [105.8, 103.0], [106, 110])
    assert manage(o, h, lo, c, sp, ny, 0, 1, 103.7)["exit"] == "stop"
