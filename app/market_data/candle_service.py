"""Closed-candle retrieval with UTC normalization, quality checks and processing watermarks.

Only *closed* bars are returned: a bar counts as closed once ``open + timeframe <= server_now - grace``.
The grace period absorbs ticks that arrive slightly late. Position 0 of ``copy_rates_from_pos`` is the
bar still forming and is therefore never used for decisions.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, time

import pandas as pd
from sqlalchemy import select

from app.broker.gateway import MarketDataGateway
from app.config import TimeframesConfig
from app.core.clock import Clock, SystemClock, ensure_utc
from app.core.enums import Timeframe
from app.market_data.data_models import CANDLE_COLUMNS, CandleFrame
from app.market_data.quality import validate_candles
from app.storage.database import Database
from app.storage.models import ProcessedCandle

log = logging.getLogger(__name__)


def normalize_rates(raw: pd.DataFrame, tf: Timeframe, gateway: MarketDataGateway) -> pd.DataFrame:
    """Raw MT5 rates (server-time epochs) -> candle frame with UTC open/close times."""
    if raw.empty:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    open_utc = gateway.server_clock.server_epochs_to_utc(raw["time"].to_numpy())
    df = pd.DataFrame(
        {
            "open_time": open_utc,
            "close_time": open_utc + pd.Timedelta(seconds=tf.seconds),
            "time_server": raw["time"].astype("int64").to_numpy(),
            "open": raw["open"].astype(float).to_numpy(),
            "high": raw["high"].astype(float).to_numpy(),
            "low": raw["low"].astype(float).to_numpy(),
            "close": raw["close"].astype(float).to_numpy(),
            "tick_volume": raw["tick_volume"].astype("int64").to_numpy(),
            "spread": raw["spread"].astype("int64").to_numpy(),
            "real_volume": raw["real_volume"].astype("int64").to_numpy(),
        }
    )
    return df.reset_index(drop=True)


class CandleService:
    def __init__(
        self, gateway: MarketDataGateway, config: TimeframesConfig, clock: Clock | None = None
    ) -> None:
        self.gateway = gateway
        self.config = config
        self.clock = clock or SystemClock()

    def closed_candles(
        self,
        symbol: str,
        tf: Timeframe,
        count: int,
        *,
        expect_live: bool = True,
        breaks: Sequence[tuple[time, time]] = (),
    ) -> CandleFrame:
        raw = self.gateway.rates_from_pos(symbol, tf, 0, count + 2)
        server_now = self.gateway.server_clock.server_now_epoch()
        if not raw.empty:
            limit = server_now - self.config.candle_close_grace_seconds
            closed_mask = raw["time"].to_numpy(dtype="int64") + tf.seconds <= limit
            raw = raw.loc[closed_mask].tail(count)
        df = normalize_rates(raw, tf, self.gateway)
        now = self.clock.now_utc()
        quality = validate_candles(
            df, tf, now, max_gap_bars=self.config.max_gap_bars, expect_live=expect_live, breaks=breaks
        )
        if len(df) < count:
            quality.flags.append(f"SHORT_HISTORY:{len(df)}/{count}")
        return CandleFrame(symbol=symbol, timeframe=tf, df=df, quality=quality, fetched_at_utc=now)


class CandleWatermarks:
    """Persisted last-evaluated bar per symbol/timeframe, so a restart never re-processes a candle."""

    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self.db = db
        self.clock = clock or SystemClock()
        self._cache: dict[tuple[str, str], datetime] = {}

    def get(self, symbol: str, tf: Timeframe) -> datetime | None:
        key = (symbol, tf.value)
        if key not in self._cache:
            with self.db.session() as sess:
                row = sess.execute(
                    select(ProcessedCandle).where(
                        ProcessedCandle.symbol == symbol, ProcessedCandle.timeframe == tf.value
                    )
                ).scalar_one_or_none()
            if row is None:
                return None
            self._cache[key] = row.last_open_time_utc
        return self._cache[key]

    def is_new(self, symbol: str, tf: Timeframe, open_time: datetime) -> bool:
        last = self.get(symbol, tf)
        return last is None or ensure_utc(open_time) > last

    def mark(self, symbol: str, tf: Timeframe, open_time: datetime) -> None:
        open_time = ensure_utc(open_time)
        with self.db.session() as sess:
            row = sess.get(ProcessedCandle, (symbol, tf.value))
            if row is None:
                sess.add(
                    ProcessedCandle(
                        symbol=symbol,
                        timeframe=tf.value,
                        last_open_time_utc=open_time,
                        updated_at=self.clock.now_utc(),
                    )
                )
            elif open_time > row.last_open_time_utc:
                row.last_open_time_utc = open_time
                row.updated_at = self.clock.now_utc()
        previous = self._cache.get((symbol, tf.value))
        self._cache[(symbol, tf.value)] = open_time if previous is None else max(previous, open_time)
