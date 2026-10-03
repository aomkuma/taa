"""Market sessions and liquidity (PLAN §A25; TAA-6A2).

**Sessions** are defined in the exchange's own timezone, so each centre's daylight-saving switch is handled by
zoneinfo (the US and Europe change on different dates; in those weeks the London/New York overlap moves by an
hour):

| Session | Local hours | Timezone |
|---|---|---|
| SYDNEY | 07:00–16:00 | Australia/Sydney |
| TOKYO | 09:00–18:00 | Asia/Tokyo |
| LONDON | 08:00–17:00 | Europe/London |
| NEW_YORK | 08:00–17:00 | America/New_York |
| EUROPE_EQUITIES | 09:00–17:30 | Europe/Berlin |
| US_EQUITIES | 09:30–16:00 | America/New_York |
| CRYPTO | always open | — |

**Mapping:** Forex trades in the four FX centres; metals in Tokyo, London and New York; energies in London and
New York; indices and stocks in their quote currency's equity session (USD → US, EUR/GBP → Europe, JPY →
Tokyo, AUD → Sydney); crypto around the clock. ``advisory.sessions.overrides`` replaces the mapping for a
symbol.

**Liquidity profile:** the median tick volume per hour of the week (UTC, Monday 00:00 = 0) from H1 history.
``ratio_now`` compares the current hour with the symbol's typical hour; it tells whether the symbol is
active *on this broker* now, which the session table alone cannot.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.advisory.asset_classes import AssetClass
from app.config import SessionWindow
from app.core.clock import ensure_utc
from app.market_data.trading_sessions import window_end

WEEKDAYS = [0, 1, 2, 3, 4]
SESSIONS: dict[str, SessionWindow] = {
    "SYDNEY": SessionWindow(days=WEEKDAYS, start="07:00", end="16:00", timezone="Australia/Sydney"),
    "TOKYO": SessionWindow(days=WEEKDAYS, start="09:00", end="18:00", timezone="Asia/Tokyo"),
    "LONDON": SessionWindow(days=WEEKDAYS, start="08:00", end="17:00", timezone="Europe/London"),
    "NEW_YORK": SessionWindow(days=WEEKDAYS, start="08:00", end="17:00", timezone="America/New_York"),
    "EUROPE_EQUITIES": SessionWindow(days=WEEKDAYS, start="09:00", end="17:30", timezone="Europe/Berlin"),
    "US_EQUITIES": SessionWindow(days=WEEKDAYS, start="09:30", end="16:00", timezone="America/New_York"),
}
ALWAYS_OPEN = "CRYPTO"
SESSION_NAMES = (*SESSIONS, ALWAYS_OPEN)
FX_CENTRES = ("SYDNEY", "TOKYO", "LONDON", "NEW_YORK")
EQUITY_BY_CURRENCY = {
    "USD": "US_EQUITIES",
    "EUR": "EUROPE_EQUITIES",
    "GBP": "EUROPE_EQUITIES",
    "CHF": "EUROPE_EQUITIES",
    "JPY": "TOKYO",
    "AUD": "SYDNEY",
}


def sessions_for(
    symbol: str,
    asset_class: AssetClass,
    quote_currency: str,
    overrides: Mapping[str, Sequence[str]] | None = None,
) -> tuple[str, ...]:
    if overrides and symbol in overrides:
        return tuple(overrides[symbol])
    if asset_class.is_forex:
        return FX_CENTRES
    if asset_class is AssetClass.METAL:
        return ("TOKYO", "LONDON", "NEW_YORK")
    if asset_class is AssetClass.ENERGY:
        return ("LONDON", "NEW_YORK")
    if asset_class is AssetClass.CRYPTO:
        return (ALWAYS_OPEN,)
    if asset_class in (AssetClass.INDEX, AssetClass.STOCK):
        return (EQUITY_BY_CURRENCY.get(quote_currency.upper(), "US_EQUITIES"),)
    return ("LONDON", "NEW_YORK")


@dataclass(frozen=True, slots=True)
class SessionStatus:
    open: bool
    active: tuple[str, ...]
    ends_at: datetime | None  # when the last active session closes (None: always open, or closed)
    next_open: datetime | None  # when the next of the symbol's sessions starts (None: always open)


def next_start(window: SessionWindow, after: datetime) -> datetime:
    """The first start of *window* strictly after *after* (UTC)."""
    tz = ZoneInfo(window.timezone)
    local = ensure_utc(after).astimezone(tz)
    for days in range(0, 9):
        day = (local + timedelta(days=days)).date()
        if day.weekday() not in window.days:
            continue
        start = datetime.combine(day, window.start_time, tzinfo=tz)
        if start > local:
            return start.astimezone(ensure_utc(after).tzinfo)
    raise ValueError(f"session {window} has no start within 9 days")


def session_state(names: Sequence[str], now: datetime) -> SessionStatus:
    now = ensure_utc(now)
    if ALWAYS_OPEN in names:
        return SessionStatus(True, (ALWAYS_OPEN,), None, None)
    windows = {n: SESSIONS[n] for n in names}
    ends = {n: window_end(w, now) for n, w in windows.items()}
    active = tuple(n for n in names if ends[n] is not None)
    upcoming = min(next_start(w, now) for w in windows.values())
    if active:
        ends_at = max(e for e in ends.values() if e is not None)
        return SessionStatus(True, active, ends_at, upcoming)
    return SessionStatus(False, (), None, upcoming)


# --- liquidity ---------------------------------------------------------------------------------------------

HOURS_PER_WEEK = 168


def hour_of_week(at: datetime) -> int:
    at = ensure_utc(at)
    return at.weekday() * 24 + at.hour


@dataclass(frozen=True)
class LiquidityProfile:
    hourly: np.ndarray  # (168,) median tick volume per UTC hour of the week, NaN where there is no data
    weeks: int

    @classmethod
    def from_h1(cls, candles: pd.DataFrame, min_bars_per_hour: int = 2) -> LiquidityProfile:
        """From H1 candles (``open_time``, ``tick_volume``).

        Hours seen fewer than *min_bars_per_hour* times are NaN.
        """
        if candles.empty:
            return cls(np.full(HOURS_PER_WEEK, np.nan), 0)
        times = pd.DatetimeIndex(pd.to_datetime(candles["open_time"], utc=True))
        how = (times.dayofweek * 24 + times.hour).to_numpy()
        vol = candles["tick_volume"].to_numpy(dtype=float)
        hourly = np.full(HOURS_PER_WEEK, np.nan)
        for h in range(HOURS_PER_WEEK):
            values = vol[how == h]
            values = values[np.isfinite(values) & (values > 0)]
            if len(values) >= min_bars_per_hour:
                hourly[h] = float(np.median(values))
        span = (times.max() - times.min()).total_seconds() if len(times) > 1 else 0.0
        weeks = round(span / (7 * 86_400))
        return cls(hourly, weeks)

    @property
    def typical(self) -> float | None:
        known = self.hourly[np.isfinite(self.hourly)]
        return float(np.median(known)) if len(known) else None

    def ratio_now(self, now: datetime) -> float | None:
        """Volume of the current hour of the week relative to the symbol's typical hour (1.0 = typical)."""
        typical = self.typical
        value = self.hourly[hour_of_week(now)]
        if typical is None or typical <= 0 or not np.isfinite(value):
            return None
        return float(value / typical)

    def best_hours(self, n: int = 3) -> list[int]:
        """The *n* most active hours of the week (UTC), most active first."""
        known = [(float(v), h) for h, v in enumerate(self.hourly) if np.isfinite(v)]
        return [h for _, h in sorted(known, key=lambda x: (-x[0], x[1]))[:n]]


def describe_hour(how: int) -> str:
    """``Tue 13:00 UTC``."""
    return f"{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][how // 24]} {how % 24:02d}:00 UTC"
