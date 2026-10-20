"""RELAY to the first developer (dev/patterns.py, read only here): the owner's rule "one bar's high and low are never
two turns" fails in the ZigZag's start-up. The same hand case as audit2/test_swings.py; precursors/fingerprint.py has
the fix (the first pivot waits while one bar holds both the highest high and the lowest low).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/audit2/test_relay_dev_zigzag.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dev"))
import patterns as P  # noqa: E402


def test_one_wide_bar_at_the_start_is_never_two_turns() -> None:
    # ATR 5, k 2 -> threshold 10. Bar 1 (30 / 0) holds both extremes; bars 2-3 stay inside it.
    # Now: a peak at bar 1 confirmed BY bar 1, then a trough at bar 1 confirmed by bar 2.
    b, _, _, c = P.zigzag(np.array([10.0, 30, 25, 26]), np.array([9.0, 0, 20, 25]), np.full(4, 5.0), 2.0)
    assert b.tolist() == [] and c.tolist() == []


def test_every_pivot_is_confirmed_by_a_later_bar() -> None:
    rng = np.random.default_rng(0)
    n = 400
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    span = np.where(np.arange(n) == 14, 15.0, rng.random(n))  # the first bar after the warm-up is wide
    atr = np.r_[np.full(14, np.nan), np.full(n - 14, 1.5)]
    b, _, _, conf = P.zigzag(c + span, c - span, atr, 3.0)
    assert (conf > b).all() and len(np.unique(b)) == len(b)
