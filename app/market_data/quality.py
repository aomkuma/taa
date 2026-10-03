"""Candle validation: ordering, OHLC consistency, session-aware gaps and staleness."""

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
        epoch_s = (opens - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1)
        deltas = np.diff(np.asarray(epoch_s, dtype="int64")) / tf.seconds
        for idx in np.nonzero(deltas > 1.0 + 1e-9)[0]:
            i = int(idx)
            missing = int(np.rint(deltas[i])) - 1
            prev_open = pd.Timestamp(opens[i]).to_pydatetime()
            next_open = pd.Timestamp(opens[i + 1]).to_pydatetime()
            if _is_expected_gap(prev_open, next_open, tf, breaks):
                continue
            report.missing_bars += missing
            report.unexpected_gaps.append((prev_open, next_open, missing))
        if report.missing_bars > max_gap_bars:
            report.add("DATA_GAPS")

    last_close = opens[-1].to_pydatetime() + timedelta(seconds=tf.seconds)
    if now_utc - last_close > timedelta(seconds=tf.seconds * stale_factor):
        report.stale = True
        if expect_live:
            report.add("DATA_STALE")
    return report
