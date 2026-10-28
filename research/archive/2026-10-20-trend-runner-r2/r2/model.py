"""Predeclared monthly walk-forward ridge selector."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS

TARGET_LOW = -1.5
TARGET_HIGH = 5.0
RUNNER_MARGIN = 0.05
SKIP_THRESHOLD = -0.05


@dataclass(frozen=True)
class RidgeFit:
    medians: np.ndarray
    means: np.ndarray
    scales: np.ndarray
    coefficients: np.ndarray


def fit_ridge(x: pd.DataFrame, y: pd.Series, *, alpha: float) -> RidgeFit:
    matrix = x.to_numpy(dtype=float)
    medians = np.nanmedian(matrix, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    matrix = np.where(np.isnan(matrix), medians, matrix)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    standardized = np.clip((matrix - means) / scales, -3.0, 3.0)
    design = np.column_stack([np.ones(len(standardized)), standardized])
    penalty = np.eye(design.shape[1]) * float(alpha)
    penalty[0, 0] = 0.0
    target = np.clip(y.to_numpy(dtype=float), TARGET_LOW, TARGET_HIGH)
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target)
    return RidgeFit(medians=medians, means=means, scales=scales, coefficients=coefficients)


def predict_ridge(fit: RidgeFit, x: pd.DataFrame) -> np.ndarray:
    matrix = x.to_numpy(dtype=float)
    matrix = np.where(np.isnan(matrix), fit.medians, matrix)
    standardized = np.clip((matrix - fit.means) / fit.scales, -3.0, 3.0)
    return fit.coefficients[0] + standardized @ fit.coefficients[1:]


def choose_action(pred_fast: np.ndarray, pred_runner: np.ndarray) -> np.ndarray:
    best = np.maximum(pred_fast, pred_runner)
    return np.where(
        best < SKIP_THRESHOLD,
        "SKIP",
        np.where(pred_runner > pred_fast + RUNNER_MARGIN, "RUNNER", "FAST"),
    )


def action_reason(pred_fast: np.ndarray, pred_runner: np.ndarray) -> np.ndarray:
    best = np.maximum(pred_fast, pred_runner)
    return np.where(
        best < SKIP_THRESHOLD,
        "both_predictions_below_skip_threshold",
        np.where(
            pred_runner > pred_fast + RUNNER_MARGIN,
            "runner_exceeds_fast_by_margin",
            "fast_default_or_runner_margin_not_met",
        ),
    )


def monthly_walk_forward(
    panel: pd.DataFrame,
    *,
    window_days: int = 90,
    alpha: float = 10.0,
    minimum_train: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = panel.sort_values(["entry_time", "trade_key"]).reset_index(drop=True).copy()
    predictions: list[pd.DataFrame] = []
    fit_records: list[dict[str, object]] = []
    months = ordered["entry_time"].dt.tz_localize(None).dt.to_period("M").unique()
    for period in months:
        month_start = period.start_time.tz_localize("UTC")
        month_end = (period + 1).start_time.tz_localize("UTC")
        train_start = month_start - pd.Timedelta(days=window_days)
        train = ordered.loc[
            (ordered["entry_time"] >= train_start)
            & (ordered["entry_time"] < month_start)
            & (ordered["outcome_available"] < month_start)
        ]
        test = ordered.loc[
            (ordered["entry_time"] >= month_start) & (ordered["entry_time"] < month_end)
        ].copy()
        if len(train) < minimum_train or test.empty:
            continue
        fast_fit = fit_ridge(train[FEATURE_COLUMNS], train["fast_r"], alpha=alpha)
        runner_fit = fit_ridge(train[FEATURE_COLUMNS], train["runner_r"], alpha=alpha)
        test["pred_fast"] = predict_ridge(fast_fit, test[FEATURE_COLUMNS])
        test["pred_runner"] = predict_ridge(runner_fit, test[FEATURE_COLUMNS])
        test["action"] = choose_action(test["pred_fast"].to_numpy(), test["pred_runner"].to_numpy())
        test["action_reason"] = action_reason(
            test["pred_fast"].to_numpy(), test["pred_runner"].to_numpy()
        )
        test["selected_r"] = np.select(
            [test["action"] == "FAST", test["action"] == "RUNNER"],
            [test["fast_r"], test["runner_r"]],
            default=0.0,
        )
        test["selected_usd"] = np.select(
            [test["action"] == "FAST", test["action"] == "RUNNER"],
            [test["fast_usd"], test["runner_usd"]],
            default=0.0,
        )
        test["refit_month"] = str(period)
        test["train_start"] = train_start
        test["train_end_exclusive"] = month_start
        test["train_count"] = len(train)
        predictions.append(test)
        for target_name, fit in (("FAST", fast_fit), ("RUNNER", runner_fit)):
            record: dict[str, object] = {
                "refit_month": str(period),
                "target": target_name,
                "window_days": window_days,
                "alpha": alpha,
                "train_count": len(train),
                "intercept": fit.coefficients[0],
            }
            record.update(
                {name: value for name, value in zip(FEATURE_COLUMNS, fit.coefficients[1:], strict=True)}
            )
            fit_records.append(record)
    if not predictions:
        return pd.DataFrame(), pd.DataFrame(fit_records)
    return pd.concat(predictions, ignore_index=True), pd.DataFrame(fit_records)
