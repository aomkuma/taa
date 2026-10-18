"""The pattern library (owner, 2026-10-18): repeats count, new patterns are added, 3-5 example pictures a pattern."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pattern_library import PatternLibrary  # noqa: E402

A = np.array([1.0, 0.0, 0.0])
B = np.array([0.0, 1.0, 0.0])
AB = np.array([0.9, 0.436, 0.0])  # 0.9 alike A, 0.436 alike B


def test_the_same_picture_on_two_days_is_one_pattern_counted_twice():
    lib = PatternLibrary(3)
    assert lib.add(A, 1, "ran_up") == (0, True)
    assert lib.add(A, 2, "ran_dn") == (0, False)
    assert len(lib.patterns) == 1 and lib.patterns[0].occ_days == [1, 2]


def test_the_same_day_counts_once():
    lib = PatternLibrary(3)
    lib.add(A, 1, "ran_up")
    lib.add(A, 1, "ran_dn")
    assert lib.patterns[0].occ_days == [1] and lib.patterns[0].occ_outcomes == ["ran_up"]


def test_a_different_picture_starts_a_new_pattern():
    lib = PatternLibrary(3)
    lib.add(A, 1, "ran_up")
    assert lib.add(B, 1, "flat") == (1, True)
    assert len(lib.patterns) == 2


def test_the_most_similar_pattern_takes_the_repeat():
    lib = PatternLibrary(3)
    lib.add(A, 1, "ran_up")
    lib.add(B, 1, "flat")
    assert lib.add(AB, 2, "fake_up") == (0, False)  # 0.9 to A beats 0.436 to B


def test_at_most_five_examples_from_different_days():
    lib = PatternLibrary(3, max_examples=5)
    for d in range(1, 9):
        lib.add(A, d, "ran_up", moment=f"t{d}")
    p = lib.patterns[0]
    assert len(p.occ_days) == 8 and len(p.examples) == 5
    assert len({d for d, _ in p.examples}) == 5


def test_evidence_uses_only_earlier_days():
    lib = PatternLibrary(3)
    lib.add(A, 1, "ran_up")
    lib.add(A, 2, "ran_up")
    lib.add(A, 3, "ran_dn")
    e = lib.evidence(A, 3, 1)  # a buy on day 3: days 1-2 only
    assert e["count"] == 2 and e["with_"] == 1.0 and e["against"] == 0.0
    e = lib.evidence(A, 4, -1)  # a sell on day 4: days 1-3, two up one down
    assert e["count"] == 3 and abs(e["with_"] - 1 / 3) < 1e-9
    assert lib.evidence(A, 1, 1)["count"] == 0  # nothing before day 1
    assert lib.evidence(B, 4, 1)["pid"] == -1  # no pattern like B: a new pattern, no evidence


def test_a_pattern_born_today_gives_no_evidence_today():
    lib = PatternLibrary(3)
    lib.add(B, 5, "ran_dn")
    assert lib.evidence(B, 5, -1)["pid"] == -1
    assert lib.evidence(B, 6, -1)["count"] == 1


def test_an_exact_eighty_percent_counts_as_alike():
    """2026-10-19: float32 storage put 16 of 20 equal attributes at 0.79999999, below the threshold."""
    import numpy as np  # noqa: PLC0415

    def bits(b):
        b = np.asarray(b, float)
        return (np.r_[b, 1 - b] / np.sqrt(len(b))).astype(np.float32)  # as cluster_fp.onehot: float32

    lib = PatternLibrary(40)
    lib.add(bits([0] * 20), 1, "ran_up")
    assert lib.add(bits([1] * 4 + [0] * 16), 2, "ran_dn") == (0, False)  # 16 of 20 equal: a repeat


def test_a_tie_goes_to_the_earliest_pattern():
    import numpy as np  # noqa: PLC0415

    from pattern_library import Pattern  # noqa: PLC0415

    lib = PatternLibrary(1)
    lib.patterns = [Pattern(0, np.array([0.8333333333333333]), 1, [1], ["ran_up"]),
                    Pattern(1, np.array([0.8333333333333335]), 1, [1], ["ran_dn"])]
    lib._L = np.array([[0.8333333333333333], [0.8333333333333335]])
    assert lib.most_similar(np.array([1.0]))[0] == 0
