"""Broker order lifecycle (PLAN §A12; TAA-1202, TAA-1203, post-fill guard of TAA-1204). DEMO account only.

**State machine** (every transition is validated and persisted before the next step):

    NEW → PRECHECKED → SENDING → FILLED | PARTIAL | REJECTED | UNKNOWN
    UNKNOWN → RECONCILED | NOT_EXECUTED                       (the reconciler decides)
    FILLED | PARTIAL | RECONCILED → PROTECTED | UNPROTECTED → EMERGENCY_CLOSED
    NEW | PRECHECKED → NOT_EXECUTED                            (pre-send re-check failed)
    SENDING → PLACED → FILLED | CANCELLED | EXPIRED            (a limit part of an entry plan, TAA-1207)
    UNKNOWN → PLACED                                           (an unknown limit found resting)

- **Write-ahead:** the intent row (unique ``idempotency_key`` = signal key + part) is committed before
  anything is sent. A second attempt with the same key sends nothing and trips DUPLICATE_EXECUTION.
- **Pre-check:** ``order_check`` must answer 0.
- **Pre-send re-check** (time of check vs time of use), right before ``order_send``: the caller's checks
  (kill switch, breakers, connection, quote freshness, spread, price drift, signal expiry). Any problem means
  NOT_EXECUTED.
- **Retcodes** (§A12 matrix): success / partial → filled; requote or price change → at most one retry with
  a fresh price if the re-check still passes (counts as a failure); ``None`` or an unknown-class code →
  UNKNOWN, DUPLICATE_EXECUTION trips and nothing is resent until reconciled; permanent errors → rejected;
  symbol restrictions → SYMBOL_RESTRICTED for that symbol; no money / autotrading disabled / account-mode
  conflicts → the kill switch is activated (HALT); too many requests → ORDER_FAILURES. Every failed send
  counts toward ORDER_FAILURES.
- **Entry plans** (TAA-1207): the market part(s) go first; the limit parts are placed only when every market
  part is protected, each with the plan's stop and target, a cancel time (``cancel_after``: the limit
  lifetime, never past the Friday cut-off) and a broker-side expiration a few minutes later as a backstop.
  The pending order's filling is chosen by ``order_check`` (RETURN, then the market filling; without the
  expiration if the symbol refuses one). :mod:`app.engine.plan_supervisor` follows the resting parts.
- **Post-fill guard:** slippage feeds the SLIPPAGE breaker; a fill whose risk at the stop exceeds the plan by
  more than ``realized_risk_tolerance`` is reduced (or closed, per policy); a position without its stop gets
  it re-attached, or is closed and UNPROTECTED_POSITION trips.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.broker.execution import CheckResult, ExecutionGateway, RequestBuilder, SendResult
from app.broker.gateway import MarketDataGateway
from app.broker.models import BrokerPosition, Deal
from app.broker.retcodes import RetcodeClass
from app.config import ExecutionConfig
from app.core.clock import Clock, ensure_utc
from app.core.decimal_utils import floor_to_step, to_decimal
from app.core.enums import EntryType, Side
from app.core.errors import SafetyViolation, TaaError
from app.core.ids import new_id, short_id
from app.engine.decision_engine import Decision, DecisionRecord
from app.market_data.data_models import SymbolSpec
from app.monitoring.alerts import EventBus, EventType
from app.risk.breaker_monitor import BreakerMonitor
from app.risk.kill_switch import KillMode, KillSwitch
from app.risk.position_sizer import SizedPart
from app.storage.database import Database
from app.storage.models import OrderIntentRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)


class IntentState(StrEnum):
    NEW = "NEW"
    PRECHECKED = "PRECHECKED"
    SENDING = "SENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    RECONCILED = "RECONCILED"
    NOT_EXECUTED = "NOT_EXECUTED"
    PROTECTED = "PROTECTED"
    UNPROTECTED = "UNPROTECTED"
    EMERGENCY_CLOSED = "EMERGENCY_CLOSED"
    PLACED = "PLACED"  # a limit part rests at the broker
    CANCELLED = "CANCELLED"  # an unfilled limit part removed (first part closed, kill switch, outside)
    EXPIRED = "EXPIRED"  # an unfilled limit part past its lifetime


S = IntentState
TRANSITIONS: dict[IntentState, frozenset[IntentState]] = {
    S.NEW: frozenset({S.PRECHECKED, S.REJECTED, S.NOT_EXECUTED}),
    S.PRECHECKED: frozenset({S.SENDING, S.NOT_EXECUTED}),
    S.SENDING: frozenset({S.FILLED, S.PARTIAL, S.REJECTED, S.UNKNOWN, S.PRECHECKED, S.PLACED}),
    S.UNKNOWN: frozenset({S.RECONCILED, S.NOT_EXECUTED, S.PLACED}),
    S.PLACED: frozenset({S.FILLED, S.CANCELLED, S.EXPIRED}),
    S.FILLED: frozenset({S.PROTECTED, S.UNPROTECTED}),
    S.PARTIAL: frozenset({S.PROTECTED, S.UNPROTECTED}),
    S.RECONCILED: frozenset({S.PROTECTED, S.UNPROTECTED}),
    S.UNPROTECTED: frozenset({S.PROTECTED, S.EMERGENCY_CLOSED}),
    S.PROTECTED: frozenset(),
    S.REJECTED: frozenset(),
    S.NOT_EXECUTED: frozenset(),
    S.EMERGENCY_CLOSED: frozenset(),
    S.CANCELLED: frozenset(),
    S.EXPIRED: frozenset(),
}
OPEN_STATES = frozenset({S.NEW, S.PRECHECKED, S.SENDING, S.UNKNOWN})
INVALID_REQUEST, INVALID_EXPIRATION, INVALID_FILL = 10013, 10022, 10030
BACKSTOP = timedelta(minutes=5)  # the broker-side expiration of a limit part, after the engine's cancel time


class IllegalTransition(SafetyViolation):
    """An intent was asked to move along an edge the state machine does not have (a bug: fail loudly)."""


# the caller's time-of-use checks: (symbol, side, fresh price, expires_at) -> problems
PreSendCheck = Callable[[str, Side, float, datetime], list[str]]
# when an unfilled limit part of a plan placed now is cancelled: (symbol, now) -> cancel time
LimitDeadline = Callable[[str, datetime], datetime]


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    intent_id: str
    idempotency_key: str
    state: IntentState
    retcode: int | None = None
    position_ticket: int | None = None
    detail: str = ""


def intent_comment(intent_id: str) -> str:
    return f"taa:{short_id(intent_id, 12)}"


class OrderManager:
    def __init__(
        self,
        db: Database,
        execution: ExecutionGateway,
        market: MarketDataGateway,
        monitor: BreakerMonitor,
        kill_switch: KillSwitch,
        clock: Clock,
        config: ExecutionConfig,
        *,
        deviation_points: int,
        presend: PreSendCheck,
        bus: EventBus | None = None,
        limit_deadline: LimitDeadline | None = None,
    ) -> None:
        self.db = db
        self.execution = execution
        self.market = market
        self.monitor = monitor
        self.kill_switch = kill_switch
        self.clock = clock
        self.config = config
        self.builder = RequestBuilder(deviation_points)
        self.presend = presend
        self.bus = bus
        self.limit_deadline = limit_deadline or (lambda _symbol, now: now + timedelta(hours=4))

    # --- state ------------------------------------------------------------------------------------------

    def _move(
        self, sess: Session, row: OrderIntentRow, new: IntentState, detail: str = "", **fields: object
    ) -> None:
        old = IntentState(row.state)
        if new not in TRANSITIONS[old]:
            raise IllegalTransition(f"intent {row.intent_id}: {old} -> {new} is not allowed")
        row.state = new.value
        row.updated_at = self.clock.now_utc()
        if detail:
            row.detail = (f"{row.detail}; {detail}" if row.detail else detail)[:2000]
        for key, value in fields.items():
            setattr(row, key, value)
        log.info("intent %s %s -> %s %s", short_id(row.intent_id), old.value, new.value, detail)

    def transition(self, intent_id: str, new: IntentState, detail: str = "", **fields: object) -> None:
        with self.db.session() as sess:
            row = sess.get(OrderIntentRow, (LOCAL_ENGINE, intent_id))
            if row is None:
                raise TaaError(f"unknown intent {intent_id}")
            self._move(sess, row, new, detail, **fields)

    def plan_groups(self) -> dict[int, str]:
        """Position ticket -> entry plan, for every intent of a plan that became a position (TAA-1207)."""
        with self.db.session() as sess:
            rows = sess.execute(
                select(OrderIntentRow.position_ticket, OrderIntentRow.plan_key).where(
                    OrderIntentRow.position_ticket.is_not(None), OrderIntentRow.plan_key != ""
                )
            ).all()
        return {int(ticket): str(plan) for ticket, plan in rows if ticket is not None}

    def plan_parts_closed(self, open_tickets: set[int]) -> set[int]:
        """Of *open_tickets*, those whose entry plan has another part that became a position and is closed
        now (TAA-1207: the remaining parts go to break-even)."""
        groups = self.plan_groups()
        closed = {plan for ticket, plan in groups.items() if ticket not in open_tickets}
        return {t for t in open_tickets if groups.get(t) in closed}

    def row(self, intent_id: str) -> OrderIntentRow:
        with self.db.session() as sess:
            row = sess.get(OrderIntentRow, (LOCAL_ENGINE, intent_id))
            if row is None:
                raise TaaError(f"unknown intent {intent_id}")
            sess.expunge(row)
            return row

    # --- execution --------------------------------------------------------------------------------------

    def execute(self, record: DecisionRecord, spec: SymbolSpec, magic: int) -> list[ExecutionOutcome]:
        """Send the orders of an accepted decision: the market part(s) first, then, only when every market
        part is protected, the limit parts of the entry plan. An unknown outcome stops the plan."""
        if record.decision is not Decision.ACCEPT or record.sizing is None or not record.sizing.ok:
            return []
        side = record.signal.side
        if side is None or record.sizing.stop_loss is None:
            return []
        plan_key = record.signal.idempotency_key
        parts = list(enumerate(record.sizing.parts))
        market = [(i, p) for i, p in parts if p.part.order_type is EntryType.MARKET]
        limits = [(i, p) for i, p in parts if p.part.order_type is EntryType.LIMIT]
        outcomes: list[ExecutionOutcome] = []
        for i, part in market:
            outcome = self._execute_part(record, spec, magic, side, plan_key, i, part)
            outcomes.append(outcome)
            if outcome.state is S.UNKNOWN:
                return outcomes  # nothing more is sent until reconciled
        if limits and not (outcomes and all(o.state is S.PROTECTED for o in outcomes)):
            log.warning(
                "plan %s: the market part is not protected; %d limit part(s) not sent",
                plan_key[:12],
                len(limits),
            )
            return outcomes
        for i, part in limits:
            outcome = self._place_limit(record, spec, magic, side, plan_key, i, part)
            outcomes.append(outcome)
            if outcome.state is S.UNKNOWN:
                break
        return outcomes

    def _new_intent(
        self,
        record: DecisionRecord,
        spec: SymbolSpec,
        magic: int,
        side: Side,
        plan_key: str,
        index: int,
        part: SizedPart,
        **fields: object,
    ) -> str | ExecutionOutcome:
        """Write the intent ahead of any send; an existing key is a second attempt (DUPLICATE_EXECUTION)."""
        signal = record.signal
        key = f"{plan_key}:{index}"
        now = self.clock.now_utc()
        tp = part.part.take_profit
        with self.db.session() as sess:
            existing = sess.execute(
                select(OrderIntentRow).where(OrderIntentRow.idempotency_key == key)
            ).scalar_one_or_none()
            if existing is not None:
                self.monitor.unknown_order(f"second execution attempt for {key[:16]} ({existing.state})")
                return ExecutionOutcome(
                    existing.intent_id, key, IntentState(existing.state), detail="duplicate"
                )
            intent_id = new_id()
            values: dict[str, object] = {
                "intent_id": intent_id,
                "idempotency_key": key,
                "decision_id": record.decision_id,
                "signal_id": signal.signal_id,
                "strategy": signal.strategy,
                "symbol": spec.name,
                "side": side.value,
                "volume": float(part.volume),
                "price_requested": float(signal.entry_price or 0.0),
                "sl": float(record.sizing.stop_loss or 0.0) if record.sizing else 0.0,
                "tp": signal.take_profit if tp is None else float(tp),
                "magic": magic,
                "comment": intent_comment(intent_id),
                "risk_money": float(part.risk_money),
                "state": S.NEW.value,
                "attempts": 0,
                "expires_at": signal.expires_at_utc,
                "created_at": now,
                "updated_at": now,
                "plan_key": plan_key,
                "part_index": index,
            }
            values.update(fields)
            sess.add(OrderIntentRow(**values))
        return intent_id

    def _execute_part(
        self,
        record: DecisionRecord,
        spec: SymbolSpec,
        magic: int,
        side: Side,
        plan_key: str,
        index: int,
        part: SizedPart,
    ) -> ExecutionOutcome:
        created = self._new_intent(record, spec, magic, side, plan_key, index, part)
        if isinstance(created, ExecutionOutcome):
            return created
        return self._send(created, spec)

    # --- limit parts (TAA-1207) -------------------------------------------------------------------------

    def _place_limit(
        self,
        record: DecisionRecord,
        spec: SymbolSpec,
        magic: int,
        side: Side,
        plan_key: str,
        index: int,
        part: SizedPart,
    ) -> ExecutionOutcome:
        level = float(part.part.entry)
        created = self._new_intent(
            record,
            spec,
            magic,
            side,
            plan_key,
            index,
            part,
            order_type=EntryType.LIMIT.value,
            limit_price=level,
            price_requested=level,
            cancel_after=self.limit_deadline(spec.name, self.clock.now_utc()),
        )
        if isinstance(created, ExecutionOutcome):
            return created
        return self._send_limit(created, spec)

    def _send_limit(self, intent_id: str, spec: SymbolSpec) -> ExecutionOutcome:
        row = self.row(intent_id)
        side = Side(row.side)
        tick = self.market.tick(spec.name)
        if tick is None or row.limit_price is None:
            return self._finish(row, S.NOT_EXECUTED, "no price to place the limit against")
        market_price = tick.ask if side is Side.BUY else tick.bid
        edge = market_price - side.sign * spec.stops_level * spec.point
        if (row.limit_price - edge) * side.sign >= 0:  # the price is already at (or through) the level
            return self._finish(
                row, S.NOT_EXECUTED, f"limit {row.limit_price} is not away from the market {market_price}"
            )
        expiration = None
        if row.cancel_after is not None:
            expiration = self.market.server_clock.utc_to_server_epoch(ensure_utc(row.cancel_after) + BACKSTOP)
        request, check = self._check_limit(row, spec, side, expiration)
        if not check.ok:
            self.monitor.observe_order_failure(f"order_check {check.retcode} {check.comment}")
            return self._finish(
                row, S.REJECTED, f"order_check {check.retcode}: {check.comment}", check.retcode
            )
        self.transition(intent_id, S.PRECHECKED)
        problems = self.presend(spec.name, side, market_price, ensure_utc(row.expires_at))
        if problems:
            return self._finish(row, S.NOT_EXECUTED, "pre-send: " + "; ".join(problems))
        self.transition(intent_id, S.SENDING, attempts=1, sent_at=self.clock.now_utc())
        result = self.execution.send(request)
        fields: dict[str, object] = {"retcode": result.retcode, "retcode_desc": result.description[:48]}
        if result.ok:
            self.transition(intent_id, S.PLACED, result.description, order_ticket=result.order, **fields)
            return ExecutionOutcome(intent_id, row.idempotency_key, S.PLACED, result.retcode)
        self.monitor.observe_order_failure(result.description)
        return self._failed(intent_id, spec, result, fields)

    def _check_limit(
        self, row: OrderIntentRow, spec: SymbolSpec, side: Side, expiration: int | None
    ) -> tuple[dict[str, Any], CheckResult]:
        """``order_check`` over the filling modes (RETURN first) and, if the symbol refuses an expiration,
        without one. Returns the first accepted request, else the last refusal."""
        last: tuple[dict[str, Any], CheckResult] | None = None
        expirations = (expiration, None) if expiration is not None else (None,)
        for filling in self.builder.pending_fillings(spec):
            for exp in expirations:
                request = self.builder.limit_entry(
                    spec,
                    side,
                    row.volume,
                    float(row.limit_price or 0.0),
                    row.sl,
                    row.tp,
                    magic=int(row.magic),
                    comment=row.comment,
                    filling=filling,
                    expiration_server=exp,
                )
                check = self.execution.check(request)
                if check.ok:
                    return request, check
                last = (request, check)
                if check.retcode != INVALID_EXPIRATION:
                    break
            if last is not None and last[1].retcode not in (INVALID_FILL, INVALID_EXPIRATION):
                break
        if last is None:  # pending_fillings always offers RETURN; this is a bug
            raise SafetyViolation("no filling mode to check a limit order with")
        return last

    def cancel(self, intent_id: str, state: IntentState, why: str) -> bool:
        """Remove an unfilled limit part (CANCELLED or EXPIRED). False when the broker refused, or the order
        is no longer there: the plan supervisor then finds out whether it filled."""
        row = self.row(intent_id)
        if row.order_ticket is None:
            self.transition(intent_id, state, why)
            return True
        result = self.execution.send(self.builder.remove_order(int(row.order_ticket)))
        if result.ok:
            self.transition(intent_id, state, why)
            log.info("limit part #%s of %s removed: %s", row.order_ticket, row.symbol, why)
            return True
        if result.retcode != INVALID_REQUEST:
            self.monitor.observe_order_failure(f"remove #{row.order_ticket}: {result.description}")
        log.warning("removing limit #%s failed: %s", row.order_ticket, result.description)
        return False

    def limit_filled(
        self, intent_id: str, spec: SymbolSpec, position: BrokerPosition | None, deal: Deal | None
    ) -> IntentState:
        """A resting limit part became a position: record the fill, then the post-fill guard."""
        fields: dict[str, object] = {}
        if position is not None:
            fields = {
                "fill_price": position.price_open,
                "fill_volume": position.volume,
                "position_ticket": position.ticket,
            }
        elif deal is not None:
            fields = {
                "fill_price": deal.price,
                "fill_volume": deal.volume,
                "position_ticket": deal.position_id,
                "deal_ticket": deal.ticket,
            }
        self.transition(intent_id, S.FILLED, "limit filled", slippage_points=0.0, **fields)
        row = self.row(intent_id)
        if self.bus is not None:
            self.bus.emit(
                EventType.POSITION_OPENED,
                symbol=row.symbol,
                side=row.side,
                volume=row.fill_volume,
                price=row.fill_price,
                ticket=row.position_ticket,
                paper=False,
            )
        return self.guard(intent_id, spec)

    def _send(self, intent_id: str, spec: SymbolSpec) -> ExecutionOutcome:
        row = self.row(intent_id)
        side = Side(row.side)
        for attempt in range(1, self.config.max_send_attempts + 1):
            tick = self.market.tick(spec.name)
            price = None if tick is None else (tick.ask if side is Side.BUY else tick.bid)
            if price is None or price <= 0:
                return self._finish(row, S.NOT_EXECUTED, "no price to send at")
            request = self.builder.market_entry(
                spec, side, row.volume, price, row.sl, row.tp, magic=int(row.magic), comment=row.comment
            )
            if attempt == 1:
                check = self.execution.check(request)
                if not check.ok:
                    self.monitor.observe_order_failure(f"order_check {check.retcode} {check.comment}")
                    return self._finish(
                        row, S.REJECTED, f"order_check {check.retcode}: {check.comment}", check.retcode
                    )
                self.transition(intent_id, S.PRECHECKED)
            problems = self.presend(spec.name, side, price, ensure_utc(row.expires_at))
            if problems:
                return self._finish(row, S.NOT_EXECUTED, "pre-send: " + "; ".join(problems))
            self.transition(
                intent_id, S.SENDING, attempts=attempt, sent_at=self.clock.now_utc(), price_requested=price
            )
            result = self.execution.send(request)
            outcome = self._handle(intent_id, spec, side, price, result, attempt)
            if outcome is not None:
                return outcome
            self.transition(intent_id, S.PRECHECKED, f"retry after {result.description}")
        return self._finish(self.row(intent_id), S.REJECTED, "requotes exhausted")

    def _finish(
        self, row: OrderIntentRow, state: IntentState, detail: str, retcode: int | None = None
    ) -> ExecutionOutcome:
        self.transition(row.intent_id, state, detail, retcode=retcode)
        if state in (S.REJECTED, S.NOT_EXECUTED) and self.bus is not None:
            self.bus.emit(
                EventType.ORDER_REJECTED, symbol=row.symbol, reason=detail, intent=short_id(row.intent_id)
            )
        return ExecutionOutcome(row.intent_id, row.idempotency_key, state, retcode, detail=detail)

    def _handle(
        self, intent_id: str, spec: SymbolSpec, side: Side, price: float, result: SendResult, attempt: int
    ) -> ExecutionOutcome | None:
        """Apply the §A12 matrix; None means "retry with a fresh price"."""
        row = self.row(intent_id)
        cls, desc = result.retcode_class, result.description
        fields: dict[str, object] = {"retcode": result.retcode, "retcode_desc": desc[:48]}
        if cls in (RetcodeClass.SUCCESS, RetcodeClass.PARTIAL):
            state = (
                S.FILLED if cls is RetcodeClass.SUCCESS and result.volume >= row.volume - 1e-9 else S.PARTIAL
            )
            slippage = (result.price - price) * side.sign / spec.point if result.price else 0.0
            position = self._position_of(row, result.deal)
            self.transition(
                intent_id,
                state,
                desc,
                order_ticket=result.order,
                deal_ticket=result.deal,
                fill_price=result.price,
                fill_volume=result.volume,
                slippage_points=round(slippage, 1),
                position_ticket=None if position is None else position.ticket,
                **fields,
            )
            self.monitor.observe_fill(spec.name, max(0.0, slippage))
            if self.bus is not None:
                self.bus.emit(
                    EventType.POSITION_OPENED,
                    symbol=spec.name,
                    side=side.value,
                    volume=result.volume,
                    price=result.price,
                    ticket=None if position is None else position.ticket,
                    paper=False,
                )
            final = self.guard(intent_id, spec)
            return ExecutionOutcome(
                intent_id,
                row.idempotency_key,
                final,
                result.retcode,
                None if position is None else position.ticket,
            )
        self.monitor.observe_order_failure(desc)
        if cls is RetcodeClass.RETRY_ONCE and attempt < self.config.max_send_attempts:
            return None
        return self._failed(intent_id, spec, result, fields)

    def _failed(
        self, intent_id: str, spec: SymbolSpec, result: SendResult, fields: dict[str, object]
    ) -> ExecutionOutcome:
        """A send that did not succeed: UNKNOWN (reconcile first) or REJECTED, with the §A12 side effects."""
        row = self.row(intent_id)
        cls, desc = result.retcode_class, result.description
        if cls is RetcodeClass.UNKNOWN:
            self.transition(intent_id, S.UNKNOWN, f"{desc} {result.last_error}", **fields)
            self.monitor.unknown_order(f"{spec.name} intent {short_id(intent_id)}: {desc}")
            if self.bus is not None:
                self.bus.emit(
                    EventType.ORDER_UNKNOWN, symbol=spec.name, intent=short_id(intent_id), retcode=desc
                )
            return ExecutionOutcome(intent_id, row.idempotency_key, S.UNKNOWN, result.retcode, detail=desc)
        if cls is RetcodeClass.SYMBOL_RESTRICTED:
            self.monitor.symbol_restricted(spec.name, desc)
        elif cls in (RetcodeClass.GLOBAL_HALT, RetcodeClass.ACCOUNT_MODE):
            self.kill_switch.activate(f"broker answered {desc}", "engine", "engine", KillMode.HALT)
        elif cls is RetcodeClass.BACKOFF:
            self.monitor.order_backoff(desc)
        self.transition(intent_id, S.REJECTED, desc, **fields)
        if self.bus is not None:
            self.bus.emit(EventType.ORDER_REJECTED, symbol=spec.name, reason=desc, intent=short_id(intent_id))
        return ExecutionOutcome(intent_id, row.idempotency_key, S.REJECTED, result.retcode, detail=desc)

    def _position_of(self, row: OrderIntentRow, deal_ticket: int) -> BrokerPosition | None:
        """The position a fill opened: by its deal, else by magic and the intent's comment."""
        positions = self._positions(row.symbol)
        if deal_ticket:
            now = self.clock.now_utc()
            window = timedelta(hours=self.config.reconcile_window_hours)
            try:
                deals = self.market.deals(now - window, now + window)
            except TaaError:
                deals = []
            deal = next((d for d in deals if d.ticket == deal_ticket), None)
            if deal is not None:
                match = next((p for p in positions if p.ticket == deal.position_id), None)
                if match is not None:
                    return match
        return next((p for p in positions if p.magic == row.magic and p.comment == row.comment), None)

    def _positions(self, symbol: str) -> Sequence[BrokerPosition]:
        try:
            return self.market.positions(symbol)
        except TaaError:
            log.warning("positions_get failed for %s", symbol)
            return []

    # --- post-fill guard (TAA-1204) ---------------------------------------------------------------------

    def guard(self, intent_id: str, spec: SymbolSpec) -> IntentState:
        """Stop present and risk within plan; otherwise fix, reduce or close. Returns the final state."""
        row = self.row(intent_id)
        position = next((p for p in self._positions(row.symbol) if p.ticket == row.position_ticket), None)
        if position is None:
            position = self._position_of(row, row.deal_ticket or 0)
            if position is None:
                # filled and already gone (stopped out at once) or not visible yet: nothing to protect now
                self.transition(intent_id, S.PROTECTED, "position not visible after the fill")
                return S.PROTECTED
            self._transition_fields(intent_id, position_ticket=position.ticket)
        if position.sl <= 0 and not self.reattach_stop(position, row.sl, spec):
            return self._emergency_close(intent_id, position, spec, "stop could not be attached")
        self._check_realized_risk(row, position, spec)
        self.transition(intent_id, S.PROTECTED)
        return S.PROTECTED

    def _transition_fields(self, intent_id: str, **fields: object) -> None:
        with self.db.session() as sess:
            row = sess.get(OrderIntentRow, (LOCAL_ENGINE, intent_id))
            if row is not None:
                for key, value in fields.items():
                    setattr(row, key, value)

    def reattach_stop(self, position: BrokerPosition, sl: float, spec: SymbolSpec) -> bool:
        """Up to three attempts within ``unprotected_grace_seconds``."""
        deadline = self.clock.monotonic() + self.config.unprotected_grace_seconds
        for _ in range(3):
            result = self.execution.send(self.builder.modify_stops(spec, position, sl, position.tp or None))
            if result.ok:
                log.warning("re-attached SL %s to position #%s", sl, position.ticket)
                return True
            if self.clock.monotonic() >= deadline:
                break
        return False

    def close_unprotected(self, position: BrokerPosition, spec: SymbolSpec, why: str) -> bool:
        """Close a position that has no stop; trips UNPROTECTED_POSITION either way. True when closed."""
        tick = self.market.tick(spec.name)
        price = (
            position.price_current if tick is None else (tick.bid if position.side is Side.BUY else tick.ask)
        )
        result = self.execution.send(self.builder.close(spec, position, price, comment="taa:unprotected"))
        self.monitor.unprotected_position(
            f"#{position.ticket} {spec.name}: {why}; close {result.description}"
        )
        if self.bus is not None:
            self.bus.emit(
                EventType.POSITION_UNPROTECTED,
                symbol=spec.name,
                ticket=position.ticket,
                close=result.description,
            )
        return result.ok

    def _emergency_close(
        self, intent_id: str, position: BrokerPosition, spec: SymbolSpec, why: str
    ) -> IntentState:
        self.transition(intent_id, S.UNPROTECTED, why)
        if self.close_unprotected(position, spec, why):
            self.transition(intent_id, S.EMERGENCY_CLOSED, "closed without a stop")
            return S.EMERGENCY_CLOSED
        return S.UNPROTECTED  # stays visible; the breaker blocks everything until an operator acts

    def _check_realized_risk(self, row: OrderIntentRow, position: BrokerPosition, spec: SymbolSpec) -> None:
        sl = position.sl if position.sl > 0 else row.sl
        loss = self.market.calc_profit(position.side, spec.name, position.volume, position.price_open, sl)
        if loss is None or row.risk_money <= 0:
            return
        realized = -loss
        limit = row.risk_money * (1 + self.config.realized_risk_tolerance)
        if realized <= limit:
            return
        keep = floor_to_step(
            to_decimal(position.volume) * to_decimal(row.risk_money / realized), spec.volume_step
        )
        excess = float(to_decimal(position.volume) - keep)
        close_all = self.config.excess_risk_policy == "close" or keep < to_decimal(spec.volume_min)
        tick = self.market.tick(spec.name)
        price = (
            position.price_current if tick is None else (tick.bid if position.side is Side.BUY else tick.ask)
        )
        volume = position.volume if close_all else excess
        if volume <= 0 or math.isclose(volume, 0.0):
            return
        result = self.execution.send(
            self.builder.close(spec, position, price, volume=volume, comment="taa:risk")
        )
        log.warning(
            "fill risk %.2f > plan %.2f: closed %s of #%s (%s)",
            realized,
            row.risk_money,
            volume,
            position.ticket,
            result.description,
        )
