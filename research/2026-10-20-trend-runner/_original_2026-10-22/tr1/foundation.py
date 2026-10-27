"""Read-only data integrity and broker-bar comparisons for TREND-RUNNER."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from tr1.bars import aggregate
from tr1.boundaries import Period
from tr1.data import BAR_COLUMNS, TickStore


@dataclass(frozen=True)
class FrameManifest:
    rows: int
    first: pd.Timestamp | None
    last: pd.Timestamp | None
    duplicate_times: int
    gaps_over_one_minute: int
    largest_gap_minutes: float


@dataclass(frozen=True)
class TickManifest:
    files: int
    rows: int
    first: pd.Timestamp | None
    last: pd.Timestamp | None
    duplicate_times: int
    crossed_spreads: int


@dataclass(frozen=True)
class BarComparison:
    timeframe: str
    matched: int
    only_derived: int
    only_broker: int
    max_abs_difference: float
    differing_values: int


def frame_manifest(frame: pd.DataFrame) -> FrameManifest:
    """Summarize ordered M1 timestamps without judging scheduled market closures."""
    if len(frame) == 0:
        return FrameManifest(0, None, None, 0, 0, 0.0)
    times = pd.DatetimeIndex(frame.index)
    delta = times.to_series().diff().dt.total_seconds().div(60.0)
    gaps = delta[delta > 1.0]
    return FrameManifest(
        rows=len(frame),
        first=times[0],
        last=times[-1],
        duplicate_times=int(times.duplicated(keep=False).sum()),
        gaps_over_one_minute=len(gaps),
        largest_gap_minutes=float(gaps.max()) if len(gaps) else 0.0,
    )


def available_tick_days(root: Path, period: Period) -> list[pd.Timestamp]:
    """List only tick filenames whose UTC date is inside the enabled period."""
    days: list[pd.Timestamp] = []
    for path in sorted(root.glob("????-??-??.parquet")):
        try:
            day = pd.Timestamp(path.stem, tz="UTC")
        except ValueError:
            continue
        if period.contains(day):
            days.append(day)
    return days


def tick_manifest(store: TickStore, days: list[pd.Timestamp]) -> TickManifest:
    """Read each enabled tick day once and summarize integrity without concatenating the store."""
    rows = duplicates = crossed = 0
    first: pd.Timestamp | None = None
    last: pd.Timestamp | None = None
    for day in days:
        ticks = store.day(day)
        stats = store.stats[day.date().isoformat()]
        rows += stats["source_rows"]
        duplicates += stats["duplicate_times"]
        if ticks.empty:
            continue
        crossed += int((ticks["ask"].to_numpy(float) < ticks["bid"].to_numpy(float)).sum())
        day_first = pd.Timestamp(ticks.iloc[0]["time_utc"])
        day_last = pd.Timestamp(ticks.iloc[-1]["time_utc"])
        first = day_first if first is None else min(first, day_first)
        last = day_last if last is None else max(last, day_last)
    return TickManifest(len(days), rows, first, last, duplicates, crossed)


def load_broker_bars(path: Path, period: Period) -> pd.DataFrame:
    """Read stored broker bars inside an enabled half-open period."""
    frame = pd.read_parquet(
        path,
        columns=BAR_COLUMNS,
        filters=[
            ("open_time", ">=", period.start.to_pydatetime()),
            ("open_time", "<", period.end.to_pydatetime()),
        ],
    )
    return frame.drop_duplicates("open_time", keep="last").sort_values("open_time").set_index("open_time")


def compare_broker_bars(m1: pd.DataFrame, broker: pd.DataFrame, timeframe: str) -> BarComparison:
    """Compare derived and stored OHLC on their common UTC open times."""
    derived = aggregate(m1, timeframe, asof=pd.Timestamp(m1.index[-1]) + pd.Timedelta(minutes=1))
    common = derived.index.intersection(broker.index)
    columns = ["open", "high", "low", "close"]
    left = derived.loc[common, columns].to_numpy(float)
    right = broker.loc[common, columns].to_numpy(float)
    difference = np.abs(left - right)
    return BarComparison(
        timeframe=timeframe,
        matched=len(common),
        only_derived=len(derived.index.difference(broker.index)),
        only_broker=len(broker.index.difference(derived.index)),
        max_abs_difference=float(np.nanmax(difference)) if difference.size else 0.0,
        differing_values=int((difference > 1e-9).sum()),
    )
