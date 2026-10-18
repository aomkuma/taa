"""rarity_lean.py by hand: one outcome per matching day and the lean; the score against no effect.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_rarity_lean.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rarity_lean import day_lean, score  # noqa: E402


def test_day_lean_takes_each_days_first_match():
    # day 5 twice (its first: ran_up), day 6 slow_dn, day 9 fake_up: up 1/3, down 1/3
    n, lean = day_lean(np.array([5, 5, 6, 9]), np.array(["ran_up", "ran_dn", "slow_dn", "fake_up"]))
    assert (n, lean) == (3, 0.0)
    assert day_lean(np.array([1, 2]), np.array(["ran_up", "slow_up"])) == (2, 1.0)
    n, lean = day_lean(np.array([], int), np.array([], str))
    assert n == 0 and math.isnan(lean)


def test_score_by_hand():
    # leans up, up, down, down, up; what followed: a run up, a run down, a run down, nothing, a slow run up (not a 10 U
    # run within 30 minutes: neither way); the half's rates 0.2 / 0.1
    s = score(np.array([1, 1, -1, -1, 1]), np.array(["ran_up", "ran_dn", "ran_dn", "flat", "slow_up"]), 0.2, 0.1)
    assert s["n"] == 5 and math.isclose(s["way"], 0.4) and math.isclose(s["other"], 0.2)
    # per prediction (way - other) - (base way - base other): 0.9, -1.1, 1.1, 0.1, -0.1
    assert math.isclose(s["edge"], 0.18)
    assert math.isclose(s["se"], math.sqrt(3.088 / 4) / math.sqrt(5))
    assert score(np.array([]), np.array([], str), 0.2, 0.1)["n"] == 0
