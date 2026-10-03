from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import BacktestConfig, PaperConfig
from app.core.clock import ManualClock
from app.core.enums import EntryType, ExitReason, Side
from app.engine.decision_engine import Decision, DecisionRecord
from app.engine.paper import LiveRates, PaperExecution
from app.execution.simulated_broker import AccountCurrencyOnly, EventKind, OrderRequest, SimulatedBroker
from app.monitoring.alerts import EventBus, EventType, MemorySink
from app.storage.database import Database
from app.storage.models import PaperIntentRow, PaperPositionRow
from tests.strategy_data import EURUSD_SPEC
from tests.unit.test_decision_engine import NOW, engine, request

S = timedelta(seconds=1)


def quote_broker() -> SimulatedBroker:
    return SimulatedBroker(
        {"EURUSD": EURUSD_SPEC}, BacktestConfig(slippage_model="none"), AccountCurrencyOnly("USD")
    )


class TestTickFills:
    def test_market_order_fills_on_the_next_quote(self) -> None:
        br = quote_broker()
        br.submit(OrderRequest("EURUSD", Side.BUY, 0.1, 1.0980, 1.1040), NOW)
        assert br.on_quote("EURUSD", 1.09990, 1.10000, NOW) == []  # same instant: not yet
        events = br.on_quote("EURUSD", 1.09992, 1.10002, NOW + S)
        assert [e.kind for e in events] == [EventKind.ENTRY]
        assert next(iter(br.positions.values())).entry_price == 1.10002

    def test_stop_and_target_on_ticks(self) -> None:
        br = quote_broker()
        br.submit(OrderRequest("EURUSD", Side.SELL, 0.1, 1.1020, 1.0960), NOW)
        br.on_quote("EURUSD", 1.1000, 1.1001, NOW + S)
        assert br.on_quote("EURUSD", 1.1018, 1.1019, NOW + 2 * S) == []
        hit = br.on_quote(
            "EURUSD", 1.1021, 1.1022, NOW + 3 * S
        )  # the ask passed the stop: gap fill at the ask
        trade = hit[0].trade
        assert trade is not None and trade.exit_reason is ExitReason.STOP_LOSS and trade.exit_price == 1.1022
        assert trade.mae == pytest.approx(1.1022 - 1.1000)

    def test_take_profit_fills_at_its_price(self) -> None:
        br = quote_broker()
        br.submit(OrderRequest("EURUSD", Side.BUY, 0.1, 1.0980, 1.1040), NOW)
        br.on_quote("EURUSD", 1.1000, 1.1001, NOW + S)
        trade = br.on_quote("EURUSD", 1.1045, 1.1046, NOW + 2 * S)[0].trade
        assert trade is not None and trade.exit_price == 1.1040

    def test_limit_and_close_request(self) -> None:
        br = quote_broker()
        br.submit(OrderRequest("EURUSD", Side.BUY, 0.1, 1.0950, None, EntryType.LIMIT, 1.0990), NOW)
        assert br.on_quote("EURUSD", 1.0995, 1.0996, NOW + S) == []
        assert [e.kind for e in br.on_quote("EURUSD", 1.0988, 1.0989, NOW + 2 * S)] == [EventKind.ENTRY]
        ticket = next(iter(br.positions))
        br.request_close(ticket, ExitReason.SIGNAL)
        trade = br.on_quote("EURUSD", 1.0993, 1.0994, NOW + 3 * S)[0].trade
        assert trade is not None and trade.exit_reason is ExitReason.SIGNAL and trade.exit_price == 1.0993


@pytest.fixture
def accepted(db: Database) -> DecisionRecord:
    record = engine(db).decide(request())
    assert record.decision is Decision.ACCEPT
    return record


def paper(db: Database, clock: ManualClock, bus: EventBus | None = None) -> PaperExecution:
    p = PaperExecution(
        db,
        "acct",
        {"EURUSD": EURUSD_SPEC},
        AccountCurrencyOnly("USD"),
        clock,
        paper=PaperConfig(slippage_points=0),
        backtest=BacktestConfig(),
        account_currency="USD",
        leverage=100,
        starting_equity=5_000.0,
        bus=bus,
    )
    p.restore()
    return p


