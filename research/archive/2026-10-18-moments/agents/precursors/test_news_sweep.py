"""news_sweep by hand: the first leg, continued / faked / neither / quiet, the sweep, the move back, the third leg.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_news_sweep.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_sweep import events, sweep  # noqa: E402

S = 10**9
T0 = 1000 * S  # the release


def path(rows):
    t, p = zip(*rows)
    return np.array(t, np.int64) * S, np.array(p, float)


def test_the_owner_case_fake_drop_sweep_up_then_down():
    # p0 100 (the tick before the release); 10 s: 97 (the first leg down, 3 USD); 5 min: 112 (10 up first: faked, the
    # sweep +12 beyond p0 - its extreme, not 111 where it first passed 10); 10 min: 95 (back 17 from 112, through p0: the third leg)
    t, p = path([(990, 100.0), (1010, 97.0), (1020, 96.5), (1200, 111.0), (1300, 112.0), (1600, 95.0)])
    x = sweep(t, p, T0)
    assert x["first"] == -1 and x["leg1"] == pytest.approx(3.5) and x["outcome"] == "faked"
    assert x["sweep"] == pytest.approx(12.0) and x["sweep_min"] == pytest.approx(5.0)
    assert x["back"] == pytest.approx(17.0) and x["third"]


def test_faked_without_the_third_leg():
    # the first leg up to 103.5, then down to 88 (the sweep 12 below p0), back only to 95: not through p0
    t, p = path([(990, 100.0), (1005, 103.5), (1200, 88.0), (1500, 95.0)])
    x = sweep(t, p, T0)
    assert x["first"] == 1 and x["outcome"] == "faked" and x["sweep"] == pytest.approx(12.0)
    assert x["back"] == pytest.approx(7.0) and not x["third"]


def test_continued_and_neither():
    t, p = path([(990, 100.0), (1010, 96.0), (1200, 89.5), (1300, 115.0)])
    assert sweep(t, p, T0)["outcome"] == "continued"  # 10 down (the first leg's way) before 10 up
    t, p = path([(990, 100.0), (1010, 96.0), (1200, 108.0), (1000 + 15 * 60 + 1, 130.0)])
    assert sweep(t, p, T0)["outcome"] == "neither"  # +30 only after 15 minutes


def test_quiet_when_the_first_3_usd_come_after_the_first_minute():
    t, p = path([(990, 100.0), (1030, 102.9), (1061, 97.0), (1200, 85.0)])
    assert sweep(t, p, T0)["outcome"] == "quiet"


def test_p0_is_the_tick_before_the_release_not_at_it():
    # a tick AT the release (1000 s) at 97: it is the first leg (from p0 100), not p0
    t, p = path([(990, 100.0), (1000, 97.0), (1200, 111.0)])
    x = sweep(t, p, T0)
    assert x["p0"] == 100.0 and x["first"] == -1 and x["outcome"] == "faked"


def test_the_release_minutes_follow_new_york_time():
    ev = events(pd.DatetimeIndex([pd.Timestamp("2026-01-09", tz="UTC"), pd.Timestamp("2026-03-10", tz="UTC"),
                                  pd.Timestamp("2026-03-14", tz="UTC")]))
    # January: EST (UTC-5) -> 13:30 / 15:00 UTC; 10 March: EDT (UTC-4) -> 12:30 / 14:00; 14 March is a Saturday
    assert [(e.strftime("%m-%d %H:%M"), n) for e, n in ev] == [
        ("01-09 13:30", "08:30 NY"), ("01-09 15:00", "10:00 NY"), ("03-10 12:30", "08:30 NY"), ("03-10 14:00", "10:00 NY")]


def test_the_third_leg_is_any_cross_of_p0():
    # the sweep to 88, then back to 101: 1 USD past p0 is the third leg
    t, p = path([(990, 100.0), (1005, 103.5), (1200, 88.0), (1500, 101.0)])
    x = sweep(t, p, T0)
    assert x["third"] and x["back"] == pytest.approx(13.0)


def test_the_owner_example_a_big_first_minute_then_the_sweep():
    # 2026-01-09's shape (the US jobs report): the first minute drops 14 (beyond 10 already) and holds there; then it
    # sweeps up 16 beyond p0 without a new low first - faked (a 10-USD rule from the release would call it continued)
    t, p = path([(990, 100.0), (1010, 86.0), (1050, 87.0), (1100, 95.0), (1300, 116.0), (1600, 104.0)])
    x = sweep(t, p, T0)
    assert x["first"] == -1 and x["leg1"] == pytest.approx(14.0) and x["outcome"] == "faked"
    assert x["sweep"] == pytest.approx(16.0) and x["back"] == pytest.approx(12.0) and not x["third"]


def test_continued_is_a_new_extreme_after_the_first_minute():
    # the first minute down 5 (95), then 94.9 - a new low - before any sweep up: continued
    t, p = path([(990, 100.0), (1010, 95.0), (1100, 99.0), (1200, 94.9), (1300, 115.0)])
    assert sweep(t, p, T0)["outcome"] == "continued"
