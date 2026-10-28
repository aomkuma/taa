"""mw.py by hand: W / M signals from made-up swings, the two detectors equal on random markets, the first passage.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_mw.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mw import detect, detect_apart, first_passage  # noqa: E402


def piv(swings):
    return tuple(np.array([s[j] for s in swings]) for j in range(4))


def closes(**at):
    c = np.full(16, 105.0)
    for k, v in at.items():
        c[int(k[1:])] = v
    return c


W3 = [(2, 100.0, -1, 4), (5, 110.0, 1, 7), (8, 101.0, -1, 10)]  # A trough 100, B peak 110 (the neckline), C trough 101


def test_w_by_hand():
    c = closes(c9=103.0, c10=106.0, c11=109.0, c12=111.0, c13=112.0)
    for f in (detect, detect_apart):
        E = f(c, piv(W3))
        assert E.i.tolist() == [12] and E.kind.tolist() == ["W"] and E.side.tolist() == [1]  # once, at the first close above
        assert (E.a.iloc[0], E.b.iloc[0], E.c.iloc[0], E.height.iloc[0]) == (100.0, 110.0, 101.0, 10.0)


def test_w_tolerance_edge():
    c = closes(c12=111.0)
    ok = [W3[0], W3[1], (8, 102.5, -1, 10)]  # |C - A| = 2.5 = 0.25 x 10: alike
    no = [W3[0], W3[1], (8, 102.6, -1, 10)]  # 2.6: not
    for f in (detect, detect_apart):
        assert f(c, piv(ok)).i.tolist() == [12]
        assert f(c, piv(no)).empty


def test_w_not_fresh_and_voided():
    for f in (detect, detect_apart):
        assert f(closes(c9=111.0, c12=111.0), piv(W3)).empty  # closed above B before C was confirmed: not fresh
        # a newer peak confirmed at bar 12 - the latest three are B, C, D, an M not broken down: no W
        newer = W3 + [(11, 109.0, 1, 12)]
        assert f(closes(c12=111.0), piv(newer)).empty


def test_m_by_hand():
    m3 = [(2, 110.0, 1, 4), (5, 100.0, -1, 7), (8, 109.0, 1, 10)]  # peaks 110 and 109, the trough 100 between
    c = closes(c10=104.0, c11=101.0, c12=99.0, c13=98.0)
    for f in (detect, detect_apart):
        E = f(c, piv(m3))
        assert E.i.tolist() == [12] and E.kind.tolist() == ["M"] and E.side.tolist() == [-1] and E.height.iloc[0] == 10.0


def test_both_detectors_equal_on_random_markets():
    from fingerprint import zigzag  # noqa: PLC0415

    for seed in range(5):
        rng = np.random.default_rng(seed)
        c = 100 + np.cumsum(rng.normal(size=3000))
        h, lo = c + rng.random(3000), c - rng.random(3000)
        atr = np.full(3000, 1.0)
        p = zigzag(h, lo, atr, 3.0)
        a, b = detect(c, p), detect_apart(c, p).sort_values("i").reset_index(drop=True)
        assert len(a) > 5 and a.equals(b)


def test_first_passage_by_hand():
    o = np.array([100.0, 101.0, 102.0, 103.0])
    assert first_passage(o, np.array([102.0, 106.0, 0, 0]), np.array([99.0, 101.0, 0, 0]), 0, 1, 5.0, 4) == "win"
    assert first_passage(o, np.array([102.0, 104.0, 0, 0]), np.array([99.0, 94.0, 0, 0]), 0, 1, 5.0, 4) == "loss"
    assert first_passage(o, np.array([102.0, 106.0, 0, 0]), np.array([99.0, 94.0, 0, 0]), 0, 1, 5.0, 4) == "loss"  # both: loss
    assert first_passage(o, np.array([102.0, 104.0]), np.array([99.0, 96.0]), 0, 1, 5.0, 2) == "none"
    # a sell from 100: the low reaches 95 on bar 1 (the high only 104), then bar 2 would reach the stop 105
    assert first_passage(o, np.array([102.0, 104.0, 106.0, 100.0]), np.array([99.0, 94.5, 100.0, 99.0]), 0, -1, 5.0, 4) == "win"
