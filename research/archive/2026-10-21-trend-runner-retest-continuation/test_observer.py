# ruff: noqa: S101, PT018
from __future__ import annotations

from journal import CandidateJournal
from observer import observe_settled_event
from test_candidate import prospective_case


def test_observer_only_journals_terminal_result_and_is_idempotent(tmp_path):
    journal = CandidateJournal(tmp_path / "observer.sqlite")
    journal.initialize()
    ev, m1, quotes = prospective_case()
    result = observe_settled_event(ev, m1, journal, quotes)
    assert result["status"] == "COMPLETE" and result["reason"] == "TIME"
    assert journal.counts() == {"source_events": 1, "terminal_results": 1}

    repeated = observe_settled_event(ev, m1, journal, quotes)
    assert repeated == result
    assert journal.counts() == {"source_events": 1, "terminal_results": 1}


def test_observer_does_not_append_pending_result(tmp_path):
    journal = CandidateJournal(tmp_path / "observer.sqlite")
    journal.initialize()
    ev, m1, quotes = prospective_case(minutes=180)  # bars end 1 h after entry: the trail cannot be known
    result = observe_settled_event(ev, m1, journal, quotes)
    assert result["status"] == "PENDING_M1_COVERAGE"
    assert journal.counts() == {"source_events": 1, "terminal_results": 0}
