"""UTC clock bars with explicit availability timestamps."""

from __future__ import annotations

import pandas as pd


def clock_bars(m1: pd.DataFrame, rule: str, *, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Aggregate M1 on UTC clock boundaries and discard the incomplete final clock bar."""
    if m1.empty:
        return pd.DataFrame(columns=["clock_start", "open", "high", "low", "close", "available_at"])
    index = pd.DatetimeIndex(pd.to_datetime(m1["open_time"], utc=True))
    source = m1.set_index(index)
    bars = source.resample(rule, label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        minute_count=("close", "size"),
    )
    bars = bars.dropna(subset=["open", "high", "low", "close"]).reset_index(names="clock_start")
    bars["available_at"] = bars["clock_start"] + pd.tseries.frequencies.to_offset(rule)
    cutoff = pd.Timestamp(cutoff)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    bars = bars.loc[bars["available_at"] <= cutoff].reset_index(drop=True)
    return bars


def add_atr(bars: pd.DataFrame, periods: int = 14) -> pd.DataFrame:
    result = bars.copy()
    previous_close = result["close"].shift(1)
    true_range = pd.concat(
        [
            result["high"] - result["low"],
            (result["high"] - previous_close).abs(),
            (result["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    result["atr"] = true_range.rolling(periods, min_periods=periods).mean()
    return result


def completed_trading_days(m1: pd.DataFrame, *, cutoff: pd.Timestamp) -> pd.DataFrame:
    """UTC-day OHLC; empty weekend dates do not create rows."""
    source = m1.copy()
    source["utc_day"] = pd.to_datetime(source["open_time"], utc=True).dt.floor("D")
    daily = source.groupby("utc_day", sort=True).agg(
        high=("high", "max"),
        low=("low", "min"),
        minute_count=("close", "size"),
    )
    daily = daily.reset_index()
    daily["available_at"] = daily["utc_day"] + pd.Timedelta(days=1)
    cutoff = pd.Timestamp(cutoff)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    return daily.loc[daily["available_at"] <= cutoff].reset_index(drop=True)


def last_available_index(available_at: pd.Series, timestamp: pd.Timestamp) -> int | None:
    values = pd.DatetimeIndex(pd.to_datetime(available_at, utc=True))
    target = pd.Timestamp(timestamp)
    target = target.tz_localize("UTC") if target.tzinfo is None else target.tz_convert("UTC")
    # DatetimeIndex can retain parquet's microsecond unit. Searching timestamps directly avoids
    # accidentally comparing its microsecond integers with Timestamp.value nanoseconds.
    position = int(values.searchsorted(target, side="right") - 1)
    return None if position < 0 else position
