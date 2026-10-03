"""Verify the configured broker timezone against live ticks (see ``ServerClock.verify``).

Tick timestamps are server time whatever the symbol, so any symbol with a live market can verify the clock.
FX is closed on weekends; 24/7 crypto symbols cover that gap (``symbols.clock_fallback_symbols``).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence

from app.broker.gateway import MarketDataGateway
from app.core.clock import ClockStatus, ClockVerification
from app.core.errors import ConfigError, SymbolUnavailable

log = logging.getLogger(__name__)


def verify_server_time(
    gateway: MarketDataGateway,
    symbol: str,
    *,
    wait_seconds: float = 10.0,
    poll_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> ClockVerification:
    sc = gateway.server_clock
    first = gateway.tick(symbol)
    if first is None:
        return ClockVerification(
            ClockStatus.UNVERIFIED_MARKET_IDLE,
            sc.expected_offset_seconds(),
            None,
            None,
            f"no tick for {symbol}",
        )
    latest = first
    waited = 0.0
    while waited < wait_seconds:
        sleep(poll_seconds)
        waited += poll_seconds
        tick = gateway.tick(symbol)
        if tick is not None and tick.time_server_msc != first.time_server_msc:
            latest = tick
            break
    advancing = latest.time_server_msc != first.time_server_msc
    return sc.verify(latest.time_server_msc / 1000.0, advancing=advancing)


def verify_server_time_any(
    gateway: MarketDataGateway,
    symbols: Sequence[str],
    *,
    wait_seconds: float = 10.0,
    poll_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str | None, ClockVerification]:
    """Try *symbols* in order and return the first result backed by advancing ticks, with its symbol.

    Symbols the server does not offer are skipped. If every market is idle, the last idle result is returned
    with symbol None, so the caller keeps using the configured timezone rules.
    """
    if not symbols:
        raise ConfigError("at least one symbol is required to verify server time")
    idle: ClockVerification | None = None
    for symbol in symbols:
        try:
            gateway.symbol_spec(symbol)  # selects it into Market Watch so its ticks arrive
        except SymbolUnavailable as exc:
            log.info("server time: skipping %s (%s)", symbol, exc)
            continue
        result = verify_server_time(
            gateway, symbol, wait_seconds=wait_seconds, poll_seconds=poll_seconds, sleep=sleep
        )
        if result.status is not ClockStatus.UNVERIFIED_MARKET_IDLE:
            return symbol, result
        idle = result
    if idle is None:
        idle = ClockVerification(
            ClockStatus.UNVERIFIED_MARKET_IDLE,
            gateway.server_clock.expected_offset_seconds(),
            None,
            None,
            f"none of {', '.join(symbols)} is available on this server",
        )
    return None, idle
