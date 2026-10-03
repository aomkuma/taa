"""The PAPER engine end to end on FakeMT5 with a simulated clock (no terminal, no network)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.broker.factory import build_read_only
from app.config import Settings, load_settings
from app.core.clock import ManualClock
from app.core.enums import Action, Timeframe, TradingMode
from app.core.errors import SafetyViolation
from app.engine.orchestrator import Engine
from app.main import main
from app.monitoring.alerts import EventBus, EventType, MemorySink
from app.risk.circuit_breaker import BreakerName
from app.storage.database import Database
from app.storage.models import PaperPositionRow, Run
from app.strategy.base_strategy import BaseStrategy
from app.strategy.registry import StrategySet
from app.strategy.signal_models import Condition, Signal, StrategyContext

START = datetime(2026, 9, 30, 9, 50, tzinfo=UTC)  # Wednesday, London session


class BuyEveryBar(BaseStrategy):
    """Test strategy: a geometrically sane BUY on every bar (2 ATR stop, 4 ATR target)."""

    name = "buy_every_bar"

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return ()

    def warmup_bars(self) -> int:
        return 1

    def evaluate(self, ctx: StrategyContext) -> Signal:
        atr = ctx.market.atr
        if atr is None:
            return self.hold(ctx)
        ask = ctx.market.ask or ctx.market.entry.close
        return self.entry(
            ctx,
            Action.BUY,
            entry_price=ask,
            stop_loss=ask - 2 * atr,
            take_profit=ask + 4 * atr,
            conditions=[Condition("always", True)],
            score=50.0,
        )


def settings(tmp_path: Path, **config: object) -> Settings:
    env = {
        "TRADING_MODE": "PAPER",
        "MT5_LOGIN": "12345678",
        "MT5_PASSWORD": "investor-pass",
        "MT5_SERVER": "FBS-Demo",
        "MT5_TERMINAL_PATH": "x",
        "KILL_SWITCH_FILE": str(tmp_path / "KILL_SWITCH"),
    }
    s = load_settings(env_file=None, config_file="config.yaml", environ=env)
    cfg = s.config.model_copy(
        update={
            "symbols": s.config.symbols.model_copy(update={"allowed": ["EURUSD"]}),
            "evidence": s.config.evidence.model_copy(update={"default_enabled": False}),
            "engine": s.config.engine.model_copy(update={"heartbeat_file": str(tmp_path / "heartbeat.json")}),
            # trading tests: the opportunity scanner has its own tests (tests/integration/test_scanner.py)
            "advisory": s.config.advisory.model_copy(
                update={"scanner": s.config.advisory.scanner.model_copy(update={"enabled": False})}
            ),
            **config,
        }
    )
    return dataclasses.replace(s, config=cfg)


@dataclasses.dataclass
class Harness:
    engine: Engine
    clock: ManualClock
    sink: MemorySink
    db: Database

    def types(self) -> list[EventType]:
        return [e.type for e in self.sink.events]


def harness(tmp_path: Path, step_seconds: float = 30.0, **config: object) -> Harness:
    s = settings(tmp_path, **config)
    clock = ManualClock(START)
    db = Database("sqlite://")
    db.create_all()
    sink = MemorySink()
    engine = Engine(
        s,
        build_read_only(s, fake=True, clock=clock),
        db,
        clock,
        bus=EventBus(clock, [sink], dedupe_seconds=0),
        sleep=lambda _: clock.advance(step_seconds),
    )
    return Harness(engine, clock, sink, db)


class TestLifecycle:
    def test_start_run_stop(self, tmp_path: Path) -> None:
        h = harness(tmp_path)
        h.engine.start()
        h.engine.run(max_cycles=40)  # 20 simulated minutes: at least one new M15 bar
        assert h.types()[0] is EventType.ENGINE_STARTED and h.types()[-1] is EventType.ENGINE_STOPPED
        assert h.engine.last_error == ""
        assert h.engine.watermarks.get("EURUSD", Timeframe.M15) is not None
        assert not h.engine.bundle.client.connected
        with h.db.session() as sess:
            assert sess.execute(select(Run.status)).scalar_one() == "STOPPED"
        status = h.engine.status()
        assert status["clock_verified"] and status["cycles"] == 40

    @pytest.mark.parametrize(
        ("mode", "match"),
        [(TradingMode.DEMO, "ENABLE_DEMO_TRADING"), (TradingMode.LIVE, "LIVE waits")],
    )
    def test_modes_other_than_paper_need_their_gates(
        self, tmp_path: Path, mode: TradingMode, match: str
    ) -> None:
        s = settings(tmp_path)
        other = dataclasses.replace(s, env=s.env.model_copy(update={"TRADING_MODE": mode}))
        with pytest.raises(SafetyViolation, match=match):
            Engine(
                other,
                build_read_only(s, fake=True),
                Database("sqlite://"),
                ManualClock(START),
                bus=EventBus(ManualClock(START)),
            )


class TestTrading:
    def test_accepted_signal_becomes_a_paper_position(self, tmp_path: Path) -> None:
        h = harness(tmp_path)
        h.engine.start()
        strategy = BuyEveryBar()
        h.engine.strategies = StrategySet((strategy,))
        h.engine.magic = {strategy.name: 7_310_000}
        h.engine.run(max_cycles=40)
        assert EventType.SIGNAL_ACCEPTED in h.types(), [e.params for e in h.sink.events]
        assert EventType.POSITION_OPENED in h.types()
        with h.db.session() as sess:
            rows = sess.execute(select(PaperPositionRow)).scalars().all()
        assert rows and all(r.sl is not None and r.sl < r.entry_price for r in rows)

    def test_kill_switch_blocks_entries(self, tmp_path: Path) -> None:
        h = harness(tmp_path)
        h.engine.start()
        h.engine.kill_switch.activate("test", "pytest", "cli")
        strategy = BuyEveryBar()
        h.engine.strategies = StrategySet((strategy,))
        h.engine.magic = {strategy.name: 7_310_000}
        h.engine.run(max_cycles=40)
        assert EventType.KILL_SWITCH_ACTIVATED in h.types()
        assert EventType.POSITION_OPENED not in h.types()


class TestResilience:
    def test_a_failing_cycle_blocks_entries_but_the_loop_continues(self, tmp_path: Path) -> None:
        h = harness(tmp_path)
        h.engine.start()
        calls = {"n": 0}
        real = h.engine.quotes.quote

        def flaky(spec):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("terminal hiccup")
            return real(spec)

        h.engine.quotes.quote = flaky  # type: ignore[method-assign]
        h.engine.run(max_cycles=5)
        assert h.engine.cycles == 5
        assert "RuntimeError" in h.engine.last_error
        assert EventType.ENGINE_ERROR in h.types()
        assert any(b.name is BreakerName.UNHANDLED_EXCEPTION for b in h.engine.board.blocking())

    def test_connection_loss_and_recovery(self, tmp_path: Path) -> None:
        h = harness(tmp_path, step_seconds=10.0)
        h.engine.start()
        fake = h.engine.bundle.fake
        assert fake is not None
        fake.disconnect()
        h.engine.running = True
        for _ in range(3):
            h.engine.cycle()
            h.clock.advance(10)
        assert EventType.CONNECTION_LOST in h.types()
        assert any(b.name is BreakerName.CONNECTION for b in h.engine.board.blocking())
        fake.reconnect()
        for _ in range(70):  # reconnect backoff, then three healthy checks
            h.engine.cycle()
            h.clock.advance(10)
        assert EventType.CONNECTION_RESTORED in h.types()
        assert not any(b.name is BreakerName.CONNECTION for b in h.engine.board.blocking())


def test_main_refuses_a_mode_mismatch(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "TRADING_MODE=PAPER\nMT5_LOGIN=12345678\nMT5_PASSWORD=investor-pass\nMT5_SERVER=FBS-Demo\n"
        "MT5_TERMINAL_PATH=x\n",
        encoding="utf-8",
    )
    assert main(["--mode", "live", "--env-file", str(env)]) == 2
