from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import ExecutionConfig
from app.core.ids import new_id
from app.engine.order_manager import IntentState
from app.engine.reconciler import Reconciler
from app.monitoring.alerts import EventBus, EventType
from app.risk.circuit_breaker import BreakerName
from app.storage.database import Database
from app.storage.models import OrderIntentRow
from tests.unit.test_order_manager import WED, Rig, execute, make_rig, record

MAGIC = 7_310_000


@pytest.fixture
def rig(tmp_path: Path, db: Database) -> Rig:
    return make_rig(tmp_path, db)


def reconciler(rig: Rig) -> Reconciler:
    return Reconciler(
        rig.db,
        rig.om,
        rig.bundle.gateway,
        rig.om.monitor,
        rig.clock,
        ExecutionConfig(),
        {"EURUSD": rig.bundle.gateway.symbol_spec("EURUSD")},
        magic_base=MAGIC,
        bus=EventBus(rig.clock, [rig.sink], dedupe_seconds=0),
    )


def state(rig: Rig) -> list[str]:
    return [r.state for r in rig.intents()]


class TestUnknown:
    def test_an_executed_order_is_found(self, rig: Rig) -> None:
        rig.fake.desk.force(None, executes=True)
        [out] = execute(rig)
        assert out.state is IntentState.UNKNOWN
        report = reconciler(rig).run()
        assert report.reconciled == [out.intent_id]
        [row] = rig.intents()
        assert row.state == "PROTECTED" and row.position_ticket == rig.bundle.gateway.positions()[0].ticket
        assert EventType.ORDER_RECONCILED in rig.events()
        assert BreakerName.DUPLICATE_EXECUTION in rig.blocking()  # stays until an operator resets it

    def test_an_order_closed_since_is_found_in_the_deals(self, rig: Rig) -> None:
        rig.fake.desk.force(None, executes=True)
        execute(rig)
        rig.fake.positions[0].sl = 2.0  # stopped out before the reconciler looked
        assert rig.bundle.gateway.positions() == []
        report = reconciler(rig).run()
        assert len(report.reconciled) == 1
        assert state(rig) == ["PROTECTED"]

    def test_a_lost_order_becomes_not_executed_after_the_wait(self, rig: Rig) -> None:
        rig.fake.desk.force(None)
        execute(rig)
        assert reconciler(rig).run().still_unknown
        assert state(rig) == ["UNKNOWN"]
        rig.clock.advance(31)
        assert reconciler(rig).run().not_executed
        assert state(rig) == ["NOT_EXECUTED"]


class TestInterrupted:
    def insert(self, rig: Rig, state_: IntentState) -> str:
        intent_id = new_id()
        with rig.db.session() as sess:
            sess.add(
                OrderIntentRow(
                    intent_id=intent_id,
                    idempotency_key=f"k-{intent_id}",
                    decision_id="d",
                    signal_id="s",
                    strategy="x",
                    symbol="EURUSD",
                    side="BUY",
                    volume=0.1,
                    price_requested=1.1,
                    sl=1.09,
                    tp=None,
                    magic=MAGIC,
                    comment="taa:none00000000",
                    risk_money=10.0,
                    state=state_.value,
                    attempts=1,
                    expires_at=WED + timedelta(hours=1),
                    sent_at=WED if state_ is IntentState.SENDING else None,
                    created_at=WED,
                    updated_at=WED,
                )
            )
        return intent_id

    def test_never_sent_is_not_executed(self, rig: Rig) -> None:
        self.insert(rig, IntentState.PRECHECKED)
        assert reconciler(rig).run().not_executed
        assert state(rig) == ["NOT_EXECUTED"]

    def test_interrupted_while_sending_is_unknown_first(self, rig: Rig) -> None:
        self.insert(rig, IntentState.SENDING)
        report = reconciler(rig).run()
        assert report.still_unknown and state(rig) == ["UNKNOWN"]
        assert BreakerName.DUPLICATE_EXECUTION in rig.blocking()
        rig.clock.advance(60)
        reconciler(rig).run()
        assert state(rig) == ["NOT_EXECUTED"]


class TestSweep:
    def test_a_missing_stop_is_reattached(self, rig: Rig) -> None:
        execute(rig)
        rig.fake.positions[0].sl = 0.0
        report = reconciler(rig).run()
        assert report.reattached == [rig.fake.positions[0].ticket]
        assert rig.bundle.gateway.positions()[0].sl > 0

    def test_a_stop_that_cannot_be_attached_closes_the_position(self, rig: Rig) -> None:
        execute(rig)
        rig.fake.positions[0].sl = 0.0
        for _ in range(3):
            rig.fake.desk.force(10016)
        report = reconciler(rig).run()
        assert report.closed_unprotected and rig.bundle.gateway.positions() == []
        assert BreakerName.UNPROTECTED_POSITION in rig.blocking()

    def test_a_stray_bot_position_trips_account_change(self, rig: Rig) -> None:
        execute(rig)
        rig.fake.positions[0].comment = "manual"
        with rig.db.session() as sess:
            for row in sess.execute(select(OrderIntentRow)).scalars():
                row.position_ticket = None
        report = reconciler(rig).run()
        assert report.strays and EventType.UNKNOWN_POSITION in rig.events()
        assert BreakerName.ACCOUNT_CHANGE in rig.blocking()

    def test_manual_positions_are_left_alone(self, rig: Rig) -> None:
        execute(rig)
        rig.fake.positions[0].magic = 0
        rig.fake.positions[0].sl = 0.0
        assert reconciler(rig).run().clean
        assert rig.bundle.gateway.positions()[0].sl == 0.0


def test_clean_account_reports_clean(rig: Rig) -> None:
    execute(rig, record(rig))
    assert reconciler(rig).run().clean
