"""Style tags of a trade (PLAN §A16 "Style tags"; TAA-1002): the segments analytics groups trades by.

Deterministic functions of a :class:`~app.analytics.trade_builder.Trade`; an unknown fact is tagged
``UNKNOWN``, never guessed.

- **setup:** ``PULLBACK`` or ``BREAKOUT`` from the signal's reason codes (``FIB_PULLBACK``,
  ``RANGE_BREAKOUT``, a neckline ``BREAK``), else from the strategy name (shadow rows store no reason codes),
  else ``OTHER``.
- **direction:** ``LONG`` (BUY) or ``SHORT`` (SELL).
- **holding:** ``SCALP`` under 1 h, ``INTRADAY`` under 24 h, ``SWING`` from 24 h.
- **session:** the entry context's session, else the main FX session at the entry instant
  (:func:`~app.strategy.context_builder.trading_session`): ``ASIA``, ``LONDON``, ``NEW_YORK``,
  ``LONDON_NY_OVERLAP`` or ``OFF``.
- **regime:** the entry timeframe's regime. **volatility:** the entry timeframe's volatility state, else a
  bucket of its ATR percentile (``LOW`` < 25, ``NORMAL`` < 75, ``HIGH`` < 90, else ``EXTREME``).
- **weekday / hour:** of the entry, in UTC (display timezones are a presentation concern).
- **symbol**, **strategy** and **scope**; shadow trades also carry their ``variant`` and ``source``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import timedelta
from enum import StrEnum

from app.analytics.trade_builder import Trade
from app.core.clock import ensure_utc
from app.core.enums import Side, VolatilityState
from app.strategy.context_builder import trading_session

UNKNOWN = "UNKNOWN"
WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
SCALP_MAX = timedelta(hours=1)
INTRADAY_MAX = timedelta(hours=24)
VOLATILITY_EDGES = ((25.0, VolatilityState.LOW), (75.0, VolatilityState.NORMAL), (90.0, VolatilityState.HIGH))


class Setup(StrEnum):
    PULLBACK = "PULLBACK"
    BREAKOUT = "BREAKOUT"
    OTHER = "OTHER"


class Holding(StrEnum):
    SCALP = "SCALP"
    INTRADAY = "INTRADAY"
    SWING = "SWING"


_SETUP_TOKENS = (
    (Setup.PULLBACK, frozenset({"PULLBACK"})),
    (Setup.BREAKOUT, frozenset({"BREAKOUT", "BREAK"})),
)


def _setup_in(words: Iterable[str]) -> Setup | None:
    tokens = {t for w in words for t in w.upper().replace("-", "_").split("_")}
    for setup, keys in _SETUP_TOKENS:
        if tokens & keys:
            return setup
    return None


def setup_of(reason_codes: Iterable[str], strategy: str) -> Setup:
    return _setup_in(reason_codes) or _setup_in([strategy]) or Setup.OTHER


def holding_style(holding: timedelta) -> Holding:
    if holding < SCALP_MAX:
        return Holding.SCALP
    return Holding.INTRADAY if holding < INTRADAY_MAX else Holding.SWING


def volatility_bucket(state: VolatilityState | None, atr_percentile: float | None) -> str:
    if state is not None:
        return state.value
    if atr_percentile is None:
        return UNKNOWN
    for edge, bucket in VOLATILITY_EDGES:
        if atr_percentile < edge:
            return bucket.value
    return VolatilityState.EXTREME.value


@dataclass(frozen=True, slots=True)
class StyleTags:
    setup: str
    direction: str
    holding: str
    session: str
    regime: str
    volatility: str
    weekday: str
    hour: int
    symbol: str
    strategy: str
    scope: str
    variant: str | None = None  # shadow trades only
    source: str | None = None

    def as_dict(self) -> dict[str, str | int | None]:
        return asdict(self)


def style_tags(trade: Trade) -> StyleTags:
    ctx = trade.context
    entry = ensure_utc(trade.entry_time)
    session = ctx.session if ctx.session is not None else trading_session(entry)
    return StyleTags(
        setup=setup_of(ctx.reason_codes, trade.strategy).value,
        direction="LONG" if trade.side is Side.BUY else "SHORT",
        holding=holding_style(trade.holding).value,
        session=session.value,
        regime=ctx.regime.value if ctx.regime is not None else UNKNOWN,
        volatility=volatility_bucket(ctx.volatility, ctx.atr_percentile),
        weekday=WEEKDAYS[entry.weekday()],
        hour=entry.hour,
        symbol=trade.symbol,
        strategy=trade.strategy or UNKNOWN,
        scope=trade.scope.value,
        variant=None if trade.shadow is None else trade.shadow.variant,
        source=None if trade.shadow is None else trade.shadow.source,
    )
