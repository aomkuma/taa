"""runpat by hand: readings turned to the run's way, the long form, the scores, the agreeing timeframes.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_runpat.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runpat import READINGS, TFS, long_form, patterns, score, turned  # noqa: E402


def test_turned_keeps_unknown():
    assert turned(np.array([1, -1, 0, 9]), -1).tolist() == [-1, 1, 0, 9]


def library(cls, structs, t="2024-06-03 08:00"):
    """A made-up library: one moment per cls; every reading 0 except the structure per timeframe (structs: rows of 6)."""
    n = len(cls)
    P = pd.DataFrame({"t_dec": pd.date_range(t, periods=n, freq="5min", tz="UTC"), "cls": cls})
    for i, tf in enumerate(TFS):
        for r in READINGS:
            P[f"{tf}_{r}"] = [s[i] for s in structs] if r == "struct" else 0
    return P


def test_long_form_turns_each_way():
    P = library(["ran_up", "ran_dn", "none"], [[1, 1, 1, 1, 1, 1], [1, -1, 1, -1, 9, 0], [0] * 6])
    L = long_form(P)
    up, dn = L[L.way == 1].reset_index(drop=True), L[L.way == -1].reset_index(drop=True)
    assert up.run.tolist() == [True, False, False] and up.other.tolist() == [False, True, False]
    assert dn.run.tolist() == [False, True, False] and dn.other.tolist() == [True, False, False]
    assert up.loc[1, "M5_struct"] == -1 and dn.loc[1, "M5_struct"] == 1 and dn.loc[1, "H1_struct"] == 9
    assert set(L.half) == {"L1"}


def test_score_by_hand():
    D = pd.DataFrame({"run": [True, True, False, False, True, False], "other": [False, False, True, False, False, False]})
    s = score(D, pd.Series([True, True, True, False, False, False]))
    # base 3/6 = 0.5; with the pattern 2/3 ran its way, 1/3 the other; 2 of the 3 runs had it
    assert s["n"] == 3 and s["run"] == pytest.approx(2 / 3) and s["other"] == pytest.approx(1 / 3)
    assert s["lift"] == pytest.approx(4 / 3) and s["used"] == pytest.approx(2 / 3)


def test_agreeing_timeframes_count_m5_to_h4():
    # M1 is not counted; 9 is not "with"
    P = library(["ran_up"], [[1, 1, 1, 9, 1, -1]])
    L = long_form(P)
    pats = patterns(L)
    up = (L.way == 1).to_numpy()
    assert pats["struct with on 3 of M5..H4"][up].tolist() == [True]
    assert pats["struct with on M5+M15+H1"][up].tolist() == [True] and pats["struct with on M5+M15+M30"][up].tolist() == [False]
    dn = (L.way == -1).to_numpy()
    assert pats["struct with on 1 of M5..H4"][dn].tolist() == [True]  # turned down only H4 (-1) is with the way
