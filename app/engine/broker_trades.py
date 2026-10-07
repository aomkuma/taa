"""Closed bot positions on the broker account (DEMO/LIVE; TAA-1208): the trade history the PWA shows.

The bot's broker positions live in MT5 and in ``order_intents`` (the position ticket of each filled part),
so nothing recorded a closed one. :class:`BrokerTradeBook` books each position into ``broker_trades`` once it
is no longer open, from its MT5 deals: entry and exit price (volume weighted), profit, swap, commission + fee,
net (the balance change), the exit reason and R against the intent's stop. One row per MT5 position, so the
parts of a split entry are separate rows, as in the terminal.

A position that closed while the engine was down is booked on the next pass (the intents of the last
:data:`LOOKBACK_DAYS` are looked at), so the history matches the terminal after a restart. When the open
positions or the deal history cannot be read, nothing is booked this pass; a position whose exit deal is not
in the history yet is tried again later.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select

from app.broker import mt5_constants as c
from app.broker.gateway import MarketDataGateway
from app.broker.models import Deal
from app.core.clock import Clock, ensure_utc
from app.core.enums import ExitReason, Side
from app.core.errors import TaaError
from app.storage.database import Database
from app.storage.models import BrokerTradeRow, OrderIntentRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)

BOOK_SECONDS = 30.0  # how often closed positions are looked up in the deal history
LOOKBACK_DAYS = 30  # intents older than this are not looked at any more
EXIT_ENTRIES = frozenset({c.DEAL_ENTRY_OUT, c.DEAL_ENTRY_OUT_BY, c.DEAL_ENTRY_INOUT})
OWNER_REASONS = frozenset({c.DEAL_REASON_CLIENT, c.DEAL_REASON_MOBILE, c.DEAL_REASON_WEB})
BOT_COMMENT = "taa:"  # BrokerPositionManager.close comments its closes "taa:<exit reason>"
_BY_VALUE = {r.value.lower(): r for r in ExitReason}


@dataclass(frozen=True, slots=True)
class _Intent:
    """The fields of a filled intent a trade needs (read once, outside the session)."""

    intent_id: str
    decision_id: str
    strategy: str
    magic: int
    symbol: str
    side: str
    sl: float
    tp: float | None
    plan_key: str
    part_index: int
    fill_price: float | None
    fill_volume: float | None
    created_at: datetime


def exit_reason(deal: Deal, r_multiple: float | None) -> ExitReason | None:
    """Why a position closed, from its last exit deal. A broker stop at or near the entry is a break-even
    exit and one beyond it a trailing stop, as the paper book names them; None when it is not known."""
    if deal.reason == c.DEAL_REASON_TP:
        return ExitReason.TAKE_PROFIT
    if deal.reason == c.DEAL_REASON_SO:
        return ExitReason.STOP_OUT
    if deal.reason == c.DEAL_REASON_SL:
        if r_multiple is None or r_multiple <= -0.25:
            return ExitReason.STOP_LOSS
        return ExitReason.BREAK_EVEN if r_multiple < 0.25 else ExitReason.TRAILING_STOP
    if deal.reason == c.DEAL_REASON_EXPERT:
        tag = deal.comment.strip().lower()
        return _BY_VALUE.get(tag[len(BOT_COMMENT) :]) if tag.startswith(BOT_COMMENT) else None
    if deal.reason in OWNER_REASONS:
        return ExitReason.MANUAL
    return None


def _vwap(deals: Sequence[Deal]) -> float | None:
    volume = sum(d.volume for d in deals)
    return None if volume <= 0 else sum(d.price * d.volume for d in deals) / volume


class BrokerTradeBook:
    def __init__(
        self, db: Database, market: MarketDataGateway, clock: Clock, *, account_key: str, mode: str
    ) -> None:
        self.db = db
        self.market = market
        self.clock = clock
        self.account_key = account_key
        self.mode = mode
        self._next = 0.0

    def run(self) -> int:
        """Book every filled bot position that is no longer open (at most every :data:`BOOK_SECONDS`).
        Returns the number of trades booked."""
        now = self.clock.monotonic()
        if now < self._next:
            return 0
        self._next = now + BOOK_SECONDS
        pending = self._unbooked()
        if not pending:
            return 0
        try:
            open_ids = {i for p in self.market.positions() for i in (p.ticket, p.identifier) if i}
        except TaaError:
            log.warning("positions_get failed; closed broker trades are booked later")
            return 0
        gone = {ticket: intent for ticket, intent in pending.items() if ticket not in open_ids}
        if not gone:
            return 0
        start = min(i.created_at for i in gone.values()) - timedelta(minutes=1)
        try:
            deals = self.market.deals(start, self.clock.now_utc() + timedelta(minutes=1))
        except TaaError:
            log.warning("history_deals_get failed; closed broker trades are booked later")
            return 0
        by_position: dict[int, list[Deal]] = defaultdict(list)
        for d in deals:
            if not d.is_cash_flow:
                by_position[d.position_id].append(d)
        rows = [
            row
            for ticket, intent in gone.items()
            if (row := self._trade(ticket, intent, by_position.get(ticket, []))) is not None
        ]
        if rows:
            with self.db.session() as sess:
                for row in rows:
                    if sess.get(BrokerTradeRow, (LOCAL_ENGINE, row.position_ticket)) is None:
                        sess.add(row)
        for row in rows:
            log.info(
                "broker trade #%s %s %s closed at %s (%s, net %s, %s R)",
                row.position_ticket,
                row.symbol,
                row.side,
                row.exit_price,
                row.exit_reason,
                row.net,
                row.r_multiple,
            )
        return len(rows)

    def _unbooked(self) -> dict[int, _Intent]:
        """Position ticket -> its intent, for the filled intents of the lookback without a booked trade."""
        since = self.clock.now_utc() - timedelta(days=LOOKBACK_DAYS)
        with self.db.session() as sess:
            intents = sess.scalars(
                select(OrderIntentRow)
                .where(OrderIntentRow.position_ticket.is_not(None), OrderIntentRow.created_at >= since)
                .order_by(OrderIntentRow.created_at)
            ).all()
            tickets = {int(i.position_ticket) for i in intents if i.position_ticket is not None}
            booked = set(
                sess.scalars(
                    select(BrokerTradeRow.position_ticket).where(BrokerTradeRow.position_ticket.in_(tickets))
                )
            )
            out: dict[int, _Intent] = {}
            for i in intents:
                ticket = int(i.position_ticket or 0)
                if ticket in booked or ticket in out:
                    continue  # the first intent of a position is the one that opened it
                out[ticket] = _Intent(
                    i.intent_id,
                    i.decision_id,
                    i.strategy,
                    i.magic,
                    i.symbol,
                    i.side,
                    i.sl,
                    i.tp,
                    i.plan_key,
                    i.part_index,
                    i.fill_price,
                    i.fill_volume,
                    ensure_utc(i.created_at),
                )
            return out

    def _trade(self, ticket: int, intent: _Intent, deals: Sequence[Deal]) -> BrokerTradeRow | None:
        entries = [d for d in deals if d.entry == c.DEAL_ENTRY_IN]
        exits = sorted((d for d in deals if d.entry in EXIT_ENTRIES), key=lambda d: d.time_utc)
        exit_price = _vwap(exits)
        entry_price = _vwap(entries) if entries else intent.fill_price
        if exit_price is None or entry_price is None:
            return None  # the exit deal is not in the history yet
        risk = abs(entry_price - intent.sl)
        sign = 1 if intent.side == Side.BUY.value else -1
        r_multiple = round(sign * (exit_price - entry_price) / risk, 3) if risk > 0 else None
        reason = exit_reason(exits[-1], r_multiple)
        profit = sum(d.profit for d in deals)
        swap = sum(d.swap for d in deals)
        commission = sum(d.commission + d.fee for d in deals)
        volume = sum(d.volume for d in entries) or intent.fill_volume or sum(d.volume for d in exits)
        return BrokerTradeRow(
            position_ticket=ticket,
            account_key=self.account_key,
            mode=self.mode,
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            strategy=intent.strategy,
            magic=intent.magic,
            symbol=intent.symbol,
            side=intent.side,
            volume=round(volume, 8),
            plan_key=intent.plan_key,
            part_index=intent.part_index,
            entry_time=min(d.time_utc for d in entries) if entries else intent.created_at,
            entry_price=round(entry_price, 8),
            sl_initial=intent.sl,
            tp=intent.tp,
            exit_time=exits[-1].time_utc,
            exit_price=round(exit_price, 8),
            exit_reason=None if reason is None else reason.value,
            profit=round(profit, 2),
            swap=round(swap, 2),
            commission=round(commission, 2),
            net=round(profit + swap + commission, 2),
            r_multiple=r_multiple,
            booked_at=self.clock.now_utc(),
        )
