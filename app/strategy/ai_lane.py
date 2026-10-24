"""The AI trader as a lane strategy (PLAN §A37, TAA-1806): its own name, magic number, statistics and Trade
history like any strategy. It never asks the AI itself (strategy code is pure): the engine hands it the AI's
decisions (:meth:`AITrader.accept`, :meth:`AITrader.request_exit`) and feeds it quotes (:meth:`on_quote`), the
path of the release straddle. Every entry it makes is an ordinary signal: the decision engine sizes it by the
owner's profile (the AI's 'half' halves the risk) and runs every check.

An order fills at the quote once price is at the AI's entry (within ``market_tolerance``): a sell when the bid
is at or above it, a buy when the ask is at or below it. It is dropped when its stop is touched first, after
``pending_minutes``, or when a new decision replaces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import Field

from app.core.clock import ensure_utc
from app.core.enums import Action, ExitReason, Side, Timeframe
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.signal_models import (
    Condition,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    StrategyContext,
)


@dataclass(frozen=True)
class AIOrder:
    """One AI decision to enter, as the engine hands it over."""

    side: Side
    entry: float
    stop: float
    target: float | None
    risk_scale: float  # 1.0 for 'full', 0.5 for 'half'
    setup: str
    reasons: tuple[str, ...]
    kb_ids: tuple[str, ...]
    confidence: int
    decided_at: datetime
    valid_until: datetime
    key: str  # the decision's id (its stored prompt and answer)
    watch_above: float | None = None  # the prices the AI asked to be woken at
    watch_below: float | None = None

    def geometry_ok(self, price: float) -> bool:
        """The stop beyond the price on the losing side, the target (if any) on the winning side."""
        if self.side is Side.SELL:
            return self.stop > price and (self.target is None or self.target < price)
        return self.stop < price and (self.target is None or self.target > price)


@dataclass(frozen=True)
class AIEntry:
    order: AIOrder
    at: datetime
    price: float

    @property
    def side(self) -> Side:
        return self.order.side


class AITraderParams(StrategyParams):
    pending_minutes: int = Field(default=30, gt=0, le=240)  # how long an order waits for its price
    market_tolerance: float = Field(
        default=1.0, ge=0, le=50
    )  # price units: this close to the entry fills now


class AITrader(BaseStrategy):
    name = "ai_trader"
    description = (
        "The AI trader (PLAN §A37): the engine hands it the AI's decisions; it enters on quotes. Unproven."
    )
    Params = AITraderParams
    advised = False

    def __init__(self, params: StrategyParams | None = None) -> None:
        super().__init__(params)
        self._orders: dict[str, AIOrder] = {}
        self._exits: set[str] = set()

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return (Timeframe.M1,)

    def warmup_bars(self) -> int:
        return 50

    def evaluate(self, ctx: StrategyContext) -> Signal:
        return self.hold(ctx, ReasonCode.NO_SETUP, explanation="the AI trader enters on quotes, not on bars")

    # --- the engine's hand-over ---------------------------------------------------------------------------

    def accept(self, symbol: str, order: AIOrder) -> None:
        """A new AI order for ``symbol``; it replaces a waiting one."""
        self._orders[symbol] = order

    def cancel(self, symbol: str) -> None:
        self._orders.pop(symbol, None)

    def request_exit(self, symbol: str) -> None:
        """The AI asked to close this lane's open position on ``symbol`` (applied at its next management)."""
        self._exits.add(symbol)

    def pending(self, symbol: str) -> AIOrder | None:
        return self._orders.get(symbol)

    def busy(self, at: datetime) -> bool:
        """An order is waiting for its price: the engine polls quotes faster."""
        return bool(self._orders)

    # --- quotes, entries, management ----------------------------------------------------------------------

    def on_quote(self, symbol: str, at: datetime, bid: float, ask: float) -> AIEntry | None:
        order = self._orders.get(symbol)
        if order is None:
            return None
        at = ensure_utc(at)
        p: AITraderParams = self.params
        tol = float(p.market_tolerance)
        if at > order.valid_until:
            self._orders.pop(symbol)
            return None
        if order.side is Side.SELL:
            if ask >= order.stop:  # the stop was reached before the entry: the idea is gone
                self._orders.pop(symbol)
                return None
            if bid >= order.entry - tol:
                self._orders.pop(symbol)
                return AIEntry(order, at, bid)
            return None
        if bid <= order.stop:
            self._orders.pop(symbol)
            return None
        if ask <= order.entry + tol:
            self._orders.pop(symbol)
            return AIEntry(order, at, ask)
        return None

    def entry_signal(self, ctx: StrategyContext, entry: AIEntry) -> Signal | None:
        """The market entry at the context's quote, None without one or when the stop / target no longer sit
        on the right sides of it (fail closed)."""
        market = ctx.market
        if market.bid is None or market.ask is None:
            return None
        o = entry.order
        price = market.bid if o.side is Side.SELL else market.ask
        if not o.geometry_ok(price):
            return None
        conds = [
            Condition("ai_decision", True, 1.0, f"{o.setup} (confidence {o.confidence}, decision {o.key})"),
            Condition("ai_knowledge", True, 1.0, ", ".join(o.kb_ids)),
            Condition("ai_watch", True, 1.0, f"above {o.watch_above} / below {o.watch_below}"),
        ]
        return self.entry(
            ctx,
            Action.SELL if o.side is Side.SELL else Action.BUY,
            entry_price=price,
            stop_loss=o.stop,
            take_profit=o.target,
            conditions=conds,
            score=float(o.confidence),
            explanation=" | ".join(o.reasons),
            risk_scale=o.risk_scale,
        )

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        symbol = ctx.market.symbol
        if symbol in self._exits:
            self._exits.discard(symbol)
            return PositionAdvice(close=ExitReason.SIGNAL, note="the AI trader asked to exit")
        return None
