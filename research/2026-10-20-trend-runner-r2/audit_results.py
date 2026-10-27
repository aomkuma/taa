"""Post-measurement diagnostics derived from the frozen primary output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from r2.features import FEATURE_COLUMNS  # noqa: E402
from r2.model import action_reason  # noqa: E402


def grouped(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        frame.loc[frame["action"] != "SKIP"]
        .groupby(column)
        .agg(trades=("selected_r", "size"), total_r=("selected_r", "sum"), mean_r=("selected_r", "mean"))
        .reset_index()
    )


def main() -> None:
    predictions = pd.read_parquet(ROOT / "predictions_primary.parquet")
    predictions["action_reason"] = action_reason(
        predictions["pred_fast"].to_numpy(), predictions["pred_runner"].to_numpy()
    )
    predictions.to_parquet(ROOT / "decisions_primary.parquet", index=False)
    predictions["iso_week"] = predictions["entry_time"].dt.strftime("%G-W%V")
    grouped(predictions, "iso_week").to_csv(ROOT / "cut_week.csv", index=False)

    for column in ("refit_month", "window"):
        matrix = pd.crosstab(predictions[column], predictions["action"], margins=True)
        matrix.to_csv(ROOT / f"action_frequency_{column}.csv")

    coefficients = pd.read_parquet(ROOT / "coefficients_primary.parquet")
    stability_rows: list[dict[str, object]] = []
    for target, target_frame in coefficients.groupby("target"):
        target_frame = target_frame.sort_values("refit_month")
        for feature in ["intercept", *FEATURE_COLUMNS]:
            values = target_frame[feature].to_numpy(dtype=float)
            signs = np.sign(values)
            stability_rows.append(
                {
                    "target": target,
                    "feature": feature,
                    "minimum": values.min(),
                    "maximum": values.max(),
                    "std": values.std(ddof=0),
                    "sign_changes": int(np.sum(signs[1:] != signs[:-1])),
                }
            )
    stability = pd.DataFrame(stability_rows).sort_values(["sign_changes", "std"], ascending=False)
    stability.to_csv(ROOT / "coefficient_stability.csv", index=False)

    executed = predictions.loc[predictions["action"] != "SKIP"].copy()
    exact_error = np.abs(executed["selected_usd"] - executed["selected_r"] * executed["risk"])
    winners = executed.loc[executed["selected_r"] > 0, "risk"]
    losers = executed.loc[executed["selected_r"] < 0, "risk"]
    scaling = {
        "identity": "selected_usd = selected_r * initial price risk at 0.01 lot",
        "maximum_identity_error": float(exact_error.max()),
        "mean_initial_risk_all": float(executed["risk"].mean()),
        "mean_initial_risk_winners": float(winners.mean()),
        "mean_initial_risk_losers": float(losers.mean()),
        "median_initial_risk_winners": float(winners.median()),
        "median_initial_risk_losers": float(losers.median()),
        "r_total": float(executed["selected_r"].sum()),
        "usd_total": float(executed["selected_usd"].sum()),
        "explanation": (
            "R equalizes each trade by its stop distance, while fixed 0.01 lot does not. "
            "The selected losing trades had larger stop distances than the winners."
        ),
    }
    (ROOT / "sizing_audit.json").write_text(json.dumps(scaling, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
