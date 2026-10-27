"""Real-data truncation checks for every causal TR1 bar/entry primitive."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from tr1.bars import aggregate, atr, confirmed_fractals, minute_bars
from tr1.boundaries import P1
from tr1.data import load_m1
from tr1.opportunity import find_first_pullback, find_impulse
from tr1.windows import Window, anchor

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
CUTS = (
    pd.Timestamp("2025-11-17 12:34", tz="UTC"),
    pd.Timestamp("2025-12-15 07:47", tz="UTC"),
    pd.Timestamp("2026-01-12 15:23", tz="UTC"),
)
TIMEFRAMES = {"M1": None, "M5": "5min", "M15": "15min"}
DEADLINES = {Window.ASIA: 120, Window.LONDON: 120, Window.NY0830: 240}
THRESHOLDS = (0.25, 0.50, 0.75)


def available_bars(m1: pd.DataFrame, rule: str | None, cut: pd.Timestamp) -> pd.DataFrame:
    bars = minute_bars(m1) if rule is None else aggregate(m1, rule)
    return bars.loc[bars["avail"] <= cut]


def values_at(bars: pd.DataFrame) -> np.ndarray:
    return atr(
        bars["high"].to_numpy(float),
        bars["low"].to_numpy(float),
        bars["close"].to_numpy(float),
        14,
    )


def h1_value(h1: pd.DataFrame, values: np.ndarray, moment: pd.Timestamp) -> float:
    index = int(pd.DatetimeIndex(h1["avail"]).searchsorted(moment, side="right")) - 1
    return float(values[index]) if index >= 0 else np.nan


def study_days(cut: pd.Timestamp) -> list[str]:
    days = pd.date_range(P1.start.normalize(), cut.normalize(), freq="1D")
    return [day.date().isoformat() for day in days if day.dayofweek < 5]


def check_cut(full_m1: pd.DataFrame, cut: pd.Timestamp) -> tuple[int, int, int]:
    truncated_m1 = full_m1.loc[full_m1.index < cut].copy()
    bar_checks = 0
    pivot_checks = 0
    candidate_checks = 0
    full_bars: dict[str, pd.DataFrame] = {}
    truncated_bars: dict[str, pd.DataFrame] = {}
    full_atr: dict[str, np.ndarray] = {}
    truncated_atr: dict[str, np.ndarray] = {}
    full_pivots: dict[str, pd.DataFrame] = {}
    truncated_pivots: dict[str, pd.DataFrame] = {}
    for name, rule in TIMEFRAMES.items():
        left = available_bars(full_m1, rule, cut)
        right = available_bars(truncated_m1, rule, cut)
        assert_frame_equal(left, right, check_exact=True)
        full_bars[name] = left
        truncated_bars[name] = right
        full_atr[name] = values_at(left)
        truncated_atr[name] = values_at(right)
        np.testing.assert_allclose(full_atr[name], truncated_atr[name], equal_nan=True, rtol=0, atol=0)
        bar_checks += len(left)
        left_pivots = confirmed_fractals(left, radius=1)
        right_pivots = confirmed_fractals(right, radius=1)
        assert_frame_equal(left_pivots, right_pivots, check_exact=True)
        full_pivots[name] = left_pivots
        truncated_pivots[name] = right_pivots
        pivot_checks += len(left_pivots)

    full_h1 = aggregate(full_m1, "1h", asof=cut)
    truncated_h1 = aggregate(truncated_m1, "1h", asof=cut)
    assert_frame_equal(full_h1, truncated_h1, check_exact=True)
    full_h1_atr = values_at(full_h1)
    truncated_h1_atr = values_at(truncated_h1)
    np.testing.assert_allclose(full_h1_atr, truncated_h1_atr, equal_nan=True, rtol=0, atol=0)
    bar_checks += len(full_h1)

    for day in study_days(cut):
        for window, deadline_minutes in DEADLINES.items():
            at = anchor(day, window)
            if not P1.contains(at) or at + pd.Timedelta(minutes=deadline_minutes) > cut:
                continue
            left_h = h1_value(full_h1, full_h1_atr, at)
            right_h = h1_value(truncated_h1, truncated_h1_atr, at)
            if not np.isclose(left_h, right_h, rtol=0, atol=0, equal_nan=True):
                raise AssertionError(f"H1 ATR changed at {at} across truncation {cut}")
            for threshold in THRESHOLDS:
                left_impulse = find_impulse(full_m1, at, left_h, threshold)
                right_impulse = find_impulse(truncated_m1, at, right_h, threshold)
                if left_impulse != right_impulse:
                    raise AssertionError(f"impulse changed at {at} threshold {threshold} cut {cut}")
                for name in TIMEFRAMES:
                    if left_impulse is None:
                        candidate_checks += 1
                        continue
                    left_candidate, _ = find_first_pullback(
                        full_bars[name],
                        left_impulse,
                        window=window.value,
                        timeframe=name,
                        deadline_minutes=deadline_minutes,
                        entry_atr_values=full_atr[name],
                        pivots=full_pivots[name],
                    )
                    right_candidate, _ = find_first_pullback(
                        truncated_bars[name],
                        right_impulse,
                        window=window.value,
                        timeframe=name,
                        deadline_minutes=deadline_minutes,
                        entry_atr_values=truncated_atr[name],
                        pivots=truncated_pivots[name],
                    )
                    if left_candidate != right_candidate:
                        raise AssertionError(
                            f"candidate changed at {at} threshold {threshold} {name} cut {cut}"
                        )
                    candidate_checks += 1
    return bar_checks, pivot_checks, candidate_checks


def main() -> None:
    full_m1 = load_m1(BAR_PATH, P1, warmup_start=pd.Timestamp("2025-09-01", tz="UTC"))
    lines = ["TR1 real-data no-look-ahead truncation - P1 only", ""]
    totals = np.zeros(3, dtype=np.int64)
    for cut in CUTS:
        counts = check_cut(full_m1, cut)
        totals += counts
        lines.append(
            f"{cut}: bar/ATR rows {counts[0]}, confirmed pivots {counts[1]}, "
            f"impulse/candidate cells {counts[2]} - PASS"
        )
    lines.extend(
        [
            "",
            f"total bar/ATR row comparisons: {totals[0]}",
            f"total confirmed-pivot comparisons: {totals[1]}",
            f"total impulse/candidate cell comparisons: {totals[2]}",
            "Appending later P1 bars did not change any value available at a cut.",
            "No P2 or exam data was opened.",
            "",
        ]
    )
    report = "\n".join(lines)
    (HERE / "out_lookahead_p1.txt").write_text(report, encoding="utf-8", newline="\n")
    print(report)  # noqa: T201


if __name__ == "__main__":
    main()
