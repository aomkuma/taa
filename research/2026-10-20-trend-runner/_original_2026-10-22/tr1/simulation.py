"""Spread-aware tick execution for TREND-RUNNER research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd


class ExitReason(StrEnum):
    STOP = "stop"
    TARGET = "target"
    TIME = "time"


@dataclass(frozen=True)
class Fill:
    index: int
    time: pd.Timestamp
    price: float


@dataclass(frozen=True)
class TradeResult:
    side: int
    entry_time: pd.Timestamp
    entry: float
    stop: float
    target: float | None
    exit_time: pd.Timestamp
    exit_price: float
    reason: ExitReason
    pnl: float
    risk: float
    r: float


def _arrays(ticks: pd.DataFrame) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    required = {"time_utc", "bid", "ask"}
    missing = required.difference(ticks.columns)
    if missing:
        raise ValueError(f"missing tick columns: {sorted(missing)}")
    times = pd.DatetimeIndex(ticks["time_utc"])
    if times.tz is None or str(times.tz) != "UTC":
        raise ValueError("tick times must be timezone-aware UTC")
    if not times.is_monotonic_increasing:
        raise ValueError("ticks must be ordered by time")
    bid = ticks["bid"].to_numpy(float)
    ask = ticks["ask"].to_numpy(float)
    if np.any(ask < bid):
        raise ValueError("crossed bid/ask quote")
    return times, bid, ask


def market_fill(
    ticks: pd.DataFrame,
    side: int,
    active_at: pd.Timestamp,
    *,
    slippage: float = 0.0,
) -> Fill | None:
    """Fill at the first quote at/after active_at, on the adverse side of the spread."""
    if side not in (-1, 1) or slippage < 0:
        raise ValueError("side must be -1/+1 and slippage must be non-negative")
    times, bid, ask = _arrays(ticks)
    active_at = pd.Timestamp(active_at)
    index = int(times.searchsorted(active_at, side="left"))
    if index >= len(times):
        return None
    price = ask[index] + slippage if side > 0 else bid[index] - slippage
    return Fill(index, times[index], float(price))


def stop_entry_fill(
    ticks: pd.DataFrame,
    side: int,
    trigger: float,
    active_at: pd.Timestamp,
    expires_at: pd.Timestamp,
    *,
    slippage: float = 0.0,
) -> Fill | None:
    """Fill a stop entry at the trigger or the first worse quote, whichever is more adverse."""
    if side not in (-1, 1) or slippage < 0:
        raise ValueError("side must be -1/+1 and slippage must be non-negative")
    times, bid, ask = _arrays(ticks)
    active_at = pd.Timestamp(active_at)
    expires_at = pd.Timestamp(expires_at)
    if expires_at < active_at:
        raise ValueError("the stop-entry expiry must not precede activation")
    start = int(times.searchsorted(active_at, side="left"))
    end = int(times.searchsorted(expires_at, side="right"))
    quote = ask if side > 0 else bid
    touched = quote[start:end] >= trigger if side > 0 else quote[start:end] <= trigger
    matches = np.flatnonzero(touched)
    if not len(matches):
        return None
    index = start + int(matches[0])
    price = max(trigger, ask[index]) + slippage if side > 0 else min(trigger, bid[index]) - slippage
    return Fill(index, times[index], float(price))


def run_trade(
    ticks: pd.DataFrame,
    side: int,
    fill: Fill,
    stop: float,
    target: float | None,
    exit_at: pd.Timestamp,
) -> TradeResult | None:
    """Run from a fill through stop, target or the first quote at/after exit_at; a stop wins a tie."""
    if side not in (-1, 1):
        raise ValueError("side must be -1 or +1")
    risk = (fill.price - stop) * side
    if not risk > 0:
        raise ValueError("the initial stop must define positive risk")
    if target is not None and (target - fill.price) * side <= 0:
        raise ValueError("the target must be beyond the entry in the trade direction")
    times, bid, ask = _arrays(ticks)
    exit_at = pd.Timestamp(exit_at)
    if fill.index >= len(times) or times[fill.index] != fill.time:
        raise ValueError("the fill does not refer to this tick stream")
    mark = bid if side > 0 else ask
    for index in range(fill.index, len(times)):
        price = mark[index]
        stop_hit = price <= stop if side > 0 else price >= stop
        if stop_hit:
            exit_price = min(stop, price) if side > 0 else max(stop, price)
            return _result(side, fill, stop, target, times[index], exit_price, ExitReason.STOP, risk)
        target_hit = target is not None and (price >= target if side > 0 else price <= target)
        if target_hit:
            return _result(side, fill, stop, target, times[index], target, ExitReason.TARGET, risk)
        if times[index] >= exit_at:
            return _result(side, fill, stop, target, times[index], price, ExitReason.TIME, risk)
    return None


def _result(
    side: int,
    fill: Fill,
    stop: float,
    target: float | None,
    exit_time: pd.Timestamp,
    exit_price: float,
    reason: ExitReason,
    risk: float,
) -> TradeResult:
    pnl = (float(exit_price) - fill.price) * side
    return TradeResult(
        side=side,
        entry_time=fill.time,
        entry=fill.price,
        stop=stop,
        target=target,
        exit_time=exit_time,
        exit_price=float(exit_price),
        reason=reason,
        pnl=pnl,
        risk=risk,
        r=pnl / risk,
    )
