"""Representative mutants for the TR3 causal ensemble."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from r3.data import FEATURE_COLUMNS  # noqa: E402
from r3.model import ensemble_decision, fit_ridge  # noqa: E402


def main() -> None:
    caught: dict[str, bool] = {}

    refit = pd.Timestamp("2026-02-01T00:00:00Z")
    rows = pd.DataFrame(
        {
            "entry_time": [refit - pd.Timedelta(days=1), refit + pd.Timedelta(days=1)],
            "runner_exit_time": [refit + pd.Timedelta(hours=1), refit + pd.Timedelta(days=2)],
        }
    )
    correct = (rows["entry_time"] < refit) & (rows["runner_exit_time"] < refit)
    entry_only = rows["entry_time"] < refit
    current_month = rows["entry_time"] < refit + pd.Timedelta(days=28)
    caught["unfinished_outcome_in_training"] = int(correct.sum()) != int(entry_only.sum())
    caught["current_month_in_training"] = int(correct.sum()) != int(current_month.sum())

    x = pd.DataFrame(np.arange(55, dtype=float).reshape(5, 11), columns=FEATURE_COLUMNS)
    reference = fit_ridge(x, pd.Series([0.0, 1.0, 2.0, 3.0, 99999.0]))
    clipped = fit_ridge(x, pd.Series([0.0, 1.0, 2.0, 3.0, 5.0]))
    caught["target_not_clipped"] = bool(np.allclose(reference.coefficients, clipped.coefficients))

    train = x.to_numpy()
    future = np.full((1, 11), 1e12)
    caught["global_scaler"] = not np.allclose(train.mean(axis=0), np.vstack([train, future]).mean(axis=0))

    design = np.ones((5, 2))
    target = np.full(5, 2.0)
    free_intercept = np.linalg.solve(design.T @ design + np.diag([0.0, 20.0]), design.T @ target)
    penalized = np.linalg.solve(design.T @ design + np.diag([20.0, 20.0]), design.T @ target)
    caught["intercept_penalized"] = not np.allclose(free_intercept, penalized)

    components = np.array([[0.20, 0.20, -0.50], [0.20, -0.01, -0.02], [0.05, 0.05, 0.05]])
    action, median, _, _ = ensemble_decision(components)
    no_disagreement = np.where(median > 0.05, "RUNNER", "SKIP")
    non_strict = np.where((median - 0.5 * np.std(components, axis=1)) >= 0.05, "RUNNER", "SKIP")
    caught["disagreement_penalty_removed"] = not np.array_equal(action, no_disagreement)
    score = median - 0.5 * np.std(components, axis=1)
    votes = np.sum(components > 0, axis=1)
    caught["positive_vote_redundancy_proved"] = bool(np.all((score > 0.05) <= (votes >= 2)))
    caught["strict_threshold_removed"] = not np.array_equal(action, non_strict)

    caught = {name: bool(value) for name, value in caught.items()}
    failures = [name for name, value in caught.items() if not value]
    report = {"status": "PASS" if not failures else "FAIL", "caught": caught, "caught_count": sum(caught.values())}
    (ROOT / "mutation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if failures:
        raise AssertionError(f"Mutants survived: {failures}")


if __name__ == "__main__":
    main()
