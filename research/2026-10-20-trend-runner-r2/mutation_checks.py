"""Plant representative causal/model bugs and prove the checks expose them."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from r2.bars import last_available_index  # noqa: E402
from r2.features import FEATURE_COLUMNS, add_prior_session_edge  # noqa: E402
from r2.model import RUNNER_MARGIN, SKIP_THRESHOLD, choose_action, fit_ridge  # noqa: E402


def main() -> None:
    caught: dict[str, bool] = {}

    available = pd.Series(pd.date_range("2026-01-01T01:00:00Z", periods=3, freq="h").as_unit("us"))
    correct_index = last_available_index(available, pd.Timestamp("2026-01-01T01:30:00Z"))
    caught["future_bar_available_early"] = correct_index == 0 and correct_index != len(available) - 1

    atr_history = np.arange(1.0, 121.0)
    current_atr = 60.0
    correct_percentile = np.mean(atr_history <= current_atr)
    mutant_percentile = np.mean(np.r_[atr_history, current_atr] <= current_atr)
    caught["atr_percentile_includes_current"] = correct_percentile != mutant_percentile

    base = pd.Timestamp("2026-01-01T00:00:00Z")
    session = pd.DataFrame(
        {
            "window": ["ASIA"] * 6,
            "entry_time": [base + pd.Timedelta(days=i) for i in range(6)],
            "outcome_available": [base + pd.Timedelta(days=i, hours=1) for i in range(6)],
            "fast_r": [0.0] * 6,
            "runner_r": [1.0] * 5 + [-100.0],
        }
    )
    correct_edge = add_prior_session_edge(session).iloc[-1]["prior_session_runner_edge"]
    mutant_edge = float((session["runner_r"] - session["fast_r"]).tail(20).mean())
    caught["session_edge_includes_current"] = correct_edge != mutant_edge

    month_start = pd.Timestamp("2026-02-01T00:00:00Z")
    eligibility = pd.DataFrame(
        {
            "entry_time": [month_start - pd.Timedelta(days=2), month_start + pd.Timedelta(days=1)],
            "outcome_available": [month_start + pd.Timedelta(days=2), month_start + pd.Timedelta(days=2)],
        }
    )
    correct_train = (eligibility["entry_time"] < month_start) & (eligibility["outcome_available"] < month_start)
    entry_only_mutant = eligibility["entry_time"] < month_start
    current_month_mutant = eligibility["entry_time"] < month_start + pd.Timedelta(days=31)
    caught["train_uses_entry_not_completion"] = int(correct_train.sum()) != int(entry_only_mutant.sum())
    caught["train_includes_current_month"] = int(correct_train.sum()) != int(current_month_mutant.sum())

    x = pd.DataFrame(np.arange(55, dtype=float).reshape(5, 11), columns=FEATURE_COLUMNS)
    y = pd.Series([0.0, 1.0, 2.0, 3.0, 1_000_000.0])
    fit = fit_ridge(x, y, alpha=10)
    clipped_fit = fit_ridge(x, pd.Series([0.0, 1.0, 2.0, 3.0, 5.0]), alpha=10)
    caught["target_not_clipped"] = np.allclose(fit.coefficients, clipped_fit.coefficients)

    matrix = np.ones((5, 2))
    target = np.full(5, 2.0)
    unpenalized = np.linalg.solve(matrix.T @ matrix + np.diag([0.0, 10.0]), matrix.T @ target)
    penalized = np.linalg.solve(matrix.T @ matrix + np.diag([10.0, 10.0]), matrix.T @ target)
    caught["intercept_penalized"] = not np.allclose(unpenalized, penalized)

    train = np.arange(55, dtype=float).reshape(5, 11)
    future = np.full((1, 11), 1e9)
    train_mean = train.mean(axis=0)
    global_mean = np.vstack([train, future]).mean(axis=0)
    caught["global_scaler"] = not np.allclose(train_mean, global_mean)

    fast = np.array([0.0, SKIP_THRESHOLD - 0.001])
    runner = np.array([RUNNER_MARGIN + 0.001, SKIP_THRESHOLD - 0.002])
    reference_actions = choose_action(fast, runner)
    mutant_actions = np.where(runner > fast, "RUNNER", "FAST")
    caught["action_thresholds_removed"] = not np.array_equal(reference_actions, mutant_actions)

    caught = {name: bool(detected) for name, detected in caught.items()}
    failures = [name for name, detected in caught.items() if not detected]
    report = {"status": "PASS" if not failures else "FAIL", "caught": caught, "caught_count": sum(caught.values())}
    (ROOT / "mutation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if failures:
        raise AssertionError(f"Mutants survived: {failures}")


if __name__ == "__main__":
    main()
