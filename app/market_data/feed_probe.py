"""Feed probe: what the broker's feed really offers (PLAN_LEARNING §L1; TAA-L001). Read-only.

Before tick features are built on it, three facts about the FBS feed are measured on the real terminal:

- **Depth of market:** whether ``market_book_*`` returns anything for a symbol, how many levels, whether sizes
  are present, and whether the book changes between samples (a static or empty book is useless for features).
- **Tick history depth:** how far back ``copy_ticks_range`` serves ticks, **up to ``max_weeks``**. Searched
  week by week on one weekday (Wednesday, a full trading day for every asset class): exponentially back,
  then a binary search between the last week with ticks and the first without. Granularity: one week.
  **Cost:** every month touched is downloaded whole into the terminal's ``Bases/<server>/ticks`` (about
  40–60 MB per month and symbol for XAUUSD or BTCUSD on FBS, measured 2026-10-06), so the search is capped
  (default 8 weeks) and the CLI refuses to run with little free disk space.
- **Tick stream character:** over a recent window, the tick count and rate, the shares of ticks with a
  ``last`` price and a ``volume`` (both are usually 0 for FX/CFD), and the ``flags`` distribution.

The probe never sends an order and only subscribes to the book for the duration of the sampling.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.broker.gateway import ReadOnlyMT5Gateway
from app.core.clock import ensure_utc
from app.core.errors import BrokerError

log = logging.getLogger(__name__)

DEFAULT_MAX_WEEKS = 8  # each month touched costs ~40-60 MB per symbol in the terminal's tick cache
RETRY_SECONDS = 2.0
RETRIES = 3
WEDNESDAY = 2


@dataclass(frozen=True, slots=True)
class BookReport:
    available: bool  # the terminal accepted the subscription
    samples: int
    empty_samples: int
    max_levels: int
    has_sizes: bool
    distinct_snapshots: int

    @property
    def verdict(self) -> str:
        if not self.available:
            return "UNAVAILABLE"
        if self.empty_samples == self.samples:
            return "EMPTY"
        return "CHANGING" if self.distinct_snapshots > 1 else "STATIC"


@dataclass(frozen=True, slots=True)
class TickReport:
    window_start: datetime
    window_end: datetime
    ticks: int
    per_minute: float
    last_share: float  # ticks with a last price
    volume_share: float  # ticks with a volume
    flags: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProbeReport:
    symbol: str
    book: BookReport
    ticks: TickReport | None
    oldest_tick_week: datetime | None  # the Wednesday of the oldest week with ticks; None: none at all
    history_days: int | None
    history_capped: bool = False  # ticks still found at the search limit: the history goes back further


def probe_book(
    gateway: ReadOnlyMT5Gateway, symbol: str, *, samples: int, interval: float, sleep: Callable[[float], None]
) -> BookReport:
    if not gateway.book_open(symbol):
        return BookReport(False, 0, 0, 0, False, 0)
    seen: list[tuple[tuple[int, float, float], ...]] = []
    empty = 0
    try:
        for i in range(samples):
            snapshot = gateway.book_snapshot(symbol) or []
            if not snapshot:
                empty += 1
            seen.append(tuple(snapshot))
            if i < samples - 1:
                sleep(interval)
    finally:
        gateway.book_close(symbol)
    return BookReport(
        available=True,
        samples=samples,
        empty_samples=empty,
        max_levels=max((len(s) for s in seen), default=0),
        has_sizes=any(level[2] > 0 for s in seen for level in s),
        distinct_snapshots=len({s for s in seen if s}),
    )


def _wednesday_before(at: datetime) -> datetime:
    day = ensure_utc(at).replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=(day.weekday() - WEDNESDAY) % 7 or 7)


def _has_ticks(
    gateway: ReadOnlyMT5Gateway,
    symbol: str,
    day: datetime,
    sleep: Callable[[float], None] | None = None,
    retries: int = 0,
) -> bool:
    """A month not in the terminal's cache is downloaded in the background, and the first query can come back
    empty (seen on FBS, 2026-10-06): ``retries`` more queries, ``RETRY_SECONDS`` apart, before saying no."""
    for attempt in range(retries + 1):
        try:
            if not gateway.raw_ticks(symbol, day, day + timedelta(days=1)).empty:
                return True
        except BrokerError:
            pass
        if sleep is not None and attempt < retries:
            sleep(RETRY_SECONDS)
    return False


def oldest_tick_week(
    gateway: ReadOnlyMT5Gateway,
    symbol: str,
    now: datetime,
    max_weeks: int = DEFAULT_MAX_WEEKS,
    sleep: Callable[[float], None] | None = None,
) -> tuple[datetime | None, bool]:
    """(The Wednesday of the oldest week with ticks within ``max_weeks``, whether the limit was reached)."""
    base = _wednesday_before(now)

    def week(k: int) -> datetime:
        return base - timedelta(weeks=k)

    def has(day: datetime) -> bool:
        return _has_ticks(gateway, symbol, day, sleep, RETRIES if sleep is not None else 0)

    if not has(week(0)):
        return None, False
    good, step = 0, 1
    while step <= max_weeks and has(week(step)):
        good, step = step, step * 2
    if step > max_weeks:  # still ticks at the last doubling inside the limit: check the limit itself
        if has(week(max_weeks)):
            return week(max_weeks), True
        step = max_weeks
    bad = step
    while bad - good > 1:
        mid = (good + bad) // 2
        if has(week(mid)):
            good = mid
        else:
            bad = mid
    return week(good), False


def tick_character(
    gateway: ReadOnlyMT5Gateway, symbol: str, start: datetime, end: datetime
) -> TickReport | None:
    try:
        ticks = gateway.raw_ticks(symbol, start, end)
    except BrokerError as exc:
        log.warning("no ticks for %s: %s", symbol, exc)
        return None
    n = len(ticks)
    minutes = max((end - start).total_seconds() / 60, 1e-9)
    return TickReport(
        window_start=start,
        window_end=end,
        ticks=n,
        per_minute=n / minutes,
        last_share=float((ticks["last"] > 0).mean()) if n else 0.0,
        volume_share=float((ticks["volume"] > 0).mean()) if n else 0.0,
        flags=dict(sorted(Counter(int(f) for f in ticks["flags"]).items())) if n else {},
    )


def probe(
    gateway: ReadOnlyMT5Gateway,
    symbols: Sequence[str],
    now: datetime,
    *,
    book_samples: int = 5,
    book_interval: float = 1.0,
    tick_window: timedelta = timedelta(hours=1),
    max_weeks: int = DEFAULT_MAX_WEEKS,
    sleep: Callable[[float], None],
) -> list[ProbeReport]:
    """Probe each symbol. The tick window is the last ``tick_window`` before ``now``; when the market is
    closed (no ticks there), the same window on the last Wednesday is used instead."""
    now = ensure_utc(now)
    out = []
    for symbol in symbols:
        book = probe_book(gateway, symbol, samples=book_samples, interval=book_interval, sleep=sleep)
        ticks = tick_character(gateway, symbol, now - tick_window, now)
        if ticks is None or ticks.ticks == 0:
            noon = _wednesday_before(now) + timedelta(hours=12)
            ticks = tick_character(gateway, symbol, noon - tick_window, noon)
        oldest, capped = oldest_tick_week(gateway, symbol, now, max_weeks, sleep)
        days = None if oldest is None else (now - oldest).days
        out.append(ProbeReport(symbol, book, ticks, oldest, days, capped))
    return out


def format_report(reports: Sequence[ProbeReport]) -> list[str]:
    lines = []
    for r in reports:
        b = r.book
        lines.append(f"{r.symbol}")
        lines.append(
            f"  depth of market: {b.verdict} (samples {b.samples}, empty {b.empty_samples}, "
            f"max levels {b.max_levels}, sizes {'yes' if b.has_sizes else 'no'}, "
            f"distinct {b.distinct_snapshots})"
        )
        if r.ticks is None:
            lines.append("  ticks: unavailable")
        else:
            t = r.ticks
            lines.append(
                f"  ticks {t.window_start:%Y-%m-%d %H:%M}-{t.window_end:%H:%M} UTC: {t.ticks} "
                f"({t.per_minute:.1f}/min), last>0 {t.last_share:.0%}, volume>0 {t.volume_share:.0%}, "
                f"flags {t.flags}"
            )
        if r.oldest_tick_week is None:
            lines.append("  tick history: none found")
        else:
            more = " or more (search limit reached)" if r.history_capped else ""
            week = f"{r.oldest_tick_week:%Y-%m-%d}"
            lines.append(f"  tick history: back to the week of {week} (~{r.history_days} days{more})")
    return lines
