"""Closed-candle sync to the cloud: bulk history upload and the engine's live stream (PLAN §A13; TAA-706).

Both send ``candles`` events (:class:`app.sync.events.CandlesPayload`): up to 1000 closed bars of one symbol
and timeframe per event, at STATE priority, through the outbox (signed, retried, never blocking trading). The
cloud upserts them into its per-engine ``history_candles`` by open time, so a resend or an overlapping upload
is harmless.

- **Bulk upload** (:func:`queue_frame`): ``python -m app.cli sync upload-history`` (or
  ``scripts/download_history.py --upload``) queues the local Parquet history; ``--send`` also delivers it.
- **Live stream** (:class:`CandleStreamer`): on the engine's candle poll, every traded symbol and configured
  timeframe sends the bars that closed since its cursor (``engine_state`` key ``candle_stream``). A symbol is
  asked again only once its next bar can have closed, and not at all while its market is shut (the next check
  waits one bar), so the stream adds almost no broker calls. The first run seeds ``SEED_BARS`` bars. After a
  long outage at most ``MAX_CATCH_UP`` bars are fetched; an upload fills anything older.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta

import pandas as pd

from app.core.clock import Clock, ensure_utc
from app.core.enums import Timeframe
from app.core.errors import TaaError
from app.market_data.candle_service import CandleService
from app.market_data.history_store import ParquetHistoryStore
from app.storage.repositories import EngineStateRepository
from app.sync.events import CANDLES, MAX_CANDLES
from app.sync.outbox import Outbox, Priority

log = logging.getLogger(__name__)

STREAM_KEY = "candle_stream"
SEED_BARS = 500
MAX_CATCH_UP = 5000


def bars_of(df: pd.DataFrame) -> list[list[object]]:
    """Wire rows of a normalized candle frame (UTC ``open_time``), oldest first."""
    frame = df.sort_values("open_time")
    return [
        [
            ensure_utc(pd.Timestamp(t).to_pydatetime()).isoformat(),
            int(ts),
            float(o),
            float(h),
            float(lo),
            float(c),
            int(v),
            int(sp),
        ]
        for t, ts, o, h, lo, c, v, sp in zip(
            frame["open_time"],
            frame["time_server"].to_numpy(dtype="int64"),
            frame["open"].to_numpy(dtype=float),
            frame["high"].to_numpy(dtype=float),
            frame["low"].to_numpy(dtype=float),
            frame["close"].to_numpy(dtype=float),
            frame["tick_volume"].to_numpy(dtype="int64"),
            frame["spread"].to_numpy(dtype="int64"),
            strict=True,
        )
    ]


def queue_frame(outbox: Outbox, server: str, symbol: str, tf: Timeframe, df: pd.DataFrame) -> int:
    """Queue a frame as ``candles`` events of at most 1000 bars; returns the number of events."""
    if df.empty:
        return 0
    bars = bars_of(df)
    events = 0
    for i in range(0, len(bars), MAX_CANDLES):
        chunk = bars[i : i + MAX_CANDLES]
        outbox.emit(
            CANDLES,
            {"server": server, "symbol": symbol, "timeframe": tf.value, "bars": chunk},
            priority=Priority.STATE,
            # a re-queued chunk (same first bar) replaces its unsent predecessor
            coalesce_key=f"candles:{symbol}:{tf.value}:{chunk[0][0]}"[:96],
        )
        events += 1
    return events


class CandleStreamer:
    def __init__(
        self,
        candles: CandleService,
        outbox: Outbox,
        state: EngineStateRepository,
        clock: Clock,
        *,
        server: str,
        timeframes: Sequence[Timeframe],
        seed_bars: int = SEED_BARS,
    ) -> None:
        self.candles = candles
        self.outbox = outbox
        self.state = state
        self.clock = clock
        self.server = server
        self.timeframes = tuple(dict.fromkeys(timeframes))
        self.seed_bars = seed_bars
        self.events = 0
        self.failures = 0
        self._next_check: dict[str, datetime] = {}
        stored = state.load(STREAM_KEY) or {}
        self.cursors: dict[str, datetime] = {k: datetime.fromisoformat(v) for k, v in stored.items()}

    def tick(self, symbols: Iterable[str]) -> int:
        """Queue the newly closed bars of every symbol and timeframe that is due. Returns events queued."""
        now = self.clock.now_utc()
        queued = 0
        changed = False
        for symbol in symbols:
            for tf in self.timeframes:
                key = f"{symbol}|{tf.value}"
                if now < self._next_check.get(key, now):
                    continue
                try:
                    n = self._stream(symbol, tf, key, now)
                except TaaError as exc:  # a broker hiccup costs this symbol one poll, nothing more
                    self.failures += 1
                    log.warning("candle stream %s %s failed: %s", symbol, tf.value, exc)
                    continue
                queued += n
                changed = changed or n > 0
        if changed:
            self.state.save(STREAM_KEY, {k: v.isoformat() for k, v in self.cursors.items()})
        self.events += queued
        return queued

    def _stream(self, symbol: str, tf: Timeframe, key: str, now: datetime) -> int:
        step = timedelta(seconds=tf.seconds)
        last = self.cursors.get(key)
        count = self.seed_bars if last is None else min(MAX_CATCH_UP, int((now - last) / step) + 2)
        frame = self.candles.closed_candles(symbol, tf, count, expect_live=False)
        df = frame.df
        if last is not None and not df.empty:
            df = df[df["open_time"] > pd.Timestamp(last)]
        if df.empty:  # nothing closed since (e.g. the market is shut): look again one bar later
            self._next_check[key] = now + step
            return 0
        newest = ensure_utc(pd.Timestamp(df["open_time"].max()).to_pydatetime())
        n = queue_frame(self.outbox, self.server, symbol, tf, df)
        self.cursors[key] = newest
        # The next bar closes one step after it opens. If that moment has passed already, the market is shut
        # (the last bar is old): look again one bar later instead of every cycle.
        due = newest + 2 * step
        self._next_check[key] = due if due > now else now + step
        return n


def queue_history(
    outbox: Outbox,
    store: ParquetHistoryStore,
    server: str,
    *,
    symbols: Sequence[str] | None = None,
    timeframes: Sequence[Timeframe] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[int, int]:
    """Queue the stored Parquet history of *server* (optionally narrowed). Returns (events, bars)."""
    events = bars = 0
    for srv, symbol, tf in store.available():
        if srv != server or (symbols and symbol not in symbols) or (timeframes and tf not in timeframes):
            continue
        df = store.load(server, symbol, tf, start, end)
        events += queue_frame(outbox, server, symbol, tf, df)
        bars += len(df)
    return events, bars
