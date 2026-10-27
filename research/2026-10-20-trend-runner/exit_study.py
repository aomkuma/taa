# ruff: noqa: S101
"""Run the four predeclared exit families on the fixed TR1 P1 entries."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from tr1.bars import aggregate, atr, confirmed_fractals
from tr1.boundaries import P1
from tr1.data import TickStore, load_m1
from tr1.exits import ExitFamily, run_exit
from tr1.structure import structure_events

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
TICK_ROOT = REPO / "data" / "ticks" / "XAUUSD"
BOOTSTRAPS = 10_000


def atr_values(bars: pd.DataFrame) -> np.ndarray:
    return atr(
        bars["high"].to_numpy(float),
        bars["low"].to_numpy(float),
        bars["close"].to_numpy(float),
        14,
    )


def execution_path(
    store: TickStore,
    start: pd.Timestamp,
    deadline: pd.Timestamp,
) -> pd.DataFrame:
    """Read through the first executable quote at/after a deadline, without crossing the period."""
    frames: list[pd.DataFrame] = []
    day = start.normalize()
    found_deadline_quote = False
    while day < store.period.end:
        path = store.root / f"{day.date().isoformat()}.parquet"
        if path.exists():
            frame = store.day(day)
            if day == start.normalize():
                frame = frame.loc[frame["time_utc"] >= start]
            if len(frame):
                frames.append(frame)
                if (frame["time_utc"] >= deadline).any():
                    found_deadline_quote = True
                    break
        day += pd.Timedelta(days=1)
    if not frames:
        return pd.DataFrame(columns=["time_utc", "bid", "ask"])
    ticks = pd.concat(frames, ignore_index=True)
    if found_deadline_quote:
        final = int(pd.DatetimeIndex(ticks["time_utc"]).searchsorted(deadline, side="left"))
        ticks = ticks.iloc[: final + 1]
    return ticks.reset_index(drop=True)


def bootstrap_interval(values: np.ndarray, seed: int) -> tuple[float, float]:
    generator = np.random.default_rng(seed)
    indexes = generator.integers(0, len(values), size=(BOOTSTRAPS, len(values)))
    means = values[indexes].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def max_drawdown(values: np.ndarray) -> float:
    cumulative = np.r_[0.0, np.cumsum(values)]
    peak = np.maximum.accumulate(cumulative)
    return float(np.max(peak - cumulative))


def losing_streak(values: np.ndarray) -> int:
    worst = current = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        worst = max(worst, current)
    return worst


def render_report(results: pd.DataFrame, tick_store: TickStore) -> str:
    lines = [
        "TR1 exit-family study - fixed P1 entries only",
        f"selected entries: {results['entry_id'].nunique()}; rows: {len(results)}",
        f"latest tick day opened: {max(tick_store.opened).date() if tick_store.opened else None}",
        "",
        "family complete censored mean_R CI95 median_R win total_R USD_001 med_hold maxDD_R worst_R "
        "loss_streak runner partial graduated mean_R_no_best1 mean_R_no_best3",
    ]
    for number, family in enumerate(ExitFamily):
        frame = results.loc[(results["family"] == family.value) & results["complete"]].copy()
        values = frame["r"].to_numpy(float)
        low, high = bootstrap_interval(values, 20261020 + number)
        ordered = frame.sort_values("entry_time")
        sorted_values = np.sort(values)
        no_best_1 = float(sorted_values[:-1].mean()) if len(values) > 1 else np.nan
        no_best_3 = float(sorted_values[:-3].mean()) if len(values) > 3 else np.nan
        all_family = results.loc[results["family"] == family.value]
        lines.append(
            f"{family.value:5} {len(frame):3d} {int((~all_family['complete']).sum()):3d} "
            f"{values.mean():+.3f} [{low:+.3f},{high:+.3f}] {np.median(values):+.3f} "
            f"{(values > 0).mean():.3f} {values.sum():+.2f} {frame['usd_001'].sum():+.2f} "
            f"{frame['holding_minutes'].median():.1f} {max_drawdown(ordered['r'].to_numpy(float)):.2f} "
            f"{values.min():+.2f} {losing_streak(ordered['r'].to_numpy(float)):d} "
            f"{all_family['runner_activated'].mean():.3f} {all_family['partial_taken'].mean():.3f} "
            f"{all_family['graduated'].mean():.3f} {no_best_1:+.3f} {no_best_3:+.3f}"
        )
        reasons = all_family["reason"].value_counts().sort_index()
        lines.append("  reasons: " + ", ".join(f"{key}={value}" for key, value in reasons.items()))
        weekly = frame.assign(week=frame["entry_time"].dt.strftime("%G-W%V")).groupby("week")["r"].sum()
        lines.append(
            f"  weeks: {int((weekly > 0).sum())}/{len(weekly)} positive; "
            f"worst={weekly.min():+.2f}; best={weekly.max():+.2f}"
        )
        for window, group in frame.groupby("window", sort=False):
            lines.append(f"  window {window}: n={len(group)}, mean_R={group['r'].mean():+.3f}")
        for side, group in frame.groupby("side", sort=True):
            lines.append(
                f"  side {'BUY' if side > 0 else 'SELL'}: n={len(group)}, mean_R={group['r'].mean():+.3f}"
            )
    complete_ids = set(results["entry_id"].unique())
    for family in ExitFamily:
        complete_ids &= set(
            results.loc[(results["family"] == family.value) & results["complete"], "entry_id"]
        )
    common = results.loc[results["entry_id"].isin(complete_ids)]
    lines.extend(["", f"common complete entries across all exits: {len(complete_ids)}"])
    for family in ExitFamily:
        frame = common.loc[common["family"] == family.value]
        lines.append(f"  {family.value}: mean_R={frame['r'].mean():+.3f}, total_R={frame['r'].sum():+.2f}")
    lines.extend(
        [
            "",
            "USD uses the repository convention for XAUUSD: 0.01 lot = 1 USD per 1.00 price move.",
            "No P2 or exam data was enabled. No exit has been selected in this report.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    opportunities = pd.read_parquet(HERE / "opportunities_p1.parquet")
    selected = opportunities.loc[
        (opportunities["threshold"] == 0.25) & (opportunities["timeframe"] == "M1")
    ].copy()
    selected = selected.sort_values("entry_time").reset_index(drop=True)
    assert len(selected) == 138
    m1 = load_m1(BAR_PATH, P1, warmup_start=pd.Timestamp("2025-09-01", tz="UTC"))
    bars = {"M5": aggregate(m1, "5min"), "M15": aggregate(m1, "15min")}
    atrs = {name: atr_values(frame) for name, frame in bars.items()}
    pivots = {name: confirmed_fractals(frame, radius=1) for name, frame in bars.items()}
    store = TickStore(TICK_ROOT, P1, cache_days=4)
    rows: list[dict[str, object]] = []
    for entry_id, opportunity in selected.iterrows():
        entry_time = pd.Timestamp(opportunity["entry_time"])
        runner_end = entry_time + pd.Timedelta(hours=8)
        path = execution_path(store, entry_time, runner_end)
        events = []
        for timeframe in ("M5", "M15"):
            events.extend(
                structure_events(
                    bars[timeframe],
                    pivots[timeframe],
                    atrs[timeframe],
                    timeframe=timeframe,
                    side=int(opportunity["side"]),
                    entry_time=entry_time,
                    entry_spread=float(opportunity["spread"]),
                    end_time=min(runner_end, P1.end),
                )
            )
        for family in ExitFamily:
            result = run_exit(
                family,
                path,
                int(opportunity["side"]),
                float(opportunity["entry"]),
                float(opportunity["stop"]),
                entry_time,
                events,
            )
            record = {
                "entry_id": entry_id,
                "window": opportunity["window"],
                "anchor": opportunity["anchor"],
                "entry_time": entry_time,
                "side": int(opportunity["side"]),
                "entry": float(opportunity["entry"]),
                "initial_stop": float(opportunity["stop"]),
                "initial_risk": float(opportunity["risk"]),
                **asdict(result),
            }
            record["family"] = result.family.value
            record["reason"] = result.reason.value
            record["usd_001"] = result.r * float(opportunity["risk"]) if result.complete else np.nan
            rows.append(record)
    results = pd.DataFrame(rows).sort_values(["entry_time", "family"]).reset_index(drop=True)
    assert results.groupby("entry_id")["family"].nunique().eq(4).all()
    assert all(day < P1.end for day in store.opened)
    results.to_parquet(HERE / "exit_results_p1.parquet", index=False)
    report = render_report(results, store)
    (HERE / "out_exit_study_p1.txt").write_text(report, encoding="utf-8", newline="\n")
    print(report)  # noqa: T201


if __name__ == "__main__":
    main()
