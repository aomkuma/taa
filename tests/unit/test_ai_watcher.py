"""The AI watcher (app/ai/watcher.py, TAA-1805): the wake rules, the budget, the session notes and the cycle with
fakes - a failed cycle is told, counted and survived. Moved in part from research/2026-10-23-entry/test_watcher.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.ai import watcher as w

T = pd.Timestamp("2026-10-23T15:00", tz="UTC")  # 22:00 Thai, 11:00 New York: inside the NY window


def at(minutes: int) -> pd.Timestamp:
    return T + pd.Timedelta(minutes=minutes)


def test_the_first_call():
    assert w.wake_reasons(T, None, None, None, [], set(), False) == ["the first call"]


def test_sleeps_when_nothing_happens():
    assert (
        w.wake_reasons(at(14), T, 4005.6, 3992.9, [3995.0, 4005.6, 3992.9], set(), True) == []
    )  # at, not beyond


def test_a_close_beyond_a_watched_price_wakes_at_once():
    assert w.wake_reasons(at(1), T, 4005.6, 3992.9, [3999.0, 4005.61], set(), True) == [
        "an M1 close over 4005.60"
    ]
    assert w.wake_reasons(at(1), T, 4005.6, 3992.9, [3992.89], set(), True) == ["an M1 close under 3992.90"]
    assert w.wake_reasons(at(1), T, None, None, [5000.0, 1.0], set(), True) == []  # nothing watched


def test_a_close_beyond_that_came_back_still_wakes():
    assert w.wake_reasons(at(2), T, None, 3992.9, [3992.0, 3995.0], set(), True) == [
        "an M1 close under 3992.90"
    ]


def test_a_new_moving_behaviour_wakes_after_the_cooldown():
    assert w.wake_reasons(at(14), T, None, None, [], {"sweep"}, True) == []
    assert w.wake_reasons(at(15), T, None, None, [], {"sweep", "break"}, True) == ["new: break, sweep"]
    assert w.wake_reasons(at(20), T, None, None, [], {"boar", "chop", "squeeze"}, True) == []  # not moving


def test_the_30_minute_check_only_in_the_owners_windows():
    assert w.wake_reasons(at(29), T, None, None, [], set(), True) == []
    assert w.wake_reasons(at(30), T, None, None, [], set(), True) == ["30-minute check"]
    assert w.wake_reasons(at(90), T, None, None, [], set(), False) == []
    assert w.wake_reasons(at(60), T, 4005.0, None, [4006.0], {"climax"}, True) == [
        "an M1 close over 4005.00",
        "new: climax",
        "30-minute check",
    ]
    assert w.wake_reasons(at(60), T, 4005.0, None, [4006.0], set(), False) == ["an M1 close over 4005.00"]


def test_spent_today_counts_the_watchers_calls_of_the_thai_day():
    rows = [
        {"as_of": "2026-10-23T16:59:00+00:00", "cost_usd": 0.01, "source": "watcher"},  # 23:59 Thai, 23 Oct
        {"as_of": "2026-10-23T17:00:00+00:00", "cost_usd": 0.02, "source": "watcher"},  # 00:00 Thai, 24 Oct
        {"as_of": "2026-10-24T01:00:00+00:00", "cost_usd": 0.03, "source": "watcher"},  # 08:00 Thai, 24 Oct
        {
            "as_of": "2026-10-24T01:30:00+00:00",
            "cost_usd": 0.50,
            "source": "manual",
        },  # a test call: not counted
        {"as_of": "2026-10-24T01:40:00+00:00", "cost_usd": 0.50},  # an old row: not counted
        {"as_of": "2026-10-24T02:00:00+00:00", "source": "watcher"},  # an error: no cost
    ]
    assert w.spent_today(rows, pd.Timestamp("2026-10-24T02:30", tz="UTC")) == pytest.approx(0.05)
    assert w.spent_today(rows, pd.Timestamp("2026-10-23T10:00", tz="UTC")) == pytest.approx(0.01)
    # 01:00 Thai on 24 Oct is still 23 Oct in UTC: the Thai day counts
    assert w.spent_today(rows, pd.Timestamp("2026-10-23T18:00", tz="UTC")) == pytest.approx(0.05)


def test_session_entry_reads_like_the_research_notes():
    rec = {
        "status": "OK",
        "final_size": "none",
        "vetoed_by": ["R01"],
        "cost_usd": 0.0163,
        "latency_ms": 5355.6,
        "decision": {
            "decision": "WAIT",
            "confidence": 62,
            "setup": "a squeeze at 3994",
            "entry": None,
            "stop": None,
            "target": None,
            "watch_above": 4006.5,
            "watch_below": 3992.9,
            "trigger": "an M5 close under 3992.9",
            "reasons": ["every frame down", "mid-range"],
        },
    }
    assert w.session_entry(
        pd.Timestamp("2026-10-23T17:24", tz="UTC"), ["an M1 close under 3992.90"], rec
    ) == (
        "\n### 00:24 Thai - the AI woken by: an M1 close under 3992.90\n"
        "- **WAIT** (size none, vetoed by R01; confidence 62): a squeeze at 3994\n"
        "- entry None, stop None, target None; watch above 4006.5 / below 3992.9\n"
        "- trigger: an M5 close under 3992.9\n- every frame down\n- mid-range\n- cost 0.0163 USD, 5355.6 ms\n"
    )


class Rig:
    """An AIWatcher with fakes: no bars are read (the behaviours are set by hand), decide records its calls."""

    def __init__(self, store: Path, answer: dict[str, Any] | Exception | None = None) -> None:
        self.calls: list[tuple[pd.Timestamp, str, str | None]] = []
        self.answer = answer
        self.behaviours: set[str] = set()
        self.watcher = w.AIWatcher(
            store,
            frames=lambda: None,  # type: ignore[arg-type, return-value]
            decide=self.decide,
            journal=lambda: "## the journal\nok",
            entries=lambda: [],
        )
        self.watcher._behaviours = lambda now: set(self.behaviours)  # type: ignore[method-assign]

    def decide(self, as_of: pd.Timestamp, text: str, model: str | None) -> dict[str, Any]:
        self.calls.append((as_of, text, model))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer or {
            "status": "OK",
            "source": "watcher",
            "cost_usd": 0.013,
            "final_size": "none",
            "decision": {"decision": "WAIT", "watch_above": 4006.0, "watch_below": 3992.9},
        }


def test_the_first_bar_wakes_the_ai_and_saves_what_to_watch(tmp_path: Path):
    rig = Rig(tmp_path)
    assert rig.watcher.on_bar(T, []) is not None
    [(as_of, text, model)] = rig.calls
    assert (as_of, model) == (T, "claude-sonnet-5-5")
    assert text == "## the journal\nok\n\nTHE AI'S OWN EARLIER CALLS:\n(none)"
    state = json.loads((tmp_path / "watch_state.json").read_text(encoding="utf-8"))
    assert (state["last_call"], state["watch_above"], state["watch_below"]) == (T.isoformat(), 4006.0, 3992.9)
    session = (tmp_path / "session_2026-10-23.md").read_text(encoding="utf-8")
    assert "### 22:00 Thai - the AI woken by: the first call" in session


def test_quiet_bars_let_it_sleep_and_a_watched_price_wakes_it(tmp_path: Path):
    rig = Rig(tmp_path)
    rig.watcher.on_bar(T, [])
    assert rig.watcher.on_bar(at(1), [3999.0, 4005.9]) is None
    assert rig.watcher.on_bar(at(2), [4006.1]) is not None
    assert len(rig.calls) == 2
    _, text, _ = rig.calls[1]
    assert "THE AI'S OWN EARLIER CALLS:\n\n### 22:00 Thai" in text  # it reads its own earlier call


def test_behaviours_are_read_at_five_minute_marks_only(tmp_path: Path):
    rig = Rig(tmp_path)
    rig.watcher.on_bar(T, [])
    rig.behaviours = {"sweep"}
    assert rig.watcher.on_bar(at(16), []) is None  # 15:16 is not a 5-minute mark: the sweep is not seen yet
    assert rig.watcher.on_bar(at(20), []) is not None  # 15:20: seen, new, past the cooldown


def test_the_state_survives_a_restart(tmp_path: Path):
    Rig(tmp_path).watcher.on_bar(T, [])
    again = Rig(tmp_path)
    assert again.watcher.on_bar(at(1), []) is None  # the last call is remembered: no 'first call' again
    assert again.watcher.on_bar(at(2), [3992.0]) is not None  # and so are the watch prices


def test_the_daily_cap_stops_the_calls(tmp_path: Path):
    rows = [
        {"as_of": T.isoformat(), "source": "watcher", "cost_usd": 0.25},
        {"as_of": T.isoformat(), "source": "watcher", "cost_usd": 0.15},
    ]
    (tmp_path / "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    rig = Rig(tmp_path)
    assert rig.watcher.on_bar(T, []) is None
    assert rig.calls == []


def test_a_failed_cycle_is_told_counted_and_survived(tmp_path: Path):
    rig = Rig(tmp_path, answer=FileNotFoundError("kb.yaml"))
    assert rig.watcher.on_bar(T, []) is None
    assert rig.watcher.failures == 1
    alert = (tmp_path / "watch_alerts.log").read_text(encoding="utf-8")
    assert alert == f"{T.isoformat()} FAILED (1): FileNotFoundError: kb.yaml\n"
    rig.answer = None
    assert rig.watcher.on_bar(at(1), []) is not None  # the next bar works: the first call is retried
