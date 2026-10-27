# ruff: noqa: E501
"""Exam-guarded, one-UTC-day-at-a-time XAUUSD tick reader for the Trend Runner re-check (2026-10-22).

Added by the 2026-10-22 debug (DEBUG_2026-10-22.md, bug B6): the earlier V1 code managed trades on M1 OHLC plus the
M1 ``spread`` column, although bid/ask ticks exist for every studied date. This module is the only tick reader of the
fixed pipeline. Its guard runs before any filesystem access: a day inside the reserved exam
``[2026-04-18, 2026-10-18)`` raises ``ExamLockedError``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
EXAM_END = pd.Timestamp("2026-10-18", tz="UTC")
DEFAULT_ROOTS = (REPO / "data" / "ticks" / "XAUUSD", Path("D:/taa-data/ticks/XAUUSD"))
COLUMNS = ["time_utc", "bid", "ask"]


class ExamLockedError(RuntimeError):
    """Raised before any read that would touch the reserved exam period."""


def utc(value: object, name: str = "time") -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None or str(ts.tz) != "UTC":
        raise ValueError(f"{name} must be a timezone-aware UTC timestamp")
    return ts


def refuse_exam(start: pd.Timestamp, end: pd.Timestamp | None = None) -> None:
    """Raise when the half-open span [start, end) (or the instant start) overlaps the exam."""
    start = utc(start, "start")
    end = start if end is None else utc(end, "end")
    if end == start:
        if EXAM_START <= start < EXAM_END:
            raise ExamLockedError(f"{start} lies inside the reserved exam [2026-04-18, 2026-10-18)")
        return
    if start < EXAM_END and end > EXAM_START:
        raise ExamLockedError(f"[{start}, {end}) overlaps the reserved exam [2026-04-18, 2026-10-18)")


@dataclass
class TickSource:
    """Reads one UTC-day Parquet file at a time; keeps at most ``cache_days`` days in memory."""

    roots: tuple[Path, ...] = DEFAULT_ROOTS
    cache_days: int = 2
    opened: list[str] = field(default_factory=list)
    _cache: dict[str, pd.DataFrame] = field(default_factory=dict, init=False, repr=False)

    def path_for(self, day: pd.Timestamp) -> Path | None:
        key = day.date().isoformat()
        for root in self.roots:
            path = Path(root) / f"{key}.parquet"
            if path.exists():
                return path
        return None

    def day(self, day: pd.Timestamp) -> pd.DataFrame | None:
        """The ordered quotes of one UTC day, or None when no file exists (weekend, holiday)."""
        day = utc(day, "day").normalize()
        refuse_exam(day, day + pd.Timedelta(days=1))
        key = day.date().isoformat()
        if key in self._cache:
            return self._cache[key]
        path = self.path_for(day)
        if path is None:
            return None
        frame = pd.read_parquet(path, columns=COLUMNS)
        times = pd.DatetimeIndex(frame["time_utc"])
        if times.tz is None or str(times.tz) != "UTC":
            raise ValueError(f"{path}: time_utc must be timezone-aware UTC")
        if len(frame) and ((times < day).any() or (times >= day + pd.Timedelta(days=1)).any()):
            raise ValueError(f"{path}: a quote lies outside its UTC day")
        # Equal timestamps keep file order (separate quotes in one recorded millisecond).
        frame = frame.sort_values("time_utc", kind="stable").reset_index(drop=True)
        self.opened.append(key)
        self._cache[key] = frame
        while len(self._cache) > self.cache_days:
            del self._cache[next(iter(self._cache))]
        return frame

    def iter_from(self, start: pd.Timestamp, *, max_days: int = 10) -> Iterator[pd.DataFrame]:
        """Yield the quotes at/after ``start``, one UTC day per chunk, for at most ``max_days`` calendar days."""
        start = utc(start, "start")
        day = start.normalize()
        for _ in range(max_days):
            frame = self.day(day)
            if frame is not None and len(frame):
                if day == start.normalize():
                    frame = frame.loc[frame["time_utc"] >= start]
                if len(frame):
                    yield frame.reset_index(drop=True)
            day += pd.Timedelta(days=1)

    def span(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Quotes in [start, end] (both inclusive) for a short span."""
        start, end = utc(start, "start"), utc(end, "end")
        refuse_exam(start, end + pd.Timedelta(microseconds=1))
        frames = []
        day = start.normalize()
        while day <= end.normalize():
            frame = self.day(day)
            if frame is not None and len(frame):
                frames.append(frame.loc[(frame["time_utc"] >= start) & (frame["time_utc"] <= end)])
            day += pd.Timedelta(days=1)
        if not frames:
            return pd.DataFrame(columns=COLUMNS)
        return pd.concat(frames, ignore_index=True)
