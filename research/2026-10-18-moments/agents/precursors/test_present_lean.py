"""present_lean.py by hand: each day's mean, the side picked, the tolerances equal to the library's rule, and the
bot's evidence equal to my plain recount on a small table worked by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_present_lean.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from picture import KEYS, as_arrays  # noqa: E402
from present_lean import day_means, evidence, pick, recount, tolerance_mask  # noqa: E402
from rarity import part_masks, thirds  # noqa: E402
from test_rarity import random_library  # noqa: E402


def test_day_means_by_hand():
    # day 3: two moments (buy +1.0 and +3.0 -> 2.0; sell -1.0 and -3.0 -> -2.0); day 4: buy -0.5, sell +0.5
    n, b, s = day_means(np.array([3, 3, 4]), np.array([1.0, 3.0, -0.5]), np.array([-1.0, -3.0, 0.5]))
    assert n == 2 and math.isclose(b, 0.75) and math.isclose(s, -0.75)
    n, b, s = day_means(np.array([], int), np.array([]), np.array([]))
    assert n == 0 and math.isnan(b)


def test_pick_by_hand():
    assert pick(5, 0.1, -0.3, 5, 0.1) == 1 and pick(5, -0.3, 0.1, 5, 0.1) == -1
    assert pick(5, 0.05, -0.3, 5, 0.1) == 0 and pick(4, 0.9, -0.3, 5, 0.1) == 0 and pick(9, 0.2, 0.2, 5, 0.1) == 1


def test_tolerances_equal_the_library_rule():
    feats, shapes = random_library(300, 8)
    A = as_arrays(feats)
    P = {f"{tf}_{k}": A[k][:, j] for j, tf in enumerate(("X", "Y")) for k in KEYS}
    cand = np.arange(300)
    for row in range(0, 300, 13):
        m = part_masks(A, shapes, thirds(shapes), row, cand)
        pos_tol = np.abs(A["pos"][cand] - A["pos"][row]) <= 0.2 + 1e-6
        # the library's position rule = the tolerance on the position AND the same edge (an equal reading, a key)
        assert np.array_equal(m["position"], pos_tol & (A["edge"][cand] == A["edge"][row]))
        for parts in (("smoothness", "pullback"), ("smoothness", "pullback", "size", "position")):
            want = np.logical_and.reduce([m[p].all(axis=1) for p in parts if p != "position"])
            if "position" in parts:
                want &= pos_tol.all(axis=1)
            assert np.array_equal(tolerance_mask(P, row, cand, ("X", "Y"), parts), want), (row, parts)


def table() -> tuple[pd.DataFrame, np.ndarray]:
    """Eight moments on two timeframes; row 7 (day 30) is evaluated. Rows 0-1 (day 1), 3 (day 10), 4 (day 12) and 5
    (day 23 - exactly 7 days before) are its L3 situation; row 1 has another 120-bar way and row 4 another edge (L3
    only); row 2 (day 5) closes between instead of above (neither); row 6 (day 25) is the same in every part but
    within 7 days."""
    base = dict(er=0.3, retr=0.5, brk=1, net_way=1, size=5.0, pos=0.8, edge=0, struct=1)
    rows = [base, dict(base, net_way=-1), dict(base, brk=0), dict(base, er=0.35), dict(base, edge=1), base, base, base]
    P = pd.DataFrame({f"{tf}_{k}": [r[k] for r in rows] for tf in ("M5", "M1") for k in base})
    P["buy_R"] = [1.0, -1.0, 2.0, 0.4, 0.9, -0.2, 3.0, 0.0]
    P["sell_R"] = [-1.0, 0.6, -2.0, -0.5, -0.9, 0.1, -3.0, 0.0]
    return P, np.array([1, 1, 5, 10, 12, 23, 25, 30])


L3 = ("smoothness", "pullback", "last top/bottom")
L6 = ("smoothness", "pullback", "last top/bottom", "120 bars' way", "size", "position")


def both(P, day, ok, level):
    got = evidence(P, day, ok, np.array([7]), ("M5", "M1"), L3 if level == "L3" else L6)[0]
    mine = recount(P, day, ok, 7, ("M5", "M1"), level)
    return got, mine


def test_evidence_and_recount_by_hand():
    P, day = table()
    ok = np.ones(8, bool)
    # L3: day 1 (rows 0, 1: buy 0.0, sell -0.2), day 10 (0.4, -0.5), day 12 (0.9, -0.9), day 23 (-0.2, 0.1)
    for got in both(P, day, ok, "L3"):
        assert got[0] == 4 and math.isclose(got[1], 0.275) and math.isclose(got[2], -0.375)
    # L6: rows 1 (its way) and 4 (its edge) drop: day 1 (1.0, -1.0), day 10 (0.4, -0.5), day 23 (-0.2, 0.1)
    for got in both(P, day, ok, "L6"):
        assert got[0] == 3 and math.isclose(got[1], 0.4) and math.isclose(got[2], -1.4 / 3)
    ok[0] = False  # row 0 without a result: day 1 is row 1 alone (-1.0, 0.6)
    for got in both(P, day, ok, "L3"):
        assert got[0] == 4 and math.isclose(got[1], 0.025) and math.isclose(got[2], -0.175)
