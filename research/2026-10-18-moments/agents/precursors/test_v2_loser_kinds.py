"""v2_loser_kinds.kind_of by hand: the three kinds of a stopped buy.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_v2_loser_kinds.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2_loser_kinds import kind_of  # noqa: E402


def test_three_kinds_by_hand():
    sp = np.full(6, 0.2)
    # a buy at 100 (bar 0), the target 10 away, the stop at 95 hit on bar 2
    lo = np.array([99.0, 98.0, 94.0, 96.0, 97.0, 98.0])
    h = np.array([101.0, 103.0, 99.0, 104.0, 108.0, 111.0])  # before the stop: up to 103 (0.3 of the target)
    k = kind_of(h, lo, sp, 0, 2, 1, 100.0, 10.0)
    assert k["kind"] == "3 entered too early" and math.isclose(k["mfe"], 0.3)  # 111 >= 110 on bar 5
    assert math.isclose(k["survive"], 6.0)  # the lowest low before the target: 94
    h2 = h.copy()
    h2[5] = 109.0  # never reaches 110: wrong way (0.3 < half)
    assert kind_of(h2, lo, sp, 0, 2, 1, 100.0, 10.0)["kind"] == "1 wrong way"
    h3 = h2.copy()
    h3[1] = 106.0  # 0.6 of the target before the stop: fell short
    assert kind_of(h3, lo, sp, 0, 2, 1, 100.0, 10.0)["kind"] == "2 fell short"
    # the stop bar's own high (bar 2) is not counted as reaching the target afterwards
    h4 = h2.copy()
    h4[2] = 112.0
    assert kind_of(h4, lo, sp, 0, 2, 1, 100.0, 10.0)["kind"] == "1 wrong way"
