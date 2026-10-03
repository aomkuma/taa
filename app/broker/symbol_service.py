"""Symbol discovery and validation. Invalid or unavailable symbols are disabled with a clear reason."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.broker.filling import resolve_filling
from app.broker.gateway import MarketDataGateway
from app.core.enums import Side
from app.core.errors import BrokerError, SymbolUnavailable
from app.market_data.data_models import SymbolSpec

log = logging.getLogger(__name__)


@dataclass
class SymbolRegistry:
    specs: dict[str, SymbolSpec] = field(default_factory=dict)
    fillings: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def available(self) -> list[str]:
        return sorted(self.specs)

    def get(self, symbol: str) -> SymbolSpec:
        spec = self.specs.get(symbol)
        if spec is None:
            raise SymbolUnavailable(self.errors.get(symbol, f"symbol {symbol!r} is not loaded"))
        return spec


def direction_allowed(spec: SymbolSpec, side: Side) -> bool:
    return spec.can_buy if side is Side.BUY else spec.can_sell


class SymbolService:
    def __init__(self, gateway: MarketDataGateway) -> None:
        self.gateway = gateway

    def load(self, symbols: list[str]) -> SymbolRegistry:
        registry = SymbolRegistry()
        for name in symbols:
            try:
                spec = self.gateway.symbol_spec(name)
            except (SymbolUnavailable, BrokerError) as exc:
                registry.errors[name] = str(exc)
                log.error("symbol %s disabled: %s", name, exc)
                continue
            problems = spec.validation_errors()
            if not spec.trading_enabled:
                problems.append("trading is disabled for this symbol (trade_mode=DISABLED)")
            filling = resolve_filling(spec)
            if filling is None:
                problems.append("no valid order filling mode for this symbol's execution mode")
            if problems:
                registry.errors[name] = "; ".join(problems)
                log.error("symbol %s disabled: %s", name, registry.errors[name])
                continue
            registry.specs[name] = spec
            registry.fillings[name] = filling  # type: ignore[assignment]
        return registry
