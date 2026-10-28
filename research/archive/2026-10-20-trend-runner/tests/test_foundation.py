# ruff: noqa: S101
from __future__ import annotations

from pathlib import Path

import pandas as pd
from tr1.boundaries import P1
from tr1.foundation import available_tick_days, compare_broker_bars, frame_manifest


def test_frame_manifest_counts_unscheduled_gaps_without_interpreting_them() -> None:
    index = pd.to_datetime(
        ["2025-10-20 00:00", "2025-10-20 00:01", "2025-10-20 00:04"],
        utc=True,
    )
    result = frame_manifest(pd.DataFrame(index=index))
    assert result.rows == 3
    assert result.gaps_over_one_minute == 1
    assert result.largest_gap_minutes == 3.0


def test_available_tick_days_never_lists_p2_or_exam(tmp_path: Path) -> None:
    for name in ("2025-10-20.parquet", "2026-01-16.parquet", "2026-04-18.parquet", "notes.parquet"):
        (tmp_path / name).touch()
    assert available_tick_days(tmp_path, P1) == [pd.Timestamp("2025-10-20", tz="UTC")]


def test_bar_comparison_reports_a_changed_value() -> None:
    index = pd.date_range("2025-10-20 00:00", periods=5, freq="1min", tz="UTC")
    m1 = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5],
            "high": [2, 3, 4, 5, 6],
            "low": [0, 1, 2, 3, 4],
            "close": [1.5, 2.5, 3.5, 4.5, 5.5],
            "tick_volume": 1,
            "spread": 20,
        },
        index=index,
    )
    broker = pd.DataFrame({"open": [1], "high": [6], "low": [0], "close": [5.0]}, index=index[:1])
    result = compare_broker_bars(m1, broker, "5min")
    assert result.matched == 1
    assert result.differing_values == 1
    assert result.max_abs_difference == 0.5
