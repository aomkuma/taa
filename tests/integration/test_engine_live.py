"""LIVE behind its gate, on FakeMT5 with a REAL account (PLAN §A3; TAA-1401). A fake account moves no money."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from sqlalchemy import select

from app.broker.factory import build_trading
from app.core.clock import ManualClock
from app.engine.backends import DemoBackend
from app.engine.orchestrator import Engine
from app.monitoring.alerts import EventBus, EventType, MemorySink
from app.risk.mode_gates import GateCondition
from app.storage.database import Database
from app.storage.models import AuditEvent, DecisionRecordRow, OrderIntentRow
from tests.integration.test_engine_demo import Demo, demo_settings, run_until, start_buyer
from tests.integration.test_engine_paper import START

PHRASE = "I-ACCEPT-LIVE-RISK-12345678"


def live(tmp_path: Path, **risk: object) -> Demo:
    s = demo_settings(
        tmp_path,
        TRADING_MODE="LIVE",
        ENABLE_DEMO_TRADING="false",
        ENABLE_LIVE_TRADING="true",
        LIVE_TRADING_CONFIRMATION=PHRASE,
        MT5_SERVER="FBS-Real",
    )
    if risk:
        s = dataclasses.replace(
            s, config=s.config.model_copy(update={"risk": s.config.risk.model_copy(update=risk)})
        )
    clock = ManualClock(START)
    db = Database("sqlite://")
    db.create_all()
    sink = MemorySink()
    engine = Engine(
        s,
        build_trading(s, fake=True, clock=clock),
        db,
        clock,
        bus=EventBus(clock, [sink], dedupe_seconds=0),
        sleep=clock.advance,
    )
    return Demo(engine, clock, sink, db)


def test_live_passes_its_gate_starts_on_probation_and_sends_protected_orders(tmp_path: Path) -> None:
    d = live(tmp_path)
    start_buyer(d)
    assert isinstance(d.engine.backend, DemoBackend) and d.engine.backend.name == "live"
    gate = d.engine.gate()
    assert gate is not None and gate.passed
    assert d.engine._probation()  # no LIVE trade yet: the first ones run at reduced risk
    with d.db.session() as sess:
        started = sess.scalars(select(AuditEvent).where(AuditEvent.event_type == "LIVE_START")).one()
    assert started.payload["probation"] is True and started.payload["server"] == "FBS-Real"
    run_until(d, EventType.POSITION_OPENED)
    with d.db.session() as sess:
        intent = sess.scalars(select(OrderIntentRow)).one()
        accepted = sess.scalars(
            select(DecisionRecordRow).where(DecisionRecordRow.decision == "ACCEPT")
        ).first()
    assert intent.state == "PROTECTED" and intent.sl > 0
    equity = d.engine.backend.equity()
    budget = equity * d.engine.config.risk.max_risk_per_trade_percent / 100
    multiplier = d.engine.config.risk.probation_multiplier
    assert accepted is not None and accepted.risk_money is not None
    assert accepted.risk_money <= budget * multiplier + 1e-6  # probation sized the order down
    d.engine.shutdown()


def test_probation_ends_after_the_configured_trades(tmp_path: Path) -> None:
    d = live(tmp_path, probation_trades=0)
    start_buyer(d)
    assert not d.engine._probation()
    d.engine.shutdown()


def test_the_gate_refuses_orders_while_the_kill_switch_is_on(tmp_path: Path) -> None:
    d = live(tmp_path)
    start_buyer(d)
    d.engine.kill_switch.activate("drill", actor="test", source="cli")
    gate = d.engine.gate()
    assert gate is not None and GateCondition.KILL_SWITCH in gate.failed_conditions
    d.engine.shutdown()
