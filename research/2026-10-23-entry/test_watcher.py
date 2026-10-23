"""Hand-worked tests for watcher.wake_reasons - when the AI is woken.

    .venv/Scripts/python -m pytest research/2026-10-23-entry/test_watcher.py -q
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import watcher as w  # noqa: E402

T = pd.Timestamp("2026-10-23T15:00", tz="UTC")


def at(minutes):
    return T + pd.Timedelta(minutes=minutes)


def test_the_first_call():
    assert w.wake_reasons(T, None, None, None, [], set()) == ["the first call"]


def test_sleeps_when_nothing_happens():
    assert w.wake_reasons(at(14), T, 4005.6, 3992.9, [3995.0, 4005.6, 3992.9], set()) == []  # at the levels, not beyond


def test_a_close_beyond_a_watched_price_wakes_at_once():
    assert w.wake_reasons(at(1), T, 4005.6, 3992.9, [3999.0, 4005.61], set()) == ["an M1 close over 4005.60"]
    assert w.wake_reasons(at(1), T, 4005.6, 3992.9, [3992.89], set()) == ["an M1 close under 3992.90"]
    assert w.wake_reasons(at(1), T, None, None, [5000.0, 1.0], set()) == []  # nothing watched


def test_a_new_moving_behaviour_wakes_after_the_cooldown():
    assert w.wake_reasons(at(3), T, None, None, [], {"sweep"}) == []
    assert w.wake_reasons(at(4), T, None, None, [], {"sweep", "break"}) == ["new: break, sweep"]
    assert w.wake_reasons(at(10), T, None, None, [], {"boar", "chop", "squeeze"}) == []  # not the moving kind


def test_the_heartbeat():
    assert w.wake_reasons(at(15), T, None, None, [], set()) == ["15-minute check"]
    assert w.wake_reasons(at(20), T, 4005.0, None, [4006.0], {"climax"}) == [
        "an M1 close over 4005.00", "new: climax", "15-minute check"]


def test_a_close_beyond_that_came_back_still_wakes():
    # under 3,992.9 then back over it before the check: the AI must still hear of it
    assert w.wake_reasons(at(2), T, None, 3992.9, [3992.0, 3995.0], set()) == ["an M1 close under 3992.90"]
