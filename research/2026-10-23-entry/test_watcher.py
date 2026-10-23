"""Hand-worked tests for watcher.wake_reasons - when the AI is woken.

    .venv/Scripts/python -m pytest research/2026-10-23-entry/test_watcher.py -q
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import watcher as w  # noqa: E402

T = pd.Timestamp("2026-10-23T15:00", tz="UTC")


def at(minutes):
    return T + pd.Timedelta(minutes=minutes)


def test_the_first_call():
    assert w.wake_reasons(T, None, None, None, [], set(), False) == ["the first call"]


def test_sleeps_when_nothing_happens():
    assert w.wake_reasons(at(14), T, 4005.6, 3992.9, [3995.0, 4005.6, 3992.9], set(), True) == []  # at the levels, not beyond


def test_a_close_beyond_a_watched_price_wakes_at_once():
    assert w.wake_reasons(at(1), T, 4005.6, 3992.9, [3999.0, 4005.61], set(), True) == ["an M1 close over 4005.60"]
    assert w.wake_reasons(at(1), T, 4005.6, 3992.9, [3992.89], set(), True) == ["an M1 close under 3992.90"]
    assert w.wake_reasons(at(1), T, None, None, [5000.0, 1.0], set(), True) == []  # nothing watched


def test_a_new_moving_behaviour_wakes_after_the_cooldown():
    assert w.wake_reasons(at(14), T, None, None, [], {"sweep"}, True) == []
    assert w.wake_reasons(at(15), T, None, None, [], {"sweep", "break"}, True) == ["new: break, sweep"]
    assert w.wake_reasons(at(20), T, None, None, [], {"boar", "chop", "squeeze"}, True) == []  # not the moving kind


def test_the_30_minute_check_only_in_the_owners_windows():
    assert w.wake_reasons(at(29), T, None, None, [], set(), True) == []
    assert w.wake_reasons(at(30), T, None, None, [], set(), True) == ["30-minute check"]
    assert w.wake_reasons(at(90), T, None, None, [], set(), False) == []
    assert w.wake_reasons(at(60), T, 4005.0, None, [4006.0], {"climax"}, True) == [
        "an M1 close over 4005.00", "new: climax", "30-minute check"]
    assert w.wake_reasons(at(60), T, 4005.0, None, [4006.0], set(), False) == ["an M1 close over 4005.00"]


def test_spent_today_counts_the_thai_day():
    rows = [{"as_of": "2026-10-23T16:59:00+00:00", "cost_usd": 0.01},   # 23:59 Thai, 23 Oct
            {"as_of": "2026-10-23T17:00:00+00:00", "cost_usd": 0.02},   # 00:00 Thai, 24 Oct
            {"as_of": "2026-10-24T01:00:00+00:00", "cost_usd": 0.03},   # 08:00 Thai, 24 Oct
            {"as_of": "2026-10-24T02:00:00+00:00"}]                     # an error: no cost
    assert w.spent_today(rows, pd.Timestamp("2026-10-24T02:30", tz="UTC")) == pytest.approx(0.05)
    assert w.spent_today(rows, pd.Timestamp("2026-10-23T10:00", tz="UTC")) == pytest.approx(0.01)
    # 01:00 Thai on 24 Oct is still 23 Oct in UTC: the Thai day counts
    assert w.spent_today(rows, pd.Timestamp("2026-10-23T18:00", tz="UTC")) == pytest.approx(0.05)


def test_a_close_beyond_that_came_back_still_wakes():
    # under 3,992.9 then back over it before the check: the AI must still hear of it
    assert w.wake_reasons(at(2), T, None, 3992.9, [3992.0, 3995.0], set(), True) == ["an M1 close under 3992.90"]
