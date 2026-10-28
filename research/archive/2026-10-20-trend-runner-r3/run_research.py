"""Execute the single frozen TR3 primary and declared diagnostics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from r3.data import FEATURE_COLUMNS, load_panel, verify_inputs  # noqa: E402
from r3.model import monthly_walk_forward  # noqa: E402


def max_drawdown(values: np.ndarray) -> float:
    equity = np.r_[0.0, np.cumsum(values)]
    return float(np.max(np.maximum.accumulate(equity) - equity))


def losing_streak(values: np.ndarray) -> int:
    current = maximum = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        maximum = max(maximum, current)
    return maximum


def bootstrap_interval(values: np.ndarray) -> list[float]:
    rng = np.random.default_rng(20261020)
    means = rng.choice(values, size=(10_000, len(values)), replace=True).mean(axis=1)
    return [float(value) for value in np.quantile(means, [0.025, 0.975])]


def metrics(r_values: pd.Series, fixed_usd: pd.Series, *, scored: int) -> dict[str, object]:
    values = r_values.to_numpy(dtype=float)
    best_first = np.sort(values)[::-1]
    return {
        "scored": scored,
        "executed": len(values),
        "total_r": float(values.sum()),
        "mean_r_executed": float(values.mean()),
        "mean_r_opportunity": float(values.sum() / scored),
        "bootstrap_95_mean_r": bootstrap_interval(values),
        "fixed_001_usd": float(fixed_usd.sum()),
        "risk_10_usd": float(values.sum() * 10.0),
        "win_rate": float(np.mean(values > 0)),
        "worst_r": float(values.min()),
        "max_drawdown_r": max_drawdown(values),
        "maximum_losing_streak": losing_streak(values),
        "total_without_best_one": float(best_first[1:].sum()),
        "total_without_best_three": float(best_first[3:].sum()),
    }


def group_cut(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        frame.loc[frame["action"] == "RUNNER"]
        .groupby(column)
        .agg(trades=("runner_r", "size"), total_r=("runner_r", "sum"), mean_r=("runner_r", "mean"))
        .reset_index()
    )


def diversity(cut: pd.DataFrame, total: float) -> bool:
    return bool(total > 0 and len(cut) > 1 and total - float(cut["total_r"].max()) > 0)


def coefficient_stability(coefficients: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for window, frame in coefficients.groupby("window_days"):
        ordered = frame.sort_values("refit_month")
        for feature in ["intercept", *FEATURE_COLUMNS]:
            values = ordered[feature].to_numpy(dtype=float)
            records.append(
                {
                    "window_days": window,
                    "feature": feature,
                    "minimum": values.min(),
                    "maximum": values.max(),
                    "std": values.std(ddof=0),
                    "sign_changes": int(np.sum(np.sign(values[1:]) != np.sign(values[:-1]))),
                }
            )
    return pd.DataFrame(records).sort_values(["sign_changes", "std"], ascending=False)


def main() -> None:
    mutation = json.loads((ROOT / "mutation_report.json").read_text(encoding="utf-8"))
    if mutation["status"] != "PASS":
        raise RuntimeError("Mutation checks must pass before measurement")
    panel = load_panel()
    primary, coefficients = monthly_walk_forward(panel)
    if primary.empty:
        raise ValueError("TR3 primary produced no scored rows")
    primary.to_parquet(ROOT / "predictions_primary.parquet", index=False)
    coefficients.to_parquet(ROOT / "coefficients_primary.parquet", index=False)
    coefficient_stability(coefficients).to_csv(ROOT / "coefficient_stability.csv", index=False)

    executed = primary.loc[primary["action"] == "RUNNER"]
    primary_metrics = metrics(executed["runner_r"], executed["runner_usd"], scored=len(primary))
    baseline_metrics = metrics(primary["runner_r"], primary["runner_usd"], scored=len(primary))
    primary["month"] = primary["entry_time"].dt.strftime("%Y-%m")
    primary["week"] = primary["entry_time"].dt.strftime("%G-W%V")
    primary["direction"] = np.where(primary["side"] == 1, "BUY", "SELL")
    cuts = {
        "month": group_cut(primary, "month"),
        "week": group_cut(primary, "week"),
        "session": group_cut(primary, "window"),
        "direction": group_cut(primary, "direction"),
    }
    for name, cut in cuts.items():
        cut.to_csv(ROOT / f"cut_{name}.csv", index=False)
    pd.crosstab(primary["month"], primary["action"], margins=True).to_csv(ROOT / "action_frequency.csv")

    diagnostics = [
        ("PRIMARY_T005_P05", 0.05, 0.5),
        ("DIAG_T000_P05", 0.00, 0.5),
        ("DIAG_T010_P05", 0.10, 0.5),
        ("DIAG_T005_P00", 0.05, 0.0),
        ("DIAG_T005_P10", 0.05, 1.0),
    ]
    diagnostic_rows: list[dict[str, object]] = []
    for name, threshold, penalty in diagnostics:
        scored, _ = monthly_walk_forward(panel, threshold=threshold, disagreement_penalty=penalty)
        selected = scored.loc[scored["action"] == "RUNNER"]
        diagnostic_rows.append(
            {
                "variant": name,
                "threshold": threshold,
                "disagreement_penalty": penalty,
                "scored": len(scored),
                "executed": len(selected),
                "total_r": selected["runner_r"].sum(),
                "mean_r": selected["runner_r"].mean(),
                "max_drawdown_r": max_drawdown(selected["runner_r"].to_numpy()),
            }
        )
    pd.DataFrame(diagnostic_rows).to_csv(ROOT / "diagnostics.csv", index=False)

    gates = {
        "at_least_100_scored": len(primary) >= 100,
        "at_least_60_executed": len(executed) >= 60,
        "mean_r_at_least_0_15": float(primary_metrics["mean_r_executed"]) >= 0.15,
        "mean_r_above_always_runner": float(primary_metrics["mean_r_executed"])
        > float(baseline_metrics["mean_r_executed"]),
        "retain_half_baseline_total_r": float(primary_metrics["total_r"])
        >= 0.5 * float(baseline_metrics["total_r"]),
        "non_negative_without_best": float(primary_metrics["total_without_best_one"]) >= 0,
        "drawdown_at_least_10pct_lower": float(primary_metrics["max_drawdown_r"])
        <= 0.9 * float(baseline_metrics["max_drawdown_r"]),
        "edge_outside_best_month": diversity(cuts["month"], float(primary_metrics["total_r"])),
        "edge_outside_best_session": diversity(cuts["session"], float(primary_metrics["total_r"])),
        "causal_and_mutation_checks": mutation["status"] == "PASS",
    }
    status = "FORWARD SHADOW CANDIDATE" if all(gates.values()) else "RESEARCH ONLY - NOT READY"
    result = {
        "status": status,
        "promotion_status": "NOT PROMOTED; all evidence is seen development data",
        "exam_used": False,
        "primary": primary_metrics,
        "always_runner": baseline_metrics,
        "action_counts": {str(key): int(value) for key, value in primary["action"].value_counts().items()},
        "gates": {key: bool(value) for key, value in gates.items()},
        "diagnostics": diagnostic_rows,
        "input_hashes": verify_inputs(),
        "mutation_checks": mutation,
    }
    (ROOT / "RESULTS.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_markdown(result, cuts)


def write_markdown(result: dict[str, object], cuts: dict[str, pd.DataFrame]) -> None:
    primary = result["primary"]
    baseline = result["always_runner"]
    lines = [
        "# TR3 design-only result",
        "",
        f"Status: **{result['status']}**. {result['promotion_status']}.",
        "",
        "The historical exam was not used. P1/P2/TR2 are all seen development evidence.",
        "",
        "## Primary robust ensemble",
        "",
        f"- Actions: {result['action_counts']}.",
        f"- {primary['executed']} executed from {primary['scored']} scored opportunities.",
        f"- {primary['total_r']:.3f}R total; {primary['mean_r_executed']:.3f}R per executed trade.",
        f"- Bootstrap 95% mean interval [{primary['bootstrap_95_mean_r'][0]:.3f}, "
        f"{primary['bootstrap_95_mean_r'][1]:.3f}].",
        f"- Drawdown {primary['max_drawdown_r']:.3f}R; losing streak {primary['maximum_losing_streak']}.",
        f"- Without best one {primary['total_without_best_one']:.3f}R; without best three "
        f"{primary['total_without_best_three']:.3f}R.",
        f"- Constant $10 risk: ${primary['risk_10_usd']:.2f}; fixed 0.01 lot audit: "
        f"${primary['fixed_001_usd']:.2f}.",
        "",
        "## Same-row always RUNNER baseline",
        "",
        f"- {baseline['total_r']:.3f}R total; {baseline['mean_r_executed']:.3f}R/trade; "
        f"drawdown {baseline['max_drawdown_r']:.3f}R.",
        "",
        "## Development gates",
        "",
    ]
    lines.extend(f"- {'PASS' if value else 'FAIL'}: {name}" for name, value in result["gates"].items())
    lines.extend(["", "## Group cuts", ""])
    for name, cut in cuts.items():
        lines.extend([f"### {name}", "", cut.to_string(index=False), ""])
    lines.extend(
        [
            "## Boundary",
            "",
            "No result here is independent validation. Diagnostics cannot replace the frozen primary. A candidate "
            "must be evaluated on genuinely new forward observations before any integration decision.",
            "",
        ]
    )
    (ROOT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
