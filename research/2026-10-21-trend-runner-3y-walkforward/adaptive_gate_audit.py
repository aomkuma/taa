"""Causally replay simple weekly adaptation hypotheses on the frozen journal.

Research only: this script never changes selector actions or source outcomes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "trade_journal.csv"
OUTPUT = ROOT / "adaptive_research"
ATR_HIGH_THRESHOLD = 0.80
ATR_LOOKBACK_WEEKS = 52
ATR_MIN_HISTORY_TRADES = 10
ATR_THRESHOLD_SENSITIVITY = (0.70, 0.75, 0.80, 0.85, 0.90)
ATR_LOOKBACK_SENSITIVITY = (8, 13, 26, 52, 104)
ATR_MIN_HISTORY_SENSITIVITY = (5, 10, 15)
RECOVERY_TESTS = ((8, 1), (8, 3), (13, 5))


def prepare(source: pd.DataFrame, *, atr_threshold: float = ATR_HIGH_THRESHOLD) -> pd.DataFrame:
    required = {"trade_key", "entry_time_utc", "action", "window", "runner_r", "h1_atr_percentile_120"}
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"source journal missing columns: {sorted(missing)}")
    if source["trade_key"].duplicated().any():
        raise ValueError("source journal contains duplicate trade keys")
    data = source.copy()
    data["entry_time_utc"] = pd.to_datetime(data["entry_time_utc"], utc=True)
    data = data.sort_values(["entry_time_utc", "trade_key"]).reset_index(drop=True)
    data["week_start_utc"] = (
        data["entry_time_utc"].dt.tz_convert(None).dt.to_period("W-SUN").dt.start_time
    )
    data["high_atr"] = data["h1_atr_percentile_120"].ge(atr_threshold)
    return data


def replay(
    data: pd.DataFrame,
    *,
    lookback_weeks: int = ATR_LOOKBACK_WEEKS,
    minimum_history_trades: int = ATR_MIN_HISTORY_TRADES,
    recovery_weeks: int | None = None,
    recovery_minimum_trades: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return RUNNER rows with causal decisions and one decision row per week."""
    selected = data.loc[data["action"].eq("RUNNER")].copy()
    weeks = pd.date_range(selected["week_start_utc"].min(), selected["week_start_utc"].max(), freq="W-MON")
    trades: list[pd.DataFrame] = []
    decisions: list[dict[str, object]] = []
    for week in weeks:
        current = selected.loc[selected["week_start_utc"].eq(week)].copy()
        previous = selected.loc[
            selected["high_atr"]
            & selected["week_start_utc"].ge(week - pd.Timedelta(weeks=lookback_weeks))
            & selected["week_start_utc"].lt(week)
        ]
        high_atr_loss_streak = (
            len(previous) >= minimum_history_trades and previous["runner_r"].sum() < 0
        )
        recovery = False
        if recovery_weeks is not None:
            recent = selected.loc[
                selected["high_atr"]
                & selected["week_start_utc"].ge(week - pd.Timedelta(weeks=recovery_weeks))
                & selected["week_start_utc"].lt(week)
            ]
            recovery = len(recent) >= recovery_minimum_trades and recent["runner_r"].sum() > 0
        gate_active = high_atr_loss_streak and not recovery
        current["adaptive_keep"] = ~(gate_active & current["high_atr"])
        current["gate_reason"] = "BASELINE"
        current.loc[~current["adaptive_keep"], "gate_reason"] = "SKIP_HIGH_ATR_AFTER_TRAILING_LOSS"
        trades.append(current)
        decisions.append(
            {
                "week_start_utc": week.strftime("%Y-%m-%d"),
                "prior_high_atr_trades_52w": len(previous),
                "prior_high_atr_runner_r_52w": float(previous["runner_r"].sum()),
                "skip_high_atr_this_week": gate_active,
                "recovery_condition_met": recovery,
                "high_atr_trades_this_week": int(current["high_atr"].sum()),
                "skipped_trades_this_week": int((~current["adaptive_keep"]).sum()),
            }
        )
    return pd.concat(trades, ignore_index=True), pd.DataFrame(decisions)


