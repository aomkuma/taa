from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from r2.bars import clock_bars, last_available_index
from r2.boundaries import DESIGN_END
from r2.data import load_design_m1, verify_frozen_inputs
from r2.features import FEATURE_COLUMNS, _price_features, add_prior_session_edge
from r2.model import action_reason, choose_action, fit_ridge, monthly_walk_forward, predict_ridge


def test_frozen_input_hashes_match() -> None:
    assert len(verify_frozen_inputs()) == 5


def test_exam_reader_boundary_is_not_overridable() -> None:
    with pytest.raises(ValueError, match="locked exam"):
        load_design_m1(end=DESIGN_END + pd.Timedelta(minutes=1))


def test_clock_bar_is_available_only_at_clock_end() -> None:
    times = pd.date_range("2026-01-05T10:00:00Z", periods=90, freq="min")
    m1 = pd.DataFrame(
        {"open_time": times, "open": np.arange(90), "high": np.arange(90) + 1, "low": np.arange(90) - 1, "close": np.arange(90) + 0.5}
    )
    bars = clock_bars(m1, "1h", cutoff=pd.Timestamp("2026-01-05T11:30:00Z"))
    assert len(bars) == 1
    assert bars.iloc[0]["available_at"] == pd.Timestamp("2026-01-05T11:00:00Z")
    assert bars.iloc[0]["close"] == 59.5


def test_availability_search_handles_microsecond_timestamp_units() -> None:
    values = pd.Series(pd.date_range("2025-01-01T00:00:00Z", periods=3, freq="h").as_unit("us"))
    assert last_available_index(values, pd.Timestamp("2025-01-01T01:30:00Z")) == 1


def test_hand_worked_price_features_use_only_completed_history() -> None:
    available = pd.date_range("2026-01-01T01:00:00Z", periods=130, freq="h")
    h1 = pd.DataFrame(
        {
            "available_at": available,
            "close": np.arange(130, dtype=float),
            "high": np.arange(130, dtype=float) + 4,
            "low": np.arange(130, dtype=float) - 4,
            "atr": np.r_[np.arange(1, 121, dtype=float), np.full(10, 60.0)],
        }
    )
    h4 = pd.DataFrame(
        {"available_at": available[3::4], "close": np.arange(len(available[3::4]), dtype=float) * 8.0}
    )
    daily = pd.DataFrame(
        {"available_at": [available[127]], "high": [131.0], "low": [110.0]}
    )
    entry = pd.Series({"trade_key": "X", "entry_time": available[128] + pd.Timedelta(minutes=1), "side": 1, "entry": 129.0})
    result = _price_features(entry, h1, h4, daily)
    assert result["h1_flow_6_atr"] == pytest.approx(6 / 60)
    assert result["h4_flow_3_atr"] == pytest.approx(24 / 60)
    assert result["open_space_atr"] == pytest.approx(2 / 60)
    # Current ATR is compared with rows 9..128, not with itself or row 129/future.
    expected = np.mean(h1.iloc[9:129]["atr"].to_numpy() <= 60.0)
    assert result["h1_atr_percentile_120"] == pytest.approx(expected)
    changed = h1.copy()
    changed.loc[129, ["close", "high", "low", "atr"]] = [9999.0, 9999.0, -9999.0, 9999.0]
    assert _price_features(entry, changed, h4, daily) == result


def test_session_edge_excludes_current_future_and_unfinished_outcomes() -> None:
    base = pd.Timestamp("2026-01-01T00:00:00Z")
    rows = []
    for index in range(7):
        entry = base + pd.Timedelta(days=index)
        rows.append(
            {
                "window": "ASIA",
                "entry_time": entry,
                "outcome_available": entry + pd.Timedelta(hours=1),
                "fast_r": 0.0,
                "runner_r": float(index + 1),
            }
        )
    # This older entry is not completed when row 6 enters and must be excluded.
    rows[5]["outcome_available"] = base + pd.Timedelta(days=20)
    result = add_prior_session_edge(pd.DataFrame(rows))
    assert result.iloc[4]["prior_session_runner_edge"] == 0.0
    assert result.iloc[6]["prior_session_runner_edge"] == pytest.approx(2.0)  # mean 1..5, clipped


