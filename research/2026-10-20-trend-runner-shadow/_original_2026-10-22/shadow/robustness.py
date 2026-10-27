"""Pure observational robustness metrics for completed forward decisions."""

from __future__ import annotations

import numpy as np
import pandas as pd

BOOTSTRAP_SAMPLES = 5_000
BLOCK_LENGTH = 5
BOOTSTRAP_SEED = 20261021
MINIMUM_ROBUSTNESS_TRADES = 20


def max_drawdown(values: np.ndarray, *, axis: int | None = None) -> np.ndarray | float:
    if axis is None:
        equity = np.r_[0.0, np.cumsum(values)]
        return float(np.max(np.maximum.accumulate(equity) - equity))
    equity = np.concatenate([np.zeros((len(values), 1)), np.cumsum(values, axis=axis)], axis=1)
    return np.max(np.maximum.accumulate(equity, axis=1) - equity, axis=1)


def path_metrics(values: np.ndarray) -> dict[str, object]:
    equity = 0.0
    peak = 0.0
    underwater = 0
    longest_underwater = 0
    losing = 0
    longest_losing = 0
    for value in values:
        equity += float(value)
        if equity >= peak:
            peak = equity
            underwater = 0
        else:
            underwater += 1
            longest_underwater = max(longest_underwater, underwater)
        losing = losing + 1 if value < 0 else 0
        longest_losing = max(longest_losing, losing)
    return {
        "max_drawdown_r": max_drawdown(values),
        "maximum_losing_streak": longest_losing,
        "longest_underwater_trades": longest_underwater,
        "terminal_underwater_trades": underwater,
        "terminal_drawdown_r": float(peak - equity),
    }


def moving_block_bootstrap(values: np.ndarray) -> dict[str, object]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    block_length = min(BLOCK_LENGTH, len(values))
    block_count = int(np.ceil(len(values) / block_length))
    starts = rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, block_count))
    offsets = np.arange(block_length)
    indices = (starts[:, :, None] + offsets[None, None, :]) % len(values)
    samples = values[indices.reshape(BOOTSTRAP_SAMPLES, -1)[:, : len(values)]]
    means = samples.mean(axis=1)
    totals = samples.sum(axis=1)
    drawdowns = np.asarray(max_drawdown(samples, axis=1))
    return {
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "block_length": block_length,
        "mean_r_quantiles_2p5_50_97p5": [
            float(value) for value in np.quantile(means, [0.025, 0.50, 0.975])
        ],
        "probability_total_r_positive": float(np.mean(totals > 0)),
        "max_drawdown_r_quantiles_50_95_99": [
            float(value) for value in np.quantile(drawdowns, [0.50, 0.95, 0.99])
        ],
    }


def _rolling(values: np.ndarray) -> dict[str, object] | None:
    if len(values) < 20:
        return None
    rolling = pd.Series(values).rolling(20).mean().dropna()
    return {
        "window_trades": 20,
        "windows": len(rolling),
        "current_mean_r": float(rolling.iloc[-1]),
        "minimum_mean_r": float(rolling.min()),
        "median_mean_r": float(rolling.median()),
        "maximum_mean_r": float(rolling.max()),
        "fraction_positive": float(np.mean(rolling > 0)),
    }


