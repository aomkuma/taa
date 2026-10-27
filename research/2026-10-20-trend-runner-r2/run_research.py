"""Run the single predeclared design-only TR2 walk-forward and write its audit artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from r2.data import verify_frozen_inputs  # noqa: E402
from r2.features import FEATURE_COLUMNS  # noqa: E402
from r2.model import monthly_walk_forward  # noqa: E402


def _native(value: object) -> object:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def max_drawdown(values: np.ndarray) -> float:
    equity = np.r_[0.0, np.cumsum(values)]
    peaks = np.maximum.accumulate(equity)
    return float(np.max(peaks - equity))


def maximum_losing_streak(values: np.ndarray) -> int:
    best = current = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        best = max(best, current)
    return best


def bootstrap_mean_interval(values: np.ndarray) -> list[float]:
    if len(values) == 0:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(20261020)
    samples = rng.choice(values, size=(10_000, len(values)), replace=True).mean(axis=1)
    return [float(value) for value in np.quantile(samples, [0.025, 0.975])]


def performance(values: pd.Series, usd: pd.Series, *, scored: int, action_counts: dict[str, int]) -> dict[str, object]:
    array = values.to_numpy(dtype=float)
    ordered = np.sort(array)[::-1]
    return {
        "scored_opportunities": scored,
        "executed_trades": len(array),
        "action_counts": action_counts,
        "total_r": float(array.sum()),
        "mean_r_per_executed": float(array.mean()) if len(array) else float("nan"),
        "mean_r_per_opportunity": float(array.sum() / scored) if scored else float("nan"),
        "total_usd_001": float(usd.sum()),
        "bootstrap_95_mean_r": bootstrap_mean_interval(array),
        "win_rate": float(np.mean(array > 0)) if len(array) else float("nan"),
        "worst_trade_r": float(array.min()) if len(array) else float("nan"),
        "max_drawdown_r": max_drawdown(array),
        "maximum_losing_streak": maximum_losing_streak(array),
        "total_r_without_best_one": float(ordered[1:].sum()) if len(ordered) > 1 else 0.0,
        "total_r_without_best_three": float(ordered[3:].sum()) if len(ordered) > 3 else 0.0,
    }


def group_cut(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    executed = frame.loc[frame["action"] != "SKIP"].copy()
    return (
        executed.groupby(column, dropna=False)
        .agg(trades=("selected_r", "size"), total_r=("selected_r", "sum"), mean_r=("selected_r", "mean"))
        .reset_index()
    )


def diversity_gate(cut: pd.DataFrame, total: float) -> bool:
    return bool(total > 0 and len(cut) > 1 and total - float(cut["total_r"].max()) > 0)


def main() -> None:
    verify_frozen_inputs()
    verification = json.loads((ROOT / "feature_verification.json").read_text(encoding="utf-8"))
    mutations = json.loads((ROOT / "mutation_report.json").read_text(encoding="utf-8"))
    if verification["status"] != "PASS" or mutations["status"] != "PASS":
        raise RuntimeError("Causal verification must pass before measurement")

    panel = pd.read_parquet(ROOT / "feature_panel.parquet")
    if len(panel) != 280 or panel[FEATURE_COLUMNS].isna().any().any():
        raise ValueError("Feature panel is incomplete")
    primary, coefficients = monthly_walk_forward(panel, window_days=90, alpha=10)
    if primary.empty:
        raise ValueError("Primary produced no scored opportunities")
    primary.to_parquet(ROOT / "predictions_primary.parquet", index=False)
    coefficients.to_parquet(ROOT / "coefficients_primary.parquet", index=False)

    executed = primary.loc[primary["action"] != "SKIP"]
    action_counts = {str(key): int(value) for key, value in primary["action"].value_counts().items()}
    strategies = {
        "PRIMARY": performance(
            executed["selected_r"], executed["selected_usd"], scored=len(primary), action_counts=action_counts
        ),
        "ALWAYS_FAST": performance(
            primary["fast_r"],
            primary["fast_usd"],
            scored=len(primary),
            action_counts={"FAST": len(primary)},
        ),
        "ALWAYS_RUNNER": performance(
            primary["runner_r"],
            primary["runner_usd"],
            scored=len(primary),
            action_counts={"RUNNER": len(primary)},
        ),
    }

    primary = primary.assign(entry_month=primary["entry_time"].dt.strftime("%Y-%m"))
    primary = primary.assign(direction=np.where(primary["side"] == 1, "BUY", "SELL"))
    cuts = {
        "month": group_cut(primary, "entry_month"),
        "session": group_cut(primary, "window"),
        "direction": group_cut(primary, "direction"),
        "action": group_cut(primary, "action"),
    }
    for name, cut in cuts.items():
        cut.to_csv(ROOT / f"cut_{name}.csv", index=False)

    variants = [
        ("PRIMARY_A10_W90", 90, 10.0),
        ("SENS_A5_W90", 90, 5.0),
        ("SENS_A20_W90", 90, 20.0),
        ("SENS_A10_W60", 60, 10.0),
        ("SENS_A10_W120", 120, 10.0),
    ]
    sensitivity_rows: list[dict[str, object]] = []
    for name, days, alpha in variants:
        scored, _ = monthly_walk_forward(panel, window_days=days, alpha=alpha)
        selected = scored.loc[scored["action"] != "SKIP"]
        sensitivity_rows.append(
            {
                "variant": name,
                "window_days": days,
                "alpha": alpha,
                "scored": len(scored),
                "executed": len(selected),
                "mean_r": selected["selected_r"].mean(),
                "total_r": selected["selected_r"].sum(),
                "max_drawdown_r": max_drawdown(selected["selected_r"].to_numpy()),
                "fast": int((scored["action"] == "FAST").sum()),
                "runner": int((scored["action"] == "RUNNER").sum()),
                "skip": int((scored["action"] == "SKIP").sum()),
            }
        )
    sensitivities = pd.DataFrame(sensitivity_rows)
    sensitivities.to_csv(ROOT / "sensitivities.csv", index=False)

    primary_metrics = strategies["PRIMARY"]
    runner_metrics = strategies["ALWAYS_RUNNER"]
    gates = {
        "at_least_100_scored": len(primary) >= 100,
        "at_least_60_executed": len(executed) >= 60,
        "mean_r_at_least_0_15": float(primary_metrics["mean_r_per_executed"]) >= 0.15,
        "non_negative_without_best_trade": float(primary_metrics["total_r_without_best_one"]) >= 0,
        "drawdown_no_worse_than_always_runner": float(primary_metrics["max_drawdown_r"])
        <= float(runner_metrics["max_drawdown_r"]),
        "edge_not_entirely_one_month": diversity_gate(cuts["month"], float(primary_metrics["total_r"])),
        "edge_not_entirely_one_session": diversity_gate(cuts["session"], float(primary_metrics["total_r"])),
        "causal_and_mutation_checks": verification["status"] == "PASS" and mutations["status"] == "PASS",
    }
    ready = all(gates.values())
    calendar_days = (primary["entry_time"].max().date() - primary["entry_time"].min().date()).days + 1
    result = {
        "status": "SHADOW CANDIDATE" if ready else "RESEARCH ONLY - NOT READY",
        "promotion_status": "NOT PROMOTED; historical exam remains locked",
        "design_evidence": "P1+P2 are both previously seen",
        "exam_read": False,
        "panel_rows": len(panel),
        "scored_start": primary["entry_time"].min(),
        "scored_end": primary["entry_time"].max(),
        "executed_per_calendar_day": len(executed) / calendar_days,
        "executed_per_active_entry_day": len(executed) / primary["entry_time"].dt.date.nunique(),
        "strategies": strategies,
        "gates": gates,
        "sensitivities": [{key: _native(value) for key, value in row.items()} for row in sensitivity_rows],
        "input_hashes": verify_frozen_inputs(),
        "verification": verification,
        "mutations": mutations,
    }
    serializable = json.loads(json.dumps(result, default=_native, allow_nan=True))
    (ROOT / "RESULTS.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    write_markdown(serializable, cuts)


def write_markdown(result: dict[str, object], cuts: dict[str, pd.DataFrame]) -> None:
    strategies = result["strategies"]
    primary = strategies["PRIMARY"]
    lines = [
        "# TR2 design-only result",
        "",
        f"Status: **{result['status']}**. {result['promotion_status']}.",
        "",
        "P1 and P2 are already-seen design evidence. The locked 2026-04-18 through 2026-10-17 exam was not read.",
        "",
        "## Primary result",
        "",
        f"- Scored {primary['scored_opportunities']} opportunities; executed {primary['executed_trades']}.",
        f"- Actions: {primary['action_counts']}.",
        f"- Total {primary['total_r']:.3f}R / ${primary['total_usd_001']:.2f} at 0.01 lot.",
        f"- Mean {primary['mean_r_per_executed']:.3f}R per executed trade; bootstrap 95% interval "
        f"[{primary['bootstrap_95_mean_r'][0]:.3f}, {primary['bootstrap_95_mean_r'][1]:.3f}].",
        f"- Max drawdown {primary['max_drawdown_r']:.3f}R; maximum losing streak "
        f"{primary['maximum_losing_streak']}.",
        f"- After removing best one: {primary['total_r_without_best_one']:.3f}R; best three: "
        f"{primary['total_r_without_best_three']:.3f}R.",
        "",
        "## Same-row baselines",
        "",
        f"- Always FAST: {strategies['ALWAYS_FAST']['total_r']:.3f}R, "
        f"{strategies['ALWAYS_FAST']['mean_r_per_executed']:.3f}R/trade, "
        f"DD {strategies['ALWAYS_FAST']['max_drawdown_r']:.3f}R.",
        f"- Always RUNNER: {strategies['ALWAYS_RUNNER']['total_r']:.3f}R, "
        f"{strategies['ALWAYS_RUNNER']['mean_r_per_executed']:.3f}R/trade, "
        f"DD {strategies['ALWAYS_RUNNER']['max_drawdown_r']:.3f}R.",
        "",
        "## Prototype gates",
        "",
    ]
    lines.extend(f"- {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result["gates"].items())
    lines.extend(["", "## Group cuts", ""])
    for name, cut in cuts.items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append(cut.to_string(index=False))
        lines.append("")
    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "This is an adaptive prototype measured on seen design data, not independent validation. Even a PASS "
            "cannot authorize live or demo orders. Forward shadow collection must last at least 60 new trading days "
            "or 100 new opportunities without opening the locked historical exam.",
            "",
        ]
    )
    (ROOT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
