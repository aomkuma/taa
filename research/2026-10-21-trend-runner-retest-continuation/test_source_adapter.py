# ruff: noqa: S101
from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest
import source_adapter
from candidate import COLLECTION_START
from journal import CandidateJournal
from test_candidate import prospective_case


def _source_rows():
    entry_time = COLLECTION_START
    exit_time = entry_time + pd.Timedelta(minutes=100)
    opportunity = {
        "trade_key": "fwd-001",
        "entry_time": entry_time.isoformat(),
        "side": 1,
        "entry": 100.0,
        "stop": 99.0,
        "spread": 0.02,
        "risk": 1.0,
    }
    outcome = {"trade_key": "fwd-001", "runner_exit_time": exit_time.isoformat(), "runner_r": -1.0}
    ticks = pd.DataFrame({"time_utc": [entry_time, exit_time], "bid": [100.0, 99.0], "ask": [100.02, 99.02]})
    return opportunity, outcome, ticks


def test_source_eligibility_uses_ordered_ticks_not_final_r():
    opportunity, outcome, ticks = _source_rows()
    event = source_adapter.classify_source_event(opportunity, outcome, ticks)
    assert event["runner_stopped_before_plus1"] is True

    hit = ticks.copy()
    hit.loc[1, "bid"] = 101.0
    hit.loc[1, "ask"] = 101.02
    event_after_target = source_adapter.classify_source_event(opportunity, outcome, hit)
    assert event_after_target["runner_stopped_before_plus1"] is False


def test_source_timeout_is_not_misclassified_as_stop():
    opportunity, outcome, ticks = _source_rows()
    outcome = {**outcome, "runner_exit_time": (COLLECTION_START + pd.Timedelta(hours=8)).isoformat()}
    ticks.loc[1, "time_utc"] = pd.Timestamp(outcome["runner_exit_time"])
    event = source_adapter.classify_source_event(opportunity, outcome, ticks)
    assert event["runner_stopped_before_plus1"] is False


def test_forward_adapter_reads_only_new_rows_and_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "source.sqlite"
    opportunity, outcome, ticks = _source_rows()
    with sqlite3.connect(db_path) as db:
        db.executescript(
            "CREATE TABLE opportunities(trade_key TEXT PRIMARY KEY, entry_time TEXT, payload_json TEXT);"
            "CREATE TABLE outcomes(trade_key TEXT PRIMARY KEY, payload_json TEXT);"
        )
        db.execute(
            "INSERT INTO opportunities VALUES (?,?,?)",
            (opportunity["trade_key"], opportunity["entry_time"], json.dumps(opportunity)),
        )
        db.execute("INSERT INTO outcomes VALUES (?,?)", (outcome["trade_key"], json.dumps(outcome)))
        old = {**opportunity, "trade_key": "old", "entry_time": "2026-10-20T12:00:00+00:00"}
        db.execute("INSERT INTO opportunities VALUES (?,?,?)", ("old", old["entry_time"], json.dumps(old)))
        db.execute("INSERT INTO outcomes VALUES (?,?)", ("old", json.dumps({**outcome, "trade_key": "old"})))

    monkeypatch.setattr(source_adapter, "_load_ticks", lambda *args: ticks)
    _, m1, quotes = prospective_case()
    monkeypatch.setattr(source_adapter, "_load_candidate_m1", lambda *args: m1)
    monkeypatch.setattr(source_adapter, "TickSource", lambda *args, **kwargs: quotes)
    journal = CandidateJournal(tmp_path / "candidate.sqlite")
    journal.initialize()
    counts = source_adapter.process_forward_source(
        db_path,
        m1_path=tmp_path / "unused.parquet",
        tick_root=tmp_path,
        journal=journal,
    )
    assert counts == {"COMPLETE": 1}
    assert journal.counts() == {"source_events": 1, "terminal_results": 1}
    again = source_adapter.process_forward_source(
        db_path,
        m1_path=tmp_path / "unused.parquet",
        tick_root=tmp_path,
        journal=journal,
    )
    assert again == {"COMPLETE": 1}
    assert journal.counts() == {"source_events": 1, "terminal_results": 1}


def test_source_eligibility_requires_exact_exit_quote():
    opportunity, outcome, ticks = _source_rows()
    ticks = ticks.iloc[:1]
    with pytest.raises(ValueError, match="exact recorded"):
        source_adapter.classify_source_event(opportunity, outcome, ticks)


def test_source_eligibility_accepts_equal_time_quotes_in_file_order():
    # Bug B10: real tick files carry several quotes per millisecond; the old check raised on them.
    opportunity, outcome, ticks = _source_rows()
    mid = pd.Timestamp(opportunity["entry_time"]) + pd.Timedelta(minutes=50)
    extra = pd.DataFrame({"time_utc": [mid, mid], "bid": [99.6, 99.7], "ask": [99.62, 99.72]})
    ticks = pd.concat([ticks.iloc[:1], extra, ticks.iloc[1:]], ignore_index=True)
    event = source_adapter.classify_source_event(opportunity, outcome, ticks)
    assert event["runner_stopped_before_plus1"] is True
