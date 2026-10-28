"""m1_lean.kept by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_m1_lean.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m1_lean import kept  # noqa: E402


def rec(p1_hi_up, p2_hi_up, days=40):
    r = {}
    for p, hi in (("P1", p1_hi_up), ("P2", p2_hi_up)):
        r |= {f"{p}_base_up": 0.04, f"{p}_base_dn": 0.05, f"{p}_lo_up": 0.04, f"{p}_hi_up": hi, f"{p}_lo_dn": 0.05, f"{p}_hi_dn": 0.05,
              f"{p}_lo_days": days, f"{p}_hi_days": days}
    return r


def test_kept_only_when_both_parts_lift_enough():
    assert kept(rec(0.06, 0.07)) == ["hi->up"]  # 1.5 x 0.04 = 0.06: the edge counts
    assert kept(rec(0.06, 0.059)) == []  # P2 short of 1.5 x
    assert kept(rec(0.09, 0.09, days=29)) == []  # too few days
