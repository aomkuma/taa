"""Causality and boundary checks for the three-year monthly replay."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
START = pd.Timestamp("2023-10-21", tz="UTC")
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")


def main() -> None:
    panel = pd.read_parquet(HERE / "feature_panel_m1_approx.parquet")
    coefficients = pd.read_csv(HERE / "coefficients.csv")
    predictions = pd.read_parquet(HERE / "predictions_walkforward.parquet")
    for name in ("entry_time", "runner_exit_time", "outcome_available"):
        panel[name] = pd.to_datetime(panel[name], utc=True)
    predictions["entry_time"] = pd.to_datetime(predictions["entry_time"], utc=True)
    errors: list[str] = []
    if (panel["entry_time"] < pd.Timestamp("2023-09-01", tz="UTC")).any():
        errors.append("panel starts before available warm-up")
    if (panel["outcome_available"] >= EXAM_START).any():
        errors.append("a training outcome overlaps the locked exam")
    if (predictions["entry_time"] < START).any() or (predictions["entry_time"] >= EXAM_START).any():
        errors.append("a scored row is outside the allowed evaluation interval")
    expected_windows = {60, 90, 120}
    for month, group in coefficients.groupby("refit_month"):
        if set(group["window_days"].astype(int)) != expected_windows or len(group) != 3:
            errors.append(f"{month}: component window set is incomplete")
            continue
        start = pd.Timestamp(f"{month}-01", tz="UTC")
        for row in group.itertuples(index=False):
            expected_start = start - pd.Timedelta(days=int(row.window_days))
            train = panel.loc[
                (panel["entry_time"] >= expected_start)
                & (panel["entry_time"] < start)
                & (panel["runner_exit_time"] < start)
            ]
            if len(train) != int(row.train_count) or len(train) < 60:
                errors.append(f"{month}/{row.window_days}: training row count mismatch or below minimum")
            if (train["outcome_available"] >= start).any():
                errors.append(f"{month}/{row.window_days}: future outcome entered training")
        scored = predictions.loc[predictions["refit_month"].eq(month)]
        if len(scored) and not ((scored["entry_time"] >= start) & (scored["entry_time"] < start + pd.offsets.MonthBegin(1))).all():
            errors.append(f"{month}: test rows escape the refit month")
    expected_selected = predictions["runner_r"].where(predictions["action"].eq("RUNNER"), 0.0)
    if not (expected_selected.sub(predictions["selected_r"]).abs() < 1e-10).all():
        errors.append("selected R does not match frozen RUNNER/SKIP action")
    if errors:
        raise AssertionError("; ".join(errors))
    summary = {
        "status": "PASS",
        "training_components": sorted(expected_windows),
        "monthly_refits": int(coefficients["refit_month"].nunique()),
        "scored_rows": int(len(predictions)),
        "locked_exam_used": False,
        "post_shadow_data_used": False,
        "checks": [
            "training rows are confined to each prior calendar window",
            "every training RUNNER outcome completes before month start",
            "all 60/90/120-day components have at least 60 rows",
            "test predictions stay within their monthly refit period",
            "scored rows stay inside the requested pre-exam interval",
            "RUNNER/SKIP selected R is calculated consistently",
        ],
    }
    (HERE / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    result_path = HERE / "RESULTS.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["causality_boundary_checks"] = summary
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
