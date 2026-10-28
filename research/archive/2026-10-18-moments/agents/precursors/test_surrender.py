"""surrender.trade by hand, tick by tick.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_surrender.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from surrender import trade  # noqa: E402

S = 10**9


def ticks(rows):
    t, b = zip(*rows)
    b = np.array(b, float)
    return np.array(t, np.int64) * S, b, b + 0.3


def test_it_runs_then_the_target():
    # a buy at the ask 100.3 + 0.07 = 100.37; within 3 minutes the bid reaches 102.4 (+2.03): it ran; then 110.4 -> the target
    t, bid, ask = ticks([(0, 100.0), (60, 102.4), (200, 105.0), (400, 110.4)])
    x = trade(t, bid, ask, 0, 1, 3, 2.0)
    assert x["exit"] == "win" and x["pnl"] == 10.0 and x["entry"] == pytest.approx(100.37)


def test_it_does_not_run_so_we_give_up_at_three_minutes():
    # the bid creeps to 101.0 (+0.63) only; at 180 s the surrender: out at that tick's bid 100.8 -> +0.43
    t, bid, ask = ticks([(0, 100.0), (60, 101.0), (180, 100.8), (300, 110.5)])
    x = trade(t, bid, ask, 0, 1, 3, 2.0)
    assert x["exit"] == "surrender" and x["pnl"] == pytest.approx(100.8 - 100.37)


def test_without_the_surrender_it_would_have_won():
    t, bid, ask = ticks([(0, 100.0), (60, 101.0), (180, 100.8), (300, 110.5)])
    assert trade(t, bid, ask, 0, 1, None, None)["exit"] == "win"


def test_the_stop_before_the_surrender_and_a_sell_on_the_ask():
    # a sell at the bid 100 - 0.07 = 99.93; the ask jumps to 110.3 (bid 110.0) at 30 s: beyond the stop -> out at 110.3
    t, bid, ask = ticks([(0, 100.0), (30, 110.0), (200, 95.0)])
    x = trade(t, bid, ask, 0, -1, 3, 2.0)
    assert x["exit"] == "stop" and x["pnl"] == pytest.approx(99.93 - 110.3)


def test_running_late_still_surrenders():
    # +2 our way only at 240 s - after K = 3 minutes: the surrender comes first, at the first tick at / after 180 s
    t, bid, ask = ticks([(0, 100.0), (100, 100.5), (190, 100.6), (240, 102.6)])
    x = trade(t, bid, ask, 0, 1, 3, 2.0)
    assert x["exit"] == "surrender" and x["pnl"] == pytest.approx(100.6 - 100.37)
