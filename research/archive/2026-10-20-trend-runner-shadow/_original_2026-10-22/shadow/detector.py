"""Independent causal implementation of the frozen TR1 entry detector."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .clocks import DEADLINE_MINUTES


@dataclass(frozen=True)
class Detection:
    window: str
    anchor: pd.Timestamp
    reference: float
    h1_atr: float
    side: int
    impulse_decision: pd.Timestamp
    pivot_time: pd.Timestamp
    pivot_price: float
    pivot_available: pd.Timestamp
    pullback_ratio: float
    decision_time: pd.Timestamp
    entry_atr: float


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = 14) -> np.ndarray:
    previous = np.r_[np.nan, close[:-1]]
    true_range = np.maximum(high, previous) - np.minimum(low, previous)
    if len(true_range):
        true_range[0] = np.nan
    return pd.Series(true_range).rolling(length).mean().to_numpy()


def aggregate(m1: pd.DataFrame, rule: str) -> pd.DataFrame:
    source = m1.copy()
    key = source.index.floor(rule)
    grouped = source.assign(_key=key).groupby("_key", sort=True)
    bars = pd.DataFrame(
        {
            "open": grouped["open"].first(),
            "high": grouped["high"].max(),
            "low": grouped["low"].min(),
            "close": grouped["close"].last(),
        }
    )
    bars.index.name = "open_time"
    bars["avail"] = bars.index + pd.tseries.frequencies.to_offset(rule)
    return bars


def _h1_at_anchor(m1: pd.DataFrame, moment: pd.Timestamp) -> float:
    h1 = aggregate(m1, "1h")
    values = atr(h1["high"].to_numpy(), h1["low"].to_numpy(), h1["close"].to_numpy())
    eligible = np.flatnonzero(pd.DatetimeIndex(h1["avail"]) <= moment)
    return np.nan if not len(eligible) else float(values[int(eligible[-1])])


def detect(m1: pd.DataFrame, at: pd.Timestamp, window: str) -> Detection | None:
    at = pd.Timestamp(at)
    deadline = at + pd.Timedelta(minutes=DEADLINE_MINUTES[window])
    if m1.empty or m1.index.max() + pd.Timedelta(minutes=1) < deadline:
        raise ValueError("M1 has not reached the full anchor deadline")
    h1_atr = _h1_at_anchor(m1, at)
    if not np.isfinite(h1_atr) or h1_atr <= 0:
        return None
    start = int(m1.index.searchsorted(at, side="left"))
    if start >= len(m1) or m1.index[start] > at + pd.Timedelta(minutes=5):
        return None
    reference = float(m1.iloc[start]["open"])
    impulse_end = int(m1.index.searchsorted(at + pd.Timedelta(minutes=60), side="left"))
    side = 0
    impulse_index = -1
    distance = 0.25 * h1_atr
    for index in range(start, impulse_end):
        close = float(m1.iloc[index]["close"])
        if close >= reference + distance:
            side, impulse_index = 1, index
            break
        if close <= reference - distance:
            side, impulse_index = -1, index
            break
    if side == 0:
        return None
    impulse_decision = pd.Timestamp(m1.index[impulse_index]) + pd.Timedelta(minutes=1)
    highs = m1["high"].to_numpy(dtype=float)
    lows = m1["low"].to_numpy(dtype=float)
    closes = m1["close"].to_numpy(dtype=float)
    entry_atrs = atr(highs, lows, closes)
    first_pivot = int(m1.index.searchsorted(impulse_decision, side="left"))
    deadline_index = int(m1.index.searchsorted(deadline, side="left"))
    for pivot in range(max(1, first_pivot), min(len(m1) - 1, deadline_index)):
        is_pivot = (
            lows[pivot] <= lows[pivot - 1] and lows[pivot] <= lows[pivot + 1]
            if side > 0
            else highs[pivot] >= highs[pivot - 1] and highs[pivot] >= highs[pivot + 1]
        )
        if not is_pivot:
            continue
        available = pd.Timestamp(m1.index[pivot + 1]) + pd.Timedelta(minutes=1)
        if available > deadline:
            continue
        if side > 0:
            extreme = float(np.max(highs[start : pivot + 1]))
            pivot_price = float(lows[pivot])
            span = extreme - reference
            depth = extreme - pivot_price
            crossed = pivot_price <= reference
            continuation = float(np.max(highs[pivot - 1 : pivot + 2]))
        else:
            extreme = float(np.min(lows[start : pivot + 1]))
            pivot_price = float(highs[pivot])
            span = reference - extreme
            depth = pivot_price - extreme
            crossed = pivot_price >= reference
            continuation = float(np.min(lows[pivot - 1 : pivot + 2]))
        ratio = depth / span if span > 0 else np.nan
        if crossed or not np.isfinite(ratio) or not 0.20 <= ratio <= 0.65:
            continue
        for current in range(pivot + 2, min(len(m1), deadline_index)):
            decision_time = pd.Timestamp(m1.index[current]) + pd.Timedelta(minutes=1)
            if decision_time > deadline:
                break
            continued = closes[current] > continuation if side > 0 else closes[current] < continuation
            if not continued:
                continue
            entry_atr = float(entry_atrs[current])
            if not np.isfinite(entry_atr) or entry_atr <= 0:
                break
            return Detection(
                window,
                at,
                reference,
                h1_atr,
                side,
                impulse_decision,
                pd.Timestamp(m1.index[pivot]),
                pivot_price,
                available,
                float(ratio),
                decision_time,
                entry_atr,
            )
    return None


def fill_and_risk(detection: Detection, ticks: pd.DataFrame) -> dict[str, object] | None:
    if ticks.empty:
        return None
    times = pd.DatetimeIndex(pd.to_datetime(ticks["time_utc"], utc=True))
    start = int(times.searchsorted(detection.decision_time, side="left"))
    if start >= len(ticks) or times[start] > detection.decision_time + pd.Timedelta(minutes=5):
        return None
    bid = float(ticks.iloc[start]["bid"])
    ask = float(ticks.iloc[start]["ask"])
    if ask < bid:
        raise ValueError("crossed tick quote")
    entry = ask if detection.side > 0 else bid
    spread = ask - bid
    buffer = max(spread, 0.10 * detection.entry_atr)
    stop = detection.pivot_price - buffer if detection.side > 0 else detection.pivot_price + buffer
    risk = (entry - stop) * detection.side
    risk_h1 = risk / detection.h1_atr
    if not 0.05 <= risk_h1 <= 0.50:
        return None
    return {
        "entry_time": times[start],
        "entry": float(entry),
        "spread": float(spread),
        "stop": float(stop),
        "risk": float(risk),
        "risk_h1": float(risk_h1),
    }
