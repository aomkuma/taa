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
    # a swing not yet confirmed at bi is not used for the last leg: at bar 92 the last known swing is the trough at 60
    f92 = features(h, lo, c, atr, P, 92)
    assert f92["leg"] == pytest.approx((192 - 159.5) / 2.0)
    # but the swing still forming counts in the structure (owner, 2026-10-19): one peak confirmed (140.5) and the high
    # since the trough at 60 (192.5) -> a higher top; troughs 109.5 -> 159.5 -> up
    assert f92["struct"] == 1
    # the close against the last confirmed top (140.5 at bar 40) and bottom (159.5 at bar 60): 192 is above the top
    assert f92["brk"] == 1
    # a straight rise: no pullback at all (each bar's low is half a point under the running high: 0.25 ATR), smooth
    assert f["retr"] == pytest.approx(0.5) and f["er"] == pytest.approx(1.0)


def test_the_path_character_tells_a_steady_rise_from_a_v():
    steady = 100.0 + np.arange(120.0)
    v = np.r_[100.0 + np.arange(40.0), 139.0 - 2 * np.arange(1, 41.0), 59.0 + 4 * np.arange(1, 41.0)]  # up, down, up
    atr = np.full(120, 2.0)
    none = (np.array([], int), np.array([], float), np.array([], int), np.array([], int))
    fs = features(steady + 0.5, steady - 0.5, steady, atr, none, 119)
    fv = features(v + 0.5, v - 0.5, v, atr, none, 119)
    assert fs["net_way"] == fv["net_way"] == 1
    assert fv["retr"] == pytest.approx((139.5 - 58.5) / 2.0)  # the fall from 139.5 to 58.5: 40.5 ATR
    assert fv["er"] == pytest.approx((219 - 100) / (39 + 80 + 160))  # 119 net over a 279 path
    assert same_tf(fs, fv, UP, UP)  # never the same picture
    assert (fs["seg0"], fs["seg1"], fs["seg2"]) == (1, 1, 1) and (fv["seg0"], fv["seg1"], fv["seg2"]) == (1, -1, 1)
    assert fs["brk"] == fv["brk"] == 9  # no swings: unknown


BASE = dict(size=10.0, pos=0.5, edge=0, leg_way=1, leg=2.0, net_way=1, struct=1, brk=0, retr=3.0, er=0.3,
            seg0=1, seg1=1, seg2=1)


def unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    x = x - x.mean()
    return x / np.sqrt((x * x).sum())


UP = unit(np.arange(40.0))  # a straight rise
SAW = unit(np.r_[np.arange(13.0), np.arange(14.0), np.arange(13.0)])  # each third rises, then falls back: a saw
FIRST_FALLS = unit(np.r_[12.0 - np.arange(13.0), 13 + np.arange(14.0), 27 + np.arange(13.0)])  # the first third falls


def has(why: list[str], prefix: str) -> bool:
    return any(w.startswith(prefix) for w in why)


def test_same_tf():
    assert same_tf(BASE, dict(BASE), UP, UP) == []
    assert has(same_tf(BASE, dict(BASE), UP, SAW), "outline")  # every third rises alike, the whole is a saw
    assert not has(same_tf(BASE, dict(BASE), UP, SAW), "third")
    assert same_tf(BASE, dict(BASE, size=14.0), UP, UP) == []  # 1.4 times: still the same size
    assert has(same_tf(BASE, dict(BASE, size=14.5), UP, UP), "size")
    assert has(same_tf(BASE, dict(BASE, leg_way=-1), UP, UP), "last leg")
    assert has(same_tf(BASE, dict(BASE, leg=3.3), UP, UP), "last leg")  # 1.65 times longer
    assert same_tf(dict(BASE, leg=0.05), dict(BASE, leg=0.08, leg_way=-1), UP, UP) == []  # both flat: alike
    assert has(same_tf(BASE, dict(BASE, pos=0.75), UP, UP), "position")
    assert has(same_tf(BASE, dict(BASE, edge=1), UP, UP), "position")
    # the owner's rule: one going up, one going down, are never the same picture
    assert has(same_tf(BASE, dict(BASE, net_way=-1), UP, UP), "the 120 bars' way")
    assert has(same_tf(BASE, dict(BASE, struct=-1), UP, UP), "swing structure")
    # the owner's picture 2: one still under its last top, the other already above it
    assert has(same_tf(BASE, dict(BASE, brk=1), UP, UP), "against the last top")
    assert same_tf(BASE, dict(BASE, retr=4.8), UP, UP) == []  # 1.6 times: alike
    assert has(same_tf(BASE, dict(BASE, retr=5.0), UP, UP), "deepest pullback")
    assert same_tf(dict(BASE, retr=0.4), dict(BASE, retr=0.9), UP, UP) == []  # both under 1 ATR: alike
    assert has(same_tf(BASE, dict(BASE, er=0.41), UP, UP), "smoothness")
    # the owner (2026-10-19): each third must look alike - the first part of one rose, of the other it was flat / fell
    assert has(same_tf(BASE, dict(BASE, seg0=0), UP, UP), "third 1's way")
    why = same_tf(BASE, dict(BASE), UP, FIRST_FALLS)
    assert has(why, "third 1's outline") and not has(why, "third 2") and not has(why, "third 3")


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
    assert L.add(1, 9, "ran_up") == (0, False)  # 9 of 10 codes, the same picture, another episode: a repeat
    assert L.add(2, 20, "ran_dn") == (1, True)  # the same codes, but the 120 bars went down: a new pattern
    assert L.patterns[0].occ_days == [1, 9] and L.patterns[1].first == 2
    assert L.best(3, before_day=1) == -1  # nothing earlier than day 1
    assert L.best(3, before_day=20) == 0  # pattern 1 was born on day 20: not yet evidence


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
        noise = 0.08 if near[i] else 1.5
        sh = np.stack([base * (1 if near[i] else rng.choice([-1, 1])) + rng.normal(0, noise, 40) for _ in range(2)])
        sh = (sh - sh.mean(axis=1, keepdims=True)) / sh.std(axis=1, keepdims=True) / np.sqrt(40)
        shapes.append(sh)
    shapes = np.stack(shapes)

    def one(i):
        if near[i]:
            # near: inside every tolerance of each other, but for one third that sometimes goes flat (a rejection)
            return dict(size=float(rng.choice([10.0, 12.0])), pos=float(rng.choice([0.45, 0.55])), edge=0, leg_way=1,
                        leg=float(rng.choice([2.0, 2.5])), net_way=1, struct=1, brk=0, retr=float(rng.choice([3.0, 4.0])),
                        er=float(rng.choice([0.3, 0.35])), seg0=1, seg1=int(rng.choice([1, 1, 1, 0])), seg2=1)
        pos = float(rng.choice([0.3, 0.45, 0.97]))
        return dict(size=float(rng.choice([8.0, 10.0, 15.0])), pos=pos, edge=1 if pos >= 0.95 else 0,
                    leg_way=int(rng.choice([-1, 1])), leg=float(rng.choice([0.05, 2.0, 4.0])),
                    net_way=int(rng.choice([-1, 1])), struct=int(rng.choice([-1, 0, 1])), brk=int(rng.choice([-1, 0, 1])),
                    retr=float(rng.choice([0.5, 3.0, 9.0])), er=float(rng.choice([0.1, 0.3, 0.6])),
                    seg0=int(rng.choice([-1, 0, 1])), seg1=int(rng.choice([-1, 0, 1])), seg2=int(rng.choice([-1, 0, 1])))

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


