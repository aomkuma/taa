"""Causal bar aggregation and MT5-compatible ATR for TREND-RUNNER."""

from __future__ import annotations

import numpy as np
import pandas as pd

SUPPORTED = {"5min": pd.Timedelta(minutes=5), "15min": pd.Timedelta(minutes=15), "1h": pd.Timedelta(hours=1)}


def minute_bars(m1: pd.DataFrame) -> pd.DataFrame:
    """Give M1 the same clock-end schema as aggregated bars."""
    if not isinstance(m1.index, pd.DatetimeIndex) or m1.index.tz is None or str(m1.index.tz) != "UTC":
        raise ValueError("M1 must have a timezone-aware UTC DatetimeIndex")
    bars = m1.copy()
    bars["last"] = bars.index
    bars["close_time"] = bars.index + pd.Timedelta(minutes=1)
    bars["avail"] = bars["close_time"]
    return bars


def aggregate(m1: pd.DataFrame, rule: str, *, asof: pd.Timestamp | None = None) -> pd.DataFrame:
    """Aggregate M1 on UTC clock boundaries; a bar becomes available only at its clock end."""
    if rule not in SUPPORTED:
        raise ValueError(f"unsupported bar rule: {rule}")
    if not isinstance(m1.index, pd.DatetimeIndex) or m1.index.tz is None or str(m1.index.tz) != "UTC":
        raise ValueError("M1 must have a timezone-aware UTC DatetimeIndex")
    if m1.index.has_duplicates or not m1.index.is_monotonic_increasing:
        raise ValueError("M1 index must be unique and increasing")
    if m1.empty:
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "tick_volume", "spread", "last", "close_time", "avail"]
        )
    key = m1.index.floor(rule)
    grouped = m1.assign(_key=key, _source_time=m1.index).groupby("_key", sort=True)
    bars = pd.DataFrame(
        {
            "open": grouped["open"].first(),
            "high": grouped["high"].max(),
            "low": grouped["low"].min(),
            "close": grouped["close"].last(),
            "tick_volume": grouped["tick_volume"].sum(),
            "spread": grouped["spread"].last(),
            "last": grouped["_source_time"].max(),
        }
    )
    bars.index.name = "open_time"
    bars["close_time"] = bars.index + SUPPORTED[rule]
    bars["avail"] = bars["close_time"]
    if asof is not None:
        asof = pd.Timestamp(asof)
        if asof.tzinfo is None or str(asof.tz) != "UTC":
            raise ValueError("asof must be timezone-aware UTC")
        bars = bars.loc[bars["avail"] <= asof]
    return bars


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """MT5 ATR true range; the first bar has no previous close."""
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    previous = np.r_[np.nan, close[:-1]]
    result = np.maximum(high, previous) - np.minimum(low, previous)
    if len(result):
        result[0] = np.nan
    return result


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = 14) -> np.ndarray:
    """MT5 ATR.mq5: the simple average of the latest true ranges."""
    if length <= 0:
        raise ValueError("ATR length must be positive")
    return pd.Series(true_range(high, low, close)).rolling(length).mean().to_numpy()


def confirmed_fractals(bars: pd.DataFrame, radius: int = 2) -> pd.DataFrame:
    """Causal fractal pivots with the time at which their right-hand bars have closed."""
    if radius <= 0:
        raise ValueError("the fractal radius must be positive")
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    width = 2 * radius + 1
    high_window = pd.Series(high).rolling(width, center=True).max().to_numpy()
    low_window = pd.Series(low).rolling(width, center=True).min().to_numpy()
    rows: list[dict[str, object]] = []
    for kind, values, window in (("high", high, high_window), ("low", low, low_window)):
        for pivot in np.flatnonzero(np.isfinite(window) & (values == window)):
            confirm = pivot + radius
            if confirm >= len(bars):
                continue
            rows.append(
                {
                    "kind": kind,
                    "pivot": pivot,
                    "pivot_time": bars.index[pivot],
                    "price": values[pivot],
                    "confirm": confirm,
                    "avail": pd.Timestamp(bars.iloc[confirm]["avail"]),
                }
            )
    columns = ["kind", "pivot", "pivot_time", "price", "confirm", "avail"]
    return pd.DataFrame(rows, columns=columns).sort_values(["avail", "kind"]).reset_index(drop=True)
