# ruff: noqa: S101
from __future__ import annotations

import pytest
from candidate import COLLECTION_START
from journal import CandidateJournal


def _event():
    return {
        "trade_key": "fwd-001",
        "stop_time_utc": COLLECTION_START.isoformat(),
        "side": 1,
        "entry": 100.0,
        "stop": 99.0,
        "spread": 0.02,
        "runner_stopped_before_plus1": True,
    }


def test_append_only_idempotent_candidate_journal(tmp_path):
    journal = CandidateJournal(tmp_path / "candidate.sqlite")
    journal.initialize()
    assert journal.record_source_event(_event()) is True
    assert journal.record_source_event(_event()) is False

    result = {"trade_key": "fwd-001", "status": "COMPLETE", "reason": "TIME", "r": 0.4}
    assert journal.record_result("fwd-001", result) is True
    assert journal.record_result("fwd-001", result) is False
    assert journal.counts() == {"source_events": 1, "terminal_results": 1}

    changed_event = {**_event(), "entry": 100.1, "stop": 99.1}
    with pytest.raises(ValueError, match="immutable source event mismatch"):
        journal.record_source_event(changed_event)
    with pytest.raises(ValueError, match="immutable candidate result mismatch"):
        journal.record_result("fwd-001", {**result, "r": 0.5})


def test_journal_refuses_preboundary_or_pending_rows(tmp_path):
    journal = CandidateJournal(tmp_path / "candidate.sqlite")
    journal.initialize()
    with pytest.raises(ValueError, match="predates collection boundary"):
        journal.record_source_event({**_event(), "stop_time_utc": "2026-10-20T23:59:00+00:00"})
    journal.record_source_event(_event())
    pending = {"trade_key": "fwd-001", "status": "PENDING_EXIT_HORIZON"}
    with pytest.raises(ValueError, match="terminal"):
        journal.record_result("fwd-001", pending)


def test_journal_refuses_result_without_source_and_bad_risk(tmp_path):
    journal = CandidateJournal(tmp_path / "candidate.sqlite")
    journal.initialize()
    with pytest.raises(ValueError, match="positive directional risk"):
        journal.record_source_event({**_event(), "stop": 101.0})
    with pytest.raises(ValueError, match="unknown source event"):
        journal.record_result("missing", {"trade_key": "missing", "status": "COMPLETE", "r": 0.1})
