"""picture.py by hand: a timeframe's picture, the same-picture rule and the library built on it.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_picture.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from picture import FastPictureLibrary, PictureLibrary, features, same_tf  # noqa: E402

BOTH = pytest.mark.parametrize("Lib", [PictureLibrary, FastPictureLibrary])


def piv(pidx, pval, ptyp, pconf):
    return np.array(pidx), np.array(pval, float), np.array(ptyp), np.array(pconf)


def test_features_of_a_rising_window():
    c = 100.0 + np.arange(120.0)  # one bar a point, 100 .. 219
    h, lo, atr = c + 0.5, c - 0.5, np.full(120, 2.0)
    P = piv([10, 40, 60, 90], [109.5, 140.5, 159.5, 190.5], [-1, 1, -1, 1], [13, 43, 63, 93])
    f = features(h, lo, c, atr, P, 119)
    assert f["size"] == pytest.approx((219.5 - 99.5) / 2.0)  # 60 ATRs
    assert f["pos"] == pytest.approx((219 - 99.5) / 120.0) and f["edge"] == 1  # at the top
    assert (f["net_way"], f["struct"]) == (1, 1)  # up 59.5 ATRs; peaks 140.5 -> 190.5, troughs 109.5 -> 159.5
    assert (f["leg_way"], f["leg"]) == (1, pytest.approx((219 - 190.5) / 2.0))  # from the last swing (a peak) up
    # a swing not yet confirmed at bi is not used: at bar 92 the last known swing is the trough at 60
    f92 = features(h, lo, c, atr, P, 92)
    assert f92["leg"] == pytest.approx((192 - 159.5) / 2.0) and f92["struct"] == 9  # one peak known: too few to say


BASE = dict(size=10.0, pos=0.5, edge=0, leg_way=1, leg=2.0, net_way=1, struct=1)


def test_same_tf():
    assert same_tf(BASE, dict(BASE), 0.9) == []
    assert same_tf(BASE, dict(BASE), 0.69)[0].startswith("outline")
    assert same_tf(BASE, dict(BASE, size=14.0), 0.9) == []  # 1.4 times: still the same size
    assert same_tf(BASE, dict(BASE, size=14.5), 0.9)[0].startswith("size")
    assert same_tf(BASE, dict(BASE, leg_way=-1), 0.9)[0].startswith("last leg")
    assert same_tf(BASE, dict(BASE, leg=3.3), 0.9)[0].startswith("last leg")  # 1.65 times longer
    assert same_tf(dict(BASE, leg=0.05), dict(BASE, leg=0.08, leg_way=-1), 0.9) == []  # both flat: alike
    assert same_tf(BASE, dict(BASE, pos=0.75), 0.9)[0].startswith("position")
    assert same_tf(BASE, dict(BASE, edge=1), 0.9)[0].startswith("position")
    # the owner's rule: one going up, one going down, are never the same picture
    assert same_tf(BASE, dict(BASE, net_way=-1), 0.9)[0].startswith("the 120 bars' way")
    assert same_tf(BASE, dict(BASE, struct=-1), 0.9)[0].startswith("swing structure")


def lib_rows():
    codes = np.array([[0] * 10, [0] * 9 + [1], [0] * 10, [0] * 10])
    shp = np.linspace(-1, 1, 40)
    shp = (shp - shp.mean()) / shp.std() / np.sqrt(40)
    shapes = np.stack([np.stack([shp])] * 4)
    feats = [[dict(BASE)], [dict(BASE)], [dict(BASE, net_way=-1)], [dict(BASE)]]
    return codes, shapes, feats


@BOTH
def test_the_library_counts_only_the_same_picture(Lib):
    codes, shapes, feats = lib_rows()
    L = Lib(codes, shapes, feats)
    assert L.add(0, 1, "ran_up") == (0, True)
    assert L.add(1, 2, "ran_up") == (0, False)  # 9 of 10 codes, the same picture: a repeat
    assert L.add(2, 3, "ran_dn") == (1, True)  # the same codes, but the 120 bars went down: a new pattern
    assert L.patterns[0].occ_days == [1, 2] and L.patterns[1].first == 2
    assert L.best(3, before_day=1) == -1  # nothing earlier than day 1
    assert L.best(3, before_day=3) == 0  # pattern 1 was born on day 3: not yet evidence


@BOTH
def test_a_tie_goes_to_the_earliest_pattern(Lib):
    codes = np.array([[0, 0, 0, 0, 0], [0, 0, 0, 0, 1], [1, 0, 0, 0, 0], [0, 0, 0, 0, 0]])
    shp = np.linspace(-1, 1, 40)
    shp = (shp - shp.mean()) / shp.std() / np.sqrt(40)
    shapes = np.stack([np.stack([shp])] * 4)
    L = Lib(codes, shapes, [[dict(BASE)]] * 4)
    L.add(1, 1, "ran_up")  # pattern 0: 0 0 0 0 1
    L.add(2, 1, "ran_up")  # 3 of 5 equal to pattern 0 (0.6): pattern 1: 1 0 0 0 0
    assert L.best(3) == 0  # row 3 (0 0 0 0 0) is 4 of 5 equal to both: the earliest


def test_the_fast_library_gives_the_same_answers():
    from picture import FastPictureLibrary  # noqa: PLC0415

    rng = np.random.default_rng(7)
    n = 160
    near = rng.random(n) < 0.7  # most rows near one picture (repeats), the rest anything (rejections)
    codes = np.where(near[:, None], (rng.random((n, 6)) < 0.08).astype(int), rng.integers(0, 2, size=(n, 6)))
    base = np.linspace(-1, 1, 40)
    shapes = []
    for i in range(n):
        noise = 0.25 if near[i] else 1.5
        sh = np.stack([base * (1 if near[i] else rng.choice([-1, 1])) + rng.normal(0, noise, 40) for _ in range(2)])
        sh = (sh - sh.mean(axis=1, keepdims=True)) / sh.std(axis=1, keepdims=True) / np.sqrt(40)
        shapes.append(sh)
    shapes = np.stack(shapes)

    def one(i):
        if near[i]:
            return dict(size=float(rng.choice([10.0, 12.0])), pos=float(rng.choice([0.45, 0.55])), edge=0, leg_way=1,
                        leg=float(rng.choice([2.0, 2.5])), net_way=1, struct=int(rng.choice([1, 1, 1, 0])))
        pos = float(rng.choice([0.3, 0.45, 0.97]))
        return dict(size=float(rng.choice([8.0, 10.0, 15.0])), pos=pos, edge=1 if pos >= 0.95 else 0,
                    leg_way=int(rng.choice([-1, 1])), leg=float(rng.choice([0.05, 2.0, 4.0])),
                    net_way=int(rng.choice([-1, 1])), struct=int(rng.choice([-1, 0, 1])))

    feats = [[one(i) for _ in range(2)] for i in range(n)]
    slow, fast = PictureLibrary(codes, shapes, feats), FastPictureLibrary(codes, shapes, feats)
    days = np.repeat(np.arange(40), 4)
    for r in range(n):
        assert slow.best(r, int(days[r])) == fast.best(r, int(days[r]))
        assert slow.add(r, int(days[r]), "ran_up") == fast.add(r, int(days[r]), "ran_up")
    assert len(slow.patterns) > 10 and any(len(p.occ_days) > 1 for p in slow.patterns)  # the test exercised both paths


@BOTH
def test_an_opposite_outline_is_another_picture(Lib):
    shp = np.linspace(-1, 1, 40)
    shp = (shp - shp.mean()) / shp.std() / np.sqrt(40)
    codes = np.zeros((2, 4), int)
    shapes = np.stack([np.stack([shp]), np.stack([-shp])])
    L = Lib(codes, shapes, [[dict(BASE)], [dict(BASE)]])
    L.add(0, 1, "ran_up")
    assert L.add(1, 2, "ran_dn") == (1, True)  # the same codes and figures, the path the other way: new