def _model_panel() -> pd.DataFrame:
    times = pd.date_range("2025-10-01T12:00:00Z", periods=150, freq="D")
    frame = pd.DataFrame({"trade_key": [f"T{i}" for i in range(len(times))], "entry_time": times})
    frame["outcome_available"] = frame["entry_time"] + pd.Timedelta(hours=2)
    for index, name in enumerate(FEATURE_COLUMNS):
        frame[name] = np.sin(np.arange(len(frame)) / (index + 2))
    frame["fast_r"] = np.cos(np.arange(len(frame)) / 5)
    frame["runner_r"] = np.sin(np.arange(len(frame)) / 7) * 2
    frame["fast_usd"] = frame["fast_r"]
    frame["runner_usd"] = frame["runner_r"]
    return frame


def test_monthly_model_is_invariant_to_current_and_future_outcome_changes() -> None:
    panel = _model_panel()
    original, _ = monthly_walk_forward(panel)
    altered = panel.copy()
    cutoff = pd.Timestamp("2026-02-01T00:00:00Z")
    altered.loc[altered["entry_time"] >= cutoff, ["fast_r", "runner_r"]] = [9999.0, -9999.0]
    changed, _ = monthly_walk_forward(altered)
    left = original.loc[original["refit_month"] == "2026-02", ["trade_key", "pred_fast", "pred_runner", "action"]]
    right = changed.loc[changed["refit_month"] == "2026-02", ["trade_key", "pred_fast", "pred_runner", "action"]]
    pd.testing.assert_frame_equal(left.reset_index(drop=True), right.reset_index(drop=True))


def test_training_requires_outcome_before_refit() -> None:
    panel = _model_panel()
    january = (panel["entry_time"] >= "2025-11-01") & (panel["entry_time"] < "2026-01-01")
    panel.loc[january, "outcome_available"] = pd.Timestamp("2026-04-01T00:00:00Z")
    predictions, _ = monthly_walk_forward(panel)
    assert predictions.empty or "2026-01" not in set(predictions["refit_month"])


def test_ridge_uses_training_scaler_and_clips_target() -> None:
    x = pd.DataFrame(np.arange(33, dtype=float).reshape(3, 11), columns=FEATURE_COLUMNS)
    y_extreme = pd.Series([0.0, 1.0, 1_000_000.0])
    y_clipped = pd.Series([0.0, 1.0, 5.0])
    first = fit_ridge(x, y_extreme, alpha=10)
    second = fit_ridge(x, y_clipped, alpha=10)
    np.testing.assert_allclose(first.coefficients, second.coefficients)
    prediction = predict_ridge(first, x.iloc[[0]])
    x_appended = pd.concat([x, pd.DataFrame([[1e9] * 11], columns=FEATURE_COLUMNS)], ignore_index=True)
    np.testing.assert_allclose(prediction, predict_ridge(first, x_appended.iloc[[0]]))


def test_action_thresholds_are_exact() -> None:
    fast = np.array([0.0, 0.0, -0.051, -0.05])
    runner = np.array([0.051, 0.05, -0.06, -0.2])
    assert choose_action(fast, runner).tolist() == ["RUNNER", "FAST", "SKIP", "FAST"]
    assert action_reason(fast, runner).tolist() == [
        "runner_exceeds_fast_by_margin",
        "fast_default_or_runner_margin_not_met",
        "both_predictions_below_skip_threshold",
        "fast_default_or_runner_margin_not_met",
    ]


def test_isolation_import_guard() -> None:
    root = Path(__file__).resolve().parents[1] / "r2"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    forbidden = ["from tr1", "import tr1", "from app", "import app", "config.yaml", "DEMO", "LIVE"]
    assert not [token for token in forbidden if token in source]
