"""Synthetic multi-timeframe candles for strategy-layer tests (consistent M15 -> H1 aggregation)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from app.config import AppConfig
from app.core.enums import Timeframe
from app.market_data.data_models import CandleFrame, QualityReport
from app.strategy.context_builder import AnalyzedFrame, analyze_frame

START = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)  # a Tuesday


def candles_from_closes(
    closes: Sequence[float] | np.ndarray,
    tf: Timeframe = Timeframe.M15,
    *,
    start: datetime = START,
    wick: float | np.ndarray = 0.0003,
    spread: int = 8,
) -> pd.DataFrame:
    """Candle rows (``CANDLE_COLUMNS`` subset) whose bars open at the previous close."""
    c = np.asarray(closes, dtype=float)
    o = np.r_[c[0], c[:-1]]
    w = np.broadcast_to(np.asarray(wick, dtype=float), c.shape)
    open_time = pd.date_range(start, periods=len(c), freq=pd.Timedelta(seconds=tf.seconds), tz="UTC")
    return pd.DataFrame(
        {
            "open_time": open_time,
            "close_time": open_time + pd.Timedelta(seconds=tf.seconds),
            "open": o,
            "high": np.maximum(o, c) + w,
            "low": np.minimum(o, c) - w,
            "close": c,
            "tick_volume": np.full(len(c), 100, dtype="int64"),
            "spread": np.full(len(c), spread, dtype="int64"),
        }
    )


def random_m15(n: int = 1600, seed: int = 3, drift: float = 0.0, vol: float = 0.0006) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = 1.1 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    wick = np.abs(rng.normal(0.0, vol * 1.1, n))
    return candles_from_closes(closes, wick=wick)


def resample(m15: pd.DataFrame, tf: Timeframe) -> pd.DataFrame:
    """Aggregate M15 rows into *tf* bars; only complete groups are kept."""
    per = tf.seconds // Timeframe.M15.seconds
    key = m15["open_time"].dt.floor(pd.Timedelta(seconds=tf.seconds))
    g = m15.groupby(key, sort=True)
    out = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
            "tick_volume": g["tick_volume"].sum(),
            "spread": g["spread"].max(),
            "count": g["close"].size(),
        }
    )
    out = out[out["count"] == per].drop(columns="count")
    out.index.name = "open_time"
    out = out.reset_index()
    out.insert(1, "close_time", out["open_time"] + pd.Timedelta(seconds=tf.seconds))
    return out


def upto(df: pd.DataFrame, t: datetime) -> pd.DataFrame:
    return df[df["close_time"] <= pd.Timestamp(t)].reset_index(drop=True)


def analyzed(frames: Mapping[Timeframe, pd.DataFrame], config: AppConfig) -> dict[Timeframe, AnalyzedFrame]:
    return {tf: analyze_frame(df, tf, config.indicators, config.regime) for tf, df in frames.items()}


class StubCandles:
    """A ``CandleSource`` serving prepared frames, returning only bars closed by the clock's now."""

    def __init__(self, frames: Mapping[Timeframe, pd.DataFrame], now: datetime) -> None:
        self.frames = dict(frames)
        self.now = now
        self.calls: list[tuple[str, Timeframe, int]] = []

    def closed_candles(self, symbol: str, tf: Timeframe, count: int) -> CandleFrame:
        self.calls.append((symbol, tf, count))
        df = upto(self.frames[tf], self.now).tail(count).reset_index(drop=True)
        return CandleFrame(symbol, tf, df, QualityReport(), self.now)
