"""Candle validation: ordering, OHLC consistency, session-aware gaps and staleness.

**Gaps** count only bars missing while the market normally trades. Weekends and configured daily breaks are
expected; so are the symbol's own closed hours, learned from the frame itself (2026-10-05): a time-of-day
slot (UTC) that holds a bar on fewer than half of the frame's trading days is a closure (a stock's night,
gold's daily pause), not missing data. Before this, every overnight close of a stock counted as ~70 missing
M15 bars and blocked all its signals as DATA_GAPS. A contiguous hole in normally traded hours (a history
sync failure) is still reported.

Two more closures are not missing data (2026-10-06, measured on FBS: 48 of 69 scanned symbols were blocked):

- **Holidays:** a bar that would fall on a UTC day with no bars at all in the frame. Labor Day (Mon
  2026-09-07) showed as 21 missing H1 bars on every US stock and blocked them for the ~8 weeks a 400-bar H1
  frame spans.
- **Quiet bars:** MT5 makes no bar when no tick arrives, so a thin symbol has scattered one-bar holes in quiet
  hours. ``DATA_GAPS`` therefore judges the **longest** hole against ``max_gap_bars``; scattered holes block
  only when together they exceed :data:`SPARSE_SHARE` of the frame (too little data to trust indicators).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd

from app.core.enums import Timeframe
from app.market_data.data_models import QualityReport


def parse_breaks(items: Sequence[str]) -> list[tuple[time, time]]:
    out = []
    for item in items:
        start, _, end = item.partition("-")
        h1, m1 = (int(x) for x in start.split(":"))
        h2, m2 = (int(x) for x in end.split(":"))
        out.append((time(h1, m1), time(h2, m2)))
    return out


def _is_expected_gap(
    prev_open: datetime, next_open: datetime, tf: Timeframe, breaks: Sequence[tuple[time, time]]
) -> bool:
    prev_close = prev_open + timedelta(seconds=tf.seconds)
    # weekend: the gap starts on Friday/Saturday and ends on Sunday/Monday
    if (
        prev_close.weekday() in (4, 5)
        and next_open.weekday() in (6, 0)
        and (next_open - prev_close) < timedelta(days=4)
    ):
        return True
    for start, end in breaks:
        day = prev_close.date()
        b_start = datetime.combine(day, start, tzinfo=prev_close.tzinfo)
        b_end = datetime.combine(day, end, tzinfo=prev_close.tzinfo)
        if b_end <= b_start:
            b_end += timedelta(days=1)
        slack = timedelta(seconds=tf.seconds)
        if prev_close >= b_start - slack and next_open <= b_end + slack:
            return True
    return False


# a slot must be seen on this many trading days before the frame can call it closed
MIN_DAYS_TO_LEARN = 3
CLOSED_SHARE = 0.5
SPARSE_SHARE = 0.10  # scattered holes beyond this share of the frame's bars still block (DATA_GAPS)


def closed_slots(epoch_s: np.ndarray, tf: Timeframe) -> np.ndarray:
    """Time-of-day slots (UTC, one per bar of *tf*) that hold a bar on fewer than half of the trading days in
    *epoch_s* (bar open times): the symbol's routine closures. Empty when there are too few days to learn
    from, or for a daily or longer timeframe."""
    per_day = 86_400 // tf.seconds
    if per_day <= 1 or len(epoch_s) == 0:
        return np.empty(0, dtype="int64")
    days = epoch_s // 86_400
    n_days = len(np.unique(days))
    if n_days < MIN_DAYS_TO_LEARN:
        return np.empty(0, dtype="int64")
    slots = (epoch_s % 86_400) // tf.seconds
    seen = np.zeros(per_day, dtype="int64")
    np.add.at(seen, np.unique(np.stack([days, slots]), axis=1)[1], 1)  # days with a bar, per slot
    return np.nonzero(seen < CLOSED_SHARE * n_days)[0].astype("int64")


def validate_candles(
    df: pd.DataFrame,
    tf: Timeframe,
    now_utc: datetime,
    *,
    max_gap_bars: int,
    expect_live: bool,
    breaks: Sequence[tuple[time, time]] = (),
    stale_factor: float = 2.0,
) -> QualityReport:
    report = QualityReport()
    if df.empty:
        report.add("NO_DATA")
        return report

    opens = pd.DatetimeIndex(df["open_time"])
    if opens.has_duplicates:
        report.add("DUPLICATE_BARS")
    if not opens.is_monotonic_increasing:
        report.add("UNORDERED_BARS")

    o, h, lo, c = (df[col].to_numpy(dtype=float) for col in ("open", "high", "low", "close"))
    invalid = (
        ~np.isfinite(o)
        | ~np.isfinite(h)
        | ~np.isfinite(lo)
        | ~np.isfinite(c)
        | (lo <= 0)
        | (lo > np.minimum(o, c))
        | (h < np.maximum(o, c))
        | (h < lo)
    )
    report.invalid_rows = int(invalid.sum())
    if report.invalid_rows:
        report.add("INVALID_OHLC")

    if len(opens) > 1:
        epoch_s = np.asarray((opens - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1), dtype="int64")
        deltas = np.diff(epoch_s) / tf.seconds
        closed = closed_slots(epoch_s, tf)
        days_with_bars = np.unique(epoch_s // 86_400) if tf.seconds < 86_400 else None
        longest = 0
        for idx in np.nonzero(deltas > 1.0 + 1e-9)[0]:
            i = int(idx)
            prev_open = pd.Timestamp(opens[i]).to_pydatetime()
            next_open = pd.Timestamp(opens[i + 1]).to_pydatetime()
            if _is_expected_gap(prev_open, next_open, tf, breaks):
                continue
            absent = np.arange(epoch_s[i] + tf.seconds, epoch_s[i + 1], tf.seconds)
            slot = (absent % 86_400) // tf.seconds
            expected = np.isin(slot, closed)
            if days_with_bars is not None and len(days_with_bars) >= MIN_DAYS_TO_LEARN:
                expected |= ~np.isin(absent // 86_400, days_with_bars)  # a whole day without bars: a holiday
            missing = int(np.count_nonzero(~expected))
            if missing == 0:
                continue
            report.missing_bars += missing
            report.unexpected_gaps.append((prev_open, next_open, missing))
            longest = max(longest, missing)
        if longest > max_gap_bars or report.missing_bars > SPARSE_SHARE * len(opens):
            report.add("DATA_GAPS")

    last_close = opens[-1].to_pydatetime() + timedelta(seconds=tf.seconds)
    if now_utc - last_close > timedelta(seconds=tf.seconds * stale_factor):
        report.stale = True
        if expect_live:
            report.add("DATA_STALE")
    return report
