"""Chunked historical download from MT5 (respects the terminal's 'Max bars in chart' cap)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from app.broker.gateway import MarketDataGateway
from app.core.clock import ensure_utc
from app.core.enums import Timeframe
from app.market_data.candle_service import normalize_rates
from app.market_data.data_models import CANDLE_COLUMNS

log = logging.getLogger(__name__)


def chunk_days_for(tf: Timeframe) -> int:
    """About 20k bars per request keeps well under typical maxbars limits."""
    return max(1, int(20_000 * tf.seconds / 86_400))


def download_history(
    gateway: MarketDataGateway, symbol: str, tf: Timeframe, start: datetime, end: datetime
) -> pd.DataFrame:
    start, end = ensure_utc(start), ensure_utc(end)
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
    if not frames:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset="open_time").sort_values("open_time")
    return df.reset_index(drop=True)
