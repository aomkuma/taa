"""Execution backends of the engine (TAA-1206): where accepted decisions go and whose book is managed.

- :class:`PaperBackend` (PAPER): simulated fills on live quotes, the paper book in the local database, the
  paper position manager. Real account positions only count toward exposure.
- :class:`DemoBackend` (DEMO, Phase 12): real broker orders on the **demo** account through the
  :class:`OrderManager`, the :class:`Reconciler` on every maintenance pass, and the
  :class:`BrokerPositionManager`; the :class:`BrokerTradeBook` books closed positions. A kill switch in
  FLATTEN mode closes every bot position (when allowed).

The engine talks to either through the same small interface, so the decision path is identical in both.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Protocol

from app.broker.gateway import MarketDataGateway
from app.broker.models import BrokerOrder, BrokerPosition, Deal
from app.core.clock import Clock
from app.core.enums import ExitReason
from app.core.errors import TaaError
from app.engine.broker_positions import BrokerPositionManager
from app.engine.broker_trades import BrokerTradeBook
from app.engine.decision_engine import DecisionRecord
from app.engine.order_manager import IntentState, OrderManager
from app.engine.paper import PaperExecution
from app.engine.plan_supervisor import PlanSupervisor
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
        IntentState.PLACED,
    }
)


class Backend(Protocol):
    name: str

    def funds(self) -> AccountFunds: ...

    def book(self) -> list[BrokerPosition]: ...

    def pending_orders(self) -> list[BrokerOrder]:
        """Resting orders whose risk counts toward portfolio heat (TAA-1207)."""
        ...

    def position_groups(self) -> dict[int, str]:
        """Position ticket -> entry plan: the parts of one plan count as one position (TAA-1207)."""
        ...

    def equity(self) -> float: ...

    def new_deals(self) -> list[Deal]: ...

    def on_quote(self, symbol: str, bid: float, ask: float, atr: float | None, now: datetime) -> None: ...

    def on_bar(self, symbol: str, ctx: StrategyContext) -> None: ...

    def place(self, record: DecisionRecord, spec: SymbolSpec, magic: int) -> bool: ...

    def maintain(self) -> None: ...

    def open_positions(self) -> int: ...

    def close_position(self, ticket: int, reason: ExitReason) -> str:
        """Close one bot position (remote POSITION_CLOSE); raises TaaError when it is unknown or fails."""
        ...


class PaperBackend:
    name = "paper"

    def __init__(
        self,
        paper: PaperExecution,
        positions: PositionManager,
        market: MarketDataGateway,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.paper = paper
        self.positions = positions
        self.market = market
        self.kill_switch = kill_switch
        self._booked = 0
        self._flattened = False

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

    def pending_orders(self) -> list[BrokerOrder]:
        """Paper limit parts plus the account's own resting orders (manual ones count under ``count``)."""
        try:
            real = self.market.orders()
        except TaaError:
            log.warning("could not read account orders; heat uses the paper orders only")
            real = []
        return [*self.paper.pending_orders(), *real]

    def position_groups(self) -> dict[int, str]:
        return self.paper.plan_groups()

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
        state = None if self.kill_switch is None else self.kill_switch.state()
        self.paper.supervise_plans(state is not None and state.active)
        if state is not None and state.active and state.mode is KillMode.FLATTEN and not self._flattened:
            for ticket in list(self.paper.broker.positions):  # paper positions close at the next quote
                self.paper.request_close(ticket, ExitReason.KILL_SWITCH)
            self._flattened = True
        elif state is None or not state.active:
            self._flattened = False

    def open_positions(self) -> int:
        return len(self.paper.broker.positions)

    def close_position(self, ticket: int, reason: ExitReason) -> str:
        if ticket not in self.paper.broker.positions:
            raise TaaError(f"no open paper position #{ticket}")
        self.paper.request_close(ticket, reason)
        return f"paper position #{ticket} closes at the next quote"


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
        *,
        plans: PlanSupervisor | None = None,
        trades: BrokerTradeBook | None = None,
    ) -> None:
        self.orders = orders
        self.reconciler = reconciler
        self.plans = plans
        self.trades = trades
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

    def pending_orders(self) -> list[BrokerOrder]:
        return self.market.orders()

    def position_groups(self) -> dict[int, str]:
        return self.orders.plan_groups()

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
        if self.plans is not None:
            self.plans.run()  # resting limit parts: fills, lifetime, kill switch, closed market parts
        if self.trades is not None:
            self.trades.run()  # closed positions into the trade history (TAA-1208)
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

    def close_position(self, ticket: int, reason: ExitReason) -> str:
        """Only the bot's own positions (its magic range): a remote command never touches manual trades."""
        pos = next((p for p in self.positions.bot_positions() if p.ticket == ticket), None)
        if pos is None:
            raise TaaError(f"no open bot position #{ticket}")
        result = self.positions.close(pos, self.market.symbol_spec(pos.symbol), reason)
        if not result.ok:
            raise TaaError(f"close of #{ticket} failed: retcode {result.retcode}")
        return f"position #{ticket} closed"