class TestPaperExecution:
    def test_lifecycle_is_persisted_and_announced(self, db: Database, accepted: DecisionRecord) -> None:
        clock = ManualClock(NOW)
        sink = MemorySink()
        p = paper(db, clock, EventBus(clock, [sink]))
        assert p.broker.balance == 5_000.0  # starting equity, since paper.initial_balance is unset
        placed = p.place(accepted, magic=7_310_000)
        assert len(placed) == 1 and not placed[0].duplicate
        with db.session() as sess:
            assert sess.execute(select(PaperIntentRow.status)).scalar_one() == "PENDING"
        clock.advance(1)
        p.on_quote("EURUSD", 1.09992, 1.10000, clock.now_utc())
        with db.session() as sess:
            assert sess.execute(select(PaperIntentRow.status)).scalar_one() == "FILLED"
            assert sess.execute(select(PaperPositionRow.status)).scalar_one() == "OPEN"
        clock.advance(1)
        p.on_quote("EURUSD", 1.10410, 1.10418, clock.now_utc())  # through the TP
        with db.session() as sess:
            row = sess.execute(select(PaperPositionRow)).scalar_one()
            assert (row.status, row.exit_reason) == ("CLOSED", "TP")
            assert row.net == pytest.approx((1.104 - 1.1) * 100_000 * 0.24)
        assert [e.type for e in sink.events] == [EventType.POSITION_OPENED, EventType.POSITION_CLOSED]
        assert all(e.params["paper"] for e in sink.events)

    def test_idempotent_placement(self, db: Database, accepted: DecisionRecord) -> None:
        p = paper(db, ManualClock(NOW))
        first = p.place(accepted, magic=7_310_000)
        again = p.place(accepted, magic=7_310_000)
        assert [i.duplicate for i in again] == [True]
        assert again[0].intent_id == first[0].intent_id
        assert len(p.broker.pending) == 1

    def test_restore_after_restart(self, db: Database, accepted: DecisionRecord) -> None:
        clock = ManualClock(NOW)
        p = paper(db, clock)
        p.place(accepted, magic=7_310_000)
        clock.advance(1)
        p.on_quote("EURUSD", 1.09992, 1.10000, clock.now_utc())
        p.modify_stop(next(iter(p.broker.positions)), 1.1002, ExitReason.BREAK_EVEN)
        p.save_marks()
        restarted = paper(db, clock)
        assert len(restarted.broker.positions) == 1
        pos = next(iter(restarted.broker.positions.values()))
        assert (pos.sl, pos.stop_kind, pos.volume) == (1.1002, ExitReason.BREAK_EVEN, 0.24)
        assert restarted.broker.next_id == p.broker.next_id  # no id is ever reused
        assert restarted.place(accepted, magic=7_310_000)[0].duplicate
        clock.advance(1)
        trade = restarted.on_quote("EURUSD", 1.1001, 1.10018, clock.now_utc())[0].trade
        assert trade is not None and trade.exit_reason is ExitReason.BREAK_EVEN

    def test_pending_intent_survives_restart(self, db: Database, accepted: DecisionRecord) -> None:
        clock = ManualClock(NOW)
        paper(db, clock).place(accepted, magic=7_310_000)
        restarted = paper(db, clock)
        clock.advance(1)
        assert [e.kind for e in restarted.on_quote("EURUSD", 1.09992, 1.10000, clock.now_utc())] == [
            EventKind.ENTRY
        ]
        with db.session() as sess:
            assert sess.execute(select(PaperIntentRow.status)).scalar_one() == "FILLED"

    def test_rejected_decisions_place_nothing(self, db: Database) -> None:
        from app.engine.decision_engine import SystemHealth

        record = engine(db).decide(request(health=SystemHealth(kill_switch_active=True)))
        assert paper(db, ManualClock(NOW)).place(record, magic=1) == []


def test_live_rates_from_fake_mt5() -> None:
    from tests.unit.test_market_data import setup

    _, _, gateway = setup(datetime(2026, 9, 30, 10, 0, tzinfo=UTC))
    rates = LiveRates(gateway, "USD")
    eur = rates.rate("EUR", NOW)
    assert eur is not None and 0.5 < eur < 2.0
    jpy = rates.rate("JPY", NOW)
    assert jpy is not None and jpy < 0.05  # 1 / USDJPY
    assert rates.rate("XYZ", NOW) is None
