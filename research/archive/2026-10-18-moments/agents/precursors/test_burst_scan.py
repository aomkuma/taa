"""burst_scan.bursts by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_burst_scan.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from burst_scan import bursts  # noqa: E402


def test_a_clean_run_up_and_its_first_minute():
    # opens 100, 101, 102 ...; bar 0: highs reach 110.5 at bar 3 (within 5) with lows never 3 below 100 -> a burst up
    o = np.array([100.0, 101, 102, 104, 108, 110, 109, 108, 108, 108])
    h = o + 1.0
    h[3] = 110.5
    lo = o - 0.5
    B = bursts(o, h, lo, n=5, x=10.0, q=3.0)
    assert B.i.tolist() == [0] and B.side.tolist() == [1]  # bar 1 also reaches +10 (bar 5's high 111): the same burst


def test_against_first_is_not_clean_and_a_fall_counts_down():
    o = np.array([100.0, 99, 96.5, 95, 91, 89, 89, 89])
    h = o + 0.5
    lo = o - 0.5
    lo[4] = 89.5
    # bar 0: down 10 at bar 4 (89.5 <= 90), up 3 never -> a burst down; bar 1 (open 99): 89.5 > 89 - no
    B = bursts(o, h, lo, n=5, x=10.0, q=3.0)
    assert B.i.tolist() == [0] and B.side.tolist() == [-1]
    h2 = h.copy()
    h2[1] = 103.5  # 3.5 against first (bar 1) -> not clean
    assert bursts(o, h2, lo, n=5, x=10.0, q=3.0).empty


def test_consecutive_starts_are_one_burst():
    o = np.array([100.0, 100.5, 101, 112, 113, 113, 113])
    h = o + 0.2
    lo = o - 0.2
    # bars 0, 1, 2 each reach +10 at bar 3 cleanly: one burst, at bar 0
    B = bursts(o, h, lo, n=5, x=10.0, q=3.0)
    assert B.i.tolist() == [0]


def test_one_bar_reaching_both_is_not_clean():
    o = np.array([100.0, 100.0, 100.0])
    h = np.array([100.5, 110.5, 100.5])
    lo = np.array([99.5, 96.5, 99.5])  # bar 1 reaches +10.5 and -3.5: which came first is unknown
    assert bursts(o, h, lo, n=3, x=10.0, q=3.0).empty
