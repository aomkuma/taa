# ruff: noqa: S101
"""Run the predeclared TR1 P1 opportunity study. P2 and exam are inaccessible."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from tr1.bars import aggregate, atr, confirmed_fractals, minute_bars
from tr1.boundaries import P1, PeriodName, period_for
from tr1.data import TickStore, load_m1
from tr1.opportunity import find_first_pullback, find_impulse, initial_stop, label_path
from tr1.simulation import market_fill
from tr1.windows import Window, anchor

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
TICK_ROOT = REPO / "data" / "ticks" / "XAUUSD"
THRESHOLDS = (0.25, 0.50, 0.75)
TIMEFRAMES = {"M1": None, "M5": "5min", "M15": "15min"}
DEADLINES = {Window.ASIA: 120, Window.LONDON: 120, Window.NY0830: 240}


def study_days() -> list[str]:
    days = pd.date_range(P1.start.normalize(), P1.end - pd.Timedelta(days=1), freq="1D")
    return [day.date().isoformat() for day in days if day.dayofweek < 5]


def h1_at(h1: pd.DataFrame, values: np.ndarray, moment: pd.Timestamp) -> float:
    available = pd.DatetimeIndex(h1["avail"])
    index = int(available.searchsorted(moment, side="right")) - 1
    return float(values[index]) if index >= 0 else np.nan


def next_anchor_after(anchors: list[pd.Timestamp], moment: pd.Timestamp) -> pd.Timestamp | None:
    index = int(pd.DatetimeIndex(anchors).searchsorted(moment, side="right"))
    return anchors[index] if index < len(anchors) else None


def main() -> None:
    assert period_for(PeriodName.P1) is P1
    m1 = load_m1(BAR_PATH, P1, warmup_start=pd.Timestamp("2025-09-01", tz="UTC"))
    entry_bars = {
        name: minute_bars(m1) if rule is None else aggregate(m1, rule) for name, rule in TIMEFRAMES.items()
    }
    entry_atr = {
        name: atr(
            bars["high"].to_numpy(float),
            bars["low"].to_numpy(float),
            bars["close"].to_numpy(float),
            14,
        )
        for name, bars in entry_bars.items()
    }
    entry_pivots = {name: confirmed_fractals(bars, radius=1) for name, bars in entry_bars.items()}
    h1 = aggregate(m1, "1h")
    h1_values = atr(
        h1["high"].to_numpy(float),
        h1["low"].to_numpy(float),
        h1["close"].to_numpy(float),
        14,
    )
    scheduled = sorted(
        anchor(day, window)
        for day in study_days()
        for window in DEADLINES
        if P1.contains(anchor(day, window))
    )
    store = TickStore(TICK_ROOT, P1, cache_days=2)
    counts: Counter[tuple[str, float, str, str]] = Counter()
    reason_counts: Counter[tuple[str, float, str, str]] = Counter()
    rows: list[dict[str, object]] = []
    for day in study_days():
        for window, deadline in DEADLINES.items():
            at = anchor(day, window)
            if not P1.contains(at):
                continue
            h1_value = h1_at(h1, h1_values, at)
            for threshold in THRESHOLDS:
                impulse = find_impulse(m1, at, h1_value, threshold)
                for timeframe, bars in entry_bars.items():
                    cell = (window.value, threshold, timeframe)
                    counts[(*cell, "anchors")] += 1
                    if impulse is None:
                        counts[(*cell, "no_impulse")] += 1
                        continue
                    counts[(*cell, "impulses")] += 1
                    candidate, reasons = find_first_pullback(
                        bars,
                        impulse,
                        window=window.value,
                        timeframe=timeframe,
                        deadline_minutes=deadline,
                        entry_atr_values=entry_atr[timeframe],
                        pivots=entry_pivots[timeframe],
                    )
                    for reason, value in reasons.items():
                        reason_counts[(*cell, reason)] += value
                    if candidate is None:
                        counts[(*cell, "no_pullback_entry")] += 1
                        continue
                    counts[(*cell, "bar_candidates")] += 1
                    fill_end = min(candidate.decision_time + pd.Timedelta(minutes=5), P1.end)
                    fill_ticks = store.span(candidate.decision_time, fill_end)
                    fill = market_fill(fill_ticks, impulse.side, candidate.decision_time)
                    if fill is None:
                        counts[(*cell, "no_fill")] += 1
                        continue
                    spread = float(fill_ticks.iloc[fill.index]["ask"] - fill_ticks.iloc[fill.index]["bid"])
                    stop, risk = initial_stop(candidate, fill, spread)
                    risk_h = risk / impulse.h1_atr
                    if risk_h < 0.05:
                        counts[(*cell, "risk_too_small")] += 1
                        continue
                    if risk_h > 0.50:
                        counts[(*cell, "risk_too_large")] += 1
                        continue
                    counts[(*cell, "fills")] += 1
                    intended_end = fill.time + pd.Timedelta(hours=8)
                    read_end = min(intended_end + pd.Timedelta(minutes=5), P1.end)
                    path = store.span(fill.time, read_end)
                    label = label_path(path, impulse.side, fill.price, stop, fill.time, intended_end)
                    following = next_anchor_after(scheduled, fill.time)
                    alive_at_next = bool(
                        following is not None
                        and following <= intended_end
                        and (label.stop_time is None or label.stop_time > following)
                    )
                    row = {
                        "window": window.value,
                        "threshold": threshold,
                        "timeframe": timeframe,
                        "anchor": at,
                        "reference": impulse.reference,
                        "h1_atr": impulse.h1_atr,
                        "side": impulse.side,
                        "impulse_decision": impulse.decision,
                        "pivot_time": candidate.pivot_time,
                        "pivot_price": candidate.pivot_price,
                        "pivot_available": candidate.pivot_available,
                        "impulse_span": candidate.impulse_span,
                        "pullback_depth": candidate.pullback_depth,
                        "pullback_depth_h1": candidate.pullback_depth / impulse.h1_atr,
                        "pullback_duration_min": (
                            candidate.pivot_available - impulse.decision
                        ).total_seconds()
                        / 60.0,
                        "pullback_ratio": candidate.pullback_ratio,
                        "continuation_level": candidate.continuation_level,
                        "decision_time": candidate.decision_time,
                        "entry_atr": candidate.entry_atr,
                        "entry_time": fill.time,
                        "entry": fill.price,
                        "spread": spread,
                        "stop": stop,
                        "risk": risk,
                        "risk_h1": risk_h,
                        "entry_minutes": (fill.time - at).total_seconds() / 60.0,
                        "next_anchor": following,
                        "alive_at_next_anchor": alive_at_next,
                        **asdict(label),
                    }
                    rows.append(row)
    opportunities = (
        pd.DataFrame(rows).sort_values(["anchor", "threshold", "timeframe"]).reset_index(drop=True)
    )
    if len(opportunities):
        assert pd.DatetimeIndex(opportunities["anchor"]).max() < P1.end
        assert pd.DatetimeIndex(opportunities["entry_time"]).max() < P1.end
    assert all(day < P1.end for day in store.opened)
    opportunities.to_parquet(HERE / "opportunities_p1.parquet", index=False)
    report = render_report(opportunities, counts, reason_counts, store)
    (HERE / "out_opportunity_p1.txt").write_text(report, encoding="utf-8", newline="\n")
    print(report)  # noqa: T201


def render_report(
    opportunities: pd.DataFrame,
    counts: Counter[tuple[str, float, str, str]],
    reasons: Counter[tuple[str, float, str, str]],
    store: TickStore,
) -> str:
    lines = [
        "TR1 opportunity study - P1 only",
        f"rows: {len(opportunities)}; physical tick files opened: {len(store.opened)}; "
        f"latest: {max(store.opened).date() if store.opened else None}",
        "",
        "window threshold tf anchors impulses bar_candidates fills 1R 2R 3R 5R "
        "median_pb_depth_H median_pb_min median_risk_H median_entry_min "
        "median_MFE median_MAE complete alive_next",
    ]
    for window in [value.value for value in DEADLINES]:
        for threshold in THRESHOLDS:
            for timeframe in TIMEFRAMES:
                key = (window, threshold, timeframe)
                cell = opportunities.loc[
                    (opportunities["window"] == window)
                    & (opportunities["threshold"] == threshold)
                    & (opportunities["timeframe"] == timeframe)
                ]

                def mean(column: str, frame: pd.DataFrame = cell) -> float:
                    return float(frame[column].mean()) if len(frame) else np.nan

                def median(column: str, frame: pd.DataFrame = cell) -> float:
                    return float(frame[column].median()) if len(frame) else np.nan

                lines.append(
                    f"{window:7} {threshold:0.2f} {timeframe:3} "
                    f"{counts[(*key, 'anchors')]:3d} {counts[(*key, 'impulses')]:3d} "
                    f"{counts[(*key, 'bar_candidates')]:3d} {counts[(*key, 'fills')]:3d} "
                    f"{mean('reached_1r'):+.3f} {mean('reached_2r'):+.3f} {mean('reached_3r'):+.3f} "
                    f"{mean('reached_5r'):+.3f} {median('pullback_depth_h1'):.3f} "
                    f"{median('pullback_duration_min'):.1f} {median('risk_h1'):.3f} "
                    f"{median('entry_minutes'):.1f} "
                    f"{median('mfe_r'):+.2f} {median('mae_r'):+.2f} {mean('complete_8h'):.3f} "
                    f"{mean('alive_at_next_anchor'):.3f}"
                )
    lines.extend(["", "rejections and examined invalid pivots:"])
    for key, value in sorted({**counts, **reasons}.items()):
        if key[3] not in {"anchors", "impulses", "bar_candidates", "fills"} and value:
            lines.append(f"{key}: {value}")
    lines.extend(
        [
            "",
            "No P2 or exam data was enabled. This is a descriptive opportunity table, not a selected rule.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
