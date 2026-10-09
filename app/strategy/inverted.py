"""Inverted setups (owner, 2026-10-09; docs/SETUP_REVIEW.md §13): the original's signal on the other side.

``inverted(cls)`` builds ``<name>_inverted``: it runs the original strategy unchanged and turns each entry
into the opposite trade **at the original's prices**:

- BUY ↔ SELL; the entry is the other side of the spread (the live bid for a SELL, the ask for a BUY);
- the new stop is the original's take-profit and the new take-profit the original's stop, so the trade exits
  exactly where the original would have, and its R:R is the original's inverse;
- the reason code ``INVERTED`` marks it, so the decision engine applies ``risk.inverted`` (a lower RR floor
  and a wider SL cap) to it and nothing else; every other risk rule is unchanged;
- an original entry without a take-profit has no stop for the inverted trade: HOLD ``NO_TARGET``.

Inverted setups are for the bot only (``advised = False``): they are never offered as theories or alerts to
users.
"""

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar

from app.core.enums import Action, Side
from app.core.ids import new_id
from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_models import ReasonCode, Signal, StrategyContext

SUFFIX = "_inverted"


def flip(signal: Signal, market_bid: float | None, market_ask: float | None) -> Signal:
    """The original entry *signal* as the opposite trade with the original's exit prices."""
    if signal.take_profit is None or signal.stop_loss is None or signal.entry_price is None:
        raise ValueError("an inverted entry needs the original's entry, stop and target")
    buy = signal.action is Action.SELL  # the inverted side
    entry = signal.entry_price  # without a live quote the original's price stands (the spread is unknown)
    if market_bid is not None and market_ask is not None:
        entry = market_ask if buy else market_bid
    return dataclasses.replace(
        signal,
        signal_id=new_id(),
        action=Action.BUY if buy else Action.SELL,
        entry_price=entry,
        stop_loss=signal.take_profit,
        take_profit=signal.stop_loss,
        reason_codes=(*signal.reason_codes, ReasonCode.INVERTED.value),
        explanation=f"inverted: {signal.explanation}" if signal.explanation else "inverted",
    )


def inverted(cls: type[BaseStrategy]) -> type[BaseStrategy]:
    """``<cls.name>_inverted``: the parameters, timeframes, warm-up and detectors of *cls*, the other side."""

    class Inverted(cls):  # type: ignore[valid-type,misc]
        name: ClassVar[str] = f"{cls.name}{SUFFIX}"
        description: ClassVar[str] = f"{cls.description} Inverted: the other side, the same exit prices."
        inverted: ClassVar[bool] = True
        advised: ClassVar[bool] = False
        original: ClassVar[type[BaseStrategy]] = cls

        def evaluate(self, ctx: StrategyContext) -> Signal:
            signal: Signal = super().evaluate(ctx)
            if not signal.is_entry:
                return signal
            if signal.take_profit is None or signal.stop_loss is None or signal.entry_price is None:
                return self.hold(ctx, ReasonCode.NO_TARGET, explanation="the original has no take-profit")
            return flip(signal, ctx.market.bid, ctx.market.ask)

        def should_close(self, ctx: StrategyContext, side: Side) -> bool:
            # the original judges its own side: an inverted SELL is the original's BUY
            closed: bool = super().should_close(ctx, side.opposite)
            return closed

    Inverted.__name__ = Inverted.__qualname__ = f"{cls.__name__}Inverted"
    return Inverted


def is_inverted(cls: type[Any]) -> bool:
    return bool(getattr(cls, "inverted", False))
