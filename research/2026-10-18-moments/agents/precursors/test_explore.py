"""explore.py by hand: the first pierce of each swing level, the double bottoms / tops and their entries, the excursions;
the pierces equal a second count written apart on random markets.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_explore.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explore import doubles, excursions, pierces  # noqa: E402


def piv(swings):
    return tuple(np.array([s[j] for s in swings]) for j in range(4))


def test_pierces_by_hand():
    n = 14
    h, lo, c, atr = np.full(n, 105.0), np.full(n, 103.0), np.full(n, 104.0), np.full(n, 2.0)
    sw = [(2, 110.0, 1, 4), (6, 100.0, -1, 8)]  # a top 110 (known from bar 4), a bottom 100 (known from bar 8)
    h[9], h[10], c[10] = 109.0, 111.0, 108.0  # bar 10 goes 1 above the top and closes 2 back inside
    lo[11], c[11] = 99.5, 101.0  # bar 11 goes 0.5 below the bottom and closes 1 back above it
    h[12] = 112.0  # a second pierce of the top: not counted
    E = pierces(h, lo, c, atr, piv(sw))
    assert E.i.tolist() == [10, 11] and E.side.tolist() == [-1, 1]
    assert E.depth.tolist() == [0.5, 0.25] and E.back.tolist() == [1.0, 0.5] and E.closed_back.tolist() == [True, True]
    assert E.age.tolist() == [8, 5]
    # a newer top (109.5, bar 9, known from bar 10) ends the old one's watch: bar 10 is its own confirmation bar, so the
    # first pierce of the new top is bar 12 (112 > 109.5); the old top 110 is never pierced while it is the latest
    sw2 = sw + [(9, 109.5, 1, 10)]
    E = pierces(h, lo, c, atr, piv(sw2))
    assert sorted(zip(E.i, E.level)) == [(11, 100.0), (12, 109.5)]


def test_pierces_equal_a_second_count():
    from fingerprint import zigzag  # noqa: PLC0415

    for seed in range(3):
        rng = np.random.default_rng(seed)
        c = 100 + np.cumsum(rng.normal(size=2000))
        h, lo = c + rng.random(2000), c - rng.random(2000)
        atr = np.full(2000, 1.0)
        p = zigzag(h, lo, atr, 3.0)
        E = pierces(h, lo, c, atr, p)
        want = []
        pidx, pval, ptyp, pconf = p
        for k in range(len(pidx)):
            same = np.nonzero(ptyp[k + 1:] == ptyp[k])[0]
            end = pconf[k + 1 + same[0]] if len(same) else len(c)
            seg = (h if ptyp[k] == 1 else -lo)[pconf[k] + 1:end]
            hit = np.nonzero(seg > (pval[k] if ptyp[k] == 1 else -pval[k]))[0]
            if len(hit):
                want.append(int(pconf[k] + 1 + hit[0]))
        assert len(E) > 10 and E.i.tolist() == want


def test_doubles_by_hand():
    c, atr = np.full(16, 105.0), np.full(16, 2.0)
    c[9], c[10], c[11], c[12] = 103.0, 106.0, 109.0, 111.0
    sw = [(2, 100.0, -1, 4), (5, 110.0, 1, 7), (8, 101.0, -1, 10)]  # a W: bottoms 100 and 101, the neckline 110
    D = doubles(c, atr, piv(sw))
    w = D[D.kind == "W"].iloc[0]
    assert (w.side, w.second_atr, w.second_share, w.gap, w.height_atr, w.turn, w.neck) == (1, 0.5, 0.1, 6, 5.0, 10, 12)
    c2 = c.copy()
    c2[9] = 111.0  # above the neckline before C was known: no fresh neckline entry
    assert doubles(c2, atr, piv(sw)).neck.iloc[0] == -1
    m = doubles(c, atr, piv([(2, 110.0, 1, 4), (5, 100.0, -1, 7), (8, 109.0, 1, 10)])).iloc[0]  # an M, the second top lower
    assert (m.kind, m.side, m.second_atr, m.second_share, m.height_atr) == ("M", -1, 0.5, 0.1, 5.0)


def test_excursions_by_hand():
    o = np.array([100.0, 101.0, 99.0, 102.0])
    h = np.array([101.0, 104.0, 100.0, 103.0])
    lo = np.array([99.0, 100.0, 97.0, 101.0])
    fav, adv = excursions(o, h, lo, np.array([0, 0]), np.array([1, -1]), 3)
    assert (fav[0], adv[0]) == (4.0, 3.0) and (fav[1], adv[1]) == (3.0, 4.0)  # bars 0-2: high 104, low 97
    fav, adv = excursions(o, h, lo, np.array([9]), np.array([1]), 3)
    assert math.isnan(fav[0])
