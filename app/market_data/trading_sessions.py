"""Entry windows per symbol (PLAN §A7 filters, §A8 session checks; TAA-407).

- **Windows** come from ``config.yaml`` → ``sessions.by_symbol`` (else ``sessions.default``). Each is defined
  in the local time of its timezone (an exchange's zone such as ``America/New_York``, or UTC), so DST moves
  with the exchange and never needs fixed UTC hours. Windows may span midnight.
- **Daily breaks** (``symbols.overrides.<sym>.daily_breaks_utc``, e.g. the XAUUSD rollover pause) mean the
  market itself is closed: ``MARKET_CLOSED``. Outside every window: ``SESSION_CLOSED``.
- **Friday cutoff** (``sessions.friday_cutoff_utc``): no new entries from Friday HH:MM UTC to the end of
  Sunday, except for symbols whose windows include Saturday or Sunday (24/7 crypto).
- ``closes_at`` is the earliest of the window's end, the next daily break and the Friday cutoff: an
  opportunity's window can never outlast it (§A26 lifecycle).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from app.config import SessionsConfig, SessionWindow, SymbolsConfig
from app.core.clock import ensure_utc
from app.market_data.quality import parse_breaks


class SessionState(StrEnum):
    OPEN = "OPEN"
    SESSION_CLOSED = "SESSION_CLOSED"  # outside the configured entry windows / after the Friday cutoff
    MARKET_CLOSED = "MARKET_CLOSED"  # inside a daily break of the instrument


@dataclass(frozen=True, slots=True)
class SessionVerdict:
    state: SessionState
    detail: str
    closes_at: datetime | None = None  # when the current open period ends (UTC)

    @property
    def is_open(self) -> bool:
        return self.state is SessionState.OPEN


def _at_local(day: datetime, t: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day.date(), t, tzinfo=tz)


def window_end(window: SessionWindow, at_utc: datetime) -> datetime | None:
    """End (UTC) of the occurrence of *window* that contains *at_utc*, or None when it is outside."""
    tz = ZoneInfo(window.timezone)
    local = ensure_utc(at_utc).astimezone(tz)
    start, end, now = window.start_time, window.end_time, local.time()
    if start < end:
        if local.weekday() in window.days and start <= now < end:
            return _at_local(local, end, tz).astimezone(ensure_utc(at_utc).tzinfo)
        return None
    # spans midnight: the evening part belongs to today, the morning part to yesterday's window
    if local.weekday() in window.days and now >= start:
        return _at_local(local + timedelta(days=1), end, tz).astimezone(ensure_utc(at_utc).tzinfo)
    if (local.weekday() - 1) % 7 in window.days and now < end:
        return _at_local(local, end, tz).astimezone(ensure_utc(at_utc).tzinfo)
    return None


class TradingSessions:
    def __init__(self, sessions: SessionsConfig, symbols: SymbolsConfig) -> None:
        self.sessions = sessions
        self.symbols = symbols

    def windows(self, symbol: str) -> list[SessionWindow]:
        return self.sessions.by_symbol.get(symbol, self.sessions.default)

    def trades_weekends(self, symbol: str) -> bool:
        return any({5, 6} & set(w.days) for w in self.windows(symbol))

    def check(self, symbol: str, at_utc: datetime) -> SessionVerdict:
        at = ensure_utc(at_utc)
        override = self.symbols.overrides.get(symbol)
        breaks = parse_breaks(override.daily_breaks_utc) if override else []
        for start, end in breaks:
            if _in_break(at.time(), start, end):
                return SessionVerdict(
                    SessionState.MARKET_CLOSED, f"daily break {start:%H:%M}-{end:%H:%M} UTC"
                )
        cutoff = self._cutoff_start(symbol, at)
        if cutoff is not None and at >= cutoff:
            return SessionVerdict(
                SessionState.SESSION_CLOSED, f"after the Friday cutoff {self.sessions.friday_cutoff_utc} UTC"
            )
        ends = [e for e in (window_end(w, at) for w in self.windows(symbol)) if e is not None]
        if not ends:
            return SessionVerdict(SessionState.SESSION_CLOSED, "outside the entry windows")
        closes = max(ends)  # overlapping windows: the period lasts until the last one ends
        candidates = [closes, *(_next_break(at, s) for s, _ in breaks)]
        if cutoff is not None:
            candidates.append(cutoff)
        return SessionVerdict(SessionState.OPEN, "", min(candidates))

    def friday_cutoff(self, symbol: str, at_utc: datetime) -> datetime | None:
        """This week's Friday cut-off (UTC) for *symbol*, or None when it does not apply (TAA-1207: resting
        limit parts are cancelled by then)."""
        return self._cutoff_start(symbol, ensure_utc(at_utc))

    def _cutoff_start(self, symbol: str, at: datetime) -> datetime | None:
        """Start of this week's Friday cutoff (UTC) when it applies to *symbol*, else None."""
        if self.sessions.friday_cutoff_utc is None or self.trades_weekends(symbol):
            return None
        hours, minutes = (int(x) for x in self.sessions.friday_cutoff_utc.split(":"))
        friday = (at - timedelta(days=(at.weekday() - 4) % 7)).replace(
            hour=hours, minute=minutes, second=0, microsecond=0
        )
        if at.weekday() < 4:
            friday += timedelta(days=7)  # Monday..Thursday: the coming Friday
        return friday


def _in_break(now: time, start: time, end: time) -> bool:
    return start <= now < end if start < end else now >= start or now < end


def _next_break(at: datetime, start: time) -> datetime:
    candidate = at.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    return candidate if candidate > at else candidate + timedelta(days=1)
