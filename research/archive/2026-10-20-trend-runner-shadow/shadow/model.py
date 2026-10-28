"""Independent frozen TR3 ensemble math for forward-only rows."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .schema import FEATURE_COLUMNS

WINDOW_DAYS = (60, 90, 120)
ALPHA = 20.0
MINIMUM_TRAIN = 60


@dataclass(frozen=True)
class RidgeModel:
    medians: np.ndarray
    means: np.ndarray
    scales: np.ndarray
    coefficients: np.ndarray

    def payload(self) -> dict[str, list[float]]:
        return {
            "medians": self.medians.tolist(),
            "means": self.means.tolist(),
            "scales": self.scales.tolist(),
            "coefficients": self.coefficients.tolist(),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> RidgeModel:
        return cls(
            np.asarray(payload["medians"], dtype=float),
            np.asarray(payload["means"], dtype=float),
            np.asarray(payload["scales"], dtype=float),
            np.asarray(payload["coefficients"], dtype=float),
        )


def fit_ridge(features: pd.DataFrame, target: pd.Series) -> RidgeModel:
    matrix = features.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=float)
    medians = np.nanmedian(matrix, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    matrix = np.where(np.isnan(matrix), medians, matrix)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    standardized = np.clip((matrix - means) / scales, -3.0, 3.0)
    design = np.column_stack([np.ones(len(matrix)), standardized])
    penalty = np.eye(design.shape[1]) * ALPHA
    penalty[0, 0] = 0.0
    clipped = np.clip(target.to_numpy(dtype=float), -1.5, 5.0)
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ clipped)
    return RidgeModel(medians, means, scales, coefficients)


def predict(model: RidgeModel, features: dict[str, float]) -> float:
    matrix = np.asarray([[features[name] for name in FEATURE_COLUMNS]], dtype=float)
    matrix = np.where(np.isnan(matrix), model.medians, matrix)
    standardized = np.clip((matrix - model.means) / model.scales, -3.0, 3.0)
    return float((model.coefficients[0] + standardized @ model.coefficients[1:])[0])


def policy_action(predictions: list[float], *, threshold: float, penalty: float) -> dict[str, object]:
    values = np.asarray(predictions, dtype=float)
    median = float(np.median(values))
    disagreement = float(np.std(values, ddof=0))
    score = median - penalty * disagreement
    positive_votes = int(np.sum(values > 0))
    action = "RUNNER" if score > threshold and positive_votes >= 2 else "SKIP"
    reason = (
        "ensemble_confident_and_majority_positive"
        if action == "RUNNER"
        else "confidence_score_not_above_threshold"
        if score <= threshold
        else "positive_vote_requirement_not_met"
    )
    return {
        "action": action,
        "reason": reason,
        "median": median,
        "disagreement": disagreement,
        "score": score,
        "positive_votes": positive_votes,
    }
