"""Render the immutable P1/P2 round-1 validation report from frozen artifacts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BOOTSTRAPS = 20_000
PERIODS = {
    "P1": (pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-01-16", tz="UTC")),
    "P2": (pd.Timestamp("2026-01-16", tz="UTC"), pd.Timestamp("2026-04-18", tz="UTC")),
}


def bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    generator = np.random.default_rng(seed)
    indexes = generator.integers(0, len(values), size=(BOOTSTRAPS, len(values)))
    low, high = np.quantile(values[indexes].mean(axis=1), [0.025, 0.975])
    return float(low), float(high)


def drawdown(values: np.ndarray) -> float:
    cumulative = np.r_[0.0, np.cumsum(values)]
    return float(np.max(np.maximum.accumulate(cumulative) - cumulative))


def losing_streak(values: np.ndarray) -> int:
    current = worst = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        worst = max(worst, current)
    return worst


def weekdays(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return sum(day.dayofweek < 5 for day in pd.date_range(start, end - pd.Timedelta(days=1), freq="1D"))


def one_position(frame: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    accepted = []
    active_until: pd.Timestamp | None = None
    for row in frame.sort_values("entry_time").itertuples():
        if active_until is None or row.entry_time >= active_until:
            accepted.append(row.Index)
            active_until = row.exit_time
    return len(frame) - len(accepted), frame.loc[accepted]


def describe_part(name: str, results: pd.DataFrame, seed: int) -> list[str]:
    frame = results.loc[(results["family"] == "SPLIT") & results["complete"]].sort_values("entry_time")
    values = frame["r"].to_numpy(float)
    usd = frame["usd_001"].to_numpy(float)
    low, high = bootstrap(values, seed)
    sorted_values = np.sort(values)
    start, end = PERIODS[name]
    days = weekdays(start, end)
    collisions, serial = one_position(frame)
    lines = [
        f"## {name} - frozen SPLIT",
        "",
        f"- {len(frame)} trades, {len(frame) / days:.2f} per scheduled weekday; "
        f"mean {values.mean():+.3f}R (95% individual-trade bootstrap {low:+.3f} to {high:+.3f}), "
        f"median {np.median(values):+.3f}R and {(values > 0).mean():.1%} positive.",
        f"- Total {values.sum():+.2f}R and {usd.sum():+.2f} USD at 0.01 lot; "
        f"{usd.sum() / days:+.2f} USD per scheduled weekday.",
        f"- Worst trade {values.min():+.2f}R / {usd.min():+.2f} USD; maximum drawdown "
        f"{drawdown(values):.2f}R / {drawdown(usd):.2f} USD; longest losing streak {losing_streak(values)}.",
        f"- Removing the best trade: {sorted_values[:-1].mean():+.3f}R/trade; removing the best three: "
        f"{sorted_values[:-3].mean():+.3f}R/trade.",
        f"- Median holding {frame['holding_minutes'].median():.1f} minutes; total exposure "
        f"{frame['holding_minutes'].sum() / 60:.1f} hours; "
        f"{int((frame['exit_time'].dt.date != frame['entry_time'].dt.date).sum())} UTC-date crossings.",
        f"- A greedy one-position-at-a-time lane has {collisions} collisions and keeps {len(serial)} trades: "
        f"{serial['r'].mean():+.3f}R/trade, {serial['r'].sum():+.2f}R; foregone "
        f"{frame['r'].sum() - serial['r'].sum():+.2f}R.",
        "",
        "Session and direction cuts:",
        "",
    ]
    for window, group in frame.groupby("window", sort=False):
        lines.append(
            f"- {window}: n={len(group)}, mean={group['r'].mean():+.3f}R, "
            f"total={group['r'].sum():+.2f}R, USD={group['usd_001'].sum():+.2f}."
        )
    for side, group in frame.groupby("side", sort=True):
        lines.append(
            f"- {'BUY' if side > 0 else 'SELL'}: n={len(group)}, mean={group['r'].mean():+.3f}R, "
            f"total={group['r'].sum():+.2f}R."
        )
    lines.extend(["", "Weekly results:", ""])
    weekly = (
        frame.assign(week=frame["entry_time"].dt.strftime("%G-W%V"))
        .groupby("week")
        .agg(trades=("r", "size"), r=("r", "sum"), usd=("usd_001", "sum"))
    )
    for week, row in weekly.iterrows():
        lines.append(f"- {week}: {int(row['trades'])} trades, {row['r']:+.2f}R, {row['usd']:+.2f} USD.")
    lines.extend(["", "Monthly results:", ""])
    monthly = (
        frame.assign(month=frame["entry_time"].dt.strftime("%Y-%m"))
        .groupby("month")
        .agg(trades=("r", "size"), mean_r=("r", "mean"), r=("r", "sum"), usd=("usd_001", "sum"))
    )
    for month, row in monthly.iterrows():
        lines.append(
            f"- {month}: {int(row['trades'])} trades, {row['mean_r']:+.3f}R/trade, "
            f"{row['r']:+.2f}R, {row['usd']:+.2f} USD."
        )
    return lines


def main() -> None:
    result_by_part = {
        name: pd.read_parquet(HERE / f"frozen_results_{name.lower()}.parquet") for name in PERIODS
    }
    lines = [
        "# TR1 frozen round-1 validation",
        "",
        "P2 was opened once at 2026-10-20 15:01:17 Thai time using the command frozen before "
        "validation. No rule, parameter, session or exit family changed. The exam was not opened.",
        "",
        "## Decision",
        "",
        "**FAIL.** Frozen SPLIT passed P1 (+0.265R/trade) but produced only +0.088R/trade in P2, below the "
        "predeclared requirement of at least +0.15R/trade in each part. Frequency and sample-size "
        "gates passed. The P2 result remains positive but is not strong enough to promote or examine.",
        "",
    ]
    lines.extend(describe_part("P1", result_by_part["P1"], 20261020))
    lines.extend([""])
    lines.extend(describe_part("P2", result_by_part["P2"], 20261021))
    lines.extend(["", "## Frozen controls on the same entries", ""])
    for name, results in result_by_part.items():
        lines.append(f"{name}:")
        for number, family in enumerate(("FAST", "SWING", "SPLIT", "STATE")):
            frame = results.loc[(results["family"] == family) & results["complete"]]
            low, high = bootstrap(frame["r"].to_numpy(float), 20261100 + number + (0 if name == "P1" else 10))
            lines.append(
                f"- {family}: n={len(frame)}, mean={frame['r'].mean():+.3f}R "
                f"(95% {low:+.3f} to {high:+.3f}), total={frame['r'].sum():+.2f}R, "
                f"USD={frame['usd_001'].sum():+.2f}."
            )
    pooled = pd.concat(
        [
            results.loc[(results["family"] == "SPLIT") & results["complete"]]
            for results in result_by_part.values()
        ],
        ignore_index=True,
    )
    lines.extend(
        [
            "",
            "## Robustness interpretation",
            "",
            f"Pooled P1+P2 is {len(pooled)} trades at {pooled['r'].mean():+.3f}R/trade, but pooling "
            "cannot override the failed per-part gate. P1's runner edge was concentrated in London "
            "and a very large winner. P2 is less concentrated but too small; adverse slippage can "
            "only reduce it, so no slippage sensitivity can rescue the primary gate.",
            "",
            "Entry timeframe is fixed M1. No entry-time market-state filter was frozen, so a "
            "market-state cut is not reported post hoc. STATE is an exit control, not permission to "
            "select P2 winners. The controls are shown for diagnosis only and cannot replace SPLIT.",
            "",
            "The result supports the original qualitative idea that some opening pullbacks become "
            "long runners, but round 1 does not identify them consistently enough. Work stops before "
            "exam and before any engine, DEMO, configuration or portfolio integration.",
            "",
        ]
    )
    report = "\n".join(lines)
    (HERE / "VALIDATION_ROUND_1.md").write_text(report, encoding="utf-8", newline="\n")
    print(report)  # noqa: T201


if __name__ == "__main__":
    main()
