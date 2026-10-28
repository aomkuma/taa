"""Frozen monthly ensemble used by TR3."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import FEATURE_COLUMNS

WINDOWS = (60, 90, 120)
ALPHA = 20.0
MINIMUM_TRAIN = 60
TARGET_LOW = -1.5
TARGET_HIGH = 5.0


@dataclass(frozen=True)
class RidgeFit:
    medians: np.ndarray
    means: np.ndarray
    scales: np.ndarray
    coefficients: np.ndarray


def fit_ridge(x: pd.DataFrame, y: pd.Series, *, alpha: float = ALPHA) -> RidgeFit:
    matrix = x.to_numpy(dtype=float)
    medians = np.nanmedian(matrix, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    matrix = np.where(np.isnan(matrix), medians, matrix)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    standardized = np.clip((matrix - means) / scales, -3.0, 3.0)
    design = np.column_stack([np.ones(len(matrix)), standardized])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    target = np.clip(y.to_numpy(dtype=float), TARGET_LOW, TARGET_HIGH)
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target)
    return RidgeFit(medians, means, scales, coefficients)


def predict(fit: RidgeFit, x: pd.DataFrame) -> np.ndarray:
    matrix = x.to_numpy(dtype=float)
    matrix = np.where(np.isnan(matrix), fit.medians, matrix)
    standardized = np.clip((matrix - fit.means) / fit.scales, -3.0, 3.0)
    return fit.coefficients[0] + standardized @ fit.coefficients[1:]


def ensemble_decision(
    components: np.ndarray,
    *,
    threshold: float = 0.05,
    disagreement_penalty: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    median = np.median(components, axis=1)
    disagreement = np.std(components, axis=1, ddof=0)
    score = median - disagreement_penalty * disagreement
    positive_votes = np.sum(components > 0.0, axis=1)
    action = np.where((score > threshold) & (positive_votes >= 2), "RUNNER", "SKIP")
    return action, median, disagreement, positive_votes


def action_reasons(
    action: np.ndarray,
    score: np.ndarray,
    positive_votes: np.ndarray,
    threshold: float,
) -> np.ndarray:
    return np.where(
        action == "RUNNER",
        "ensemble_confident_and_majority_positive",
        np.where(
            score <= threshold,
            "confidence_score_not_above_threshold",
            "positive_vote_requirement_not_met",
        ),
    )


def monthly_walk_forward(
    panel: pd.DataFrame,
    *,
    threshold: float = 0.05,
    disagreement_penalty: float = 0.5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = panel.sort_values(["entry_time", "trade_key"]).reset_index(drop=True).copy()
    months = ordered["entry_time"].dt.tz_localize(None).dt.to_period("M").unique()
    scored_frames: list[pd.DataFrame] = []
    coefficient_rows: list[dict[str, object]] = []
    for period in months:
        month_start = period.start_time.tz_localize("UTC")
        month_end = (period + 1).start_time.tz_localize("UTC")
        test = ordered.loc[
            (ordered["entry_time"] >= month_start) & (ordered["entry_time"] < month_end)
        ].copy()
        if test.empty:
            continue
        predictions: list[np.ndarray] = []
        fits: list[tuple[int, pd.DataFrame, RidgeFit]] = []
        for window_days in WINDOWS:
            train_start = month_start - pd.Timedelta(days=window_days)
            train = ordered.loc[
                (ordered["entry_time"] >= train_start)
                & (ordered["entry_time"] < month_start)
                & (ordered["runner_exit_time"] < month_start)
            ]
            if len(train) < MINIMUM_TRAIN:
                fits = []
                break
            fit = fit_ridge(train[FEATURE_COLUMNS], train["runner_r"])
            predictions.append(predict(fit, test[FEATURE_COLUMNS]))
            fits.append((window_days, train, fit))
        if not fits:
            continue
        components = np.column_stack(predictions)
        action, median, disagreement, votes = ensemble_decision(
            components, threshold=threshold, disagreement_penalty=disagreement_penalty
        )
        score = median - disagreement_penalty * disagreement
        for index, window_days in enumerate(WINDOWS):
            test[f"pred_w{window_days}"] = components[:, index]
        test["ensemble_median"] = median
        test["ensemble_disagreement"] = disagreement
        test["confidence_score"] = score
        test["positive_votes"] = votes
        test["action"] = action
        test["action_reason"] = action_reasons(action, score, votes, threshold)
        test["selected_r"] = np.where(action == "RUNNER", test["runner_r"], 0.0)
        test["selected_usd_fixed_001"] = np.where(action == "RUNNER", test["runner_usd"], 0.0)
        test["selected_usd_risk10"] = test["selected_r"] * 10.0
        test["refit_month"] = str(period)
        scored_frames.append(test)
        for window_days, train, fit in fits:
            row: dict[str, object] = {
                "refit_month": str(period),
                "window_days": window_days,
                "train_count": len(train),
                "train_start": month_start - pd.Timedelta(days=window_days),
                "train_end_exclusive": month_start,
                "intercept": fit.coefficients[0],
            }
            row.update(
                {name: value for name, value in zip(FEATURE_COLUMNS, fit.coefficients[1:], strict=True)}
            )
            coefficient_rows.append(row)
    if not scored_frames:
        return pd.DataFrame(), pd.DataFrame(coefficient_rows)
    return pd.concat(scored_frames, ignore_index=True), pd.DataFrame(coefficient_rows)
