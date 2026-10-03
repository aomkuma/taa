"""Session-range detectors (PLAN §A29, family SESSIONS, tier T1): Asian-range breakout and London / New York
opening-range breakouts.

Sessions are defined in each exchange's **local** time (zoneinfo), so daylight-saving changes move them
correctly (CODING_STANDARDS §3). A bar belongs to a session by its **open** time. A range is used only when
its session is fully covered by bars (fail closed on missing data) and closed before the breakout bar.
Intraday timeframes only (≤ H1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt
import pandas as pd
from pydantic import Field, field_validator

from app.evidence.chart_patterns import volume_score
from app.evidence.framework import (
    Detector,
    DetectorParams,
    Direction,
    Evidence,
    EvidenceContext,
    Family,
    KeyLevel,
    Tier,
)

IntArray = npt.NDArray[np.int64]


def _hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


@dataclass(frozen=True)
class LocalClock:
    """Each bar's open time in one timezone: calendar day ordinal and minute of day."""

    day: IntArray
    minute: IntArray


def local_clock(ctx: EvidenceContext, tz: str) -> LocalClock:
    def compute() -> LocalClock:
        opens = (ctx.times - pd.Timedelta(seconds=ctx.timeframe.seconds)).tz_convert(ZoneInfo(tz))
        days = opens.normalize().tz_localize(None)
        day = np.asarray((days - pd.Timestamp("1970-01-01")) // pd.Timedelta(days=1), dtype=np.int64)
        minute = np.asarray(opens.hour * 60 + opens.minute, dtype=np.int64)
        return LocalClock(day, minute)

    return ctx.memo(("local_clock", tz), compute)


class SessionParams(DetectorParams):
    min_range_atr: float = Field(default=0.5, ge=0, le=20)
    max_range_atr: float = Field(default=4.0, gt=0, le=50)


def _validate_hhmm(value: str) -> str:
    _hhmm(value)
    return value


def _validate_tz(value: str) -> str:
    ZoneInfo(value)
    return value


@dataclass(frozen=True, slots=True)
class Range:
    high: float
    low: float
    last_pos: int  # last bar of the range

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2

    @property
    def height(self) -> float:
        return self.high - self.low


def collect_ranges(ctx: EvidenceContext, clock: LocalClock, start: time, end: time) -> dict[int, Range]:
    """High/low of the bars opening in ``[start, end)`` local time, per local day, if fully covered."""
    lo_min, hi_min = start.hour * 60 + start.minute, end.hour * 60 + end.minute
    tf_min = ctx.timeframe.seconds // 60
    expected = (hi_min - lo_min) // tf_min
    inside = (clock.minute >= lo_min) & (clock.minute < hi_min)
    out: dict[int, Range] = {}
    for day in np.unique(clock.day[inside]):
        pos = np.flatnonzero(inside & (clock.day == day))
        if len(pos) < expected:
            continue  # missing bars: the range is unknown
        out[int(day)] = Range(float(ctx.h[pos].max()), float(ctx.l[pos].min()), int(pos[-1]))
    return out


def _breakouts(
    detector: Detector,
    ctx: EvidenceContext,
    ranges: dict[int, Range],
    window_clock: LocalClock,
    window: tuple[int, int],
    params: Any,
    variant: str | None,
) -> list[Evidence]:
    """First close beyond each day's range inside the local-time window (once per day)."""
    atr = ctx.atr_array()
    out: list[Evidence] = []
    done: set[int] = set()
    in_window = (window_clock.minute >= window[0]) & (window_clock.minute < window[1])
    for t in (int(i) for i in np.flatnonzero(in_window)):
        day = int(window_clock.day[t])
        r = ranges.get(day)
        if r is None or day in done or t <= r.last_pos or t < 1:
            continue
        a = atr[r.last_pos]
        if not np.isfinite(a) or not (params.min_range_atr * a <= r.height <= params.max_range_atr * a):
            continue
        sign = 1 if ctx.c[t] > r.high else (-1 if ctx.c[t] < r.low else 0)
        if sign == 0:
            continue
        done.add(day)
        edge = r.high if sign > 0 else r.low
        out.append(
            detector.make(
                ctx,
                t,
                Direction.BULL if sign > 0 else Direction.BEAR,
                0.5 + 0.5 * volume_score(ctx, t),
                key_levels=[KeyLevel("range_high", r.high), KeyLevel("range_low", r.low)],
                invalidation=r.mid,
                targets=[edge + sign * r.height],
                details={"range_atr": round(r.height / a, 3)},
                variant=variant,
            )
        )
    return out


class AsianParams(SessionParams):
    asian_tz: str = "Asia/Tokyo"
    asian_start: str = "09:00"
    asian_end: str = "15:00"
    breakout_tz: str = "Europe/London"
    breakout_start: str = "08:00"
    breakout_end: str = "12:00"

    _hhmm = field_validator("asian_start", "asian_end", "breakout_start", "breakout_end")(_validate_hhmm)
    _tz = field_validator("asian_tz", "breakout_tz")(_validate_tz)


class AsianRangeBreakout(Detector):
    """The Tokyo-session range (09:00–15:00 Tokyo), broken by the first close beyond it during the London
    morning (08:00–12:00 London) of the same calendar day. Target: the range height beyond the broken edge."""

    id = "sessions.asian_breakout"
    name = "Asian-range breakout"
    family = Family.SESSIONS
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = AsianParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        if ctx.timeframe.seconds > 3600 or ctx.n == 0:
            return []
        asia = local_clock(ctx, params.asian_tz)
        london = local_clock(ctx, params.breakout_tz)
        ranges = collect_ranges(ctx, asia, _hhmm(params.asian_start), _hhmm(params.asian_end))
        # key the Tokyo ranges by the London calendar day of their last bar, so both clocks agree on "the day"
        by_london_day = {int(london.day[r.last_pos]): r for r in ranges.values()}
        ws, we = _hhmm(params.breakout_start), _hhmm(params.breakout_end)
        window = (ws.hour * 60 + ws.minute, we.hour * 60 + we.minute)
        return _breakouts(self, ctx, by_london_day, london, window, params, None)


class OpenRangeParams(SessionParams):
    sessions: dict[str, tuple[str, str]] = Field(
        default_factory=lambda: {
            "london": ("Europe/London", "08:00"),
            "new_york": ("America/New_York", "08:00"),
        },
        min_length=1,
    )
    range_minutes: int = Field(default=60, ge=1, le=600)
    window_minutes: int = Field(default=180, ge=1, le=1440)  # after the opening range

    @field_validator("sessions")
    @classmethod
    def _sessions(cls, value: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str]]:
        for tz, hhmm in value.values():
            _validate_tz(tz)
            _validate_hhmm(hhmm)
        return value


class OpenRangeBreakout(Detector):
    """Opening-range breakout: the high/low of the first ``range_minutes`` after a session opens (London
    and New York, local time), broken by the first close beyond it within the next ``window_minutes``."""

    id = "sessions.open_breakout"
    name = "Opening-range breakout"
    family = Family.SESSIONS
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = OpenRangeParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        if ctx.timeframe.seconds > 3600 or ctx.n == 0:
            return []
        out: list[Evidence] = []
        for name, (tz, hhmm) in params.sessions.items():
            clock = local_clock(ctx, tz)
            opening = _hhmm(hhmm)
            start = opening.hour * 60 + opening.minute
            range_end = start + params.range_minutes
            if range_end > 24 * 60:
                continue
            ranges = collect_ranges(ctx, clock, opening, time(range_end // 60 % 24, range_end % 60))
            window = (range_end, min(range_end + params.window_minutes, 24 * 60))
            out += _breakouts(self, ctx, ranges, clock, window, params, name)
        return out