def summarize(trades: pd.DataFrame) -> dict[str, object]:
    baseline = trades["runner_r"]
    adaptive = trades.loc[trades["adaptive_keep"], "runner_r"]
    selected_year = trades.assign(year=trades["entry_time_utc"].dt.year)
    yearly: dict[str, dict[str, float | int]] = {}
    for year, group in selected_year.groupby("year"):
        kept = group.loc[group["adaptive_keep"], "runner_r"]
        yearly[str(year)] = {
            "baseline_trades": len(group),
            "baseline_r": float(group["runner_r"].sum()),
            "adaptive_trades": len(kept),
            "adaptive_r": float(kept.sum()),
        }
    baseline_top5 = float(trades["runner_r"].nlargest(5).sum())
    adaptive_top5 = float(trades.loc[trades["adaptive_keep"], "runner_r"].nlargest(5).sum())
    return {
        "source": SOURCE.name,
        "atr_percentile_threshold": ATR_HIGH_THRESHOLD,
        "lookback_weeks": ATR_LOOKBACK_WEEKS,
        "minimum_prior_high_atr_trades": ATR_MIN_HISTORY_TRADES,
        "baseline": {
            "trades": len(baseline),
            "total_r": float(baseline.sum()),
            "mean_r": float(baseline.mean()),
            "win_rate": float((baseline > 0).mean()),
            "top5_r": baseline_top5,
            "r_ex_top5": float(baseline.sum() - baseline_top5),
        },
        "adaptive": {
            "trades": len(adaptive),
            "total_r": float(adaptive.sum()),
            "mean_r": float(adaptive.mean()),
            "win_rate": float((adaptive > 0).mean()),
            "top5_r": adaptive_top5,
            "r_ex_top5": float(adaptive.sum() - adaptive_top5),
        },
        "yearly": yearly,
        "research_only": True,
    }


def sensitivity(source: pd.DataFrame) -> dict[str, list[dict[str, float | int]]]:
    thresholds = []
    for threshold in ATR_THRESHOLD_SENSITIVITY:
        trades, _ = replay(prepare(source, atr_threshold=threshold))
        result = summarize(trades)["adaptive"]
        thresholds.append({"atr_threshold": threshold, **result})
    lookbacks = []
    data = prepare(source)
    for lookback in ATR_LOOKBACK_SENSITIVITY:
        trades, _ = replay(data, lookback_weeks=lookback)
        result = summarize(trades)["adaptive"]
        lookbacks.append({"lookback_weeks": lookback, **result})
    history_sizes = []
    for minimum in ATR_MIN_HISTORY_SENSITIVITY:
        trades, _ = replay(data, minimum_history_trades=minimum)
        result = summarize(trades)["adaptive"]
        history_sizes.append({"minimum_prior_high_atr_trades": minimum, **result})
    recovery_results = []
    for recovery_weeks, minimum in RECOVERY_TESTS:
        trades, decisions = replay(
            data,
            recovery_weeks=recovery_weeks,
            recovery_minimum_trades=minimum,
        )
        result = summarize(trades)["adaptive"]
        active = decisions["skip_high_atr_this_week"].astype(bool)
        recovery_results.append(
            {
                "recovery_weeks": recovery_weeks,
                "recovery_minimum_high_atr_trades": minimum,
                **result,
                "gate_active_weeks": int(active.sum()),
                "gate_transitions": int((active != active.shift(fill_value=False)).sum()),
            }
        )
    return {
        "atr_threshold_sensitivity": thresholds,
        "lookback_sensitivity": lookbacks,
        "minimum_history_sensitivity": history_sizes,
        "recovery_sensitivity": recovery_results,
    }


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    source = pd.read_csv(SOURCE)
    data = prepare(source)
    trades, decisions = replay(data)
    summary = summarize(trades)
    summary.update(sensitivity(source))
    trades.to_csv(OUTPUT / "adaptive_atr_gate_trades.csv", index=False)
    decisions.to_csv(OUTPUT / "adaptive_atr_gate_weekly_decisions.csv", index=False)
    (OUTPUT / "adaptive_atr_gate_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
