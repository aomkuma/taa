"""TAA-1208: closed bot positions on the broker account are booked once from the MT5 deals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import select

from app.broker import mt5_constants as c
from app.broker.gateway import MarketDataGateway
from app.broker.models import Deal
from app.core.clock import ManualClock
from app.core.enums import ExitReason
from app.core.errors import BrokerError
from app.engine.broker_trades import BOOK_SECONDS, LOOKBACK_DAYS, BrokerTradeBook, exit_reason
from app.storage.database import Database
from app.storage.models import BrokerTradeRow, OrderIntentRow

T0 = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)


class StubMarket:
    def __init__(self) -> None:
        self.open: list[int] = []
        self.history: list[Deal] = []
        self.fail_positions = False
        self.fail_deals = False
        self.deal_calls = 0

    def positions(self, symbol: str | None = None) -> list[SimpleNamespace]:
        if self.fail_positions:
            raise BrokerError("positions_get failed")
        return [SimpleNamespace(ticket=t, identifier=t) for t in self.open]

    def deals(self, start_utc: datetime, end_utc: datetime) -> list[Deal]:
        self.deal_calls += 1
        if self.fail_deals:
            raise BrokerError("history_deals_get failed")
        return [d for d in self.history if start_utc <= d.time_utc < end_utc]


def deal(
    position: int,
    entry: int,
    price: float,
    *,
    at: datetime,
    volume: float = 0.1,
    profit: float = 0.0,
    swap: float = 0.0,
    commission: float = 0.0,
    reason: int = c.DEAL_REASON_EXPERT,
    comment: str = "",
    kind: int = c.DEAL_TYPE_BUY,
) -> Deal:
    return Deal(
        ticket=position * 10 + entry,
        order=position,
        position_id=position,
        symbol="EURUSD",
        type=kind,
        entry=entry,
        volume=volume,
        price=price,
        profit=profit,
        commission=commission,
        swap=swap,
        fee=0.0,
        magic=7310002,
        comment=comment,
        time_utc=at,
        reason=reason,
    )


def intent(
    db: Database,
    position: int,
    *,
    side: str = "BUY",
    sl: float = 1.0980,
    created: datetime = T0,
    part: int = 0,
) -> None:
    with db.session() as sess:
        sess.add(
            OrderIntentRow(
                intent_id=f"i{position}",
                idempotency_key=f"k{position}",
                decision_id="d1",
                signal_id="s1",
                strategy="example_trend_pullback",
                symbol="EURUSD",
                side=side,
                volume=0.1,
                price_requested=1.1000,
                sl=sl,
                tp=1.1040,
                magic=7310002,
                comment="taa",
                risk_money=20.0,
                state="PROTECTED",
                order_ticket=position,
                position_ticket=position,
                fill_price=1.1000,
                fill_volume=0.1,
                expires_at=created + timedelta(minutes=5),
                created_at=created,
                updated_at=created,
                plan_key="p1" if part else "",
                part_index=part,
            )
        )


@pytest.fixture
def setup() -> tuple[Database, ManualClock, StubMarket, BrokerTradeBook]:
    db = Database("sqlite://")
    db.create_all()
    clock = ManualClock(T0 + timedelta(hours=2))
    market = StubMarket()
    book = BrokerTradeBook(db, cast(MarketDataGateway, market), clock, account_key="acc", mode="DEMO")
    return db, clock, market, book


def trades(db: Database) -> list[BrokerTradeRow]:
    with db.session() as sess:
        rows = list(sess.scalars(select(BrokerTradeRow).order_by(BrokerTradeRow.position_ticket)))
        for r in rows:
            sess.expunge(r)
        return rows


def test_a_closed_position_is_booked_with_net_and_r(
    setup: tuple[Database, ManualClock, StubMarket, BrokerTradeBook],
) -> None:
    db, _, market, book = setup
    intent(db, 101)
    market.history = [
        deal(101, c.DEAL_ENTRY_IN, 1.1001, at=T0 + timedelta(seconds=1)),
        deal(
            101,
            c.DEAL_ENTRY_OUT,
            1.0981,
            at=T0 + timedelta(hours=1),
            profit=-20.0,
            swap=-0.12,
            commission=-0.5,
            reason=c.DEAL_REASON_SL,
            comment="[sl 1.09810]",
            kind=c.DEAL_TYPE_SELL,
        ),
    ]
    assert book.run() == 1
    [row] = trades(db)
    assert (row.position_ticket, row.mode, row.account_key, row.strategy) == (
        101,
        "DEMO",
        "acc",
        "example_trend_pullback",
    )
    assert (row.entry_price, row.exit_price, row.volume) == (1.1001, 1.0981, 0.1)
    assert (row.profit, row.swap, row.commission, row.net) == (-20.0, -0.12, -0.5, -20.62)
    assert row.r_multiple == pytest.approx(-0.952, abs=1e-3)  # measured from the real fill, not the request
    assert row.exit_reason == ExitReason.STOP_LOSS.value
    assert row.entry_time == T0 + timedelta(seconds=1) and row.exit_time == T0 + timedelta(hours=1)


def test_open_positions_and_missing_exit_deals_wait(
    setup: tuple[Database, ManualClock, StubMarket, BrokerTradeBook],
) -> None:
    db, clock, market, book = setup
    intent(db, 101)
    market.open = [101]
    assert book.run() == 0
    assert market.deal_calls == 0  # nothing gone: no history read
    market.open = []
    market.history = [deal(101, c.DEAL_ENTRY_IN, 1.1, at=T0)]  # the exit deal is not in the history yet
    clock.advance(BOOK_SECONDS)
    assert book.run() == 0
    market.history.append(
        deal(101, c.DEAL_ENTRY_OUT, 1.104, at=T0 + timedelta(hours=1), profit=40.0, reason=c.DEAL_REASON_TP)
    )
    clock.advance(BOOK_SECONDS)
    assert book.run() == 1
    assert trades(db)[0].exit_reason == ExitReason.TAKE_PROFIT.value


def test_booked_once_and_throttled(setup: tuple[Database, ManualClock, StubMarket, BrokerTradeBook]) -> None:
    db, clock, market, book = setup
    intent(db, 101)
    market.history = [
        deal(101, c.DEAL_ENTRY_IN, 1.1, at=T0),
        deal(101, c.DEAL_ENTRY_OUT, 1.101, at=T0 + timedelta(minutes=5), profit=10.0),
    ]
    assert book.run() == 1
    assert book.run() == 0  # within BOOK_SECONDS
    clock.advance(BOOK_SECONDS)
    assert book.run() == 0
    assert market.deal_calls == 1  # nothing left to book: no history read
    assert len(trades(db)) == 1


@pytest.mark.parametrize("failing", ["positions", "deals"])
def test_unreadable_broker_books_nothing(
    setup: tuple[Database, ManualClock, StubMarket, BrokerTradeBook], failing: str
) -> None:
    db, clock, market, book = setup
    intent(db, 101)
    market.history = [
        deal(101, c.DEAL_ENTRY_IN, 1.1, at=T0),
        deal(101, c.DEAL_ENTRY_OUT, 1.101, at=T0 + timedelta(minutes=5)),
    ]
    setattr(market, f"fail_{failing}", True)
    assert book.run() == 0
    assert trades(db) == []
    setattr(market, f"fail_{failing}", False)
    clock.advance(BOOK_SECONDS)
    assert book.run() == 1


def test_parts_of_a_plan_are_separate_rows_and_old_intents_are_skipped(
    setup: tuple[Database, ManualClock, StubMarket, BrokerTradeBook],
) -> None:
    db, clock, market, book = setup
    intent(db, 101, side="SELL", sl=1.1020)
    intent(db, 102, side="SELL", sl=1.1020, part=1)
    intent(db, 99, created=clock.now_utc() - timedelta(days=LOOKBACK_DAYS + 1))
    end = T0 + timedelta(hours=1)
    market.history = [
        deal(101, c.DEAL_ENTRY_IN, 1.1000, at=T0, kind=c.DEAL_TYPE_SELL),
        deal(102, c.DEAL_ENTRY_IN, 1.1010, at=T0 + timedelta(minutes=20), kind=c.DEAL_TYPE_SELL),
        deal(101, c.DEAL_ENTRY_OUT, 1.0999, at=end, profit=1.0, reason=c.DEAL_REASON_SL),
        deal(102, c.DEAL_ENTRY_OUT, 1.0999, at=end, profit=11.0, reason=c.DEAL_REASON_SL),
        Deal(1, 0, 0, "", c.DEAL_TYPE_BALANCE, 0, 0.0, 0.0, 1000.0, 0.0, 0.0, 0.0, 0, "", T0),
    ]
    assert book.run() == 2
    first, second = trades(db)
    assert (first.part_index, second.part_index) == (0, 1)
    assert first.exit_reason == ExitReason.BREAK_EVEN.value  # +0.05R: a stop moved to the entry
    assert second.r_multiple == pytest.approx(1.1) and second.exit_reason == ExitReason.TRAILING_STOP.value
    assert first.net == 1.0  # the balance deal is no part of a trade


@pytest.mark.parametrize(
    ("reason", "comment", "r", "expected"),
    [
        (c.DEAL_REASON_TP, "[tp]", 2.0, ExitReason.TAKE_PROFIT),
        (c.DEAL_REASON_SO, "", -1.4, ExitReason.STOP_OUT),
        (c.DEAL_REASON_SL, "", -1.02, ExitReason.STOP_LOSS),
        (c.DEAL_REASON_SL, "", None, ExitReason.STOP_LOSS),
        (c.DEAL_REASON_SL, "", 0.01, ExitReason.BREAK_EVEN),
        (c.DEAL_REASON_SL, "", 0.8, ExitReason.TRAILING_STOP),
        (c.DEAL_REASON_EXPERT, "taa:time", 0.3, ExitReason.TIME_STOP),
        (c.DEAL_REASON_EXPERT, "taa:kill_switch", 0.3, ExitReason.KILL_SWITCH),
        (c.DEAL_REASON_EXPERT, "other EA", 0.3, None),
        (c.DEAL_REASON_CLIENT, "", 0.3, ExitReason.MANUAL),
        (c.DEAL_REASON_MOBILE, "", 0.3, ExitReason.MANUAL),
        (-1, "", 0.3, None),
    ],
)
def test_exit_reason(reason: int, comment: str, r: float | None, expected: ExitReason | None) -> None:
    d = deal(1, c.DEAL_ENTRY_OUT, 1.1, at=T0, reason=reason, comment=comment)
    assert exit_reason(d, r) is expected
