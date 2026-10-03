"""Restart safety (TAA-604): a restarted engine never duplicates a signal and never fills a stale order."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select

from app.broker.factory import build_read_only
from app.core.clock import ManualClock
from app.engine.orchestrator import Engine
from app.market_data.candle_service import CandleWatermarks
from app.monitoring.alerts import EventBus, EventType, MemorySink
from app.risk.circuit_breaker import BreakerName
from app.storage.database import Database
from app.storage.models import DecisionRecordRow, PaperIntentRow, PaperPositionRow, ProcessedCandle
from app.strategy.arbitration import SignalArbiter
from app.strategy.registry import StrategySet
from tests.integration.test_engine_paper import START, BuyEveryBar, settings


def make_engine(tmp_path: Path, db: Database, clock: ManualClock, sink: MemorySink) -> Engine:
    s = settings(tmp_path)
    return Engine(
        s,
        build_read_only(s, fake=True, clock=clock),
        db,
        clock,
        bus=EventBus(clock, [sink], dedupe_seconds=0),
        sleep=clock.advance,  # server-time verification waits on the simulated clock
    )


def start_with_buyer(engine: Engine) -> None:
    engine.start()
    strategy = BuyEveryBar()
    engine.strategies = StrategySet((strategy,))
    engine.magic = {strategy.name: 7_310_000}
    engine.positions.strategies_by_magic = {7_310_000: strategy}


def run_until(
    engine: Engine, clock: ManualClock, sink: MemorySink, event: EventType, limit: int = 80
) -> None:
    for _ in range(limit):
        engine.cycle()
        if any(e.type is event for e in sink.events):
            return
        clock.advance(30)
    raise AssertionError(f"{event} never happened")


def count(db: Database, model: type) -> int:
    with db.session() as sess:
        return int(sess.execute(select(func.count()).select_from(model)).scalar_one())


def fresh_db() -> Database:
    db = Database("sqlite://")
    db.create_all()
    return db


def test_no_duplicate_signal_after_a_restart(tmp_path: Path) -> None:
    db, clock, sink = fresh_db(), ManualClock(START), MemorySink()
    first = make_engine(tmp_path, db, clock, sink)
    start_with_buyer(first)
    run_until(first, clock, sink, EventType.POSITION_OPENED)
    first.shutdown()
    assert count(db, PaperIntentRow) == 1

    # worst case: the watermark is lost too, so the same bar is evaluated again after the restart
    with db.session() as sess:
        sess.execute(delete(ProcessedCandle))
    second = make_engine(tmp_path, db, clock, sink)
    start_with_buyer(second)
    assert len(second.paper.broker.positions) == 1  # the open paper position came back
    assert "EURUSD" in second._last_entry
    second.cycle()
    assert count(db, PaperIntentRow) == 1
    assert count(db, PaperPositionRow) == 1
    # first line of defence: the restored arbiter cooldown suppresses the re-signal (no new decision at all)
    with db.session() as sess:
        accepted = sess.execute(
            select(func.count()).select_from(DecisionRecordRow).where(DecisionRecordRow.decision == "ACCEPT")
        ).scalar_one()
    assert accepted == 1
    # second line: even with the cooldown gone, the decision engine refuses an already-accepted signal
    with db.session() as sess:
        sess.execute(delete(ProcessedCandle))
    second.watermarks = CandleWatermarks(db, clock)  # drop its in-memory cache too
    second.arbiter = SignalArbiter(0)
    clock.advance(5)  # past the candle-poll interval
    second.cycle()
    with db.session() as sess:
        last = sess.execute(
            select(DecisionRecordRow.reason_codes).order_by(DecisionRecordRow.created_at.desc()).limit(1)
        ).scalar_one()
    assert "DUPLICATE_SIGNAL" in last
    assert count(db, PaperIntentRow) == 1
    second.shutdown()


def test_a_pending_order_expires_instead_of_filling_late(tmp_path: Path) -> None:
    db, clock, sink = fresh_db(), ManualClock(START), MemorySink()
    first = make_engine(tmp_path, db, clock, sink)
    start_with_buyer(first)
    run_until(first, clock, sink, EventType.SIGNAL_ACCEPTED)  # placed, not yet filled
    first.shutdown()
    clock.advance(3600)  # the engine was down for an hour: the signal expired
    second = make_engine(tmp_path, db, clock, sink)
    start_with_buyer(second)
    assert len(second.paper.broker.pending) == 1
    second.cycle()
    with db.session() as sess:
        statuses = (
            sess.execute(select(PaperIntentRow.status).order_by(PaperIntentRow.created_at)).scalars().all()
        )
    assert statuses[0] == "EXPIRED"  # the order from before the restart was never filled
    assert count(db, PaperPositionRow) == 0
    second.shutdown()


def test_breakers_and_watermarks_survive(tmp_path: Path) -> None:
    db, clock, sink = fresh_db(), ManualClock(START), MemorySink()
    first = make_engine(tmp_path, db, clock, sink)
    first.start()
    first.board.trip(BreakerName.MAX_DRAWDOWN, "test")
    for _ in range(40):
        first.cycle()
        clock.advance(30)
    mark = first.watermarks.get("EURUSD", first.config.timeframes.entry)
    first.shutdown()
    second = make_engine(tmp_path, db, clock, sink)
    second.start()
    assert [b.name for b in second.board.blocking()] == [BreakerName.MAX_DRAWDOWN]
    assert second.watermarks.get("EURUSD", second.config.timeframes.entry) == mark
    second.shutdown()


def test_a_real_position_with_the_bots_magic_trips_account_change(tmp_path: Path) -> None:
    db, clock, sink = fresh_db(), ManualClock(START), MemorySink()
    engine = make_engine(tmp_path, db, clock, sink)
    fake = engine.bundle.fake
    assert fake is not None
    fake.add_position(
        ticket=99,
        symbol="EURUSD",
        type=0,
        volume=0.1,
        price_open=1.1,
        sl=0.0,
        tp=0.0,
        price_current=1.1,
        profit=0.0,
        swap=0.0,
        magic=7_310_003,
        comment="",
        time=int((START - timedelta(hours=1)).timestamp()),
    )
    engine.start()
    assert EventType.UNKNOWN_POSITION in [e.type for e in sink.events]
    assert any(b.name is BreakerName.ACCOUNT_CHANGE for b in engine.board.blocking())
    engine.shutdown()
