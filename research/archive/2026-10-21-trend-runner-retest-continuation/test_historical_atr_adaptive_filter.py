from __future__ import annotations

# Pytest assertions intentionally use Python's assertion syntax.
# ruff: noqa: S101
from datetime import timedelta

import pandas as pd
from historical_atr_adaptive_filter import replay


def event(key: str, index: int, r: float, regime: str = "NORMAL_OR_LOW") -> dict[str, object]:
    stop = pd.Timestamp("2024-01-01T00:00:00Z") + timedelta(days=7 * index)
    return {
        "trade_key": key,
        "decision_time": stop,
        "source_stop_time_utc": stop,
        "exit_time_utc": stop + timedelta(hours=1),
        "side": "BUY",
        "window": "LONDON",
        "status": "COMPLETE",
        "r": r,
        "atr_m15_pct": 0.5,
        "atr_m15_available_at": stop - timedelta(minutes=15),
        "atr_m30_pct": 0.5,
        "atr_m30_available_at": stop - timedelta(minutes=30),
        "atr_h1_pct": 0.5,
        "atr_h1_available_at": stop - timedelta(hours=1),
        "atr_composite_pct": 0.5,
        "atr_regime": regime,
    }


def test_atr_state_trains_only_on_prior_allowed_settled_trades():
    rows = [event(str(index), index, -1.0) for index in range(5)]
    rows.extend([event("blocked-sixth", 5, 4.0), event("seventh", 6, 1.0)])
    rows.append(event("other-regime", 7, 1.0, regime="HIGH"))

    decisions = replay(pd.DataFrame(rows))

    assert decisions.iloc[5]["action"] == "BLOCK_NONPOSITIVE_TRAILING"
    assert decisions.iloc[5]["prior_allowed_completed_n"] == 5
    assert decisions.iloc[6]["action"] == "BLOCK_NONPOSITIVE_TRAILING"
    assert decisions.iloc[6]["prior_allowed_completed_n"] == 5
    assert decisions.iloc[7]["action"] == "ALLOW_WARMUP"
    assert decisions.iloc[7]["prior_allowed_completed_n"] == 0
    assert decisions.iloc[7]["fixed_atr_action"] == "BLOCK_HIGH_ATR"
    assert decisions.iloc[7]["fixed_atr_blocked_r"] == 1.0


def test_same_state_outcome_not_used_before_it_settles():
    rows = [
        event("long", 0, 10.0),
        event("overlap", 0, -1.0),
    ]

    decisions = replay(pd.DataFrame(rows))

    assert decisions.iloc[1]["prior_allowed_completed_n"] == 0
    assert decisions.iloc[1]["action"] == "ALLOW_WARMUP"
