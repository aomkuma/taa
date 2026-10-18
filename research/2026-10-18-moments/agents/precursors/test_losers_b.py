"""losers_b.anatomy by hand: the path of a buy and of a sell in shares of the distance, and the kinds.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_losers_b.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from losers_b import anatomy  # noqa: E402

NS_MIN = 60 * 10**9


def market(h, lo, sp=0.0):
    h, lo = np.array(h, float), np.array(lo, float)
    return dict(o=(h + lo) / 2, h=h, lo=lo, sp=np.full(len(h), sp))


def test_a_buy_winner_went_against_first():
    mk = market([100.5, 100.2, 104.5], [99.5, 97.0, 100.0])  # entry at bar 0's open 100 (no spread) + 0.07
    a = anatomy(mk, 0, 1, 4.0, dict(exit="win", pnl=4.0, xj=2))
    assert a["kind"] == "won" and a["mfe"] == pytest.approx((104.5 - 100.07) / 4) and a["mae"] == pytest.approx((100.07 - 97.0) / 4)


def test_a_sell_fell_short_uses_the_ask():
    # a sell at 100 - 0.07 = 99.93, spread 0.2: bar 1's low 97.5 + 0.2 = 97.7 is 2.23 its way (over half of 4);
    # bar 2's high 103.9 + 0.2 = 104.1 >= the stop 103.93; afterwards never down to the target 95.93
    mk = market([100.5, 100.0, 103.9] + [101.0] * 5, [99.5, 97.5, 100.0] + [99.0] * 5, sp=0.2)
    a = anatomy(mk, 0, -1, 4.0, dict(exit="stop", pnl=-4.15, xj=2))
    assert a["kind"] == "2 fell short" and a["mfe"] == pytest.approx(2.23 / 4) and a["mae"] == pytest.approx((104.1 - 99.93) / 4)


def test_a_stopped_buy_that_ran_later_was_early():
    mk = market([100.5, 100.2, 101.0, 105.0], [99.5, 95.9, 98.0, 100.0])  # stopped at bar 1 (95.9 <= 96.07), target at bar 3
    a = anatomy(mk, 0, 1, 4.0, dict(exit="stop", pnl=-4.15, xj=1))
    assert a["kind"] == "3 entered too early" and a["survive"] == pytest.approx((100.07 - 95.9) / 4)