def _group_cuts(frame: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    if frame.empty:
        return {"month": [], "direction": [], "session": []}
    source = frame.copy()
    source["month"] = pd.to_datetime(source["entry_time"], utc=True).dt.strftime("%Y-%m")
    source["direction"] = np.where(source["side"].astype(int) > 0, "BUY", "SELL")
    result: dict[str, list[dict[str, object]]] = {}
    for name, column in (("month", "month"), ("direction", "direction"), ("session", "window")):
        cut = (
            source.groupby(column, sort=True)
            .agg(trades=("runner_r", "size"), total_r=("runner_r", "sum"), mean_r=("runner_r", "mean"))
            .reset_index()
            .rename(columns={column: "group"})
        )
        result[name] = [
            {
                "group": str(row.group),
                "trades": int(row.trades),
                "total_r": float(row.total_r),
                "mean_r": float(row.mean_r),
            }
            for row in cut.itertuples(index=False)
        ]
    return result


def analyze_champion(selected: pd.DataFrame, *, evaluation_ready: bool) -> dict[str, object]:
    if selected.empty:
        return {
            "status": "INSUFFICIENT",
            "reason": "no completed Champion RUNNER trades",
            "executed": 0,
            "minimum_required": MINIMUM_ROBUSTNESS_TRADES,
            "hypothetical_slippage_stress": "EXCLUDED_BY_USER",
        }
    ordered = selected.sort_values("entry_time").reset_index(drop=True)
    values = ordered["runner_r"].to_numpy(float)
    wins = values[values > 0]
    losses = values[values < 0]
    descending = np.sort(values)[::-1]
    total = float(values.sum())
    without_best_one = float(descending[1:].sum()) if len(values) > 1 else 0.0
    without_best_three = float(descending[3:].sum()) if len(values) > 3 else None
    rolling = _rolling(values)
    bootstrap = (
        moving_block_bootstrap(values) if len(values) >= MINIMUM_ROBUSTNESS_TRADES else None
    )
    gates = {
        "observed_total_positive": total > 0,
        "positive_after_best_three_removed": bool(
            without_best_three is not None and without_best_three > 0
        ),
        "moving_block_95pct_lower_mean_positive": bool(
            bootstrap is not None and bootstrap["mean_r_quantiles_2p5_50_97p5"][0] > 0
        ),
        "at_least_70pct_rolling_20_windows_positive": bool(
            rolling is not None and rolling["fraction_positive"] >= 0.70
        ),
    }
    if len(values) < MINIMUM_ROBUSTNESS_TRADES:
        status = "INSUFFICIENT"
        reason = "fewer than 20 completed Champion RUNNER trades"
    elif not evaluation_ready:
        status = "COLLECTING"
        reason = "formal 100-opportunity and 60-trading-day gate is not complete"
    elif total <= 0:
        status = "NOT_POSITIVE"
        reason = "observed total R is non-positive"
    else:
        status = "ROBUST_POSITIVE" if all(gates.values()) else "FRAGILE_POSITIVE"
        reason = (
            "all robustness gates pass"
            if status == "ROBUST_POSITIVE"
            else "one or more robustness gates fail"
        )
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) else None
    payoff_ratio = float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) else None
    return {
        "status": status,
        "reason": reason,
        "executed": len(values),
        "minimum_required": MINIMUM_ROBUSTNESS_TRADES,
        "hypothetical_slippage_stress": "EXCLUDED_BY_USER",
        "total_r": total,
        "mean_r": float(values.mean()),
        "win_rate": float(np.mean(values > 0)),
        "profit_factor": profit_factor,
        "payoff_ratio": payoff_ratio,
        **path_metrics(values),
        "total_without_best_one_r": without_best_one,
        "total_without_best_three_r": without_best_three,
        "best_one_share_of_net_profit": float(descending[0] / total) if total != 0 else None,
        "best_three_share_of_net_profit": float(descending[:3].sum() / total) if total != 0 else None,
        "rolling_20": rolling,
        "moving_block_bootstrap": bootstrap,
        "group_cuts": _group_cuts(ordered),
        "gates": gates,
    }


def policy_comparison(decisions: pd.DataFrame, outcomes: pd.DataFrame) -> dict[str, object]:
    if decisions.empty or outcomes.empty:
        return {}
    completed = decisions.loc[decisions["status"] == "SCORED"].merge(
        outcomes[["trade_key", "runner_r"]], on="trade_key", how="inner", validate="many_to_one"
    )
    result: dict[str, object] = {}
    for policy, frame in completed.groupby("policy", sort=True):
        selected = frame.loc[frame["action"] == "RUNNER", "runner_r"].to_numpy(float)
        result[str(policy)] = {
            "completed_scored": len(frame),
            "selected_completed": len(selected),
            "selected_total_r": float(selected.sum()),
            "selected_mean_r": float(selected.mean()) if len(selected) else None,
            "selected_drawdown_r": max_drawdown(selected) if len(selected) else 0.0,
        }
    return result
