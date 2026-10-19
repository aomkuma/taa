"""loser_charts.levels by hand.

    data/venv-research/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_loser_charts.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loser_charts import levels, one_per_reason  # noqa: E402


def test_the_lines_of_a_buy_and_a_sell():
    # a buy at 106.37 risking 2.97: the stop 103.40, the target at 3 R 115.28; a sell mirrored
    assert levels(1, 106.37, 2.97, 3.0) == pytest.approx((103.40, 115.28))
    assert levels(-1, 100.0, 4.0, 3.0) == pytest.approx((104.0, 88.0))


def test_one_loser_per_reason_nearest_its_median():
    L = pd.DataFrame(dict(reason=["a", "b", "a", "a", "b", "a", "a"], pnl=[-1.0, -5.0, -2.0, -9.0, -4.0, -10.0, -30.0], t=range(7)))
    P = one_per_reason(L)
    # "a": median -9 -> the -9 (the mean -10.4 would pick -10), 5 losers, first; "b": median -4.5, -5 and -4 tie -> the
    # earlier (row 1)
    assert P.reason.tolist() == ["a", "b"] and P.pnl.tolist() == [-9.0, -5.0] and P.n_reason.tolist() == [5, 2]
