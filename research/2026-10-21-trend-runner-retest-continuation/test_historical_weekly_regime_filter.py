from __future__ import annotations

# Pytest assertions intentionally use Python's assertion syntax.
# ruff: noqa: S101
from datetime import timedelta

import pandas as pd
from historical_weekly_regime_filter import replay


def event(key: str, stop, exit_time, r: float) -> dict[str, object]:
    return {
        "trade_key": key,
        "source_stop_time_utc": stop,
        "exit_time_utc": exit_time,
        "side": "BUY",
        "window": "LONDON",
        "status": "COMPLETE",
        "r": r,
    }


def test_prior_allowed_completed_history_controls_later_week():
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    rows = []
    for index in range(5):
        stop = start + timedelta(days=7 * index)
        rows.append(event(str(index), stop, stop + timedelta(hours=2), 1.0))
    stop = start + timedelta(days=35)
    rows.append(event("sixth", stop, stop + timedelta(hours=2), -1.0))

    decisions = replay(pd.DataFrame(rows))

    assert decisions.iloc[:5]["action"].tolist() == ["ALLOW_WARMUP"] * 5
    assert decisions.iloc[5]["prior_allowed_completed_n"] == 5
    assert decisions.iloc[5]["action"] == "ALLOW_POSITIVE_TRAILING"


def test_unsettled_prior_attempt_cannot_leak_its_future_result():
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    rows = [
        event("still_open", start, start + timedelta(days=2), 10.0),
        event("next_day", start + timedelta(days=1), start + timedelta(days=1, hours=2), -1.0),
    ]

    decisions = replay(pd.DataFrame(rows))

    assert decisions.iloc[1]["prior_allowed_completed_n"] == 0
    assert decisions.iloc[1]["action"] == "ALLOW_WARMUP"
