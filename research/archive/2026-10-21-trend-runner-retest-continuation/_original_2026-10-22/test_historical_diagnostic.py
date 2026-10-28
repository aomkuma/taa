# ruff: noqa: S101
from __future__ import annotations

import pandas as pd
import pytest
from candidate import simulate_candidate, simulate_historical_diagnostic

EARLIEST = pd.Timestamp("2023-09-01", tz="UTC")
EXAM = pd.Timestamp("2026-04-18", tz="UTC")


def _event(stop_time: pd.Timestamp) -> dict[str, object]:
    return {
        "trade_key": "historic-001",
        "stop_time_utc": stop_time,
        "side": 1,
        "entry": 100.0,
        "stop": 99.0,
        "spread": 0.02,
        "runner_stopped_before_plus1": True,
    }


def _bars(start: pd.Timestamp) -> pd.DataFrame:
    index = pd.date_range(start, periods=10, freq="min")
    return pd.DataFrame(
        {"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0, "spread": 2.0},
        index=index,
    )


def test_historical_replay_accepts_only_pre_exam_rows():
    event = _event(EARLIEST + pd.Timedelta(days=1))
    result = simulate_historical_diagnostic(event, _bars(EARLIEST), exam_start=EXAM, earliest_data=EARLIEST)
    assert result["status"] == "PENDING_RECLAIM_HORIZON"
    with pytest.raises(ValueError, match="pre-boundary"):
        simulate_candidate(event, _bars(EARLIEST))


def test_historical_replay_rejects_locked_exam_event_and_bars():
    with pytest.raises(ValueError, match="locked exam"):
        simulate_historical_diagnostic(
            _event(EXAM),
            _bars(EXAM - pd.Timedelta(minutes=10)),
            exam_start=EXAM,
            earliest_data=EARLIEST,
        )
    with pytest.raises(ValueError, match="declared diagnostic boundary"):
        simulate_historical_diagnostic(
            _event(EXAM - pd.Timedelta(hours=1)),
            _bars(EXAM - pd.Timedelta(minutes=5)),
            exam_start=EXAM,
            earliest_data=EARLIEST,
        )
