"""touch.touches by hand, and a second count on random markets.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_touch.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from touch import touches  # noqa: E402

# a larger timeframe of 6 bars completing at 10 .. 60; a top 110 at its bar 1, known at bar 2 (from 30 on); ATR 2,
# so the touch band is 109.5 .. 110
Y = dict(avail=np.array([10, 20, 30, 40, 50, 60]), atr=np.full(6, 2.0),
         piv=(np.array([1]), np.array([110.0]), np.array([1]), np.array([2])))


def m5(highs, start=31):
    h = np.array(highs, float)
    return h, h - 1.0, np.arange(start, start + len(h))


def test_touch_by_hand():
    h, lo, av = m5([108.0, 109.2, 109.6, 112.0])  # bar 2 (109.6) is the first inside the band, not beyond the top
    E = touches(h, lo, av, Y)
    assert E.i.tolist() == [2] and E.side.tolist() == [-1] and np.isclose(E.gap.iloc[0], 0.2) and E.age.tolist() == [1]  # the larger bar closed by 33 is bar 2: 1 bar after the top


def test_a_pierce_first_ends_the_watch():
    h, lo, av = m5([108.0, 110.5, 109.8])  # bar 1 goes beyond the top: no touch, even if bar 2 is in the band
    assert touches(h, lo, av, Y).empty


def test_only_after_the_swing_is_known_and_inside_its_window():
    h, lo, av = m5([109.8, 108.0], start=29)  # bar 0 completes at 29: before the top is known (30) - not a touch
    assert touches(h, lo, av, Y).empty
    h, lo, av = m5([108.0, 108.0, 109.8])  # completing at 31, 32, 33: with a window of 2 larger bars (bars 1-2, to 30)
    assert touches(h, lo, av, Y, win=2).empty  # the top is out of its window before bar 2
    assert touches(h, lo, av, Y, win=6).i.tolist() == [2]


def test_bottoms_mirror():
    Yb = dict(Y, piv=(np.array([1]), np.array([100.0]), np.array([-1]), np.array([2])))
    lo = np.array([102.0, 100.4, 99.0])
    E = touches(lo + 1.0, lo, np.arange(31, 34), Yb)
    assert E.i.tolist() == [1] and E.side.tolist() == [1] and np.isclose(E.gap.iloc[0], 0.2)


def test_a_second_count_on_random_markets():
    from fingerprint import zigzag  # noqa: PLC0415

    rng = np.random.default_rng(4)
    c = 100 + np.cumsum(rng.normal(size=6000))
    h, lo = c + rng.random(6000), c - rng.random(6000)
    av = np.arange(1, 6001)
    yh, ylo = h.reshape(-1, 12).max(axis=1), lo.reshape(-1, 12).min(axis=1)  # a larger timeframe of 12 small bars
    yav = av[11::12]
    yatr = np.full(len(yh), 3.0)
    piv = zigzag(yh, ylo, yatr, 3.0)
    Yr = dict(avail=yav, atr=yatr, piv=piv)
    E = touches(h, lo, av, Yr)
    want = []
    for k in range(len(piv[0])):
        lvl, typ = piv[1][k], piv[2][k]
        s0 = int(yav[piv[3][k]])  # small bars completing after the swing is known: av > yav[conf]
        s1 = int(yav[min(piv[0][k] + 119, len(yav) - 1)])
        seg_h, seg_l = h[s0:s1], lo[s0:s1]
        beyond = (seg_h > lvl) if typ == 1 else (seg_l < lvl)
        near = (seg_h >= lvl - 0.75) if typ == 1 else (seg_l <= lvl + 0.75)
        first_b = np.argmax(beyond) if beyond.any() else len(seg_h)
        first_n = np.argmax(near & ~beyond) if (near & ~beyond).any() else len(seg_h)
        if first_n < first_b:
            want.append(s0 + int(first_n))
    assert len(E) > 20 and sorted(E.i.tolist()) == sorted(want)
