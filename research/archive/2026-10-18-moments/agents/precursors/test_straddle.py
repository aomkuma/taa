"""straddle.straddle by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_straddle.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from straddle import straddle  # noqa: E402

NS_MIN = 60 * 10**9


def market(h, lo, c=None, sp=0.3):
    h, lo = np.array(h, float), np.array(lo, float)
    c = (h + lo) / 2 if c is None else np.array(c, float)
    n = len(h)
    return dict(o=c, h=h, lo=lo, c=c, sp=np.full(n, sp), ot_ns=np.arange(n, dtype=np.int64) * NS_MIN, ny=np.zeros(n, bool))


def test_a_buy_stop_then_the_target():
    # close 100, b 3: bar 1's high 103.5 triggers the buy at 103 + 0.3 + 0.07 = 103.37; s 5 -> stop 98.37; bar 2 high 113.4 >= 113.37
    mk = market([100.5, 103.5, 113.4, 113], [99.5, 101.0, 103.0, 112])
    x = straddle(mk, 0, 100.0, 3.0, 5.0)
    assert x["side"] == 1 and x["fj"] == 1 and x["exit"] == "win" and x["pnl"] == pytest.approx(10.0)


def test_a_sell_stop_then_its_stop():
    # low 96.9 triggers the sell at 97 - 0.07 = 96.93; stop 101.93 on the ask: bar 2 high 101.7 + 0.3 = 102.0 reaches it
    mk = market([100.5, 99.0, 101.7], [99.5, 96.9, 97.0])
    x = straddle(mk, 0, 100.0, 3.0, 5.0)
    assert x["side"] == -1 and x["exit"] == "stop" and x["pnl"] == pytest.approx(-(101.93 + 0.15 - 96.93))


def test_both_in_one_bar_is_a_full_stop_and_nothing_is_none():
    mk = market([100.5, 104.0], [99.5, 96.0])
    x = straddle(mk, 0, 100.0, 3.0, 5.0)
    assert x["exit"] == "both" and x["pnl"] < -5.15
    assert straddle(market([100.5] * 70, [99.5] * 70), 0, 100.0, 3.0, 5.0) is None


def test_the_fill_bar_touching_the_stop():
    # the buy fills at 103.37 in bar 1, whose low 98.0 is under the stop 98.37: a stop
    mk = market([100.5, 103.5, 104], [99.5, 98.0, 102])
    assert straddle(mk, 0, 100.0, 3.0, 5.0)["exit"] == "stop"


def test_the_bound_from_above_skips_what_m1_cannot_order():
    mk = market([100.5, 104.0], [99.5, 96.0])
    assert straddle(mk, 0, 100.0, 3.0, 5.0, pessimistic=False) is None  # both levels in one bar: no trade
    # the fill bar's low 98.0 (maybe before the fill) is not read: the buy goes on to the target in bar 2
    mk = market([100.5, 103.5, 113.5, 113], [99.5, 98.0, 103.0, 112])
    x = straddle(mk, 0, 100.0, 3.0, 5.0, pessimistic=False)
    assert x["exit"] == "win" and x["fj"] == 1
