"""Audit of the second developer's ZigZag (dev2/swings.py::zigzag, rule 2 of its DEV_LOG V3-1), READ ONLY.

The same hand cases as audit2/test_swings.py (precursors/fingerprint.py), written for dev2's interface (a threshold per
bar) and its written rule 2: a tie keeps the FIRST bar (fingerprint moves the pivot to the later bar), the threshold is
read at the confirming bar, the next extreme is tracked from the confirming bar.

Audited version: dev2/swings.py sha256 9ebfe2dd5de473b7..., file time 2026-10-20 12:26:40 Thai (05:26:40 UTC).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/audit2/test_dev2_swings.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dev2"))
import swings as W  # noqa: E402


def zz(h: list[float], lo: list[float], thr: float | list[float] = 10.0) -> list[tuple[int, float, int, int]]:
    t = np.full(len(h), float(thr)) if np.isscalar(thr) else np.array(thr, float)
    b, p, k, c = W.zigzag(np.array(h, float), np.array(lo, float), t)
    return list(zip(b.tolist(), p.tolist(), k.tolist(), c.tolist(), strict=True))


def test_one_wide_bar_at_the_start_is_never_two_turns() -> None:
    assert zz([10, 30, 25, 26], [9, 0, 20, 25]) == []


def test_after_a_wide_bar_the_first_turn_waits_for_a_bar_that_takes_an_extreme_out() -> None:
    assert zz([10, 30, 25, 26, 31, 24], [9, 0, 20, 25, 28, 20]) == [(1, 0.0, -1, 4), (4, 31.0, 1, 5)]


def test_an_outside_bar_in_an_up_leg_extends_it_and_is_one_turn() -> None:
    assert zz([10, 15, 19, 25, 20], [9, 12, 16, 14, 15]) == [(0, 9.0, -1, 2), (3, 25.0, 1, 4)]


def test_an_outside_bar_in_a_down_leg_is_mirrored() -> None:
    assert zz([-9, -12, -16, -14, -15], [-10, -15, -19, -25, -20]) == [(0, -9.0, 1, 2), (3, -25.0, -1, 4)]


def test_a_tie_keeps_the_first_bar_and_exactly_the_threshold_confirms() -> None:
    # trough 9 at 0 confirmed by bar 1 (19 - 9 = 10, exactly); bar 2's equal high 19 does NOT move the peak (rule 2);
    # bar 3's low 9 is exactly 10 below -> the peak at 1 confirmed by 3
    assert zz([10, 19, 19, 12], [9, 15, 16, 9]) == [(0, 9.0, -1, 1), (1, 19.0, 1, 3)]
    assert zz([-9, -15, -16, -9], [-10, -19, -19, -12]) == [(0, -9.0, 1, 1), (1, -19.0, -1, 3)]


def test_just_under_the_threshold_confirms_nothing() -> None:
    assert zz([10, 18.99, 17], [9, 15, 16]) == []


def test_the_threshold_is_read_at_the_confirming_bar() -> None:
    # trough 9 at 0 confirmed by bar 1 (thr 10); bar 2's low 9 is 10 below the peak 19, but bar 2's threshold is 20
    assert zz([10, 19, 12], [9, 15, 9], [10, 10, 20]) == [(0, 9.0, -1, 1)]
    # the reverse: the peak's own bar has threshold 20, the confirming bar 10 -> confirmed (trough 9 @0 by bar 1 at
    # thr 5; the peak moves to bar 2 (19); bar 3's low 9 is 10 below it, bar 3's threshold 10)
    assert zz([10, 15, 19, 12], [9, 12, 15, 9], [10, 5, 20, 10]) == [(0, 9.0, -1, 1), (2, 19.0, 1, 3)]


def series(seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = 400
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    wide = rng.random(n) < 0.05
    wide[0] = True
    span = np.where(wide, 15.0, rng.random(n))
    thr = 3.0 + 3.0 * rng.random(n)  # a threshold that changes every bar, as max(S, ATR) does
    return c + span, c - span, thr


@pytest.mark.parametrize("seed", range(20))
def test_every_pivot_is_confirmed_by_a_later_bar_and_no_bar_turns_twice(seed: int) -> None:
    h, lo, thr = series(seed)
    b, _, k, conf = W.zigzag(h, lo, thr)
    assert len(b) > 10
    assert (conf > b).all()
    assert len(np.unique(b)) == len(b)
    assert (np.diff(k) != 0).all()


@pytest.mark.parametrize("seed", range(5))
def test_no_look_ahead_the_pivots_known_at_d_do_not_depend_on_later_bars(seed: int) -> None:
    h, lo, thr = series(seed)
    full = W.zigzag(h, lo, thr)
    for d in range(20, 400, 23):
        cut = W.zigzag(h[: d + 1], lo[: d + 1], thr[: d + 1])
        known = full[3] <= d
        for a, x in zip(full, cut, strict=True):
            assert a[known].tolist() == x.tolist()


@pytest.mark.xfail(strict=True, reason="QUESTION to the measurer / owner: rule 2 tracks the next extreme from the "
                   "confirming bar and never revises a confirmed pivot; with a threshold that grows, price can undercut a "
                   "confirmed trough and the trough stays where it was (real learning bars: 0.1 % of M1 .. 1.0 % of H1 "
                   "pivots, audit2/out_check_dev2_swings.txt part C)")
def test_a_trough_is_the_lowest_low_between_its_two_peaks() -> None:
    # thr 10 to bar 4, then 30. Trough 99 @0 (by 1); peak 112 @1 (by 2); trough 95 @3 (by 4: 106 - 95 = 11).
    # Bar 5 (low 90) undercuts the trough while the peak 106 is tracked: 106 - 90 = 16 < 30, so nothing happens.
    # Bar 6 makes 140, bar 7 (105) confirms the peak at 6. Between the peaks 112 @1 and 140 @6 the lowest low is 90 @5,
    # but the recorded trough is 95 @3.
    h = [100, 112, 108, 104, 106, 105, 140, 135]
    lo = [99, 105, 101, 95, 100, 90, 104, 105]
    thr = [10, 10, 10, 10, 10, 30, 30, 30]
    piv = zz(h, lo, thr)
    assert [(b, k) for b, _, k, _ in piv] == [(0, -1), (1, 1), (3, -1), (6, 1)]  # what the code gives (passes)
    troughs = [(b, p) for b, p, k, _ in piv if k == -1 and 1 < b < 6]
    assert troughs == [(5, 90.0)]  # the owner's chart: the swing low between the two peaks (fails: (3, 95.0))


@pytest.mark.xfail(strict=True, reason="QUESTION: `running()` (rule 4's 'running extreme of the leg after the last "
                   "pivot', the lowest low since the pivot) and the extreme the structure uses (the ZigZag's, tracked from "
                   "the confirming bar) differ when the threshold shrinks (real bars: 104 of 173,030 M1 bars, part D)")
def test_running_equals_the_extreme_the_structure_tracks() -> None:
    # peak 20 @1 (trough 9 @0 by 1); bar 2's low 14 is 6 below (thr 7: no); bar 3's low 15 is 5 below (thr 4: the peak
    # is confirmed by 3, the trough tracked from bar 3 = 15). running() after the peak: the lowest low of bars 2..3 = 14.
    h, lo = np.array([10, 20, 18, 17.0]), np.array([9, 12, 14, 15.0])
    piv, dirs, exts = W.zigzag(h, lo, np.array([10, 10, 7, 4.0]), state=True)
    assert piv[0].tolist() == [0, 1] and dirs[3] == -1 and exts[3] == 3  # what the code gives (passes)
    assert W.running(piv, h, lo, 3) == (int(exts[3]), float(lo[exts[3]]), -1)  # (2, 14.0, -1) != (3, 15.0, -1)


# ---------------------------------------------------------------- round 3: the measurer's two test gaps (2026-10-20)
# The measurer's planted bugs `known_at` one bar ahead and `running()` including the pivot bar
# (precursors/plant_dev2_v31.py) were missed by every unit test; these two catch them (audit2/mutants_dev2_swings_r3.py).
def _piv(h: list[float], lo: list[float], thr: float = 10.0):
    return W.zigzag(np.array(h, float), np.array(lo, float), np.full(len(h), thr))


def test_known_at_leaves_out_a_pivot_confirmed_on_the_next_bar() -> None:
    # trough 9 @0 confirmed by bar 1 (19 - 9 = 10); peak 19 @1 confirmed by bar 3 (19 - 9 = 10)
    piv = _piv([10, 19, 15, 12], [9, 15, 12, 9])
    assert list(zip(*(a.tolist() for a in piv), strict=True)) == [(0, 9.0, -1, 1), (1, 19.0, 1, 3)]
    assert [len(W.known_at(piv, d)[0]) for d in range(4)] == [0, 1, 1, 2]  # confirmed at d + 1 -> not known at d
    assert W.known_at(piv, 2)[3].tolist() == [1]  # bar 2 knows the trough only
    assert W.known_at(piv, 0)[0].tolist() == []  # bar 0 knows nothing (its trough is confirmed by bar 1)


@pytest.mark.parametrize("mirror", [False, True])
def test_running_starts_after_the_pivot_bar(mirror: bool) -> None:
    # trough 9 @0 confirmed by bar 1 (30 - 9); peak 30 @1 confirmed by bar 3 (30 - 19.5 = 10.5). The peak bar's own low 12
    # is below every later low (21, 19.5, 18): the running low after the peak is 18 @4, never 12 @1.
    h, lo = [10, 30, 25, 22, 24], [9, 12, 21, 19.5, 18]
    if mirror:  # the same picture upside down: a trough whose own high is above every later high
        h, lo = [-x for x in lo], [-x for x in h]
    piv = _piv(h, lo)
    s = -1 if mirror else 1
    assert list(zip(*(a.tolist() for a in piv), strict=True)) == [(0, s * 9.0, -s, 1), (1, s * 30.0, s, 3)]
    assert W.running(piv, np.array(h, float), np.array(lo, float), 3) == (3, s * 19.5, -s)
    assert W.running(piv, np.array(h, float), np.array(lo, float), 4) == (4, s * 18.0, -s)
    # before the peak is confirmed (bar 2) the running leg is the one after the trough: its high since bar 1
    assert W.running(piv, np.array(h, float), np.array(lo, float), 2) == (1, s * 30.0, s)
