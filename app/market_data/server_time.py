"""Verify the configured broker timezone against live ticks (see ``ServerClock.verify``)."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.broker.gateway import MarketDataGateway
from app.core.clock import ClockStatus, ClockVerification


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
