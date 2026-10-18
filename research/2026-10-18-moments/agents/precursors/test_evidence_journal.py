"""R13: the evidence recorded with every trade. The moment's codes are the library's codes (the same code at the same
time), the matches are re-counted by brute force (attribute by attribute, no one-hot), and the walk-forward rule
holds (only earlier days). The four losers' values are a result, not a test: they are recomputed whenever the library
is rebuilt (2026-10-18: the library built with the old indicators gave the 102 trigger matches of trade 1).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_evidence_journal.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import plib  # noqa: E402
from evidence_journal import SHORT, evidence  # noqa: E402
from library_match import LAYERS, MOMENTS, attrs, moment_codes  # noqa: E402

CLS_UP, CLS_DN = ("ran_up", "slow_up"), ("ran_dn", "slow_dn")


@pytest.fixture(scope="module")
def lib():
    return pd.read_parquet(HERE / "snaps.parquet"), pd.read_parquet(HERE / "snap_fingerprints.parquet")


@pytest.fixture(scope="module")
def m():
    return plib.load()


def test_the_library_holds_the_learning_period_only(lib):
    S, FS = lib
    assert S.S.min() >= plib.LEARN_START and len(S) == len(FS)


def test_a_moments_codes_are_the_librarys_codes(lib, m):
    """The codes computed for a trade's decision bar equal the stored codes of a snap at the same bar - the same
    indicators, swings and levels on both sides of the comparison."""
    S, FS = lib
    pick = np.linspace(0, len(S) - 1, 40).astype(int)
    bars_t = m.index[S.idx.to_numpy()[pick]]
    FM, CM = moment_codes(m, pd.DatetimeIndex(bars_t))
    for tfs in LAYERS.values():
        a_lib = attrs(FS.iloc[pick].reset_index(drop=True), S.iloc[pick].reset_index(drop=True), tfs)
        a_mom = attrs(FM.reset_index(drop=True), CM.reset_index(drop=True), tfs)
        for x, y in zip(a_lib, a_mom):
            np.testing.assert_array_equal(np.asarray(x, int), np.asarray(y, int))
    np.testing.assert_array_equal(FM.to_numpy(int), FS.iloc[pick].to_numpy(int))  # all 20 attributes, six TFs


def test_the_matches_recounted_by_brute_force(lib, m):
    S, FS = lib
    t = pd.DatetimeIndex([pd.Timestamp(x[1], tz="Asia/Bangkok").tz_convert("UTC") for x in MOMENTS])
    sides = np.array([x[2] for x in MOMENTS])
    # the four losers lie before the library starts; move them into it: the same clock times on 2026-06-10 .. 06-15
    t = pd.DatetimeIndex([pd.Timestamp(f"2026-06-{10 + k} {x.tz_convert('Asia/Bangkok'):%H:%M}", tz="Asia/Bangkok")
                          .tz_convert("UTC") for k, x in enumerate(t)])
    t = pd.DatetimeIndex([m.index[m.index.searchsorted(x)] for x in t])  # existing bars
    E = evidence(m, t, sides, grow=False)
    FM, CM = moment_codes(m, t)
    day_s = S.S.dt.tz_convert("Asia/Bangkok").dt.normalize()
    for layer, tfs in LAYERS.items():
        L = SHORT[layer]
        A = np.column_stack(attrs(FS, S, tfs)).astype(int)
        Q = np.column_stack(attrs(FM.reset_index(drop=True), CM.reset_index(drop=True), tfs)).astype(int)
        for i in range(len(t)):
            earlier = (day_s < t[i].tz_convert("Asia/Bangkok").normalize()).to_numpy()
            share = (A == Q[i]).mean(axis=1)
            hit = earlier & (share >= 0.8)
            assert E[f"{L}_n"].iloc[i] == hit.sum()
            assert E[f"{L}_days"].iloc[i] == day_s[hit].nunique()
            if hit.sum():
                cls = S.cls.to_numpy()[hit]
                up, dn = np.isin(cls, CLS_UP).mean(), np.isin(cls, CLS_DN).mean()
                assert E[f"{L}_with"].iloc[i] == pytest.approx(up if sides[i] > 0 else dn)
                assert E[f"{L}_against"].iloc[i] == pytest.approx(dn if sides[i] > 0 else up)
                assert E[f"{L}_fake"].iloc[i] == pytest.approx(np.isin(cls, ("fake_up", "fake_dn")).mean())
    assert set(E.evidence) <= {"supports", "against", "mixed", "none"}


def test_a_new_pattern_joins_the_library_and_teaches_a_later_day():
    from evidence_journal import match_pool  # noqa: PLC0415

    # pool: a snap on day 1 (ran up) and a trade moment on day 2 that was a new pattern (it ran down afterwards)
    VP = np.array([[1.0, 0.0], [0.0, 1.0]])
    day_p = np.array([1, 2])
    up, dn = np.array([True, False]), np.array([False, True])
    no = np.array([False, False])
    VQ = np.array([[0.0, 1.0], [0.0, 1.0]])  # queries alike the day-2 trade moment
    cols = match_pool(VP, day_p, up, dn, no, no, VQ, np.array([3, 2]), np.array([-1, -1]))
    assert cols["n"][0] == 1 and cols["with"][0] == 1.0  # day 3: learned from day 2 (a sell, and it ran down)
    assert cols["n"][1] == 0  # day 2 itself: never its own day (walk-forward)


def test_the_pattern_library_record(lib, m):
    from evidence_journal import evidence_patterns  # noqa: PLC0415

    S, _ = lib
    t = pd.DatetimeIndex([m.index[m.index.searchsorted(pd.Timestamp(x, tz="UTC"))]
                          for x in ("2026-05-12 02:29", "2026-06-03 13:44", "2026-07-21 08:09", "2026-08-26 14:59")])
    sides = np.array([-1, 1, 1, -1])
    E, libs = evidence_patterns(m, t, sides)
    for L, lb in libs.items():
        # every pattern: counted at most once a day, at most five examples from different days
        for p in lb.patterns:
            assert len(p.occ_days) == len(set(p.occ_days)) and p.occ_days == sorted(p.occ_days)
            assert len(p.examples) <= 5 and len({d for d, _ in p.examples}) == len(p.examples)
        # far fewer patterns than moments: repeats are counted, not stored
        assert len(lb.patterns) < len(S) + 4
    # the evidence = the recorded pattern's occurrences on earlier days, and that pattern existed before the day
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    seen = 0
    for L in ("ctx", "set", "trg"):
        for i in range(4):
            pid = int(E[f"{L}_pid"].iloc[i])
            day = (t[i].tz_convert("Asia/Bangkok").normalize() - day0).days
            if pid >= 0:
                seen += 1
                p = libs[L].patterns[pid]
                assert p.created_day < day
                assert E[f"{L}_count"].iloc[i] == sum(d < day for d in p.occ_days)  # earlier days only
                assert E[f"{L}_sim"].iloc[i] >= 0.8 - 1e-6
            else:
                assert E[f"{L}_count"].iloc[i] == 0
            assert int(E[f"{L}_joined"].iloc[i]) >= 0  # every moment is counted into the library
    assert seen > 0
