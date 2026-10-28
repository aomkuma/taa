"""P1-only opening-impulse and first-pullback opportunity definitions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tr1.bars import atr, confirmed_fractals
from tr1.simulation import Fill


@dataclass(frozen=True)
class Impulse:
    anchor: pd.Timestamp
    reference: float
    h1_atr: float
    threshold: float
    side: int
    decision: pd.Timestamp
    decision_bar: pd.Timestamp


@dataclass(frozen=True)
class BarCandidate:
    window: str
    timeframe: str
    impulse: Impulse
    pivot_bar: int
    pivot_time: pd.Timestamp
    pivot_price: float
    pivot_available: pd.Timestamp
    impulse_span: float
    pullback_depth: float
    pullback_ratio: float
    continuation_level: float
    decision_bar: int
    decision_time: pd.Timestamp
    entry_atr: float


@dataclass(frozen=True)
class PathLabel:
    stopped: bool
    stop_time: pd.Timestamp | None
    mfe_r: float
    mae_r: float
    reached_1r: bool
    reached_2r: bool
    reached_3r: bool
    reached_5r: bool
    time_1r_min: float
    time_2r_min: float
    time_3r_min: float
    time_5r_min: float
    mae_before_1r: float
    mae_before_2r: float
    mae_before_3r: float
    mae_before_5r: float
    giveback_after_1r: float
    giveback_after_2r: float
    r_60: float
    r_120: float
    r_240: float
    r_480: float
    complete_8h: bool


def find_impulse(
    m1: pd.DataFrame,
    anchor: pd.Timestamp,
    h1_atr: float,
    threshold: float,
) -> Impulse | None:
    """Find the first qualifying M1 close in the first 60 minutes after an anchor."""
    if not np.isfinite(h1_atr) or h1_atr <= 0 or threshold <= 0:
        return None
    anchor = pd.Timestamp(anchor)
    start = int(m1.index.searchsorted(anchor, side="left"))
    if start >= len(m1) or m1.index[start] > anchor + pd.Timedelta(minutes=5):
        return None
    reference = float(m1.iloc[start]["open"])
    end_time = anchor + pd.Timedelta(minutes=60)
    end = int(m1.index.searchsorted(end_time, side="left"))
    distance = threshold * h1_atr
    for index in range(start, end):
        close = float(m1.iloc[index]["close"])
        up = close >= reference + distance
        down = close <= reference - distance
        if up == down:
            continue
        return Impulse(
            anchor=anchor,
            reference=reference,
            h1_atr=h1_atr,
            threshold=threshold,
            side=1 if up else -1,
            decision=pd.Timestamp(m1.index[index]) + pd.Timedelta(minutes=1),
            decision_bar=pd.Timestamp(m1.index[index]),
        )
    return None


def find_first_pullback(
    bars: pd.DataFrame,
    impulse: Impulse,
    *,
    window: str,
    timeframe: str,
    deadline_minutes: int,
    entry_atr_values: np.ndarray | None = None,
    pivots: pd.DataFrame | None = None,
) -> tuple[BarCandidate | None, dict[str, int]]:
    """Find the first valid radius-1 pullback and its first continuation close."""
    reasons = {"pivot_before_impulse": 0, "crossed_origin": 0, "depth": 0, "no_continuation": 0}
    if bars.empty:
        return None, reasons
    highs = bars["high"].to_numpy(float)
    lows = bars["low"].to_numpy(float)
    closes = bars["close"].to_numpy(float)
    entry_atr = (
        atr(highs, lows, closes, 14)
        if entry_atr_values is None
        else np.asarray(entry_atr_values, dtype=float)
    )
    if len(entry_atr) != len(bars):
        raise ValueError("entry_atr_values must align with bars")
    pivots = confirmed_fractals(bars, radius=1) if pivots is None else pivots
    kind = "low" if impulse.side > 0 else "high"
    deadline = impulse.anchor + pd.Timedelta(minutes=deadline_minutes)
    eligible = pivots.loc[
        (pivots["kind"] == kind) & (pivots["pivot_time"] >= impulse.decision) & (pivots["avail"] <= deadline)
    ]
    for pivot in eligible.itertuples(index=False):
        index = int(pivot.pivot)
        if index < 1 or index + 1 >= len(bars) or bars.index[index] < impulse.decision:
            reasons["pivot_before_impulse"] += 1
            continue
        anchor_index = int(bars.index.searchsorted(impulse.anchor, side="left"))
        if anchor_index > index:
            continue
        if impulse.side > 0:
            extreme = float(np.max(highs[anchor_index : index + 1]))
            pivot_price = float(lows[index])
            span = extreme - impulse.reference
            depth = extreme - pivot_price
            crossed_origin = pivot_price <= impulse.reference
            continuation = float(np.max(highs[index - 1 : index + 2]))
        else:
            extreme = float(np.min(lows[anchor_index : index + 1]))
            pivot_price = float(highs[index])
            span = impulse.reference - extreme
            depth = pivot_price - extreme
            crossed_origin = pivot_price >= impulse.reference
            continuation = float(np.min(lows[index - 1 : index + 2]))
        if crossed_origin:
            reasons["crossed_origin"] += 1
            continue
        ratio = depth / span if span > 0 else np.nan
        if not np.isfinite(ratio) or not 0.20 <= ratio <= 0.65:
            reasons["depth"] += 1
            continue
        start = max(index + 2, int(bars.index.searchsorted(pd.Timestamp(pivot.avail), side="left")))
        decision_index: int | None = None
        for current in range(start, len(bars)):
            available = pd.Timestamp(bars.iloc[current]["avail"])
            if available > deadline:
                break
            continued = closes[current] > continuation if impulse.side > 0 else closes[current] < continuation
            if continued:
                decision_index = current
                break
        if decision_index is None:
            reasons["no_continuation"] += 1
            continue
        value = float(entry_atr[decision_index])
        if not np.isfinite(value) or value <= 0:
            reasons["no_continuation"] += 1
            continue
        return (
            BarCandidate(
                window=window,
                timeframe=timeframe,
                impulse=impulse,
                pivot_bar=index,
                pivot_time=pd.Timestamp(bars.index[index]),
                pivot_price=pivot_price,
                pivot_available=pd.Timestamp(pivot.avail),
                impulse_span=float(span),
                pullback_depth=float(depth),
                pullback_ratio=float(ratio),
                continuation_level=continuation,
                decision_bar=decision_index,
                decision_time=pd.Timestamp(bars.iloc[decision_index]["avail"]),
                entry_atr=value,
            ),
            reasons,
        )
    return None, reasons


def initial_stop(candidate: BarCandidate, fill: Fill, spread: float) -> tuple[float, float]:
    """Return the buffered stop and price risk; reject invalid quotes at the caller."""
    if spread < 0:
        raise ValueError("spread must be non-negative")
    buffer = max(spread, 0.10 * candidate.entry_atr)
    stop = candidate.pivot_price - buffer if candidate.impulse.side > 0 else candidate.pivot_price + buffer
    risk = (fill.price - stop) * candidate.impulse.side
    return float(stop), float(risk)


def label_path(
    ticks: pd.DataFrame,
    side: int,
    entry: float,
    stop: float,
    start: pd.Timestamp,
    intended_end: pd.Timestamp,
) -> PathLabel:
    """Describe a stopped eight-hour path; labels never feed an entry or runner gate."""
    risk = (entry - stop) * side
    if side not in (-1, 1) or risk <= 0:
        raise ValueError("invalid side or initial stop")
    times = pd.DatetimeIndex(ticks["time_utc"])
    if times.tz is None or str(times.tz) != "UTC" or not times.is_monotonic_increasing:
        raise ValueError("ticks must be ordered, timezone-aware UTC")
    bid = ticks["bid"].to_numpy(float)
    ask = ticks["ask"].to_numpy(float)
    if np.any(ask < bid):
        raise ValueError("crossed bid/ask quote")
    mark = bid if side > 0 else ask
    milestones = (1, 2, 3, 5)
    current_r = (mark - entry) * side / risk
    stop_mask = mark <= stop if side > 0 else mark >= stop
    stop_matches = np.flatnonzero(stop_mask)
    stop_index = int(stop_matches[0]) if len(stop_matches) else len(times)
    horizon_matches = np.flatnonzero(times >= intended_end)
    horizon_index = int(horizon_matches[0]) if len(horizon_matches) else len(times)
    stopped = stop_index <= horizon_index and stop_index < len(times)
    stop_time = times[stop_index] if stopped else None
    if stopped:
        observed_end = stop_index + 1
        progress_end = stop_index  # the stop quote cannot also earn a milestone or clock exit
    elif horizon_index < len(times):
        observed_end = progress_end = horizon_index + 1
    else:
        observed_end = progress_end = len(times)
    observed = current_r[:observed_end]
    progress = current_r[:progress_end]
    mfe = max(0.0, float(np.max(observed))) if len(observed) else 0.0
    mae = min(0.0, float(np.min(observed))) if len(observed) else 0.0
    reached: dict[int, bool] = {}
    reached_at: dict[int, pd.Timestamp | None] = {}
    reached_index: dict[int, int | None] = {}
    for value in milestones:
        matches = np.flatnonzero(progress >= value)
        index = int(matches[0]) if len(matches) else None
        reached[value] = index is not None
        reached_index[value] = index
        reached_at[value] = times[index] if index is not None else None

    running_peak = np.maximum.accumulate(progress) if len(progress) else np.empty(0)

    def giveback(value: int) -> float:
        index = reached_index[value]
        if index is None:
            return np.nan
        return float(np.max(running_peak[index:] - progress[index:]))

    def adverse_before(value: int) -> float:
        index = reached_index[value]
        end = index + 1 if index is not None else observed_end
        return min(0.0, float(np.min(current_r[:end]))) if end else 0.0

    horizons = {60: np.nan, 120: np.nan, 240: np.nan, 480: np.nan}
    progress_times = times[:progress_end]
    for minute in horizons:
        matches = np.flatnonzero(progress_times >= start + pd.Timedelta(minutes=minute))
        if len(matches):
            horizons[minute] = float(progress[int(matches[0])])
    complete = stopped or horizon_index < len(times)

    def elapsed(value: int) -> float:
        time = reached_at[value]
        return (time - start).total_seconds() / 60.0 if time is not None else np.nan

    return PathLabel(
        stopped=stopped,
        stop_time=stop_time,
        mfe_r=float(mfe),
        mae_r=float(mae),
        reached_1r=reached[1],
        reached_2r=reached[2],
        reached_3r=reached[3],
        reached_5r=reached[5],
        time_1r_min=elapsed(1),
        time_2r_min=elapsed(2),
        time_3r_min=elapsed(3),
        time_5r_min=elapsed(5),
        mae_before_1r=adverse_before(1),
        mae_before_2r=adverse_before(2),
        mae_before_3r=adverse_before(3),
        mae_before_5r=adverse_before(5),
        giveback_after_1r=giveback(1),
        giveback_after_2r=giveback(2),
        r_60=float(horizons[60]),
        r_120=float(horizons[120]),
        r_240=float(horizons[240]),
        r_480=float(horizons[480]),
        complete_8h=complete,
    )
