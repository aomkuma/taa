"""Live quotes: spread in points, tick age, rolling median spread and invalid-price detection."""

from __future__ import annotations

import math
import statistics
from collections import deque

from app.broker.gateway import MarketDataGateway
from app.core.clock import Clock, SystemClock
from app.market_data.data_models import Quote, SymbolSpec


class QuoteService:
    def __init__(
        self,
        gateway: MarketDataGateway,
        clock: Clock | None = None,
        stale_seconds: float = 120.0,
        window: int = 300,
    ) -> None:
        self.gateway = gateway
        self.clock = clock or SystemClock()
        self.stale_seconds = stale_seconds
        self._spreads: dict[str, deque[float]] = {}
        self._last_mid: dict[str, float] = {}
        self._window = window

    def quote(self, spec: SymbolSpec) -> Quote:
        now = self.clock.now_utc()
        tick = self.gateway.tick(spec.name)
        if tick is None:
            return Quote(spec.name, math.nan, math.nan, math.nan, now, math.inf, False, "no tick available")
        age = (now - tick.time_utc).total_seconds()
        spread_points = (tick.ask - tick.bid) / spec.point if spec.point else math.nan
        problem = ""
        if not (math.isfinite(tick.bid) and math.isfinite(tick.ask)) or tick.bid <= 0 or tick.ask <= 0:
            problem = "non-positive or non-finite price"
        elif tick.ask < tick.bid:
            problem = "ask below bid"
        elif age > self.stale_seconds:
            problem = f"stale tick ({age:.0f}s old)"
        quote = Quote(
            spec.name, tick.bid, tick.ask, round(spread_points, 1), tick.time_utc, age, not problem, problem
        )
        if quote.valid:
            self._spreads.setdefault(spec.name, deque(maxlen=self._window)).append(quote.spread_points)
        return quote

    def median_spread(self, symbol: str) -> float | None:
        values = self._spreads.get(symbol)
        return statistics.median(values) if values and len(values) >= 10 else None

    def is_price_jump(self, quote: Quote, atr: float | None, max_atr_multiple: float) -> bool:
        """True when the mid moved more than ``max_atr_multiple`` x ATR since the previous valid quote."""
        if not quote.valid:
            return False
        previous = self._last_mid.get(quote.symbol)
        self._last_mid[quote.symbol] = quote.mid
        if previous is None or not atr or atr <= 0:
            return False
        return abs(quote.mid - previous) > max_atr_multiple * atr
