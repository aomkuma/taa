# ruff: noqa: T201
"""Deterministic pre-forward profit robustness audit for the frozen TR3 primary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "2026-10-20-trend-runner-r3"
PREDICTIONS = SOURCE / "predictions_primary.parquet"
FROZEN_RESULTS = SOURCE / "RESULTS.json"
SEED_IID = 20261020
SEED_BLOCK = 20261021
BOOTSTRAP_SAMPLES = 20_000
BLOCK_LENGTH = 5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def max_drawdown(values: np.ndarray, *, axis: int | None = None) -> np.ndarray | float:
    if axis is None:
        equity = np.r_[0.0, np.cumsum(values)]
        return float(np.max(np.maximum.accumulate(equity) - equity))
    equity = np.concatenate([np.zeros((len(values), 1)), np.cumsum(values, axis=axis)], axis=1)
    return np.max(np.maximum.accumulate(equity, axis=1) - equity, axis=1)


def path_metrics(values: np.ndarray) -> dict[str, object]:
    equity = 0.0
    peak = 0.0
    current_underwater = 0
    longest_underwater = 0
    losing = 0
    longest_losing = 0
    for value in values:
        equity += float(value)
        if equity >= peak:
            peak = equity
            current_underwater = 0
        else:
            current_underwater += 1
            longest_underwater = max(longest_underwater, current_underwater)
        losing = losing + 1 if value < 0 else 0
        longest_losing = max(longest_losing, losing)
    return {
        "max_drawdown_r": max_drawdown(values),
        "longest_underwater_trades": longest_underwater,
        "terminal_underwater_trades": current_underwater,
        "terminal_drawdown_r": float(peak - equity),
        "maximum_losing_streak": longest_losing,
    }


def summarize_bootstrap(samples: np.ndarray) -> dict[str, object]:
    means = samples.mean(axis=1)
    totals = samples.sum(axis=1)
    drawdowns = np.asarray(max_drawdown(samples, axis=1))
    return {
        "samples": len(samples),
        "mean_r_quantiles_2p5_50_97p5": [
            float(value) for value in np.quantile(means, [0.025, 0.50, 0.975])
        ],
        "probability_total_r_positive": float(np.mean(totals > 0)),
        "total_r_quantiles_2p5_50_97p5": [
            float(value) for value in np.quantile(totals, [0.025, 0.50, 0.975])
        ],
        "max_drawdown_r_quantiles_50_95_99": [
            float(value) for value in np.quantile(drawdowns, [0.50, 0.95, 0.99])
        ],
    }


def bootstrap(values: np.ndarray) -> tuple[dict[str, object], dict[str, object]]:
    iid_rng = np.random.default_rng(SEED_IID)
    iid = iid_rng.choice(values, size=(BOOTSTRAP_SAMPLES, len(values)), replace=True)
    blocks = int(np.ceil(len(values) / BLOCK_LENGTH))
    block_rng = np.random.default_rng(SEED_BLOCK)
    starts = block_rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, blocks))
    offsets = np.arange(BLOCK_LENGTH)
    indices = (starts[:, :, None] + offsets[None, None, :]) % len(values)
    block_samples = values[indices.reshape(BOOTSTRAP_SAMPLES, -1)[:, : len(values)]]
    return summarize_bootstrap(iid), summarize_bootstrap(block_samples)


def removal_stress(values: np.ndarray) -> pd.DataFrame:
    descending = np.sort(values)[::-1]
    return pd.DataFrame(
        [
            {
                "best_trades_removed": count,
                "remaining_total_r": float(descending[count:].sum()),
                "profitable": bool(descending[count:].sum() > 0),
            }
            for count in range(0, 6)
        ]
    )


def group_cut(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        frame.groupby(column)
        .agg(trades=("runner_r", "size"), total_r=("runner_r", "sum"), mean_r=("runner_r", "mean"))
        .reset_index()
    )


def main() -> None:
    predictions = pd.read_parquet(PREDICTIONS).sort_values("entry_time").reset_index(drop=True)
    if set(predictions["source_period"]) - {"P1", "P2"}:
        raise ValueError("audit input contains a period outside safe-design P1/P2")
    executed = predictions.loc[predictions["action"] == "RUNNER"].copy()
    values = executed["runner_r"].to_numpy(float)
    frozen = json.loads(FROZEN_RESULTS.read_text(encoding="utf-8"))
    primary = frozen["primary"]
    reconciliations = {
        "executed": len(values) == int(primary["executed"]),
        "total_r": bool(np.isclose(values.sum(), primary["total_r"], rtol=1e-12, atol=1e-12)),
        "mean_r": bool(
            np.isclose(values.mean(), primary["mean_r_executed"], rtol=1e-12, atol=1e-12)
        ),
        "fixed_001_usd": bool(
            np.isclose(
                executed["selected_usd_fixed_001"].sum(),
                primary["fixed_001_usd"],
                rtol=1e-12,
                atol=1e-12,
            )
        ),
        "risk_10_usd": bool(
            np.isclose(executed["selected_usd_risk10"].sum(), primary["risk_10_usd"])
        ),
    }
    if not all(reconciliations.values()):
        raise AssertionError(f"frozen R3 reconciliation failed: {reconciliations}")

    removals = removal_stress(values)
    iid, moving_block = bootstrap(values)
    wins = values[values > 0]
    losses = values[values < 0]
    rolling = pd.Series(values).rolling(20).mean().dropna()
    distribution = {
        "gross_profit_r": float(wins.sum()),
        "gross_loss_r": float(losses.sum()),
        "profit_factor": float(wins.sum() / abs(losses.sum())),
        "win_rate": float(np.mean(values > 0)),
        "average_win_r": float(wins.mean()),
        "average_loss_r": float(losses.mean()),
        "payoff_ratio": float(wins.mean() / abs(losses.mean())),
        "top_1_profit_share_of_total": float(np.sort(values)[-1] / values.sum()),
        "top_3_profit_share_of_total": float(np.sort(values)[-3:].sum() / values.sum()),
    }
    rolling_summary = {
        "window_executed_trades": 20,
        "windows": len(rolling),
        "minimum_mean_r": float(rolling.min()),
        "median_mean_r": float(rolling.median()),
        "maximum_mean_r": float(rolling.max()),
        "fraction_positive": float(np.mean(rolling > 0)),
    }
    cuts = {
        "month": group_cut(executed.assign(month=executed["entry_time"].dt.strftime("%Y-%m")), "month"),
        "direction": group_cut(
            executed.assign(direction=np.where(executed["side"] > 0, "BUY", "SELL")),
            "direction",
        ),
        "session": group_cut(executed, "window").rename(columns={"window": "session"}),
    }
    for name, frame in cuts.items():
        frame.to_csv(ROOT / f"cut_{name}.csv", index=False)
    removals.to_csv(ROOT / "best_trade_removal.csv", index=False)
    rolling_frame = executed[["trade_key", "entry_time", "runner_r"]].copy()
    rolling_frame["rolling_20_mean_r"] = pd.Series(values).rolling(20).mean().to_numpy()
    rolling_frame.to_csv(ROOT / "rolling_20.csv", index=False)

    best_three_positive = bool(
        removals.loc[removals["best_trades_removed"] == 3, "profitable"].iloc[0]
    )
    block_lower_positive = moving_block["mean_r_quantiles_2p5_50_97p5"][0] > 0
    rolling_stable = rolling_summary["fraction_positive"] >= 0.70
    if values.sum() <= 0:
        verdict = "NOT_POSITIVE"
    elif block_lower_positive and best_three_positive and rolling_stable:
        verdict = "ROBUST"
    else:
        verdict = "FRAGILE_POSITIVE"

    result = {
        "verdict": verdict,
        "meaning": "diagnostic evidence only; no promotion or live-trading authorization",
        "scope": "frozen safe-design P1/P2 predictions; exam unopened",
        "hypothetical_slippage_stress": "EXCLUDED_BY_USER",
        "input_sha256": sha256(PREDICTIONS),
        "reconciliation": reconciliations,
        "observed": {
            "scored": len(predictions),
            "executed": len(values),
            "total_r": float(values.sum()),
            "mean_r": float(values.mean()),
            "fixed_001_usd": float(executed["selected_usd_fixed_001"].sum()),
            "risk_10_usd": float(executed["selected_usd_risk10"].sum()),
            **path_metrics(values),
        },
        "distribution": distribution,
        "rolling_20": rolling_summary,
        "best_trade_removal": removals.to_dict(orient="records"),
        "iid_bootstrap": iid,
        "moving_block_bootstrap": moving_block,
        "stability": {
            "profitable_months": int((cuts["month"]["total_r"] > 0).sum()),
            "months": len(cuts["month"]),
            "profitable_directions": int((cuts["direction"]["total_r"] > 0).sum()),
            "directions": len(cuts["direction"]),
            "profitable_sessions": int((cuts["session"]["total_r"] > 0).sum()),
            "sessions": len(cuts["session"]),
        },
        "gates": {
            "observed_total_positive": bool(values.sum() > 0),
            "positive_after_best_three_removed": best_three_positive,
            "moving_block_95pct_lower_mean_positive": block_lower_positive,
            "at_least_70pct_rolling_20_windows_positive": rolling_stable,
        },
        "bootstrap_configuration": {
            "samples_each": BOOTSTRAP_SAMPLES,
            "iid_seed": SEED_IID,
            "moving_block_seed": SEED_BLOCK,
            "moving_block_length": BLOCK_LENGTH,
        },
    }
    (ROOT / "RESULTS.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(result, cuts)
    print(json.dumps(result, indent=2))


def write_report(result: dict[str, object], cuts: dict[str, pd.DataFrame]) -> None:
    observed = result["observed"]
    distribution = result["distribution"]
    iid = result["iid_bootstrap"]
    block = result["moving_block_bootstrap"]
    rolling = result["rolling_20"]
    lines = [
        "# TR3 pre-forward profit robustness audit",
        "",
        f"Verdict: **{result['verdict']}**.",
        "",
        "This is diagnostic safe-design evidence only. The historical exam was not opened and the "
        "Champion was not changed.",
        "",
        "## Observed path",
        "",
        f"- {observed['executed']} executed trades from {observed['scored']} scored opportunities.",
        f"- {observed['total_r']:+.3f}R total and {observed['mean_r']:+.3f}R/trade.",
        f"- Maximum drawdown {observed['max_drawdown_r']:.3f}R; longest underwater span "
        f"{observed['longest_underwater_trades']} executed trades.",
        f"- Profit factor {distribution['profit_factor']:.3f}; payoff ratio "
        f"{distribution['payoff_ratio']:.3f}; "
        f"win rate {distribution['win_rate']:.1%}.",
        "## Fragility",
        "",
        "- Removing the best three trades leaves "
        f"{result['best_trade_removal'][3]['remaining_total_r']:+.3f}R.",
        f"- Top three trades equal {distribution['top_3_profit_share_of_total']:.1%} of observed net profit.",
        f"- Rolling 20-trade expectancy: minimum {rolling['minimum_mean_r']:+.3f}R, median "
        f"{rolling['median_mean_r']:+.3f}R; {rolling['fraction_positive']:.1%} of windows were positive.",
        f"- Profitable months: {result['stability']['profitable_months']}/{result['stability']['months']}; "
        f"directions: {result['stability']['profitable_directions']}/{result['stability']['directions']}; "
        f"sessions: {result['stability']['profitable_sessions']}/{result['stability']['sessions']}.",
        "",
        "## Resampling uncertainty",
        "",
        f"- IID 95% mean interval: [{iid['mean_r_quantiles_2p5_50_97p5'][0]:+.3f}, "
        f"{iid['mean_r_quantiles_2p5_50_97p5'][2]:+.3f}]R; positive-total probability "
        f"{iid['probability_total_r_positive']:.1%}.",
        f"- Moving-block 95% mean interval: [{block['mean_r_quantiles_2p5_50_97p5'][0]:+.3f}, "
        f"{block['mean_r_quantiles_2p5_50_97p5'][2]:+.3f}]R; positive-total probability "
        f"{block['probability_total_r_positive']:.1%}.",
        f"- Moving-block simulated drawdown median/95th/99th: "
        f"{block['max_drawdown_r_quantiles_50_95_99'][0]:.3f}/"
        f"{block['max_drawdown_r_quantiles_50_95_99'][1]:.3f}/"
        f"{block['max_drawdown_r_quantiles_50_95_99'][2]:.3f}R.",
        "",
        "## Interpretation",
        "",
        "Observed expectancy is positive, but robustness still depends on the resampled lower bound, "
        "best-trade removal, and rolling-window stability. Hypothetical slippage stress was excluded by user "
        "direction. Forward "
        "shadow collection is justified; promotion or capital deployment is not.",
        "",
        "## Group cuts",
        "",
    ]
    for name, frame in cuts.items():
        lines.extend([f"### {name}", "", frame.to_string(index=False), ""])
    (ROOT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
