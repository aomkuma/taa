"""Choose an order filling mode from the symbol's execution mode and allowed-filling flags.

Rules (MQL5 docs, ENUM_ORDER_TYPE_FILLING):
* Request / Instant execution: FOK, IOC and RETURN are all allowed.
* Market execution: RETURN is NOT allowed; FOK/IOC only if the symbol's flags permit them.
* Exchange execution: FOK/IOC per flags, RETURN allowed.

FOK is preferred (all-or-nothing: no unexpected partial positions), then IOC, then RETURN.
"""

from __future__ import annotations

from app.broker import mt5_constants as c
from app.market_data.data_models import SymbolSpec


def allowed_fillings(spec: SymbolSpec) -> list[int]:
    flags = spec.filling_mode
    mode = spec.execution_mode
    if mode in (c.SYMBOL_TRADE_EXECUTION_REQUEST, c.SYMBOL_TRADE_EXECUTION_INSTANT):
        return [c.ORDER_FILLING_FOK, c.ORDER_FILLING_IOC, c.ORDER_FILLING_RETURN]
    options: list[int] = []
    if flags & c.SYMBOL_FILLING_FOK:
        options.append(c.ORDER_FILLING_FOK)
    if flags & c.SYMBOL_FILLING_IOC:
        options.append(c.ORDER_FILLING_IOC)
    if mode == c.SYMBOL_TRADE_EXECUTION_EXCHANGE:
        options.append(c.ORDER_FILLING_RETURN)
    return options


def resolve_filling(spec: SymbolSpec) -> int | None:
    """Preferred filling mode, or None when no valid mode exists (symbol must not be traded)."""
    options = allowed_fillings(spec)
    return options[0] if options else None


FILLING_NAMES = {
    c.ORDER_FILLING_FOK: "FOK",
    c.ORDER_FILLING_IOC: "IOC",
    c.ORDER_FILLING_RETURN: "RETURN",
    c.ORDER_FILLING_BOC: "BOC",
}
