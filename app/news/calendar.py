"""News blackouts (PLAN §A8 ``NEWS_BLACKOUT``, R5; TAA-407).

The MT5 Python API has no economic calendar, so :class:`NewsCalendar` is an interface. Milestone 1 ships
:class:`ManualBlackouts`, read from ``config.yaml`` → ``sessions.news_blackouts``. A blackout applies to a
symbol when it lists the symbol, or one of the symbol's currencies (base or profit); a blackout that lists
neither applies to every symbol.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.config import BlackoutWindow
from app.core.clock import ensure_utc


@dataclass(frozen=True, slots=True)
class Blackout:
    start: datetime
    end: datetime
    reason: str
    currencies: frozenset[str] = frozenset()
    symbols: frozenset[str] = frozenset()

    def affects(self, symbol: str, currencies: Iterable[str]) -> bool:
        if not self.symbols and not self.currencies:
            return True
        return symbol in self.symbols or bool(self.currencies & set(currencies))

    def covers(self, at: datetime) -> bool:
        return self.start <= ensure_utc(at) < self.end


class NewsCalendar(Protocol):
    def blackouts(self) -> Sequence[Blackout]: ...


class ManualBlackouts:
    def __init__(self, windows: Iterable[BlackoutWindow]) -> None:
        self._items = tuple(
            sorted(
                (
                    Blackout(
                        ensure_utc(w.start_utc),
                        ensure_utc(w.end_utc),
                        w.reason,
                        frozenset(c.upper() for c in w.currencies),
                        frozenset(w.symbols),
                    )
                    for w in windows
                ),
                key=lambda b: b.start,
            )
        )

    def blackouts(self) -> Sequence[Blackout]:
        return self._items


class NewsFilter:
    def __init__(self, calendar: NewsCalendar) -> None:
        self.calendar = calendar

    def active(self, symbol: str, currencies: Iterable[str], at: datetime) -> Blackout | None:
        cur = tuple(currencies)
        return next((b for b in self.calendar.blackouts() if b.covers(at) and b.affects(symbol, cur)), None)

    def next_start(self, symbol: str, currencies: Iterable[str], after: datetime) -> datetime | None:
        """Start of the next blackout affecting *symbol* after *after* (an opportunity window ends there)."""
        cur, after = tuple(currencies), ensure_utc(after)
        starts = [b.start for b in self.calendar.blackouts() if b.start > after and b.affects(symbol, cur)]
        return min(starts, default=None)
