"""Setup OWN V2 (v2b.py) by hand: the outline library, the side decision and the trade plan.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_v2b.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pattern_library import PatternLibrary  # noqa: E402
from v2b import NPTS, OutlineLibrary, decide, plan  # noqa: E402


def unit_shape(sign: float, n_tf: int = 2) -> np.ndarray:
    x = np.linspace(-1, 1, NPTS)
    x = (x - x.mean()) / x.std() / np.sqrt(NPTS)  # as snaps.shapes: zero mean, unit norm
    return np.stack([sign * x] * n_tf)


def test_without_the_gate_it_counts_like_the_pattern_library():
    rng = np.random.default_rng(3)
    V = rng.integers(0, 2, size=(60, 10)).astype(float)
    V = np.hstack([V, 1 - V]) / np.sqrt(10)  # one-hot of 10 binary attributes: dot = share equal
    days = np.repeat(np.arange(20), 3)
    outs = rng.choice(["ran_up", "ran_dn", "flat"], size=60)
    a, b = OutlineLibrary(20, 2, rho=None), PatternLibrary(20)
    for v, d, o in zip(V, days, outs):
        assert a.add(v, unit_shape(1.0), int(d), str(o)) == b.add(v, int(d), str(o))
    assert [p.occ_days for p in a.patterns] == [p.occ_days for p in b.patterns]


def test_the_outline_gate_splits_alike_codes_with_unlike_paths():
    v = np.array([1.0, 0.0])
    gate, free = OutlineLibrary(2, 2, rho=0.6), OutlineLibrary(2, 2, rho=None)
    for lib in (gate, free):
        lib.add(v, unit_shape(1.0), 1, "ran_up")
    assert gate.add(v, unit_shape(-1.0), 2, "ran_dn") == (1, True)  # the paths run opposite: a new pattern
    assert free.add(v, unit_shape(-1.0), 2, "ran_dn") == (0, False)  # codes only: a repeat
    assert gate.add(v, unit_shape(1.0), 3, "ran_up") == (0, False)  # the same outline: a repeat of the first


def test_the_lean_uses_earlier_days_only():
    v, s = np.array([1.0, 0.0]), unit_shape(1.0)
    lib = OutlineLibrary(2, 2, rho=0.6)
    lib.add(v, s, 1, "ran_up")
    lib.add(v, s, 2, "slow_dn")
    assert lib.lean(v, s, 2) == (1, 1.0)  # only day 1 (up) is known on day 2
    assert lib.lean(v, s, 3) == (2, 0.0)  # up 1/2 - down 1/2
    assert lib.lean(v, unit_shape(-1.0), 3)[0] == 0  # the outline does not match: no evidence


def test_decide():
    leans = {"ctx": (9, -0.1), "set": (5, 0.3), "trg": (2, 0.5)}
    assert decide(leans, ("set",), 3, 0.2) == 1
    assert decide(leans, ("set",), 3, 0.4) == 0  # not decisive enough
    assert decide(leans, ("set", "trg"), 3, 0.2) == 0  # the trigger layer has 2 earlier days only
    assert decide(leans, ("set", "trg"), 2, 0.2) == 1  # 0.3 + 0.5
    assert decide({"set": (5, -0.25)}, ("set",), 3, 0.2) == -1
    assert decide({"set": (5, float("nan"))}, ("set",), 3, 0.2) == 0


def test_plan():
    etf, sl, tp = plan({"M1": 2.0, "M5": 4.0, "M15": 6.0, "M30": 9.0}, 4100.0)
    assert (etf, sl, tp) == ("M15", 6.0, pytest.approx(10.0))
    etf, sl, tp = plan({"M1": 1.0, "M5": 2.0, "M15": 3.0, "M30": 4.0}, 2050.0)
    assert (etf, sl, tp) == ("M30", 5.0, pytest.approx(5.0))  # none covers 5 USD: M30, the 5 USD floor; 10 U = 5 USD here


def test_the_gate_needs_every_timeframe_alike():
    v = np.array([1.0, 0.0])
    lib = OutlineLibrary(2, 2, rho=0.6)
    up, dn = unit_shape(1.0, 1)[0], unit_shape(-1.0, 1)[0]
    lib.add(v, np.stack([up, up]), 1, "ran_up")
    assert lib.add(v, np.stack([up, dn]), 2, "ran_dn") == (1, True)  # one timeframe alike, the other opposite: new


def onehot_bits(bits) -> np.ndarray:
    b = np.asarray(bits, float)
    return np.r_[b, 1 - b] / np.sqrt(len(b))  # dot = the share of equal attributes


def test_a_pattern_born_the_same_day_is_not_evidence():
    a = onehot_bits([0] * 20)
    c = onehot_bits([1] * 5 + [0] * 15)  # 15 of 20 equal to a (0.75): a new pattern
    q = onehot_bits([1] * 4 + [0] * 16)  # 16 of 20 equal to a (0.8), 19 of 20 to c
    s = unit_shape(1.0)
    lib = OutlineLibrary(40, 2, rho=None)
    lib.add(a, s, 1, "ran_up")
    assert lib.add(c, s, 2, "ran_dn") == (1, True)
    assert lib.lean(q, s, 2) == (1, 1.0)  # day 2 sees only the day-1 pattern, though the day-2 one is closer


def test_a_tie_goes_to_the_earliest_pattern():
    """2026-10-19 (the independent check): equal similarities came out 2e-16 apart and float noise picked the pattern."""
    from v2b import Pattern  # noqa: PLC0415

    lib = OutlineLibrary(1, 2, rho=None)
    lib.patterns = [Pattern(0, 1, [1], ["ran_up"]), Pattern(1, 1, [1], ["ran_dn"])]
    lib._L = np.array([[0.8333333333333333], [0.8333333333333335]])  # the same 15 / 18, two floats
    lib._S = np.zeros((2, 2, NPTS))
    lib._created = np.array([1, 1])
    assert lib.most_similar(np.array([1.0]), unit_shape(1.0))[0] == 0
