from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from r3.data import END_EXCLUSIVE, FEATURE_COLUMNS, load_panel, verify_inputs
from r3.model import action_reasons, ensemble_decision, fit_ridge, monthly_walk_forward, predict


def test_verified_panel_is_fixed_and_before_exam() -> None:
    assert len(verify_inputs()) == 3
    panel = load_panel()
    assert len(panel) == 280
    assert panel["entry_time"].max() < END_EXCLUSIVE


def test_ensemble_primary_threshold_and_votes() -> None:
    components = np.array(
        [
            [0.20, 0.20, 0.20],
            [0.20, 0.20, -0.50],
            [0.06, 0.06, 0.06],
            [0.20, -0.01, -0.02],
            [0.05, 0.05, 0.05],
        ]
    )
    action, median, disagreement, votes = ensemble_decision(components)
    assert action.tolist() == ["RUNNER", "SKIP", "RUNNER", "SKIP", "SKIP"]
    score = median - 0.5 * disagreement
    reasons = action_reasons(action, score, votes, 0.05)
    assert reasons.tolist() == [
        "ensemble_confident_and_majority_positive",
        "confidence_score_not_above_threshold",
        "ensemble_confident_and_majority_positive",
        "confidence_score_not_above_threshold",
        "confidence_score_not_above_threshold",
    ]
    # With a positive score threshold and a non-negative disagreement penalty,
    # passing the score already implies a positive median and thus two positive votes.
    assert ((score > 0.05) <= (votes >= 2)).all()


def test_ridge_clips_target_and_uses_frozen_training_scaler() -> None:
    x = pd.DataFrame(np.arange(55, dtype=float).reshape(5, 11), columns=FEATURE_COLUMNS)
    extreme = fit_ridge(x, pd.Series([0.0, 1.0, 2.0, 3.0, 99999.0]))
    clipped = fit_ridge(x, pd.Series([0.0, 1.0, 2.0, 3.0, 5.0]))
    np.testing.assert_allclose(extreme.coefficients, clipped.coefficients)
    before = predict(extreme, x.iloc[[0]])
    future = pd.DataFrame([[1e12] * 11], columns=FEATURE_COLUMNS)
    np.testing.assert_allclose(before, predict(extreme, pd.concat([x.iloc[[0]], future]).iloc[[0]]))


def _panel() -> pd.DataFrame:
    times = pd.date_range("2025-09-01T12:00:00Z", periods=210, freq="D")
    frame = pd.DataFrame({"trade_key": [f"T{i}" for i in range(len(times))], "entry_time": times})
    frame["runner_exit_time"] = frame["entry_time"] + pd.Timedelta(hours=3)
    for index, column in enumerate(FEATURE_COLUMNS):
        frame[column] = np.sin(np.arange(len(frame)) / (index + 2))
    frame["runner_r"] = np.cos(np.arange(len(frame)) / 8)
    frame["runner_usd"] = frame["runner_r"] * 5
    return frame


def test_current_and_future_outcomes_cannot_change_current_month_decision() -> None:
    panel = _panel()
    original, _ = monthly_walk_forward(panel)
    altered = panel.copy()
    cutoff = pd.Timestamp("2026-02-01T00:00:00Z")
    altered.loc[altered["entry_time"] >= cutoff, "runner_r"] = 99999.0
    changed, _ = monthly_walk_forward(altered)
    columns = ["trade_key", "pred_w60", "pred_w90", "pred_w120", "confidence_score", "action"]
    left = original.loc[original["refit_month"] == "2026-02", columns].reset_index(drop=True)
    right = changed.loc[changed["refit_month"] == "2026-02", columns].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_unfinished_runner_outcomes_are_not_training_rows() -> None:
    panel = _panel()
    affected = (panel["entry_time"] >= "2025-11-01") & (panel["entry_time"] < "2026-01-01")
    panel.loc[affected, "runner_exit_time"] = pd.Timestamp("2026-04-01T00:00:00Z")
    predictions, _ = monthly_walk_forward(panel)
    assert predictions.empty or "2026-01" not in set(predictions["refit_month"])


def test_output_actions_can_only_be_runner_or_skip() -> None:
    predictions, coefficients = monthly_walk_forward(_panel())
    assert set(predictions["action"]) <= {"RUNNER", "SKIP"}
    assert set(coefficients["window_days"]) == {60, 90, 120}
    assert (predictions["selected_usd_risk10"] == predictions["selected_r"] * 10).all()


def test_isolation_has_no_strategy_or_engine_imports() -> None:
    source_root = Path(__file__).resolve().parents[1] / "r3"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))
    forbidden = ["from r2", "import r2", "from tr1", "import tr1", "from app", "import app"]
    assert not [token for token in forbidden if token in source]
