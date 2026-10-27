# ruff: noqa: S101
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from tr1.boundaries import P1, DataBoundaryError
from tr1.data import TickStore, load_m1


def bar_frame(times: list[str]) -> pd.DataFrame:
    index = pd.to_datetime(times, utc=True)
    return pd.DataFrame(
        {
            "open_time": index,
            "close_time": index + pd.Timedelta(minutes=1),
            "open": range(len(index)),
            "high": range(1, len(index) + 1),
            "low": range(len(index)),
            "close": range(len(index)),
            "tick_volume": 1,
            "spread": 20,
        }
    )


def test_m1_reader_filters_before_returning_rows(tmp_path: Path) -> None:
    path = tmp_path / "M1.parquet"
    bar_frame(
        [
            "2025-10-17 23:59",
            "2025-10-18 00:00",
            "2026-01-15 23:59",
            "2026-01-16 00:00",
        ]
    ).to_parquet(path, index=False)
    result = load_m1(path, P1)
    assert result.index.tolist() == [P1.start, P1.end - pd.Timedelta(minutes=1)]
    assert result.attrs == {"source_rows": 2, "duplicates_removed": 0}


def test_m1_reader_accepts_only_utc_warmup(tmp_path: Path) -> None:
    path = tmp_path / "M1.parquet"
    bar_frame(["2025-10-17 23:59", "2025-10-18 00:00"]).to_parquet(path, index=False)
    result = load_m1(path, P1, warmup_start=pd.Timestamp("2025-10-17 23:59", tz="UTC"))
    assert len(result) == 2
    with pytest.raises(DataBoundaryError):
        load_m1(path, P1, warmup_start=pd.Timestamp("2025-10-17"))


def test_tick_boundary_fails_before_a_missing_file_is_opened(tmp_path: Path) -> None:
    store = TickStore(tmp_path, P1)
    with pytest.raises(DataBoundaryError, match="outside P1"):
        store.day(P1.end)
    assert store.opened == []


def test_tick_reader_checks_the_files_utc_day(tmp_path: Path) -> None:
    day = pd.Timestamp("2025-10-20", tz="UTC")
    frame = pd.DataFrame(
        {
            "time_utc": [day, day + pd.Timedelta(milliseconds=1)],
            "bid": [100.0, 100.1],
            "ask": [100.2, 100.3],
        }
    )
    frame.to_parquet(tmp_path / "2025-10-20.parquet", index=False)
    store = TickStore(tmp_path, P1)
    result = store.day(day)
    assert len(result) == 2
    assert store.opened == [day]
    assert store.stats["2025-10-20"] == {"source_rows": 2, "duplicate_times": 0}


def test_tick_reader_preserves_same_millisecond_quotes_in_file_order(tmp_path: Path) -> None:
    day = pd.Timestamp("2025-10-20", tz="UTC")
    frame = pd.DataFrame(
        {
            "time_utc": [day, day, day + pd.Timedelta(milliseconds=1)],
            "bid": [100.0, 99.0, 101.0],
            "ask": [100.2, 99.2, 101.2],
        }
    )
    frame.to_parquet(tmp_path / "2025-10-20.parquet", index=False)
    store = TickStore(tmp_path, P1)
    result = store.day(day)
    assert result["bid"].tolist() == [100.0, 99.0, 101.0]
    assert store.stats["2025-10-20"] == {"source_rows": 3, "duplicate_times": 1}


def test_tick_cache_does_not_reopen_a_day(tmp_path: Path) -> None:
    day = pd.Timestamp("2025-10-20", tz="UTC")
    pd.DataFrame({"time_utc": [day], "bid": [100.0], "ask": [100.2]}).to_parquet(
        tmp_path / "2025-10-20.parquet", index=False
    )
    store = TickStore(tmp_path, P1, cache_days=1)
    first = store.day(day)
    second = store.day(day)
    assert first is second
    assert store.opened == [day]


def test_tick_reader_rejects_a_row_from_another_day(tmp_path: Path) -> None:
    day = pd.Timestamp("2025-10-20", tz="UTC")
    pd.DataFrame(
        {
            "time_utc": [day + pd.Timedelta(days=1)],
            "bid": [100.0],
            "ask": [100.2],
        }
    ).to_parquet(tmp_path / "2025-10-20.parquet", index=False)
    with pytest.raises(DataBoundaryError, match="outside its allowed UTC day"):
        TickStore(tmp_path, P1).day(day)


def test_tick_span_joins_two_allowed_days_and_stops_at_the_exact_bounds(tmp_path: Path) -> None:
    day = pd.Timestamp("2025-10-20", tz="UTC")
    for offset in (0, 1):
        current = day + pd.Timedelta(days=offset)
        pd.DataFrame(
            {
                "time_utc": [current, current + pd.Timedelta(hours=23, minutes=59)],
                "bid": [100.0, 101.0],
                "ask": [100.2, 101.2],
            }
        ).to_parquet(tmp_path / f"{current.date().isoformat()}.parquet", index=False)
    result = TickStore(tmp_path, P1).span(
        day + pd.Timedelta(hours=23),
        day + pd.Timedelta(days=1, hours=1),
    )
    assert result["time_utc"].tolist() == [
        day + pd.Timedelta(hours=23, minutes=59),
        day + pd.Timedelta(days=1),
    ]


def test_tick_span_refuses_to_cross_the_period_end_before_opening_files(tmp_path: Path) -> None:
    store = TickStore(tmp_path, P1)
    with pytest.raises(DataBoundaryError, match="crosses"):
        store.span(P1.end - pd.Timedelta(minutes=1), P1.end + pd.Timedelta(minutes=1))
    assert store.opened == []
