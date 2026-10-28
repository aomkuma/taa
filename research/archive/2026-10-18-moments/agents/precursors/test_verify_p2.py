"""verify_p2.metrics by hand (the measurer's second computation of the P2 numbers).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_verify_p2.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_p2 import metrics  # noqa: E402


def test_the_metrics_by_hand():
    # USD +2 -1 -1 +3 -2 (in entry order; shuffled rows must not matter): equity 0 2 1 0 3 1 -> the drawdown 2 (2 -> 0);
    # win 2 / 5; R mean 0.1, sd 1.0840 (ddof 1), the 95 % range 0.1 +- 1.96 x 1.0840 / sqrt 5 = +- 0.9502; the longest
    # losing streak 2; the worst -2; 5 trades over 10 weekdays
    T = pd.DataFrame(dict(entry_t=[3, 1, 5, 2, 4], pnl=[-1.0, 2.0, -2.0, -1.0, 3.0], R=[-0.5, 1.0, -1.0, -0.5, 1.5]))
    x = metrics(T, 10)
    assert x["n"] == 5 and x["per_day"] == 0.5 and x["win"] == pytest.approx(0.4) and x["usd"] == pytest.approx(1.0)
    assert x["R"] == pytest.approx(0.1) and x["R_lo"] == pytest.approx(-0.8502, abs=1e-4) and x["R_hi"] == pytest.approx(1.0502, abs=1e-4)
    assert x["dd"] == pytest.approx(2.0) and x["worst"] == -2.0 and x["streak"] == 2


def test_a_drawdown_from_the_start_counts():
    # the first trades lose: the drawdown is measured from 0, not from the first trade's equity
    T = pd.DataFrame(dict(entry_t=[1, 2, 3], pnl=[-3.0, -2.0, 4.0], R=[-1.0, -1.0, 2.0]))
    assert metrics(T, 3)["dd"] == pytest.approx(5.0)


def test_a_break_even_trade_is_not_a_win():
    T = pd.DataFrame(dict(entry_t=[1, 2], pnl=[0.0, 1.0], R=[0.0, 0.5]))
    assert metrics(T, 2)["win"] == pytest.approx(0.5)
