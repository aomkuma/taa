from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import select

from app.config import PositionManagementConfig
from app.core.clock import ManualClock
from app.core.enums import ExitReason, Side, Timeframe
from app.engine.decision_engine import DecisionRecord
from app.engine.paper import PaperExecution
from app.engine.position_manager import PositionManager
from app.monitoring.alerts import EventBus, EventType, MemorySink
from app.storage.database import Database
from app.storage.models import PaperPositionRow
from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_models import Signal, StrategyContext
from tests.strategy_data import EURUSD_SPEC
from tests.unit.test_decision_engine import NOW, engine, request
from tests.unit.test_paper_execution import paper
from tests.unit.test_strategy_models import make_context

MAGIC = 7_310_000


@pytest.fixture
def record(db: Database) -> DecisionRecord:
    return engine(db).decide(request())


ATR = 0.0005


class Closer(BaseStrategy):
    name = "closer"

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return ()

    def warmup_bars(self) -> int:
        return 1

    def evaluate(self, ctx: StrategyContext) -> Signal:
        return self.hold(ctx)

    def should_close(self, ctx: StrategyContext, side: Side) -> bool:
        return True


def setup(
    db: Database, record: DecisionRecord, cfg: PositionManagementConfig | None = None, **spec_kw: int
) -> tuple[ManualClock, PaperExecution, PositionManager, MemorySink]:
    clock = ManualClock(NOW)
    sink = MemorySink()
    bus = EventBus(clock, [sink])
    p = paper(db, clock, bus)
    p.place(record, magic=MAGIC)
    clock.advance(1)
    p.on_quote("EURUSD", 1.09992, 1.10000, clock.now_utc())  # filled at 1.10000; risk 0.0020
    spec = dataclasses.replace(EURUSD_SPEC, **spec_kw)
    pm = PositionManager(
        p, cfg or PositionManagementConfig(), {"EURUSD": spec}, clock, strategies_by_magic={}, bus=bus
    )
    return clock, p, pm, sink


def position(p: PaperExecution):  # type: ignore[no-untyped-def]
    return next(iter(p.broker.positions.values()))


class TestRules:
    def test_break_even_then_trailing_with_rate_limit(self, db: Database, record: DecisionRecord) -> None:
        clock, p, pm, sink = setup(db, record)
        clock.advance(1)
        pm.on_quote("EURUSD", 1.10200, 1.10208, ATR)  # +1R
        assert position(p).sl == pytest.approx(1.10000 + 2 * EURUSD_SPEC.point)
        assert position(p).stop_kind is ExitReason.BREAK_EVEN
        clock.advance(1)
        pm.on_quote("EURUSD", 1.10310, 1.10318, ATR)  # past +1.5R, but only 1 s after the last change
        assert position(p).stop_kind is ExitReason.BREAK_EVEN
        clock.advance(10)
        pm.on_quote("EURUSD", 1.10310, 1.10318, ATR)
        assert position(p).sl == pytest.approx(1.10310 - 2 * ATR)
        assert position(p).stop_kind is ExitReason.TRAILING_STOP
        moves = [e for e in sink.events if e.type is EventType.STOP_MOVED]
        assert [m.params["kind"] for m in moves] == ["BE", "TRAIL"]
        with db.session() as sess:
            row = sess.execute(select(PaperPositionRow)).scalar_one()
            assert (row.sl, row.stop_kind) == (pytest.approx(1.10210), "TRAIL")

    def test_stops_level_blocks_a_move_too_close_to_price(self, db: Database, record: DecisionRecord) -> None:
        clock, p, pm, _ = setup(db, record, stops_level=300)
        clock.advance(1)
        pm.on_quote("EURUSD", 1.10200, 1.10208, ATR)
        assert position(p).sl == pytest.approx(1.098, abs=1e-5)  # unchanged

    def test_stop_never_moves_back(self, db: Database, record: DecisionRecord) -> None:
        clock, p, pm, _ = setup(db, record)
        clock.advance(11)
        pm.on_quote("EURUSD", 1.10310, 1.10318, ATR)
        high = position(p).sl
        clock.advance(11)
        pm.on_quote("EURUSD", 1.10250, 1.10258, ATR)  # the price fell back; the trail must not follow
        assert position(p).sl == high

    def test_time_stop_counts_closed_bars(self, db: Database, record: DecisionRecord) -> None:
        clock, p, pm, _ = setup(db, record, PositionManagementConfig(time_stop_bars=2))
        ctx = StrategyContext(make_context(), {}, NOW)
        pm.on_bar("EURUSD", ctx)
        clock.advance(1)
        pm.on_quote("EURUSD", 1.1001, 1.10018, ATR)
        assert not position(p).close_requested
        pm.on_bar("EURUSD", ctx)
        pm.on_quote("EURUSD", 1.1001, 1.10018, ATR)
        clock.advance(1)
        trade = p.on_quote("EURUSD", 1.1001, 1.10018, clock.now_utc())[0].trade
        assert trade is not None and trade.exit_reason is ExitReason.TIME_STOP

    def test_strategy_close_signal(self, db: Database, record: DecisionRecord) -> None:
        clock, p, pm, _ = setup(db, record)
        pm.strategies_by_magic = {MAGIC: Closer()}
        pm.on_bar("EURUSD", StrategyContext(make_context(), {}, NOW))
        clock.advance(1)
        trade = p.on_quote("EURUSD", 1.1001, 1.10018, clock.now_utc())[0].trade
        assert trade is not None and trade.exit_reason is ExitReason.SIGNAL

    def test_missing_stop_is_reattached(self, db: Database, record: DecisionRecord) -> None:
        _, p, pm, _ = setup(db, record)
        position(p).sl = None
        pm.on_quote("EURUSD", 1.1001, 1.10018, ATR)
        assert position(p).sl == pytest.approx(1.098, abs=1e-5)

    def test_excursions_are_tracked_and_saved(self, db: Database, record: DecisionRecord) -> None:
        clock, p, _, _ = setup(db, record)
        for bid in (1.0990, 1.1015, 1.1000):
            clock.advance(1)
            p.on_quote("EURUSD", bid, bid + 0.00008, clock.now_utc())
        p.save_marks()
        with db.session() as sess:
            row = sess.execute(select(PaperPositionRow)).scalar_one()
        assert row.mae == pytest.approx(0.0010)
        assert row.mfe == pytest.approx(0.0015)
