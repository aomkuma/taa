from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.broker import mt5_constants as c
from app.broker.execution import ExecutionGateway
from app.broker.factory import BrokerBundle, build_trading
from app.config import BreakerConfig, ExecutionConfig, RiskConfig
from app.core.clock import ManualClock
from app.core.enums import Action, Side, Timeframe, TradingMode
from app.engine.decision_engine import Decision, DecisionRecord, Profile
from app.engine.order_manager import IllegalTransition, IntentState, OrderManager
from app.monitoring.alerts import EventBus, EventType, MemorySink
from app.risk.breaker_monitor import BreakerMonitor
from app.risk.circuit_breaker import BreakerBoard, BreakerName, default_specs
from app.risk.kill_switch import KillSwitch
from app.risk.position_sizer import PositionSizer, SizedPart
from app.storage.database import Database
from app.storage.models import OrderIntentRow
from tests.unit.test_execution_gateway import settings
from tests.unit.test_strategy_models import make_context, make_signal

WED = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)


@dataclasses.dataclass
class Rig:
    bundle: BrokerBundle
    om: OrderManager
    board: BreakerBoard
    kill: KillSwitch
    sink: MemorySink
    db: Database
    clock: ManualClock
    problems: list[str]

    @property
    def fake(self):  # type: ignore[no-untyped-def]
        assert self.bundle.fake is not None
        return self.bundle.fake

    def sends(self) -> int:
        return int(self.fake.calls["order_send"])

    def intents(self) -> list[OrderIntentRow]:
        with self.db.session() as sess:
            rows = sess.execute(select(OrderIntentRow).order_by(OrderIntentRow.created_at)).scalars().all()
            sess.expunge_all()
            return list(rows)

    def blocking(self) -> set[BreakerName]:
        return {b.name for b in self.board.blocking("EURUSD")}

    def events(self) -> list[EventType]:
        return [e.type for e in self.sink.events]


@pytest.fixture
def rig(tmp_path: Path, db: Database) -> Rig:
    clock = ManualClock(WED)
    bundle = build_trading(settings(), fake=True, clock=clock)
    bundle.client.connect()
    board = BreakerBoard(
        db,
        default_specs(BreakerConfig(), consecutive_pause_hours=24),
        clock,
        mode=TradingMode.DEMO,
        tz_name="Europe/Athens",
    )
    monitor = BreakerMonitor(board, BreakerConfig(), RiskConfig(), clock)
    kill = KillSwitch(tmp_path / "KILL", db, None, clock)
    sink = MemorySink()
    problems: list[str] = []
    om = OrderManager(
        db,
        ExecutionGateway(bundle.client),
        bundle.gateway,
        monitor,
        kill,
        clock,
        ExecutionConfig(),
        deviation_points=10,
        presend=lambda *_: list(problems),
        bus=EventBus(clock, [sink], dedupe_seconds=0),
    )
    return Rig(bundle, om, board, kill, sink, db, clock, problems)


def record(
    rig: Rig, side: Side = Side.BUY, risk_override: float | None = None, key_bar: int = 0
) -> DecisionRecord:
    spec = rig.bundle.gateway.symbol_spec("EURUSD")
    tick = rig.bundle.gateway.tick("EURUSD")
    assert tick is not None
    entry = tick.ask if side is Side.BUY else tick.bid
    sl = entry - side.sign * 0.0020
    tp = entry + side.sign * 0.0040
    bar = datetime(2026, 9, 30, 9, 45, tzinfo=UTC) + timedelta(minutes=15 * key_bar)
    signal = make_signal(
        evidence=(),
        action=Action.BUY if side is Side.BUY else Action.SELL,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        data_timestamp_utc=bar,
        created_at_utc=bar,
        expires_at_utc=bar + timedelta(hours=1),
        bar_times=((Timeframe.M15, bar),),
    )
    account = rig.bundle.gateway.account()
    from app.risk.position_sizer import AccountFunds

    funds = AccountFunds(account.equity, account.balance, account.margin, account.margin_free)
    sizing = PositionSizer(RiskConfig(), rig.bundle.gateway).size(spec, side, entry, sl, funds, lot_limit=1.0)
    assert sizing.ok, sizing.detail
    if risk_override is not None:
        part = sizing.parts[0]
        tiny = SizedPart(
            part.part, part.volume, part.taps, Decimal(str(risk_override)) / part.volume, Decimal(0)
        )
        sizing = dataclasses.replace(sizing, parts=(tiny,))
    return DecisionRecord(
        decision_id="dec-1",
        created_at=WED,
        profile=Profile.EXECUTION,
        decision=Decision.ACCEPT,
        signal=signal,
        market=make_context(),
        checks=(),
        sizing=sizing,
        config_hash="h",
        code_version="t",
    )


def execute(rig: Rig, rec: DecisionRecord | None = None):  # type: ignore[no-untyped-def]
    rec = rec or record(rig)
    return rig.om.execute(rec, rig.bundle.gateway.symbol_spec("EURUSD"), magic=7_310_000)


