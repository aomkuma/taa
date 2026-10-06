"""Plan supervisor: the resting limit parts of entry plans on the broker account (PLAN §A31; TAA-1207).

Runs after the reconciler at start-up and on every health interval (``DemoBackend.maintain``), DEMO and LIVE
only (PAPER keeps its limit parts in :class:`app.engine.paper.PaperExecution`).

- A PLACED part whose order is gone **filled** when a position opened by it exists (the position identifier
  is the order ticket in MT5; else magic + the intent's comment) or an IN deal of that order does: FILLED,
  then the post-fill guard (PROTECTED). Otherwise it was removed outside the engine or expired at the
  broker: EXPIRED after its cancel time, else CANCELLED.
- A part still resting is **removed** when:
  - the kill switch is active, in any mode: CANCELLED;
  - its cancel time has passed (the limit lifetime, never past the Friday cut-off): EXPIRED;
  - every market part of its plan is closed (stopped, at target or closed by hand): CANCELLED.

  A refused removal stays PLACED and is tried again on the next run.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select

from app.broker import mt5_constants as c
from app.broker.models import BrokerOrder, BrokerPosition, Deal
from app.config import ExecutionConfig
from app.core.clock import Clock, ensure_utc
from app.core.enums import EntryType
from app.core.errors import TaaError
from app.engine.order_manager import IntentState, OrderManager
from app.market_data.data_models import SymbolSpec
from app.risk.kill_switch import KillSwitch
from app.storage.models import OrderIntentRow

log = logging.getLogger(__name__)
S = IntentState


@dataclass
class PlanReport:
    filled: list[str] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    expired: list[str] = field(default_factory=list)
    removal_failed: list[str] = field(default_factory=list)


def _opened_by(row: OrderIntentRow, positions: Sequence[BrokerPosition]) -> BrokerPosition | None:
    ticket = row.position_ticket or row.order_ticket
    return next(
        (
            p
            for p in positions
            if (ticket is not None and ticket in (p.ticket, p.identifier))
            or (p.magic == row.magic and p.comment.startswith(row.comment))
        ),
        None,
    )


class PlanSupervisor:
    def __init__(
        self,
        orders: OrderManager,
        kill_switch: KillSwitch,
        clock: Clock,
        config: ExecutionConfig,
        specs: Mapping[str, SymbolSpec],
    ) -> None:
        self.orders = orders
        self.market = orders.market
        self.kill_switch = kill_switch
        self.clock = clock
        self.config = config
        self.specs = dict(specs)

    def run(self) -> PlanReport:
        report = PlanReport()
        placed = self._intents([S.PLACED])
        if not placed:
            return report
        try:
            resting = {o.ticket: o for o in self.market.orders()}
            positions = self.market.positions()
        except TaaError:
            log.warning("orders_get or positions_get failed; resting limit parts are checked next time")
            return report
        now = self.clock.now_utc()
        killed = self.kill_switch.state().active
        markets_open = self._market_parts_open({r.plan_key for r in placed}, positions)
        deals: list[Deal] | None = None
        deals_loaded = False
        for row in placed:
            if row.order_ticket is not None and row.order_ticket in resting:
                self._maybe_remove(row, resting[row.order_ticket], now, killed, markets_open, report)
                continue
            position = _opened_by(row, positions)
            deal = None
            if position is None:
                if not deals_loaded:
                    deals, deals_loaded = self._deals(), True
                if deals is None:
                    continue  # without the history a fill cannot be told from a removal: next time
                deal = next(
                    (
                        d
                        for d in deals
                        if d.entry == c.DEAL_ENTRY_IN
                        and (
                            (row.order_ticket is not None and d.order == row.order_ticket)
                            or (d.magic == row.magic and d.comment.startswith(row.comment))
                        )
                    ),
                    None,
                )
            spec = self.specs.get(row.symbol)
            if (position is not None or deal is not None) and spec is not None:
                self.orders.limit_filled(row.intent_id, spec, position, deal)
                report.filled.append(row.intent_id)
            elif position is None and deal is None:
                gone = S.EXPIRED if self._due(row, now) else S.CANCELLED
                self.orders.transition(row.intent_id, gone, "the order is gone without a fill")
                (report.expired if gone is S.EXPIRED else report.cancelled).append(row.intent_id)
        if report.filled or report.cancelled or report.expired or report.removal_failed:
            log.info("plan supervisor: %s", report)
        return report

    # --- decisions --------------------------------------------------------------------------------------

    @staticmethod
    def _due(row: OrderIntentRow, now: datetime) -> bool:
        return row.cancel_after is not None and now >= ensure_utc(row.cancel_after)

    def _maybe_remove(
        self,
        row: OrderIntentRow,
        order: BrokerOrder,
        now: datetime,
        killed: bool,
        markets_open: Mapping[str, bool],
        report: PlanReport,
    ) -> None:
        if killed:
            state, why = S.CANCELLED, "kill switch"
        elif self._due(row, now):
            state, why = S.EXPIRED, "limit lifetime over"
        elif not markets_open.get(row.plan_key, True):
            state, why = S.CANCELLED, "the plan's market part is closed"
        else:
            return
        if self.orders.cancel(row.intent_id, state, why):
            (report.expired if state is S.EXPIRED else report.cancelled).append(row.intent_id)
        else:
            report.removal_failed.append(row.intent_id)
            log.warning("limit #%s (%s) still rests: removal failed", order.ticket, order.symbol)

    def _market_parts_open(self, plan_keys: set[str], positions: Sequence[BrokerPosition]) -> dict[str, bool]:
        """Per plan: is any of its market parts still an open position? Plans whose market part never
        became a position (a bug or an operator's doing) count as closed."""
        with self.orders.db.session() as sess:
            rows = list(
                sess.execute(
                    select(OrderIntentRow).where(
                        OrderIntentRow.plan_key.in_(sorted(plan_keys)),
                        OrderIntentRow.order_type == EntryType.MARKET.value,
                    )
                ).scalars()
            )
            sess.expunge_all()
        out = dict.fromkeys(plan_keys, False)
        for row in rows:
            if row.state in (S.PROTECTED.value, S.UNPROTECTED.value) and _opened_by(row, positions):
                out[row.plan_key] = True
        return out

    # --- data -------------------------------------------------------------------------------------------

    def _intents(self, states: Sequence[IntentState]) -> list[OrderIntentRow]:
        with self.orders.db.session() as sess:
            rows = list(
                sess.execute(
                    select(OrderIntentRow).where(OrderIntentRow.state.in_([s.value for s in states]))
                ).scalars()
            )
            sess.expunge_all()
        return rows

    def _deals(self) -> list[Deal] | None:
        now = self.clock.now_utc()
        window = timedelta(hours=self.config.reconcile_window_hours)
        try:
            return self.market.deals(now - 2 * window, now + window)
        except TaaError:
            log.warning("history_deals_get failed; filled limit parts are checked next time")
            return None
