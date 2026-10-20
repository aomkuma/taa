"""Chunked historical download from MT5 (respects the terminal's 'Max bars in chart' cap).

The download is checked against the newest bar the terminal reports. ``copy_rates_range`` serves the
terminal's local history only: on 2026-10-19 (Monday, market open) it returned XAUUSD M1 through Friday's
close, while M5..D1 on the same run and a later ``copy_rates_from_pos`` call had Monday's bars. A download
whose last bar is older than the newest bar inside its window is read again after a wait, and fails with
:class:`HistoryIncompleteError` when it stays short, instead of storing stale history silently.

Only closed bars are returned (close_time <= the window's end): the bar still forming at the end is left out,
so a partial bar is never stored. The completeness check runs before that cut, on the bars as downloaded.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta

import pandas as pd

from app.broker.gateway import MarketDataGateway
from app.core.clock import ensure_utc
from app.core.enums import Timeframe
from app.core.errors import DataQualityError
from app.market_data.candle_service import normalize_rates
from app.market_data.data_models import CANDLE_COLUMNS

log = logging.getLogger(__name__)

TAIL_RETRIES = 4  # waits of 1, 2, 4 and 8 s (15 s in all) before the download fails
TAIL_FIRST_WAIT_S = 1.0


class HistoryIncompleteError(DataQualityError):
    """The terminal reports a newer bar inside the window than its history download returned."""


def chunk_days_for(tf: Timeframe) -> int:
    """About 20k bars per request keeps well under typical maxbars limits."""
    return max(1, int(20_000 * tf.seconds / 86_400))


def _download_range(
    gateway: MarketDataGateway, symbol: str, tf: Timeframe, start: datetime, end: datetime
) -> pd.DataFrame:
    step = timedelta(days=chunk_days_for(tf))
    frames = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + step, end)
        raw = gateway.rates_range(symbol, tf, cursor, chunk_end)
        if not raw.empty:
            frames.append(normalize_rates(raw, tf, gateway))
        log.info("downloaded %s %s %s..%s: %d bars", symbol, tf, cursor.date(), chunk_end.date(), len(raw))
        cursor = chunk_end
    return _combine(frames)


def _combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="open_time", keep="last").sort_values("open_time")
    return df.reset_index(drop=True)


def expected_last_open(
    gateway: MarketDataGateway, symbol: str, tf: Timeframe, start: datetime, end: datetime
) -> pd.Timestamp | None:
    """The newest bar open in [start, end) that the terminal shows outside ``copy_rates_range``.

    Two sources: the newest bars (``copy_rates_from_pos``; position 0 is the forming bar, used here only to
    check the download's completeness, never for a decision) and the bar that holds the latest tick (in case
    the newest bars are stale too). None when neither lies in the window (e.g. a window that ended earlier).
    """
    clock = gateway.server_clock
    candidates: list[pd.Timestamp] = []
    newest = gateway.rates_from_pos(symbol, tf, 0, 3)
    if not newest.empty:
        candidates.extend(pd.Timestamp(t) for t in clock.server_epochs_to_utc(newest["time"].to_numpy()))
    tick = gateway.tick(symbol)
    if tick is not None and tick.time_server_msc > 0:
        # MT5 bars of M1..D1 open on multiples of their length in server wall-clock time (D1: server midnight)
        server_s = tick.time_server_msc // 1000
        candidates.append(pd.Timestamp(clock.server_epoch_to_utc(server_s // tf.seconds * tf.seconds)))
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    inside = [t for t in candidates if lo <= t < hi]
    return max(inside) if inside else None


def closed_bars(df: pd.DataFrame, end: datetime) -> pd.DataFrame:
    """The bars closed by ``end``: the one still forming then is dropped (closed candles only)."""
    if df.empty:
        return df
    return df.loc[df["close_time"] <= pd.Timestamp(end)].reset_index(drop=True)


def download_history(
    gateway: MarketDataGateway,
    symbol: str,
    tf: Timeframe,
    start: datetime,
    end: datetime,
    *,
    sleep: Callable[[float], None] | None = None,
) -> pd.DataFrame:
    """Closed bars with a UTC open in [start, end) (close_time <= end), checked to reach the newest bar the
    terminal shows in the window.

    Raises :class:`HistoryIncompleteError` when the download still ends early after ``TAIL_RETRIES`` waits.
    """
    start, end = ensure_utc(start), ensure_utc(end)
    pause = sleep if sleep is not None else time.sleep
    df = _download_range(gateway, symbol, tf, start, end)
    wait = TAIL_FIRST_WAIT_S
    for attempt in range(TAIL_RETRIES + 1):
        expected = expected_last_open(gateway, symbol, tf, start, end)
        last = None if df.empty else pd.Timestamp(df["open_time"].iloc[-1])
        if expected is None or (last is not None and last >= expected):
            return closed_bars(df, end)
        if attempt == TAIL_RETRIES:
            break
        log.warning(
            "%s %s history ends at %s but the terminal shows a bar at %s; reading the tail again in %.0f s",
            symbol,
            tf,
            last,
            expected,
            wait,
        )
        pause(wait)
        wait *= 2
        tail_start = start if last is None else max(start, last.to_pydatetime())
        df = _combine([df, _download_range(gateway, symbol, tf, tail_start, end)])
    raise HistoryIncompleteError(
        f"{symbol} {tf} history ends at {last} but the terminal shows a bar at {expected} "
        f"(window {start}..{end}); its history is not synchronised - nothing was returned"
    )
