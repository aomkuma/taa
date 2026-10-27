"""Method audit: compare the M1 approximation with frozen P1/P2 tick results."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "2026-10-20-trend-runner"


def utc(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for name in columns:
        result[name] = pd.to_datetime(result[name], utc=True)
    return result


def main() -> None:
    m1_entries = utc(pd.read_parquet(HERE / "entries_m1_approx.parquet"),
                     ["anchor", "entry_time", "impulse_decision", "pivot_time", "pivot_available", "decision_time"])
    m1_outcomes = utc(pd.read_parquet(HERE / "outcomes_m1_approx.parquet"),
                      ["anchor", "entry_time", "fast_exit_time", "runner_exit_time", "outcome_available"])
    m1 = m1_entries.merge(
        m1_outcomes[["trade_key", "fast_r", "runner_r", "fast_exit_time", "runner_exit_time"]],
        on="trade_key", validate="one_to_one", suffixes=("", "_outcome"),
    )
    report: dict[str, object] = {}
    for period in ("p1", "p2"):
        reference = utc(pd.read_parquet(BASE / f"frozen_entries_{period}.parquet"),
                        ["anchor", "entry_time", "impulse_decision", "pivot_time", "pivot_available", "decision_time"])
        results = utc(pd.read_parquet(BASE / f"frozen_results_{period}.parquet"), ["entry_time", "exit_time"])
        reference = reference.reset_index(drop=True).reset_index(names="entry_id")
        outcomes = results.loc[results["family"].isin(["FAST", "SPLIT"])]
        wide = outcomes.pivot(index="entry_id", columns="family", values="r").rename(
            columns={"FAST": "tick_fast_r", "SPLIT": "tick_runner_r"}
        )
        reference = reference.merge(wide, left_on="entry_id", right_index=True, validate="one_to_one")
        joined = reference.merge(m1, on=["window", "anchor"], how="left", suffixes=("_tick", "_m1"), validate="one_to_one")
        matched = joined.dropna(subset=["trade_key"]).copy()
        signal_fields = ["side", "impulse_decision", "pivot_time", "pivot_available", "decision_time"]
        signal_equal = np.ones(len(matched), dtype=bool)
        for field in signal_fields:
            signal_equal &= matched[f"{field}_tick"].to_numpy() == matched[f"{field}_m1"].to_numpy()
        outcome_rows = []
        m1_o = m1.set_index(["window", "anchor"])
        for row in reference.itertuples(index=False):
            key = (row.window, row.anchor)
            if key not in m1_o.index:
                continue
            approx = m1_o.loc[key]
            if isinstance(approx, pd.DataFrame):
                approx = approx.iloc[0]
            outcome_rows.append({
                "tick_fast_r": row.tick_fast_r,
                "tick_runner_r": row.tick_runner_r,
                "m1_fast_r": float(approx["fast_r"]),
                "m1_runner_r": float(approx["runner_r"]),
            })
        outcome_frame = pd.DataFrame(outcome_rows)
        outcomes_audit = {}
        for family in ("fast", "runner"):
            delta = outcome_frame[f"m1_{family}_r"] - outcome_frame[f"tick_{family}_r"]
            outcomes_audit[family] = {
                "matched_n": int(len(delta)),
                "tick_mean_r": float(outcome_frame[f"tick_{family}_r"].mean()),
                "m1_mean_r": float(outcome_frame[f"m1_{family}_r"].mean()),
                "tick_total_r": float(outcome_frame[f"tick_{family}_r"].sum()),
                "m1_total_r": float(outcome_frame[f"m1_{family}_r"].sum()),
                "mean_absolute_error_r": float(delta.abs().mean()),
                "same_profit_sign_rate": float((np.sign(outcome_frame[f"m1_{family}_r"]) == np.sign(outcome_frame[f"tick_{family}_r"])).mean()),
            }
        report[period.upper()] = {
            "frozen_entries": int(len(reference)),
            "matched_anchors": int(len(matched)),
            "anchor_match_rate": float(len(matched) / len(reference)),
            "exact_direction_and_signal_times": int(signal_equal.sum()),
            "exact_signal_time_rate_among_matches": float(signal_equal.mean()) if len(matched) else None,
            "median_absolute_entry_price_difference": float((matched["entry_m1"] - matched["entry_tick"]).abs().median()) if len(matched) else None,
                "mean_absolute_entry_price_difference": float((matched["entry_m1"] - matched["entry_tick"]).abs().mean()) if len(matched) else None,
            "median_absolute_initial_risk_difference": float((matched["risk_m1"] - matched["risk_tick"]).abs().median()) if len(matched) else None,
                "mean_absolute_initial_risk_difference": float((matched["risk_m1"] - matched["risk_tick"]).abs().mean()) if len(matched) else None,
            "outcomes": outcomes_audit,
        }
    (HERE / "method_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    results_path = HERE / "RESULTS.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    results["method_audit_vs_frozen_tick_p1_p2"] = report
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
