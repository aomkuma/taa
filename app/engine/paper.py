"""PAPER execution (PLAN §A3; TAA-602): the simulated broker on live quotes, with its book persisted.

- An accepted decision becomes one **intent** per order of its sizing plan. The intent's idempotency key is
  ``<signal idempotency key>:<part>``, unique in the database, so a decision replayed after a restart (or
  twice by mistake) never opens a second position.
- Fills, exits, rejections and expiries from :meth:`SimulatedBroker.on_quote` are written to
  ``paper_intents`` / ``paper_positions`` and the account balance in the same step, and published as
  notification events.
- :meth:`PaperExecution.restore` rebuilds the broker from the database at startup: balance, id counter, open
  positions (with their current stop and how it got there) and pending intents.

No broker order is ever sent: the broker here is simulated, and the MT5 gateway is read-only.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.broker.gateway import MarketDataGateway
from app.config import BacktestConfig, PaperConfig
from app.core.clock import Clock, ensure_utc
from app.core.enums import EntryType, ExitReason, Side
from app.core.errors import SymbolUnavailable
from app.core.ids import new_id
from app.engine.decision_engine import Decision, DecisionRecord
from app.execution.simulated_broker import (
    BrokerEvent,
    EventKind,
    OrderRequest,
    RateSource,
    SimPosition,
    SimulatedBroker,
)
from app.market_data.data_models import SymbolSpec
from app.monitoring.alerts import EventBus, EventType
from app.storage.database import Database
from app.storage.models import PaperAccountRow, PaperIntentRow, PaperPositionRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)


class LiveRates:
    """Account-currency rates from live bids of ``<CUR><ACCOUNT>`` or ``<ACCOUNT><CUR>``."""

    def __init__(self, gateway: MarketDataGateway, account_currency: str) -> None:
        self.gateway = gateway
        self.account = account_currency
        self._missing: set[str] = set()

    def _bid(self, symbol: str) -> float | None:
        if symbol in self._missing:
            return None
        try:
            self.gateway.symbol_spec(symbol)  # selects it so ticks arrive
        except SymbolUnavailable:
            self._missing.add(symbol)
            return None
        tick = self.gateway.tick(symbol)
        return None if tick is None or tick.bid <= 0 else tick.bid

    def rate(self, currency: str, at: datetime) -> float | None:
        if currency == self.account:
            return 1.0
        direct = self._bid(f"{currency}{self.account}")
        if direct is not None:
            return direct
        inverse = self._bid(f"{self.account}{currency}")
        return None if inverse is None else 1.0 / inverse


@dataclass(frozen=True, slots=True)
class PlacedIntent:
    intent_id: str
    idempotency_key: str
    order_id: int
    duplicate: bool  # True: the key existed already, nothing new was placed


def broker_config(paper: PaperConfig, backtest: BacktestConfig, initial_balance: float) -> BacktestConfig:
    """The simulated broker's settings for PAPER: live spreads, fixed adverse slippage, no randomness."""
    return backtest.model_copy(
        update={
            "initial_balance": initial_balance,
            "slippage_model": "fixed" if paper.slippage_points > 0 else "none",
            "slippage_points": paper.slippage_points,
            "swap_enabled": paper.swap_enabled,
        }
    )