@BOTH
def test_the_same_episode_counts_once(Lib):
    codes, shapes, feats = lib_rows()
    L = Lib(codes[[0, 1, 1, 1]], shapes[[0, 1, 1, 1]], [feats[0], feats[1], feats[1], feats[1]])
    L.add(0, 1, "ran_up")
    L.add(1, 3, "ran_dn")  # two days later: the same episode
    L.add(2, 8, "ran_dn")  # seven days after day 1: a new episode
    L.add(3, 10, "ran_up")  # two days after day 8: the same episode again
    assert L.patterns[0].occ_days == [1, 8] and L.patterns[0].occ_outcomes == ["ran_up", "ran_dn"]



@BOTH
def test_a_third_drawn_otherwise_is_another_picture(Lib):
    codes = np.zeros((2, 4), int)
    shapes = np.stack([np.stack([UP]), np.stack([FIRST_FALLS])])  # the first third falls in one, rises in the other
    L = Lib(codes, shapes, [[dict(BASE)], [dict(BASE)]])  # every figure equal, the thirds' ways too
    L.add(0, 1, "ran_up")
    assert L.add(1, 20, "ran_dn") == (1, True)


@BOTH
def test_evidence_comes_from_other_episodes_only(Lib):
    from picture import evidence  # noqa: PLC0415

    codes, shapes, feats = lib_rows()
    rows = [0, 1, 1, 1]
    L = Lib(codes[rows], shapes[rows], [feats[r] for r in rows])
    L.add(0, 100, "ran_up")  # the pattern is born on day 100
    assert evidence(L, 1, 101)[0] == 0  # the next day (an hour later across midnight): the same episode - no evidence
    assert evidence(L, 1, 106)[0] == 0  # six days later: still too close
    assert evidence(L, 1, 107) == (1, 1.0, 0)  # seven days later: one earlier episode, it ran up
    L.add(2, 110, "ran_dn")  # a second episode on day 110
    assert evidence(L, 3, 115) == (1, 1.0, 0)  # on day 115 the day-110 episode is not yet usable
    assert evidence(L, 3, 117) == (2, 0.0, 0)  # on day 117 both: up 1/2, down 1/2


def test_zoom_reads_the_smaller_timeframe_when_the_swings_are_too_few():
    from picture import zoom  # noqa: PLC0415

    # the smaller timeframe over the same span: troughs 90 -> 110, peaks 100 -> 120 (confirmed), the close 125
    h = np.array([95.0, 100, 92, 115, 120, 112, 125])
    lo = h - 2.0
    lo[[2, 5]] = [90.0, 110.0]
    P = piv([1, 2, 4, 5], [100.0, 90.0, 120.0, 110.0], [1, -1, 1, -1], [2, 3, 5, 6])
    small = (h, lo, 125.0, P, 6, 0)
    big = dict(BASE, struct=9, brk=9)
    z = zoom(big, small)
    assert (z["struct"], z["brk"]) == (1, 1)  # HH/HL read on the smaller timeframe, the close above its last top
    assert zoom(dict(BASE), small) == dict(BASE)  # a timeframe that reads its own swings is left alone
    assert zoom(big, None) == big  # nothing smaller (M1 is given a finer swing instead)
    assert zoom(dict(BASE, struct=9), small)["brk"] == BASE["brk"]  # only the missing reading is filled
