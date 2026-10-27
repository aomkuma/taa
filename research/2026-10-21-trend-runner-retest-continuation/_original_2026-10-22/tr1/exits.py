"""Frozen-candidate exit-family simulator for TREND-RUNNER round 1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd


class ExitFamily(StrEnum):
    FAST = "FAST"
    SWING = "SWING"
    SPLIT = "SPLIT"
    STATE = "STATE"


class ExitReason(StrEnum):
    STOP = "STOP"
    TARGET = "TARGET"
    TIME = "TIME"
    CENSORED = "CENSORED"


@dataclass(frozen=True)
class StructureEvent:
    avail: pd.Timestamp
    timeframe: str
    pivot_time: pd.Timestamp
    pivot_price: float
    stop: float


@dataclass(frozen=True)
class ExitResult:
    family: ExitFamily
    complete: bool
    exit_time: pd.Timestamp | None
    exit_price: float
    reason: ExitReason
    r: float
    holding_minutes: float
    runner_activated: bool
    partial_taken: bool
    graduated: bool
    final_stop: float


def _validate(
    ticks: pd.DataFrame,
    side: int,
    entry: float,
    initial_stop: float,
    entry_time: pd.Timestamp,
) -> tuple[pd.DatetimeIndex, np.ndarray, float]:
    if side not in (-1, 1):
        raise ValueError("side must be -1 or 1")
    risk = (entry - initial_stop) * side
    if risk <= 0:
        raise ValueError("initial stop must define positive risk")
    times = pd.DatetimeIndex(ticks["time_utc"])
    if times.tz is None or str(times.tz) != "UTC" or not times.is_monotonic_increasing:
        raise ValueError("ticks must be ordered, timezone-aware UTC")
    if len(times) and times[0] < entry_time:
        raise ValueError("ticks must start at or after entry")
    bid = ticks["bid"].to_numpy(float)
    ask = ticks["ask"].to_numpy(float)
    if np.any(ask < bid):
        raise ValueError("crossed bid/ask quote")
    return times, bid if side > 0 else ask, float(risk)


def _tighter(side: int, current: float, candidate: float) -> float:
    return max(current, candidate) if side > 0 else min(current, candidate)


def _stopped(side: int, mark: float, stop: float) -> bool:
    return mark <= stop if side > 0 else mark >= stop


def _trail_event_applies(
    event: StructureEvent,
    graduated: bool,
    graduation_time: pd.Timestamp | None,
    runner_end: pd.Timestamp,
) -> bool:
    if event.avail > runner_end:
        return False
    if not graduated:
        return event.timeframe == "M5"
    return event.timeframe == "M15" and graduation_time is not None and event.avail >= graduation_time


def _finish(
    family: ExitFamily,
    reason: ExitReason,
    side: int,
    entry: float,
    risk: float,
    entry_time: pd.Timestamp,
    exit_time: pd.Timestamp | None,
    exit_price: float,
    stop: float,
    *,
    partial: bool = False,
    runner: bool = False,
    graduated: bool = False,
) -> ExitResult:
    complete = reason is not ExitReason.CENSORED
    raw_r = (exit_price - entry) * side / risk if np.isfinite(exit_price) else np.nan
    result_r = (1.0 / 3.0) + (2.0 / 3.0) * raw_r if partial and complete else raw_r
    holding = (exit_time - entry_time).total_seconds() / 60.0 if exit_time is not None else np.nan
    return ExitResult(
        family,
        complete,
        exit_time,
        float(exit_price),
        reason,
        float(result_r),
        float(holding),
        runner,
        partial,
        graduated,
        float(stop),
    )


def _ordered_events(events: list[StructureEvent]) -> list[StructureEvent]:
    return sorted(events, key=lambda event: (event.avail, event.timeframe, event.pivot_time))


def run_exit(
    family: ExitFamily | str,
    ticks: pd.DataFrame,
    side: int,
    entry: float,
    initial_stop: float,
    entry_time: pd.Timestamp,
    events: list[StructureEvent],
) -> ExitResult:
    """Run one predeclared exit family over ordered executable quotes."""
    family = ExitFamily(family)
    entry_time = pd.Timestamp(entry_time)
    times, mark, risk = _validate(ticks, side, entry, initial_stop, entry_time)
    events = _ordered_events(events)
    fast_end = entry_time + pd.Timedelta(minutes=60)
    runner_end = entry_time + pd.Timedelta(hours=8)
    target_1r = entry + side * risk
    target_2r = entry + side * 2.0 * risk
    target_3r = entry + side * 3.0 * risk
    stop = float(initial_stop)
    partial = False
    runner = family in (ExitFamily.SWING, ExitFamily.SPLIT)
    graduated = False
    graduation_time: pd.Timestamp | None = None
    reached_1r_time: pd.Timestamp | None = None
    known_m5: list[StructureEvent] = []
    event_index = 0

    for index, time in enumerate(times):
        price = float(mark[index])
        # Events known strictly before this quote must affect its stop. STATE remembers them for its gate.
        while event_index < len(events) and events[event_index].avail < time:
            event = events[event_index]
            event_index += 1
            if event.timeframe == "M5":
                known_m5.append(event)
            if runner and _trail_event_applies(event, graduated, graduation_time, runner_end):
                stop = _tighter(side, stop, event.stop)
        same_events: list[StructureEvent] = []
        while event_index < len(events) and events[event_index].avail == time:
            same_events.append(events[event_index])
            event_index += 1
        if _stopped(side, price, stop):
            return _finish(
                family,
                ExitReason.STOP,
                side,
                entry,
                risk,
                entry_time,
                time,
                price,
                stop,
                partial=partial,
                runner=runner,
                graduated=graduated,
            )

        if family in (ExitFamily.FAST, ExitFamily.STATE) and not runner:
            reached_target = price >= target_2r if side > 0 else price <= target_2r
            if reached_target:
                return _finish(
                    family,
                    ExitReason.TARGET,
                    side,
                    entry,
                    risk,
                    entry_time,
                    time,
                    target_2r,
                    stop,
                )

        if family is ExitFamily.SPLIT and not partial:
            reached_partial = price >= target_1r if side > 0 else price <= target_1r
            if reached_partial:
                partial = True

        if family is ExitFamily.STATE and not runner:
            known_m5.extend(event for event in same_events if event.timeframe == "M5")
            if time <= fast_end:
                reached_1r = price >= target_1r if side > 0 else price <= target_1r
                if reached_1r and reached_1r_time is None:
                    reached_1r_time = time
                qualifying = [
                    event
                    for event in known_m5
                    if event.avail <= fast_end and _tighter(side, initial_stop, event.stop) != initial_stop
                ]
                if reached_1r_time is not None and qualifying:
                    runner = True
                    for event in qualifying:
                        stop = _tighter(side, stop, event.stop)
                    if _stopped(side, price, stop):
                        return _finish(
                            family,
                            ExitReason.STOP,
                            side,
                            entry,
                            risk,
                            entry_time,
                            time,
                            price,
                            stop,
                            runner=True,
                        )
            if not runner and time >= fast_end:
                return _finish(
                    family,
                    ExitReason.TIME,
                    side,
                    entry,
                    risk,
                    entry_time,
                    time,
                    price,
                    stop,
                )

        if family is ExitFamily.FAST and time >= fast_end:
            return _finish(
                family,
                ExitReason.TIME,
                side,
                entry,
                risk,
                entry_time,
                time,
                price,
                stop,
            )

        if runner and not graduated:
            reached_3r = price >= target_3r if side > 0 else price <= target_3r
            if reached_3r:
                graduated = True
                graduation_time = time

        # Exact-time confirmations occur after price actions at that timestamp.
        for event in same_events:
            if runner and _trail_event_applies(event, graduated, graduation_time, runner_end):
                stop = _tighter(side, stop, event.stop)
        if _stopped(side, price, stop):
            return _finish(
                family,
                ExitReason.STOP,
                side,
                entry,
                risk,
                entry_time,
                time,
                price,
                stop,
                partial=partial,
                runner=runner,
                graduated=graduated,
            )
        if runner and time >= runner_end:
            return _finish(
                family,
                ExitReason.TIME,
                side,
                entry,
                risk,
                entry_time,
                time,
                price,
                stop,
                partial=partial,
                runner=runner,
                graduated=graduated,
            )

    last_time = times[-1] if len(times) else None
    last_price = float(mark[-1]) if len(mark) else np.nan
    return _finish(
        family,
        ExitReason.CENSORED,
        side,
        entry,
        risk,
        entry_time,
        last_time,
        last_price,
        stop,
        partial=partial,
        runner=runner,
        graduated=graduated,
    )
