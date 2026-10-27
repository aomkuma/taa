"""Independent causal FAST and RUNNER outcome simulator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from .detector import aggregate, atr


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
    family: str
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


@dataclass(frozen=True)
class StructureContext:
    bars: dict[str, pd.DataFrame]
    atrs: dict[str, np.ndarray]
    pivots: dict[str, pd.DataFrame]


def _confirmed_fractals(bars: pd.DataFrame) -> pd.DataFrame:
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    high_window = pd.Series(high).rolling(3, center=True).max().to_numpy()
    low_window = pd.Series(low).rolling(3, center=True).min().to_numpy()
    rows: list[dict[str, object]] = []
    for kind, values, window in (("high", high, high_window), ("low", low, low_window)):
        for pivot in np.flatnonzero(np.isfinite(window) & (values == window)):
            confirm = int(pivot + 1)
            if confirm >= len(bars):
                continue
            rows.append(
                {
                    "kind": kind,
                    "pivot_time": bars.index[pivot],
                    "price": float(values[pivot]),
                    "confirm": confirm,
                    "avail": pd.Timestamp(bars.iloc[confirm]["avail"]),
                }
            )
    columns = ["kind", "pivot_time", "price", "confirm", "avail"]
    return pd.DataFrame(rows, columns=columns).sort_values(["avail", "kind"]).reset_index(drop=True)


def build_structure_context(m1: pd.DataFrame) -> StructureContext:
    if not isinstance(m1.index, pd.DatetimeIndex) or m1.index.tz is None:
        raise ValueError("M1 must have a timezone-aware DatetimeIndex")
    if str(m1.index.tz) != "UTC" or m1.index.has_duplicates or not m1.index.is_monotonic_increasing:
        raise ValueError("M1 timestamps must be unique, increasing UTC")
    bars = {"M5": aggregate(m1, "5min"), "M15": aggregate(m1, "15min")}
    atrs = {
        name: atr(
            frame["high"].to_numpy(float),
            frame["low"].to_numpy(float),
            frame["close"].to_numpy(float),
        )
        for name, frame in bars.items()
    }
    pivots = {name: _confirmed_fractals(frame) for name, frame in bars.items()}
    return StructureContext(bars, atrs, pivots)


def structure_events(
    context: StructureContext,
    *,
    side: int,
    entry_time: pd.Timestamp,
    entry_spread: float,
    end_time: pd.Timestamp,
) -> list[StructureEvent]:
    if side not in (-1, 1):
        raise ValueError("side must be -1 or +1")
    if not np.isfinite(entry_spread) or entry_spread < 0:
        raise ValueError("entry spread must be finite and non-negative")
    entry_time = pd.Timestamp(entry_time)
    end_time = pd.Timestamp(end_time)
    kind = "low" if side > 0 else "high"
    events: list[StructureEvent] = []
    for timeframe in ("M5", "M15"):
        pivots = context.pivots[timeframe]
        eligible = pivots.loc[
            (pivots["kind"] == kind)
            & (pivots["pivot_time"] >= entry_time)
            & (pivots["avail"] >= entry_time)
            & (pivots["avail"] <= end_time)
        ]
        for pivot in eligible.itertuples(index=False):
            atr_value = float(context.atrs[timeframe][int(pivot.confirm)])
            if not np.isfinite(atr_value) or atr_value <= 0:
                continue
            buffer = max(float(entry_spread), 0.10 * atr_value)
            price = float(pivot.price)
            stop = price - buffer if side > 0 else price + buffer
            events.append(
                StructureEvent(
                    pd.Timestamp(pivot.avail),
                    timeframe,
                    pd.Timestamp(pivot.pivot_time),
                    price,
                    float(stop),
                )
            )
    return sorted(events, key=lambda event: (event.avail, event.timeframe, event.pivot_time))


def _tighter(side: int, current: float, candidate: float) -> float:
    return max(current, candidate) if side > 0 else min(current, candidate)


def _stopped(side: int, price: float, stop: float) -> bool:
    return price <= stop if side > 0 else price >= stop


def _event_applies(
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
    family: str,
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
        family, complete, exit_time, float(exit_price), reason, float(result_r), float(holding),
        runner, partial, graduated, float(stop),
    )


def run_exit(
    family: str,
    ticks: pd.DataFrame,
    side: int,
    entry: float,
    initial_stop: float,
    entry_time: pd.Timestamp,
    events: list[StructureEvent],
) -> ExitResult:
    if family not in {"FAST", "RUNNER"}:
        raise ValueError("family must be FAST or RUNNER")
    if side not in (-1, 1):
        raise ValueError("side must be -1 or +1")
    entry_time = pd.Timestamp(entry_time)
    risk = (float(entry) - float(initial_stop)) * side
    if not np.isfinite(risk) or risk <= 0:
        raise ValueError("initial stop must define positive finite risk")
    times = pd.DatetimeIndex(ticks["time_utc"])
    if times.tz is None or str(times.tz) != "UTC":
        raise ValueError("ticks must be timezone-aware UTC")
    if not times.is_monotonic_increasing:
        raise ValueError("ticks must be increasing")
    if len(times) and times[0] < entry_time:
        raise ValueError("ticks must start at or after entry")
    bid = ticks["bid"].to_numpy(float)
    ask = ticks["ask"].to_numpy(float)
    if np.any(ask < bid):
        raise ValueError("crossed bid/ask quote")
    mark = bid if side > 0 else ask
    events = sorted(events, key=lambda event: (event.avail, event.timeframe, event.pivot_time))
    fast_end = entry_time + pd.Timedelta(minutes=60)
    runner_end = entry_time + pd.Timedelta(hours=8)
    target_1r = entry + side * risk
    target_2r = entry + side * 2.0 * risk
    target_3r = entry + side * 3.0 * risk
    stop = float(initial_stop)
    partial = False
    runner = family == "RUNNER"
    graduated = False
    graduation_time: pd.Timestamp | None = None
    event_index = 0

    for index, time in enumerate(times):
        price = float(mark[index])
        while event_index < len(events) and events[event_index].avail < time:
            event = events[event_index]
            event_index += 1
            if runner and _event_applies(event, graduated, graduation_time, runner_end):
                stop = _tighter(side, stop, event.stop)
        same_events: list[StructureEvent] = []
        while event_index < len(events) and events[event_index].avail == time:
            same_events.append(events[event_index])
            event_index += 1
        if _stopped(side, price, stop):
            return _finish(
                family, ExitReason.STOP, side, entry, risk, entry_time, time, price, stop,
                partial=partial, runner=runner, graduated=graduated,
            )
        if family == "FAST":
            reached_target = price >= target_2r if side > 0 else price <= target_2r
            if reached_target:
                return _finish(
                    family, ExitReason.TARGET, side, entry, risk, entry_time, time, target_2r, stop
                )
        elif not partial:
            reached_partial = price >= target_1r if side > 0 else price <= target_1r
            if reached_partial:
                partial = True
        if family == "FAST" and time >= fast_end:
            return _finish(family, ExitReason.TIME, side, entry, risk, entry_time, time, price, stop)
        if runner and not graduated:
            reached_3r = price >= target_3r if side > 0 else price <= target_3r
            if reached_3r:
                graduated = True
                graduation_time = time
        for event in same_events:
            if runner and _event_applies(event, graduated, graduation_time, runner_end):
                stop = _tighter(side, stop, event.stop)
        if _stopped(side, price, stop):
            return _finish(
                family, ExitReason.STOP, side, entry, risk, entry_time, time, price, stop,
                partial=partial, runner=runner, graduated=graduated,
            )
        if runner and time >= runner_end:
            return _finish(
                family, ExitReason.TIME, side, entry, risk, entry_time, time, price, stop,
                partial=partial, runner=True, graduated=graduated,
            )
    last_time = times[-1] if len(times) else None
    last_price = float(mark[-1]) if len(mark) else np.nan
    return _finish(
        family, ExitReason.CENSORED, side, entry, risk, entry_time, last_time, last_price, stop,
        partial=partial, runner=runner, graduated=graduated,
    )
