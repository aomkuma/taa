"""Execution backends of the engine (TAA-1206): where accepted decisions go and whose book is managed.

- :class:`PaperBackend` (PAPER): simulated fills on live quotes, the paper book in the local database, the
  paper position manager. Real account positions only count toward exposure.
- :class:`DemoBackend` (DEMO, Phase 12): real broker orders on the **demo** account through the
  :class:`OrderManager`, the :class:`Reconciler` on every maintenance pass, and the
  :class:`BrokerPositionManager`. A kill switch in FLATTEN mode closes every bot position (when allowed).

The engine talks to either through the same small interface, so the decision path is identical in both.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Protocol

from app.broker.gateway import MarketDataGateway
from app.broker.models import BrokerPosition, Deal
from app.core.clock import Clock
from app.core.errors import TaaError
from app.engine.broker_positions import BrokerPositionManager
from app.engine.decision_engine import DecisionRecord
from app.engine.order_manager import IntentState, OrderManager
from app.engine.paper import PaperExecution
from app.engine.position_manager import PositionManager
from app.engine.reconciler import Reconciler
from app.market_data.data_models import SymbolSpec
from app.risk.kill_switch import KillMode, KillSwitch
from app.risk.position_sizer import AccountFunds
from app.strategy.signal_models import StrategyContext

log = logging.getLogger(__name__)
PLACED_STATES = frozenset(
    {
        IntentState.FILLED,
        IntentState.PARTIAL,
        IntentState.PROTECTED,
        IntentState.RECONCILED,
        IntentState.UNKNOWN,
    }
)


class Backend(Protocol):
    name: str

    def funds(self) -> AccountFunds: ...

    def book(self) -> list[BrokerPosition]: ...

    def equity(self) -> float: ...

    def new_deals(self) -> list[Deal]: ...

    def on_quote(self, symbol: str, bid: float, ask: float, atr: float | None, now: datetime) -> None: ...

    def on_bar(self, symbol: str, ctx: StrategyContext) -> None: ...

    def place(self, record: DecisionRecord, spec: SymbolSpec, magic: int) -> bool: ...

    def maintain(self) -> None: ...

    def open_positions(self) -> int: ...


class PaperBackend:
    name = "paper"

    def __init__(self, paper: PaperExecution, positions: PositionManager, market: MarketDataGateway) -> None:
        self.paper = paper
        self.positions = positions
        self.market = market
        self._booked = 0

    def funds(self) -> AccountFunds:
        return self.paper.broker.funds()

    def book(self) -> list[BrokerPosition]:
        """Paper positions plus every real position on the account (manual trades count toward exposure)."""
        try:
            real = self.market.positions()
        except TaaError:
            log.warning("could not read account positions; exposure uses the paper book only")
            real = []
        return [*self.paper.broker.broker_positions(), *real]

    def equity(self) -> float:
        return self.paper.broker.equity

    def new_deals(self) -> list[Deal]:
        new = self.paper.broker.deals[self._booked :]
        self._booked = len(self.paper.broker.deals)
        return new

    def on_quote(self, symbol: str, bid: float, ask: float, atr: float | None, now: datetime) -> None:
        self.paper.on_quote(symbol, bid, ask, now)
        self.positions.on_quote(symbol, bid, ask, atr)

    def on_bar(self, symbol: str, ctx: StrategyContext) -> None:
        self.positions.on_bar(symbol, ctx)

    def place(self, record: DecisionRecord, spec: SymbolSpec, magic: int) -> bool:
        return any(not p.duplicate for p in self.paper.place(record, magic))

    def maintain(self) -> None:
        self.paper.save_marks()

    def open_positions(self) -> int:
        return len(self.paper.broker.positions)


class DemoBackend:
    name = "demo"

    def __init__(
        self,
        orders: OrderManager,
        reconciler: Reconciler,
        positions: BrokerPositionManager,
        market: MarketDataGateway,
        kill_switch: KillSwitch,
        clock: Clock,
    ) -> None:
        self.orders = orders
        self.reconciler = reconciler
        self.positions = positions
        self.market = market
        self.kill_switch = kill_switch
        self.clock = clock
        self._flattened = False

    def funds(self) -> AccountFunds:
        a = self.market.account()
        return AccountFunds(equity=a.equity, balance=a.balance, margin=a.margin, margin_free=a.margin_free)

    def book(self) -> list[BrokerPosition]:
        return self.market.positions()

    def equity(self) -> float:
        return self.market.account().equity

    def new_deals(self) -> list[Deal]:
        """Recent account deals; the loss tracker books each ticket once."""
        now = self.clock.now_utc()
        try:
            return self.market.deals(now - timedelta(days=8), now + timedelta(days=1))
        except TaaError:
            log.warning("history_deals_get failed; loss tracking uses equity only this time")
            return []

    def on_quote(self, symbol: str, bid: float, ask: float, atr: float | None, now: datetime) -> None:
        self.positions.on_quote(symbol, bid, ask, atr)

    def on_bar(self, symbol: str, ctx: StrategyContext) -> None:
        self.positions.on_bar(symbol, ctx)

    def place(self, record: DecisionRecord, spec: SymbolSpec, magic: int) -> bool:
        outcomes = self.orders.execute(record, spec, magic)
        return any(o.state in PLACED_STATES for o in outcomes)

    def maintain(self) -> None:
        self.reconciler.run()
        state = self.kill_switch.state()
        if state.active and state.mode is KillMode.FLATTEN and not self._flattened:
            self.positions.flatten(state.reason or "kill switch FLATTEN")
            self._flattened = True
        elif not state.active:
            self._flattened = False

    def open_positions(self) -> int:
        try:
            return len(self.positions.bot_positions())
        except TaaError:
            return 0
