"""present.py by hand: which clock times become library moments (the data's origin: the clock, the owner's windows
and the bar present at t - nothing later), and what followed each (the first run within 30 minutes).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_present.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from present import NS_MIN, clock_moments, run_label  # noqa: E402

U = pd.Timestamp


def test_clock_moments_by_hand():
    # Wednesday 2026-07-15 (New York on summer time, UTC-4): 13:20 UTC = 09:20 New York (no window), 13:25-13:59 UTC =
    # the New York 09:30 window (09:25-10:00); the M1 bars present: 13:19, 13:24, 13:29 (13:34 missing)
    idx = pd.DatetimeIndex([U("2026-07-15 13:19", tz="UTC"), U("2026-07-15 13:24", tz="UTC"), U("2026-07-15 13:29", tz="UTC")])
    got = clock_moments(idx, U("2026-07-15 13:20", tz="UTC"), U("2026-07-15 13:40", tz="UTC"))
    assert list(got) == [U("2026-07-15 13:25", tz="UTC"), U("2026-07-15 13:30", tz="UTC")]
    # Saturday 2026-07-18 at the same time: no window, though its bar is present
    sat = pd.DatetimeIndex([U("2026-07-18 13:24", tz="UTC")])
    assert len(clock_moments(sat, U("2026-07-18 13:25", tz="UTC"), U("2026-07-18 13:30", tz="UTC"))) == 0
    # the end is not included
    assert len(clock_moments(idx, U("2026-07-15 13:25", tz="UTC"), U("2026-07-15 13:25", tz="UTC"))) == 0


def test_run_label_by_hand():
    mins = np.array([100, 129, 130, 185, 200, 300]) * NS_MIN
    starts = np.array([129, 215, 215, 400]) * NS_MIN  # an up run at 129; a down and an up run on the same bar 215; down 400
    side = np.array([1, -1, 1, -1])
    got = run_label(mins, starts, side)
    # 100: the run at 129 is in [100, 130); 129: a run starting at the decision's own bar counts; 130: 129 is before it
    # and 215 is not before 160; 185: 215 is not before 215; 200: two runs on bar 215 - the up one; 300: 400 too late
    assert got.tolist() == ["ran_up", "ran_up", "none", "none", "ran_up", "none"]
    assert run_label(np.array([0]), np.array([], np.int64), np.array([], int)).tolist() == ["none"]
