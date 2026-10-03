"""Deterministic synthetic OHLCV frames for indicator tests."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

START = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)


def random_ohlc(
    n: int = 500, seed: int = 7, start_price: float = 1.1000, vol: float = 0.0008
) -> pd.DataFrame:
    """A random-walk H1 frame with consistent OHLC (low <= open/close <= high) and tick volume."""
    rng = np.random.default_rng(seed)
    close = start_price * np.exp(np.cumsum(rng.normal(0.0, vol, n)))
    open_ = np.concatenate(([start_price], close[:-1]))
    spread_up = np.abs(rng.normal(0.0, vol * start_price, n))
    spread_down = np.abs(rng.normal(0.0, vol * start_price, n))
    high = np.maximum(open_, close) + spread_up
    low = np.minimum(open_, close) - spread_down
    index = pd.date_range(START, periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": rng.integers(50, 5000, n).astype("int64"),
        },
        index=index,
    )


def mutate_after(df: pd.DataFrame, t: int, seed: int = 99) -> pd.DataFrame:
    """Return a copy whose bars after position *t* are replaced by an unrelated (but valid) path."""
    other = random_ohlc(len(df), seed=seed, start_price=float(df["close"].iloc[t]) * 1.5)
    out = df.copy()
    for col in out.columns:
        out.iloc[t + 1 :, out.columns.get_loc(col)] = other[col].iloc[t + 1 :].to_numpy()
    return out
