"""charts_d by hand: the 12-trade pick rule (3 winners and 3 losers nearest each part's middle; a zero is a loser; ties
the earlier) and the exam guard.

    data/venv-research/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_charts_d.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import charts_d as C  # noqa: E402

H = 3600 * 10**9


def test_the_pick_rule():
    rows = []
    for p in ("P1", "P2"):
        mid = C.MIDDLE[p]
        for k, pnl in enumerate([5, -3, 2, 0, 7, -1, 4, -2, 9, -8]):
            rows.append(dict(part=p, entry_t=mid + (k + 1) * H * (1 if k % 2 else -1), pnl=float(pnl)))
    T = pd.DataFrame(rows)
    got = C.pick12(T)
    assert len(got) == 12
    p1 = [(r.part, r.pnl) for r, _ in got[:6]]
    # distances 1, 2, 3, ... hours: winners 5 (1 h), 2 (3 h), 7 (5 h); losers -3 (2 h), 0 (4 h), -1 (6 h)
    assert p1 == [("P1", 5.0), ("P1", 2.0), ("P1", 7.0), ("P1", -3.0), ("P1", 0.0), ("P1", -1.0)]
    assert all("nearest its middle" in w for _, w in got)
    tie = pd.DataFrame([dict(part="P1", entry_t=C.MIDDLE["P1"] + H, pnl=1.0), dict(part="P1", entry_t=C.MIDDLE["P1"] - H, pnl=2.0)])
    assert [r.pnl for r, _ in C.pick12(tie)] == [2.0, 1.0]  # equal distance: the earlier first


def test_no_chart_reaches_the_exam():
    with pytest.raises(RuntimeError):
        C.m1_window(C.EXAM.value - H, C.EXAM.value + H)
