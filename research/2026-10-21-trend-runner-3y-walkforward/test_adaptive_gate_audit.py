# ruff: noqa: S101
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adaptive_gate_audit import prepare, replay


def test_gate_uses_only_prior_weeks_and_only_blocks_high_atr() -> None:
    rows = [
        {
            "trade_key": f"prior-{index}",
            "entry_time_utc": f"2025-01-06T0{index}:00:00Z",
            "action": "RUNNER",
            "window": "LONDON",
            "runner_r": -1.0,
            "h1_atr_percentile_120": 0.9,
        }
        for index in range(10)
    ]
    rows.extend(
        [
            {
                "trade_key": "current-high",
                "entry_time_utc": "2025-02-03T06:00:00Z",
                "action": "RUNNER",
                "window": "LONDON",
                "runner_r": 5.0,
                "h1_atr_percentile_120": 0.9,
            },
            {
                "trade_key": "current-normal",
                "entry_time_utc": "2025-02-03T07:00:00Z",
                "action": "RUNNER",
                "window": "LONDON",
                "runner_r": -1.0,
                "h1_atr_percentile_120": 0.5,
            },
        ]
    )

    trades, decisions = replay(prepare(pd.DataFrame(rows)))
    current = trades.loc[trades["trade_key"].str.startswith("current-")].set_index("trade_key")

    assert not current.loc["current-high", "adaptive_keep"]
    assert current.loc["current-normal", "adaptive_keep"]
    assert decisions.iloc[-1]["prior_high_atr_trades_52w"] == 10
    assert decisions.iloc[-1]["prior_high_atr_runner_r_52w"] == -10.0


def test_current_week_outcomes_cannot_disable_their_own_week() -> None:
    rows = [
        {
            "trade_key": "current-1",
            "entry_time_utc": "2025-01-06T06:00:00Z",
            "action": "RUNNER",
            "window": "LONDON",
            "runner_r": -1.0,
            "h1_atr_percentile_120": 0.9,
        }
        for _ in range(10)
    ]
    rows = [dict(row, trade_key=f"current-{index}") for index, row in enumerate(rows)]

    trades, decisions = replay(prepare(pd.DataFrame(rows)))

    assert trades["adaptive_keep"].all()
    assert not decisions["skip_high_atr_this_week"].any()
