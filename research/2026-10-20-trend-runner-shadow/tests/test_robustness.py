# ruff: noqa: S101
from __future__ import annotations

import numpy as np
import pandas as pd
from shadow.robustness import analyze_champion, moving_block_bootstrap


def frame(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "entry_time": pd.date_range("2027-01-01T00:00:00Z", periods=len(values), freq="1D"),
            "side": [1 if index % 2 == 0 else -1 for index in range(len(values))],
            "window": ["ASIA" if index % 2 == 0 else "LONDON" for index in range(len(values))],
            "runner_r": values,
        }
    )


def test_status_transitions_are_predeclared_and_cost_free() -> None:
    insufficient = analyze_champion(frame([1.0] * 19), evaluation_ready=False)
    collecting = analyze_champion(frame([1.0] * 25), evaluation_ready=False)
    robust = analyze_champion(frame([1.0] * 25), evaluation_ready=True)
    fragile = analyze_champion(frame([-1.0] * 17 + [10.0] * 3), evaluation_ready=True)
    not_positive = analyze_champion(frame([-1.0] * 20), evaluation_ready=True)

    assert insufficient["status"] == "INSUFFICIENT"
    assert collecting["status"] == "COLLECTING"
    assert robust["status"] == "ROBUST_POSITIVE"
    assert fragile["status"] == "FRAGILE_POSITIVE"
    assert not_positive["status"] == "NOT_POSITIVE"
    assert robust["hypothetical_slippage_stress"] == "EXCLUDED_BY_USER"
    assert "cost_stress" not in robust


def test_moving_block_bootstrap_is_deterministic() -> None:
    values = np.asarray([-1.0, 0.5, 2.0, -0.25, 1.5] * 4)
    first = moving_block_bootstrap(values)
    second = moving_block_bootstrap(values)
    assert first == second
    assert first["samples"] == 5_000
    assert first["block_length"] == 5


def test_group_cuts_preserve_completed_forward_rows() -> None:
    result = analyze_champion(frame([1.0] * 20), evaluation_ready=False)
    assert sum(row["trades"] for row in result["group_cuts"]["direction"]) == 20
    assert sum(row["trades"] for row in result["group_cuts"]["session"]) == 20
    assert result["rolling_20"]["fraction_positive"] == 1.0
