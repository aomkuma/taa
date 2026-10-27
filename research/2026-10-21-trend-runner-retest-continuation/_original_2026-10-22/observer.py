"""Append-only wrapper for a reviewed, already-settled forward source event."""
from __future__ import annotations

import pandas as pd
from candidate import simulate_candidate
from journal import FINAL_STATUSES, CandidateJournal


def observe_settled_event(
    event: dict[str, object], m1_after_collection_start: pd.DataFrame, journal: CandidateJournal
) -> dict[str, object]:
    """Record a settled source event and its candidate result once terminal.

    Caller must establish from the frozen source RUNNER path that the event stopped
    before its first +1R touch. The observer never modifies the source journal.
    """
    journal.record_source_event(event)
    result = simulate_candidate(event, m1_after_collection_start)
    if result["status"] in FINAL_STATUSES:
        journal.record_result(str(event["trade_key"]), result)
    return result