class TestHappyPath:
    def test_filled_and_protected(self, rig: Rig) -> None:
        [out] = execute(rig)
        assert out.state is IntentState.PROTECTED and out.retcode == 10009 and out.position_ticket
        [row] = rig.intents()
        assert (row.state, row.attempts, row.retcode) == ("PROTECTED", 1, 10009)
        assert (
            row.comment.startswith("taa:") and row.fill_price and row.position_ticket == out.position_ticket
        )
        [pos] = rig.bundle.gateway.positions()
        assert pos.sl == pytest.approx(row.sl) and pos.magic == 7_310_000 and pos.comment == row.comment
        assert EventType.POSITION_OPENED in rig.events()
        assert rig.fake.calls["order_check"] == 1 and rig.sends() == 1

    def test_same_decision_is_never_sent_twice(self, rig: Rig) -> None:
        rec = record(rig)
        execute(rig, rec)
        again = execute(rig, rec)
        assert again[0].detail == "duplicate"
        assert rig.sends() == 1
        assert BreakerName.DUPLICATE_EXECUTION in rig.blocking()

    def test_rejected_decisions_send_nothing(self, rig: Rig) -> None:
        rec = dataclasses.replace(record(rig), decision=Decision.REJECT)
        assert execute(rig, rec) == [] and rig.sends() == 0


class TestBeforeSending:
    def test_pre_send_recheck_blocks(self, rig: Rig) -> None:
        rig.problems.append("kill switch active")
        [out] = execute(rig)
        assert out.state is IntentState.NOT_EXECUTED and rig.sends() == 0
        assert "kill switch" in rig.intents()[0].detail

    def test_order_check_failure_rejects(self, rig: Rig) -> None:
        # replace, don't mutate: FakeSymbol objects are shared by every FakeMT5 instance
        rig.fake.symbols["EURUSD"] = dataclasses.replace(
            rig.fake.symbols["EURUSD"], trade_mode=c.SYMBOL_TRADE_MODE_CLOSEONLY
        )
        [out] = execute(rig)
        assert out.state is IntentState.REJECTED and out.retcode == 10044 and rig.sends() == 0


class TestRetcodes:
    def test_one_requote_then_fill(self, rig: Rig) -> None:
        rig.fake.desk.force(10004)
        [out] = execute(rig)
        assert out.state is IntentState.PROTECTED
        assert rig.intents()[0].attempts == 2 and rig.sends() == 2

    def test_requotes_exhausted(self, rig: Rig) -> None:
        rig.fake.desk.force(10004)
        rig.fake.desk.force(10020)
        [out] = execute(rig)
        assert out.state is IntentState.REJECTED and rig.sends() == 2
        assert rig.bundle.gateway.positions() == []

    def test_unknown_outcome_stops_everything(self, rig: Rig) -> None:
        rig.fake.desk.force(None)
        [out] = execute(rig)
        assert out.state is IntentState.UNKNOWN
        assert BreakerName.DUPLICATE_EXECUTION in rig.blocking()
        assert EventType.ORDER_UNKNOWN in rig.events()

    @pytest.mark.parametrize(
        ("code", "effect"),
        [
            (10016, None),
            (10018, BreakerName.SYMBOL_RESTRICTED),
            (10024, BreakerName.ORDER_FAILURES),
        ],
    )
    def test_rejections(self, rig: Rig, code: int, effect: BreakerName | None) -> None:
        rig.fake.desk.force(code)
        [out] = execute(rig)
        assert out.state is IntentState.REJECTED and out.retcode == code
        if effect is not None:
            assert effect in rig.blocking()

    @pytest.mark.parametrize("code", [10019, 10027, 10046])
    def test_halting_codes_activate_the_kill_switch(self, rig: Rig, code: int) -> None:
        rig.fake.desk.force(code)
        execute(rig)
        assert rig.kill.is_active()

    def test_repeated_failures_trip_order_failures(self, rig: Rig) -> None:
        for i in range(3):
            rig.fake.desk.force(10016)
            execute(rig, record(rig, key_bar=i))
        assert BreakerName.ORDER_FAILURES in rig.blocking()

    def test_illegal_transitions_raise(self, rig: Rig) -> None:
        execute(rig)
        with pytest.raises(IllegalTransition):
            rig.om._transition(rig.intents()[0].intent_id, IntentState.SENDING)


class TestPostFillGuard:
    def strip_stops(self, rig: Rig, *, then_fail: int = 0) -> None:
        """The entry fills without its stop; optionally the next *then_fail* sends (the re-attach) fail."""
        desk = rig.fake.desk
        original: Callable[[dict[str, Any]], Any] = desk._execute

        def execute_without_sl(request: dict[str, Any]) -> Any:
            result = original(request)
            is_entry = request.get("action") == c.TRADE_ACTION_DEAL and not request.get("position")
            if is_entry:
                for p in rig.fake.positions:
                    p.sl = 0.0
                for _ in range(then_fail):
                    desk.force(10016)
            return result

        desk._execute = execute_without_sl

    def test_missing_stop_is_reattached(self, rig: Rig) -> None:
        self.strip_stops(rig)
        [out] = execute(rig)
        assert out.state is IntentState.PROTECTED
        assert rig.bundle.gateway.positions()[0].sl > 0

    def test_unattachable_stop_closes_the_position(self, rig: Rig) -> None:
        self.strip_stops(rig, then_fail=3)  # every re-attach attempt is refused
        [out] = execute(rig)
        assert out.state is IntentState.EMERGENCY_CLOSED
        assert rig.bundle.gateway.positions() == []
        assert BreakerName.UNPROTECTED_POSITION in rig.blocking()
        assert EventType.POSITION_UNPROTECTED in rig.events()

    def test_fill_risk_above_plan_is_reduced(self, rig: Rig) -> None:
        rec = record(rig, risk_override=10.0)  # the plan says $10 at the stop; the fill risks ~$50
        [out] = execute(rig, rec)
        assert out.state is IntentState.PROTECTED
        [pos] = rig.bundle.gateway.positions()
        assert pos.volume < float(rec.sizing.parts[0].volume)  # type: ignore[union-attr]
        assert pos.volume == pytest.approx(0.04, abs=0.011)
