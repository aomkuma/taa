"""Filtered bar and tick readers for TREND-RUNNER."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from tr1.boundaries import DataBoundaryError, Period, require_utc

BAR_COLUMNS = [
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
]
TICK_COLUMNS = ["time_utc", "bid", "ask"]


def load_m1(path: Path, period: Period, *, warmup_start: pd.Timestamp | None = None) -> pd.DataFrame:
    """Read M1 rows with pushdown filters and verify the half-open period after reading."""
    start = period.start if warmup_start is None else require_utc(warmup_start)
    if start >= period.end:
        raise DataBoundaryError("the M1 start must be before the period end")
    frame = pd.read_parquet(
        path,
        columns=BAR_COLUMNS,
        filters=[("open_time", ">=", start.to_pydatetime()), ("open_time", "<", period.end.to_pydatetime())],
    )
    if frame.empty:
        return frame.set_index(pd.DatetimeIndex([], name="open_time", tz="UTC"))
    times = pd.DatetimeIndex(frame["open_time"])
    if times.tz is None or str(times.tz) != "UTC":
        raise DataBoundaryError("M1 open_time must be timezone-aware UTC")
    if (times < start).any() or (times >= period.end).any():
        raise DataBoundaryError("the Parquet reader returned an M1 row outside the allowed boundary")
    source_rows = len(frame)
    duplicate_rows = int(frame.duplicated("open_time", keep="last").sum())
    frame = frame.drop_duplicates("open_time", keep="last").sort_values("open_time")
    result = frame.set_index("open_time", drop=True)
    result.attrs.update(source_rows=source_rows, duplicates_removed=duplicate_rows)
    return result


@dataclass
class TickStore:
    """One-file-per-UTC-day tick reader whose boundary check precedes every filesystem read."""

    root: Path
    period: Period
    cache_days: int = 0
    opened: list[pd.Timestamp] = field(default_factory=list)
    stats: dict[str, dict[str, int]] = field(default_factory=dict)
    _cache: dict[str, pd.DataFrame] = field(default_factory=dict, init=False, repr=False)

    def day(self, day: pd.Timestamp) -> pd.DataFrame:
        day = require_utc(day).normalize()
        if not self.period.contains(day):
            raise DataBoundaryError(f"{day.date()} is outside {self.period.name}")
        key = day.date().isoformat()
        if key in self._cache:
            return self._cache[key]
        self.opened.append(day)
        path = self.root / f"{key}.parquet"
        frame = pd.read_parquet(path, columns=TICK_COLUMNS)
        if frame.empty:
            return frame
        times = pd.DatetimeIndex(frame["time_utc"])
        if times.tz is None or str(times.tz) != "UTC":
            raise DataBoundaryError("tick time_utc must be timezone-aware UTC")
        next_day = day + pd.Timedelta(days=1)
        if (times < day).any() or (times >= next_day).any() or (times >= self.period.end).any():
            raise DataBoundaryError("the tick file contains a row outside its allowed UTC day")
        source_rows = len(frame)
        duplicate_rows = int(frame.duplicated("time_utc", keep="last").sum())
        self.stats[key] = {
            "source_rows": source_rows,
            "duplicate_times": duplicate_rows,
        }
        # More than one quote can arrive in the same recorded millisecond. Their file order is information: a
        # stop/target simulator must see all of them and preserve that order rather than inventing one quote.
        result = frame.sort_values("time_utc", kind="stable").reset_index(drop=True)
        if self.cache_days > 0:
            self._cache[key] = result
            while len(self._cache) > self.cache_days:
                del self._cache[next(iter(self._cache))]
        return result

    def span(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Read ticks in [start, end], opening only UTC days allowed by this store's period."""
        start = require_utc(start)
        end = require_utc(end)
        if end < start:
            raise ValueError("the tick span end must not precede its start")
        if not self.period.contains(start) or end > self.period.end:
            raise DataBoundaryError("the tick span crosses the enabled period boundary")
        frames: list[pd.DataFrame] = []
        day = start.normalize()
        final_day = end.normalize()
        while day <= final_day and day < self.period.end:
            path = self.root / f"{day.date().isoformat()}.parquet"
            if path.exists():
                frames.append(self.day(day))
            day += pd.Timedelta(days=1)
        if not frames:
            return pd.DataFrame(columns=TICK_COLUMNS)
        ticks = pd.concat(frames, ignore_index=True)
        return ticks.loc[(ticks["time_utc"] >= start) & (ticks["time_utc"] <= end)].reset_index(drop=True)