class PaperExecution:
    def __init__(
        self,
        db: Database,
        account_key: str,
        specs: Mapping[str, SymbolSpec],
        rates: RateSource,
        clock: Clock,
        *,
        paper: PaperConfig,
        backtest: BacktestConfig,
        account_currency: str,
        leverage: float,
        starting_equity: float,
        bus: EventBus | None = None,
    ) -> None:
        self.db = db
        self.account_key = account_key
        self.clock = clock
        self.bus = bus
        self._account_currency = account_currency
        initial = paper.initial_balance or starting_equity
        self.broker = SimulatedBroker(
            dict(specs),
            broker_config(paper, backtest, initial),
            rates,
            account_currency=account_currency,
            leverage=leverage,
        )
        self._intent_by_order: dict[int, str] = {}

    # --- startup ----------------------------------------------------------------------------------------

    def restore(self) -> int:
        """Load the persisted book into the broker; returns the number of open positions restored."""
        now = self.clock.now_utc()
        with self.db.session() as sess:
            account = sess.get(PaperAccountRow, (LOCAL_ENGINE, self.account_key))
            if account is None:
                sess.add(
                    PaperAccountRow(
                        account_key=self.account_key,
                        currency=self._account_currency,
                        initial_balance=self.broker.balance,
                        balance=self.broker.balance,
                        next_id=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
                return 0
            self.broker.balance = account.balance
            self.broker.next_id = int(account.next_id)
            intents = {
                r.intent_id: r
                for r in sess.execute(
                    select(PaperIntentRow).where(PaperIntentRow.account_key == self.account_key)
                ).scalars()
            }
            for row in sess.execute(
                select(PaperPositionRow).where(
                    PaperPositionRow.account_key == self.account_key, PaperPositionRow.status == "OPEN"
                )
            ).scalars():
                intent = intents.get(row.intent_id)
                request = (
                    _request(intent)
                    if intent is not None
                    else OrderRequest(row.symbol, Side(row.side), row.volume, row.sl, row.tp)
                )
                self.broker.positions[row.ticket] = SimPosition(
                    ticket=row.ticket,
                    request=request,
                    entry_time=row.entry_time,
                    entry_price=row.entry_price,
                    sl=row.sl,
                    tp=row.tp,
                    commission=row.commission,
                    swap=row.swap,
                    price_current=row.price_current,
                    mae=row.mae,
                    mfe=row.mfe,
                    stop_kind=ExitReason(row.stop_kind),
                    bars_held=row.bars_held,
                )
            for intent in intents.values():
                if intent.status == "PENDING":
                    self.broker.restore_pending(intent.order_id, _request(intent), intent.created_at)
                    self._intent_by_order[intent.order_id] = intent.intent_id
        return len(self.broker.positions)

    # --- orders -----------------------------------------------------------------------------------------

    def place(self, record: DecisionRecord, magic: int) -> list[PlacedIntent]:
        """Turn an accepted decision into persisted intents and simulated orders (idempotent)."""
        if record.decision is not Decision.ACCEPT or record.sizing is None or not record.sizing.ok:
            return []
        signal = record.signal
        side = signal.side
        if side is None:
            return []
        now = self.clock.now_utc()
        sl = None if record.sizing.stop_loss is None else float(record.sizing.stop_loss)
        placed: list[PlacedIntent] = []
        with self.db.session() as sess:
            for i, part in enumerate(record.sizing.parts):
                key = f"{signal.idempotency_key}:{i}"
                existing = sess.execute(
                    select(PaperIntentRow).where(PaperIntentRow.idempotency_key == key)
                ).scalar_one_or_none()
                if existing is not None:
                    log.warning("intent %s already exists (%s); not placed again", key[:16], existing.status)
                    placed.append(PlacedIntent(existing.intent_id, key, existing.order_id, True))
                    continue
                tp = float(part.part.take_profit) if part.part.take_profit is not None else signal.take_profit
                request = OrderRequest(
                    symbol=signal.symbol,
                    side=side,
                    volume=float(part.volume),
                    sl=sl,
                    tp=tp,
                    entry_type=part.part.order_type,
                    price=None if part.part.order_type is EntryType.MARKET else float(part.part.entry),
                    expires_at=signal.expires_at_utc,
                    magic=magic,
                    comment=signal.strategy[:25],
                    strategy=signal.strategy,
                    signal_id=signal.signal_id,
                    risk_money=float(part.risk_money),
                )
                order_id = self.broker.submit(request, now)
                intent_id = new_id()
                self._intent_by_order[order_id] = intent_id
                sess.add(_intent_row(self.account_key, intent_id, key, record, request, order_id, now))
                placed.append(PlacedIntent(intent_id, key, order_id, False))
            self._save_account(sess, now)
        return placed

    def modify_stop(self, ticket: int, sl: float, stop_kind: ExitReason | None) -> None:
        self.broker.modify(ticket, sl=sl, stop_kind=stop_kind)
        with self.db.session() as sess:
            row = sess.get(PaperPositionRow, (LOCAL_ENGINE, ticket))
            if row is not None:
                row.sl = sl
                if stop_kind is not None:
                    row.stop_kind = stop_kind.value
                row.updated_at = self.clock.now_utc()

    def request_close(self, ticket: int, reason: ExitReason) -> None:
        self.broker.request_close(ticket, reason)

    # --- quotes -----------------------------------------------------------------------------------------

    def on_quote(self, symbol: str, bid: float, ask: float, at: datetime) -> list[BrokerEvent]:
        events = self.broker.on_quote(symbol, bid, ask, at)
        if events:
            with self.db.session() as sess:
                for event in events:
                    self._persist(sess, event)
                self._save_account(sess, ensure_utc(at))
            for event in events:
                self._notify(event)
        return events

    def save_marks(self) -> None:
        """Persist marks, excursions, swap and bars held of the open positions (called periodically)."""
        now = self.clock.now_utc()
        with self.db.session() as sess:
            for pos in self.broker.positions.values():
                row = sess.get(PaperPositionRow, (LOCAL_ENGINE, pos.ticket))
                if row is not None:
                    row.price_current, row.mae, row.mfe = pos.price_current, pos.mae, pos.mfe
                    row.swap, row.bars_held, row.updated_at = pos.swap, pos.bars_held, now
            self._save_account(sess, now)

    # --- internals --------------------------------------------------------------------------------------

    def _save_account(self, sess: Session, now: datetime) -> None:
        account = sess.get(PaperAccountRow, (LOCAL_ENGINE, self.account_key))
        if account is not None:
            account.balance = self.broker.balance
            account.next_id = self.broker.next_id
            account.updated_at = now

    def _persist(self, sess: Session, event: BrokerEvent) -> None:
        intent_id = self._intent_by_order.pop(event.order_id, None) if event.order_id is not None else None
        intent = sess.get(PaperIntentRow, (LOCAL_ENGINE, intent_id)) if intent_id else None
        now = ensure_utc(event.at)
        if event.kind is EventKind.ENTRY and event.ticket is not None:
            pos = self.broker.positions[event.ticket]
            if intent is not None:
                intent.status, intent.ticket, intent.updated_at = "FILLED", event.ticket, now
            sess.add(
                PaperPositionRow(
                    ticket=pos.ticket,
                    account_key=self.account_key,
                    intent_id=intent_id or "",
                    symbol=pos.symbol,
                    side=pos.side.value,
                    volume=pos.volume,
                    entry_time=pos.entry_time,
                    entry_price=pos.entry_price,
                    sl=pos.sl,
                    tp=pos.tp,
                    stop_kind=pos.stop_kind.value,
                    commission=pos.commission,
                    swap=pos.swap,
                    price_current=pos.price_current,
                    status="OPEN",
                    updated_at=now,
                )
            )
        elif event.kind in (EventKind.REJECTED, EventKind.EXPIRED) and intent is not None:
            intent.status, intent.detail, intent.updated_at = event.kind.value, event.detail, now
        elif event.kind is EventKind.EXIT and event.trade is not None:
            t = event.trade
            row = sess.get(PaperPositionRow, (LOCAL_ENGINE, t.ticket))
            if row is not None:
                row.status, row.exit_time, row.exit_price = "CLOSED", t.exit_time, t.exit_price
                row.exit_reason, row.profit, row.net = t.exit_reason.value, t.profit, t.net
                row.r_multiple, row.commission, row.swap = t.r_multiple, t.commission, t.swap
                row.mae, row.mfe, row.updated_at = t.mae, t.mfe, now

    def _notify(self, event: BrokerEvent) -> None:
        if self.bus is None:
            return
        if event.kind is EventKind.ENTRY and event.ticket is not None:
            pos = self.broker.positions.get(event.ticket)
            self.bus.emit(
                EventType.POSITION_OPENED,
                symbol=event.symbol,
                ticket=event.ticket,
                side=None if pos is None else pos.side.value,
                volume=None if pos is None else pos.volume,
                price=None if pos is None else pos.entry_price,
                paper=True,
            )
        elif event.kind is EventKind.EXIT and event.trade is not None:
            t = event.trade
            self.bus.emit(
                EventType.POSITION_CLOSED,
                symbol=t.symbol,
                ticket=t.ticket,
                reason=t.exit_reason.value,
                net=round(t.net, 2),
                r=None if t.r_multiple is None else round(t.r_multiple, 2),
                paper=True,
            )
        elif event.kind is EventKind.REJECTED:
            self.bus.emit(EventType.ORDER_REJECTED, symbol=event.symbol, reason=event.detail, paper=True)


def _request(row: PaperIntentRow) -> OrderRequest:
    return OrderRequest(
        symbol=row.symbol,
        side=Side(row.side),
        volume=row.volume,
        sl=row.sl,
        tp=row.tp,
        entry_type=EntryType(row.entry_type),
        price=row.price,
        expires_at=row.expires_at,
        magic=int(row.magic),
        comment=row.strategy[:25],
        strategy=row.strategy,
        signal_id=row.signal_id,
        risk_money=row.risk_money,
    )


def _intent_row(
    account_key: str,
    intent_id: str,
    key: str,
    record: DecisionRecord,
    request: OrderRequest,
    order_id: int,
    now: datetime,
) -> PaperIntentRow:
    return PaperIntentRow(
        intent_id=intent_id,
        account_key=account_key,
        idempotency_key=key,
        decision_id=record.decision_id,
        signal_id=record.signal.signal_id,
        strategy=record.signal.strategy,
        symbol=request.symbol,
        side=request.side.value,
        volume=request.volume,
        entry_type=request.entry_type.value,
        price=request.price,
        sl=request.sl,
        tp=request.tp,
        expires_at=request.expires_at,
        magic=request.magic,
        risk_money=request.risk_money,
        order_id=order_id,
        status="PENDING",
        created_at=now,
        updated_at=now,
    )
