"""Reconciler (PLAN §A12, A11 "Reconciliation"; TAA-1204). Runs at startup and every health interval.

1. **UNKNOWN intents** (``order_send`` gave no usable answer): the order may exist. Positions are searched by
   magic and the intent's comment, then the deal history over a window widened by
   ``reconcile_window_hours`` on each side (broker history times are server wall-clock, §A5). Found →
   RECONCILED and the post-fill guard runs. Not found ``reconcile_after_seconds`` after the send →
   NOT_EXECUTED. DUPLICATE_EXECUTION stays tripped: an operator resets it after reading the report.
2. **Interrupted intents** (the process stopped mid-flight): SENDING means the order may have gone out, so it
   becomes UNKNOWN and is resolved as above; NEW or PRECHECKED was never sent: NOT_EXECUTED.
3. **Protection sweep:** every position carrying the bot's magic must have a stop. A missing one is
   re-attached from its intent, otherwise the position is closed and UNPROTECTED_POSITION trips.
4. **Strays:** a position or a resting order with the bot's magic that no intent explains trips
   ACCOUNT_CHANGE.

A limit part of an entry plan (TAA-1207) whose send was unknown is looked up among the resting orders first:
found → PLACED (the plan supervisor follows it from there).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select

from app.broker import mt5_constants as c
from app.broker.gateway import MarketDataGateway
from app.broker.models import BrokerOrder, BrokerPosition, Deal
from app.config import ExecutionConfig
from app.core.clock import Clock, ensure_utc
from app.core.enums import EntryType
from app.core.errors import TaaError
from app.core.ids import short_id
from app.engine.order_manager import IntentState, OrderManager
from app.market_data.data_models import SymbolSpec
from app.monitoring.alerts import EventBus, EventType
from app.risk.breaker_monitor import BreakerMonitor
from app.risk.exposure_manager import MAGIC_RANGE
from app.storage.database import Database
from app.storage.models import OrderIntentRow

log = logging.getLogger(__name__)
S = IntentState


@dataclass
class ReconcileReport:
    reconciled: list[str] = field(default_factory=list)
    not_executed: list[str] = field(default_factory=list)
    still_unknown: list[str] = field(default_factory=list)
    reattached: list[int] = field(default_factory=list)
    closed_unprotected: list[int] = field(default_factory=list)
    strays: list[int] = field(default_factory=list)
    placed: list[str] = field(default_factory=list)  # unknown limit parts found resting
    stray_orders: list[int] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.still_unknown or self.closed_unprotected or self.strays or self.stray_orders)


class Reconciler:
    def __init__(
        self,
        db: Database,
        orders: OrderManager,
        market: MarketDataGateway,
        monitor: BreakerMonitor,
        clock: Clock,
        config: ExecutionConfig,
        specs: Mapping[str, SymbolSpec],
        *,
        magic_base: int,
        bus: EventBus | None = None,
    ) -> None:
        self.db = db
        self.orders = orders
        self.market = market
        self.monitor = monitor
        self.clock = clock
        self.config = config
        self.specs = dict(specs)
        self.magic_base = magic_base
        self.bus = bus

    def is_bot(self, magic: int) -> bool:
        return self.magic_base <= magic < self.magic_base + MAGIC_RANGE

    def run(self) -> ReconcileReport:
        report = ReconcileReport()
        positions = self._positions()
        deals = self._deals()
        orders = self._orders()
        for row in self._open_intents():
            self._resolve(row, positions, deals, orders, report)
        self._sweep(self._positions(), report)
        if orders is not None:
            self._sweep_orders(orders, report)
        if not report.clean:
            log.warning("reconciliation: %s", report)
        return report

    # --- intents ----------------------------------------------------------------------------------------

    def _open_intents(self) -> list[OrderIntentRow]:
        with self.db.session() as sess:
            rows = sess.execute(
                select(OrderIntentRow).where(
                    OrderIntentRow.state.in_(
                        [S.NEW.value, S.PRECHECKED.value, S.SENDING.value, S.UNKNOWN.value]
                    )
                )
            ).scalars()
            out = list(rows)
            sess.expunge_all()
            return out

    def _resolve(
        self,
        row: OrderIntentRow,
        positions: list[BrokerPosition],
        deals: list[Deal],
        orders: list[BrokerOrder] | None,
        report: ReconcileReport,
    ) -> None:
        state = IntentState(row.state)
        if state in (S.NEW, S.PRECHECKED):
            self.orders.transition(row.intent_id, S.NOT_EXECUTED, "interrupted before sending")
            report.not_executed.append(row.intent_id)
            return
        if state is S.SENDING:
            self.orders.transition(row.intent_id, S.UNKNOWN, "interrupted while sending")
            self.monitor.unknown_order(
                f"{row.symbol} intent {short_id(row.intent_id)} interrupted while sending"
            )
        resting = next(
            (o for o in orders or () if o.magic == row.magic and o.comment.startswith(row.comment)), None
        )
        if resting is not None:
            self.orders.transition(row.intent_id, S.PLACED, "found resting", order_ticket=resting.ticket)
            report.placed.append(row.intent_id)
            self._announce(row, "PLACED")
            return
        if orders is None and row.order_type == EntryType.LIMIT.value:
            report.still_unknown.append(row.intent_id)  # it may be resting: decide when orders_get works
            return
        position = next(
            (p for p in positions if p.magic == row.magic and p.comment.startswith(row.comment)), None
        )
        entry = next(
            (
                d
                for d in deals
                if d.magic == row.magic and d.entry == c.DEAL_ENTRY_IN and d.comment.startswith(row.comment)
            ),
            None,
        )
        found = None
        if position is not None:
            found = (position.price_open, position.volume, position.ticket)
        elif entry is not None:
            found = (entry.price, entry.volume, entry.position_id)
        if found is not None:
            fill_price, fill_volume, ticket = found
            self.orders.transition(
                row.intent_id,
                S.RECONCILED,
                "found on the account",
                fill_price=fill_price,
                fill_volume=fill_volume,
                position_ticket=ticket,
                deal_ticket=None if entry is None else entry.ticket,
            )
            report.reconciled.append(row.intent_id)
            spec = self.specs.get(row.symbol)
            if spec is not None:
                self.orders.guard(row.intent_id, spec)
            self._announce(row, "RECONCILED")
            return
        sent = row.sent_at or row.created_at
        if (self.clock.now_utc() - ensure_utc(sent)).total_seconds() >= self.config.reconcile_after_seconds:
            self.orders.transition(row.intent_id, S.NOT_EXECUTED, "not found on the account")
            report.not_executed.append(row.intent_id)
            self._announce(row, "NOT_EXECUTED")
        else:
            report.still_unknown.append(row.intent_id)

    def _announce(self, row: OrderIntentRow, outcome: str) -> None:
        if self.bus is not None:
            self.bus.emit(
                EventType.ORDER_RECONCILED,
                symbol=row.symbol,
                intent=short_id(row.intent_id),
                outcome=outcome,
                note="reset DUPLICATE_EXECUTION after reviewing",
            )

    # --- positions --------------------------------------------------------------------------------------

    def _sweep(self, positions: list[BrokerPosition], report: ReconcileReport) -> None:
        with self.db.session() as sess:
            intents = list(sess.execute(select(OrderIntentRow)).scalars())
            sess.expunge_all()
        by_ticket = {r.position_ticket: r for r in intents if r.position_ticket}
        by_comment = {r.comment: r for r in intents}
        for pos in positions:
            if not self.is_bot(pos.magic):
                continue
            intent = by_ticket.get(pos.ticket) or next(
                (r for comment, r in by_comment.items() if pos.comment.startswith(comment)), None
            )
            if intent is None:
                report.strays.append(pos.ticket)
                self.monitor.account_changed(
                    f"position #{pos.ticket} {pos.symbol} has the bot's magic but no intent"
                )
                if self.bus is not None:
                    self.bus.emit(
                        EventType.UNKNOWN_POSITION, symbol=pos.symbol, ticket=pos.ticket, magic=pos.magic
                    )
                continue
            spec = self.specs.get(pos.symbol)
            if pos.sl > 0 or spec is None:
                continue
            if self.orders.reattach_stop(pos, intent.sl, spec):
                report.reattached.append(pos.ticket)
            else:
                report.closed_unprotected.append(pos.ticket)
                self.orders.close_unprotected(pos, spec, "no stop found by the reconciler")

    def _sweep_orders(self, orders: list[BrokerOrder], report: ReconcileReport) -> None:
        with self.db.session() as sess:
            intents = list(sess.execute(select(OrderIntentRow)).scalars())
            sess.expunge_all()
        tickets = {r.order_ticket for r in intents if r.order_ticket}
        comments = [r.comment for r in intents]
        for order in orders:
            if not self.is_bot(order.magic) or order.ticket in tickets:
                continue
            if any(order.comment.startswith(comment) for comment in comments):
                continue
            report.stray_orders.append(order.ticket)
            self.monitor.account_changed(
                f"resting order #{order.ticket} {order.symbol} has the bot's magic but no intent"
            )

    def _orders(self) -> list[BrokerOrder] | None:
        try:
            return self.market.orders()
        except TaaError:
            log.warning("orders_get failed during reconciliation")
            return None

    def _positions(self) -> list[BrokerPosition]:
        try:
            return self.market.positions()
        except TaaError:
            log.warning("positions_get failed during reconciliation")
            return []

    def _deals(self) -> list[Deal]:
        now = self.clock.now_utc()
        window = timedelta(hours=self.config.reconcile_window_hours)
        try:
            return self.market.deals(now - 2 * window, now + window)
        except TaaError:
            log.warning("history_deals_get failed during reconciliation")
            return []
