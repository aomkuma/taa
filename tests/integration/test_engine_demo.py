"""The DEMO engine end to end on FakeMT5: broker orders on the demo account, reconciliation, flatten."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from sqlalchemy import select

from app.broker import mt5_constants as c
from app.broker.factory import build_trading
from app.config import Settings, load_settings
from app.core.clock import ManualClock
from app.engine.backends import DemoBackend
from app.engine.orchestrator import Engine
from app.monitoring.alerts import EventBus, EventType, MemorySink
from app.risk.kill_switch import KillMode
from app.storage.database import Database
from app.storage.models import OrderIntentRow
from app.strategy.registry import StrategySet
from tests.integration.test_engine_paper import START, BuyEveryBar

MAGIC = 7_310_000


def demo_settings(tmp_path: Path, **env: str) -> Settings:
    base = {
        "TRADING_MODE": "DEMO",
        "ENABLE_DEMO_TRADING": "true",
        "MT5_LOGIN": "12345678",
        "MT5_PASSWORD": "master-pass",
        "MT5_SERVER": "FBS-Demo",
        "MT5_TERMINAL_PATH": "x",
        "KILL_SWITCH_FILE": str(tmp_path / "KILL_SWITCH"),
        "KILL_SWITCH_FLATTEN_ALLOWED": "true",
    }
    base.update(env)
    s = load_settings(env_file=None, config_file="config.yaml", environ=base)
    cfg = s.config.model_copy(
        update={
            "symbols": s.config.symbols.model_copy(update={"allowed": ["EURUSD"]}),
            "evidence": s.config.evidence.model_copy(update={"default_enabled": False}),
            "engine": s.config.engine.model_copy(update={"heartbeat_file": str(tmp_path / "heartbeat.json")}),
            # trading tests: the opportunity scanner has its own tests (tests/integration/test_scanner.py)
            "advisory": s.config.advisory.model_copy(
                update={"scanner": s.config.advisory.scanner.model_copy(update={"enabled": False})}
            ),
        }
    )
    return dataclasses.replace(s, config=cfg)


@dataclasses.dataclass
class Demo:
    engine: Engine
    clock: ManualClock
    sink: MemorySink
    db: Database

    def types(self) -> list[EventType]:
        return [e.type for e in self.sink.events]

    def intents(self) -> list[str]:
        with self.db.session() as sess:
            return list(sess.execute(select(OrderIntentRow.state)).scalars())


def demo(tmp_path: Path, db: Database | None = None, clock: ManualClock | None = None) -> Demo:
    s = demo_settings(tmp_path)
    clock = clock or ManualClock(START)
    if db is None:
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


def start_buyer(d: Demo) -> None:
    d.engine.start()
    strategy = BuyEveryBar()
    d.engine.strategies = StrategySet((strategy,))
    d.engine.magic = {strategy.name: MAGIC}


def run_until(d: Demo, event: EventType, limit: int = 80) -> None:
    for _ in range(limit):
        d.engine.cycle()
        if event in d.types():
            return
        d.clock.advance(30)
    raise AssertionError(f"{event} never happened; events: {d.types()}")


def test_demo_sends_a_protected_broker_order(tmp_path: Path) -> None:
    d = demo(tmp_path)
    start_buyer(d)
    assert isinstance(d.engine.backend, DemoBackend)
    assert d.engine.gate() is not None and d.engine.gate().passed  # type: ignore[union-attr]
    run_until(d, EventType.POSITION_OPENED)
    positions = d.engine.gateway.positions()
    assert len(positions) == 1
    assert positions[0].magic == MAGIC and positions[0].sl > 0
    assert d.intents() == ["PROTECTED"]
    assert d.engine.bundle.fake is not None and d.engine.bundle.fake.calls["order_send"] >= 1
    d.engine.shutdown()


def test_restart_does_not_resend_and_does_not_flag_own_positions(tmp_path: Path) -> None:
    db = Database("sqlite://")
    db.create_all()
    clock = ManualClock(START)
    first = demo(tmp_path, db, clock)
    start_buyer(first)
    run_until(first, EventType.POSITION_OPENED)
    fake = first.engine.bundle.fake
    first.engine.shutdown()
    # the same broker account after a restart (a new FakeMT5 would forget the position)
    second = demo(tmp_path, db, clock)
    second.engine.bundle.client._mt5 = fake
    second.engine.bundle.fake = fake
    start_buyer(second)
    assert EventType.UNKNOWN_POSITION not in second.types()  # our own position, matched to its intent
    for _ in range(3):
        second.engine.cycle()
        second.clock.advance(1)
    assert second.intents() == ["PROTECTED"]
    assert len(second.engine.gateway.positions()) == 1
    second.engine.shutdown()


def test_kill_switch_flatten_closes_bot_positions(tmp_path: Path) -> None:
    d = demo(tmp_path)
    start_buyer(d)
    run_until(d, EventType.POSITION_OPENED)
    d.engine.kill_switch.activate("drill", "pytest", "cli", KillMode.FLATTEN)
    d.clock.advance(10)
    d.engine.cycle()  # health interval due: maintenance flattens
    assert d.engine.gateway.positions() == []
    assert EventType.POSITION_CLOSED in d.types()
    deals = d.engine.bundle.fake.deals if d.engine.bundle.fake else []
    assert any(x.entry == c.DEAL_ENTRY_OUT for x in deals)
    d.engine.shutdown()


def test_no_entries_while_the_kill_switch_halts(tmp_path: Path) -> None:
    d = demo(tmp_path)
    start_buyer(d)
    d.engine.kill_switch.activate("halt", "pytest", "cli")
    for _ in range(40):
        d.engine.cycle()
        d.clock.advance(30)
    assert d.engine.gateway.positions() == []
    assert d.engine.bundle.fake is not None and d.engine.bundle.fake.calls["order_send"] == 0
    d.engine.shutdown()
