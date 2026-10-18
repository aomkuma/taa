"""r_lean.py by hand: each matching day's first result, the side picked, and the independent recount on a tiny table.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_r_lean.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r_lean import day_means, pick, recount  # noqa: E402


def test_day_means_takes_each_days_first():
    # day 3 twice (its first: buy +1.0, sell -1.2), day 4 (buy -0.5, sell +0.4)
    n, mb, ms = day_means(np.array([3, 3, 4]), np.array([1.0, 9.0, -0.5]), np.array([-1.2, 9.0, 0.4]))
    assert n == 2 and math.isclose(mb, 0.25) and math.isclose(ms, -0.4)
    n, mb, ms = day_means(np.array([], int), np.array([]), np.array([]))
    assert n == 0 and math.isnan(mb) and math.isnan(ms)


def test_pick_by_hand():
    assert pick(5, 0.12, -0.3, 5, 0.1) == 1  # the buy, over the threshold, enough days
    assert pick(5, 0.1, -0.3, 5, 0.1) == 1  # the buy exactly at the threshold
    assert pick(5, -0.3, 0.1, 5, 0.1) == -1  # the sell exactly at the threshold
    assert pick(5, 0.05, -0.3, 5, 0.1) == 0  # the better side under the threshold
    assert pick(4, 0.9, -0.3, 5, 0.1) == 0  # too few days
    assert pick(9, 0.2, 0.2, 5, 0.1) == 1  # a tie: the buy
    assert pick(9, float("nan"), 0.2, 5, 0.1) == 0


def test_recount_by_hand():
    # four snaps on M5 / M1; row 3 (day 20) is evaluated: rows 0 (day 1) and 1 (day 1) the same L3 situation, row 2
    # (day 15, within 7 days) the same but too recent; row 1 has another 120-bar way (L3 yes, L6 no)
    base = dict(er=0.3, retr=0.5, brk=1, net_way=1, size=5.0, pos=0.8, edge=0, struct=1)
    rows = [base, dict(base, net_way=-1), base, base]
    T = pd.DataFrame({f"{tf}_{k}": [r[k] for r in rows] for tf in ("M5", "M1") for k in base})
    day = np.array([1, 1, 15, 20])
    rb, rs = np.array([1.0, -1.0, 2.0, 0.0]), np.array([-1.0, 0.5, -2.0, 0.0])
    ok_c = np.ones(4, bool)
    assert recount(T, ok_c, day, rb, rs, 3, ("M5", "M1"), "L3") == (1, 1.0, -1.0)  # day 1's first: row 0
    assert recount(T, ok_c, day, rb, rs, 3, ("M5", "M1"), "L6") == (1, 1.0, -1.0)
    ok_c[0] = False  # row 0 without a result: day 1's first is now row 1 (L3), nothing for L6
    assert recount(T, ok_c, day, rb, rs, 3, ("M5", "M1"), "L3") == (1, -1.0, 0.5)
    n, mb, ms = recount(T, ok_c, day, rb, rs, 3, ("M5", "M1"), "L6")
    assert n == 0 and math.isnan(mb)
