"""Entry plans on the broker account: market part first, limit parts after, the plan supervisor (TAA-1207)."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from pathlib import Path

import pytest

from app.broker import mt5_constants as c
from app.config import ExecutionConfig, RiskConfig
from app.core.enums import EntryType, Side
from app.engine.decision_engine import DecisionRecord
from app.engine.order_manager import IntentState
from app.engine.plan_supervisor import PlanSupervisor
from app.risk.circuit_breaker import BreakerName
from app.risk.kill_switch import KillMode
from app.risk.position_sizer import AccountFunds, PositionSizer, SplitMode, build_parts
from app.storage.database import Database
from tests.unit.test_order_manager import WED, Rig, execute, make_rig, record
from tests.unit.test_reconciler import reconciler

S = IntentState
MAGIC = 7_310_000
ATR = 0.0010  # 10 pips: limits 5, 10, 15 pips below a BUY's market part, the stop 20 pips below


@pytest.fixture
def rig(tmp_path: Path, db: Database) -> Rig:
    return make_rig(tmp_path, db)


def plan_record(rig: Rig, parts: int = 4, side: Side = Side.BUY) -> DecisionRecord:
    """A SCALE_IN plan: one market part and up to *parts* - 1 limit parts toward the stop."""
    base = record(rig, side)
    s = base.signal
    assert s.entry_price is not None and s.stop_loss is not None
    spec = rig.bundle.gateway.symbol_spec("EURUSD")
    account = rig.bundle.gateway.account()
    funds = AccountFunds(account.equity, account.balance, account.margin, account.margin_free)
    plan = build_parts(
        SplitMode.SCALE_IN, side, s.entry_price, s.stop_loss, s.take_profit, k=parts, atr=ATR, spacing_atr=0.5
    )
    sizing = PositionSizer(RiskConfig(), rig.bundle.gateway).size_plan(
        spec, side, plan, s.stop_loss, funds, lot_limit=5.0, lot_unit=0.01
    )
    assert sizing.ok and len(sizing.parts) == parts, sizing.detail
    return dataclasses.replace(base, sizing=sizing)


def supervisor(rig: Rig) -> PlanSupervisor:
    return PlanSupervisor(
        rig.om, rig.kill, rig.clock, ExecutionConfig(), {"EURUSD": rig.bundle.gateway.symbol_spec("EURUSD")}
    )


def pin(rig: Rig) -> float:
    """Hold the bid where it is (the fake's random walk would fill the limits over hours)."""
    tick = rig.bundle.gateway.tick("EURUSD")
    assert tick is not None
    rig.fake.price_override["EURUSD"] = tick.bid
    return tick.bid


def states(rig: Rig) -> list[str]:
    return [r.state for r in sorted(rig.intents(), key=lambda r: r.part_index)]


class TestSending:
    def test_market_part_first_then_the_limits(self, rig: Rig) -> None:
        rec = plan_record(rig)
        outcomes = execute(rig, rec)
        assert [o.state for o in outcomes] == [S.PROTECTED, S.PLACED, S.PLACED, S.PLACED]
        rows = sorted(rig.intents(), key=lambda r: r.part_index)
        assert {r.plan_key for r in rows} == {rec.signal.idempotency_key}
        assert [r.order_type for r in rows] == ["MARKET", "LIMIT", "LIMIT", "LIMIT"]
        assert all(r.cancel_after == WED + timedelta(hours=4) for r in rows[1:])
        orders = rig.bundle.gateway.orders()
        assert sorted(o.ticket for o in orders) == sorted(r.order_ticket for r in rows[1:])
        for row in rows[1:]:
            order = next(o for o in orders if o.ticket == row.order_ticket)
            assert (order.type, order.sl, order.tp, order.magic, order.comment) == (
                c.ORDER_TYPE_BUY_LIMIT,
                pytest.approx(row.sl),
                pytest.approx(row.tp),
                MAGIC,
                row.comment,
            )
            assert order.price_open == pytest.approx(row.limit_price)
            assert order.expiration_utc == WED + timedelta(hours=4, minutes=5)  # broker-side backstop
        levels = [r.limit_price for r in rows[1:]]
        assert levels == sorted(levels, reverse=True)

    def test_limits_wait_for_a_protected_market_part(self, rig: Rig) -> None:
        rig.problems.append("spread too wide")
        outcomes = execute(rig, plan_record(rig))
        assert [o.state for o in outcomes] == [S.NOT_EXECUTED]
        assert rig.bundle.gateway.orders() == [] and rig.bundle.gateway.positions() == []

    def test_an_unknown_market_part_stops_the_plan(self, rig: Rig) -> None:
        rig.fake.desk.force(None)
        outcomes = execute(rig, plan_record(rig))
        assert [o.state for o in outcomes] == [S.UNKNOWN]
        assert rig.bundle.gateway.orders() == []

    def test_a_level_the_market_already_passed_is_not_placed(self, rig: Rig) -> None:
        rec = plan_record(rig)
        first_limit = float(rec.sizing.parts[1].part.entry)  # type: ignore[union-attr]
        execute_at = first_limit - 0.00003  # the ask is now below the first limit's level
        rig.fake.price_override["EURUSD"] = execute_at - 0.00008
        outcomes = execute(rig, rec)
        assert outcomes[1].state is S.NOT_EXECUTED and "not away from the market" in outcomes[1].detail
        assert [o.state for o in outcomes[2:]] == [S.PLACED, S.PLACED]

    def test_filling_and_expiration_fall_back_through_order_check(self, rig: Rig) -> None:
        sym = rig.fake.symbols["EURUSD"]
        sym.pending_return_filling = False
        sym.pending_expiration = False
        execute(rig, plan_record(rig, parts=2))
        [order] = rig.fake.orders
        assert (order.type_filling, order.type_time) == (c.ORDER_FILLING_FOK, c.ORDER_TIME_GTC)

    def test_same_price_parts_send_their_own_targets(self, rig: Rig) -> None:
        base = record(rig)
        s = base.signal
        assert s.entry_price is not None and s.stop_loss is not None
        plan = build_parts(
            SplitMode.SAME_PRICE, Side.BUY, s.entry_price, s.stop_loss, s.take_profit, k=3, tp_r=(1.0, 1.5)
        )
        account = rig.bundle.gateway.account()
        funds = AccountFunds(account.equity, account.balance, account.margin, account.margin_free)
        sizing = PositionSizer(RiskConfig(), rig.bundle.gateway).size_plan(
            rig.bundle.gateway.symbol_spec("EURUSD"), Side.BUY, plan, s.stop_loss, funds, lot_limit=5.0
        )
        outcomes = execute(rig, dataclasses.replace(base, sizing=sizing))
        assert [o.state for o in outcomes] == [S.PROTECTED] * 3
        tps = sorted(p.tp for p in rig.bundle.gateway.positions())
        assert tps == pytest.approx([float(p.part.take_profit) for p in sizing.parts])  # type: ignore[arg-type]
        assert all(p.part.order_type is EntryType.MARKET for p in sizing.parts)


class TestSupervisor:
    def test_a_filled_limit_is_recorded_and_guarded(self, rig: Rig) -> None:
        execute(rig, plan_record(rig))
        first = sorted(rig.intents(), key=lambda r: r.part_index)[1]
        assert first.limit_price is not None
        rig.fake.price_override["EURUSD"] = first.limit_price - 0.0001  # the ask trades through it
        report = supervisor(rig).run()
        assert report.filled == [first.intent_id]
        row = next(r for r in rig.intents() if r.intent_id == first.intent_id)
        assert row.state == "PROTECTED" and row.position_ticket == first.order_ticket
        assert row.fill_price == pytest.approx(first.limit_price)

    def test_lifetime_over(self, rig: Rig) -> None:
        execute(rig, plan_record(rig))
        pin(rig)
        rig.clock.advance(4 * 3600)
        report = supervisor(rig).run()
        assert len(report.expired) == 3 and rig.bundle.gateway.orders() == []
        assert states(rig) == ["PROTECTED", "EXPIRED", "EXPIRED", "EXPIRED"]

    def test_kill_switch_cancels_resting_parts(self, rig: Rig) -> None:
        execute(rig, plan_record(rig))
        rig.kill.activate("test", "op", "cli", KillMode.HALT)
        supervisor(rig).run()
        assert states(rig) == ["PROTECTED", "CANCELLED", "CANCELLED", "CANCELLED"]
        assert rig.bundle.gateway.orders() == []

    def test_the_market_part_closing_cancels_the_rest(self, rig: Rig) -> None:
        execute(rig, plan_record(rig))
        bid = pin(rig)
        rig.fake.positions[0].tp = bid - 0.0001  # at its target now: the server closes it
        assert rig.bundle.gateway.positions() == []
        supervisor(rig).run()
        assert states(rig) == ["PROTECTED", "CANCELLED", "CANCELLED", "CANCELLED"]
        assert rig.bundle.gateway.orders() == []

    def test_an_order_removed_outside_the_engine(self, rig: Rig) -> None:
        execute(rig, plan_record(rig, parts=2))
        rig.fake.orders.clear()
        supervisor(rig).run()
        assert states(rig) == ["PROTECTED", "CANCELLED"]

    def test_quiet_when_nothing_rests(self, rig: Rig) -> None:
        execute(rig)
        before = rig.fake.calls["orders_get"]
        supervisor(rig).run()
        assert rig.fake.calls["orders_get"] == before


class TestReconciler:
    def test_an_unknown_limit_found_resting_is_placed(self, rig: Rig) -> None:
        rec = plan_record(rig, parts=2)
        rig.fake.desk.force(10009)  # the market part
        rig.fake.desk.force(None, executes=True)  # the limit went through but the answer was lost
        execute(rig, rec)
        assert states(rig)[1] == "UNKNOWN"
        report = reconciler(rig).run()
        assert report.placed and states(rig)[1] == "PLACED"
        row = sorted(rig.intents(), key=lambda r: r.part_index)[1]
        assert row.order_ticket == rig.bundle.gateway.orders()[0].ticket

    def test_a_stray_order_with_the_bot_magic(self, rig: Rig) -> None:
        bid, ask = rig.bundle.gateway.tick("EURUSD").bid, rig.bundle.gateway.tick("EURUSD").ask  # type: ignore[union-attr]
        from app.broker.execution import RequestBuilder

        request = RequestBuilder(10).limit_entry(
            rig.bundle.gateway.symbol_spec("EURUSD"),
            Side.BUY,
            0.01,
            ask - 0.001,
            bid - 0.003,
            None,
            magic=MAGIC,
            comment="someone",
            filling=c.ORDER_FILLING_RETURN,
            expiration_server=None,
        )
        assert rig.om.execution.send(request).ok
        report = reconciler(rig).run()
        assert report.stray_orders and BreakerName.ACCOUNT_CHANGE in rig.blocking()


class TestBreakEven:
    """SAME_PRICE: after one part closes at its target the rest go to break-even (TAA-1207)."""

    def same_price(self, rig: Rig) -> float:
        base = record(rig)
        s = base.signal
        assert s.entry_price is not None and s.stop_loss is not None
        plan = build_parts(
            SplitMode.SAME_PRICE, Side.BUY, s.entry_price, s.stop_loss, s.take_profit, k=3, tp_r=(1.0, 1.5)
        )
        account = rig.bundle.gateway.account()
        funds = AccountFunds(account.equity, account.balance, account.margin, account.margin_free)
        sizing = PositionSizer(RiskConfig(), rig.bundle.gateway).size_plan(
            rig.bundle.gateway.symbol_spec("EURUSD"), Side.BUY, plan, s.stop_loss, funds, lot_limit=5.0
        )
        execute(rig, dataclasses.replace(base, sizing=sizing))
        return min(p.price_open for p in rig.bundle.gateway.positions())

    def test_the_rest_move_to_break_even_once_a_part_closes(self, rig: Rig) -> None:
        from tests.unit.test_broker_positions import ATR as BP_ATR
        from tests.unit.test_broker_positions import manager, tick

        entry = self.same_price(rig)
        rig.fake.price_override["EURUSD"] = entry + 0.0006  # +0.3R: the A11 break-even (1R) is not due
        mgr = manager(rig)
        mgr.on_quote("EURUSD", *tick(rig), BP_ATR)
        assert all(p.sl < entry for p in rig.bundle.gateway.positions())  # all parts open: nothing moves
        first = min(rig.bundle.gateway.positions(), key=lambda p: p.tp)
        bid, _ = tick(rig)
        spec = rig.bundle.gateway.symbol_spec("EURUSD")
        assert rig.om.execution.send(rig.om.builder.close(spec, first, bid)).ok  # its target, in effect
        rig.clock.advance(60)
        mgr.on_quote("EURUSD", *tick(rig), BP_ATR)
        rest = rig.bundle.gateway.positions()
        assert len(rest) == 2
        assert all(p.sl == pytest.approx(p.price_open + 2 * spec.point) for p in rest)


def test_paper_parts_move_to_break_even_too(db: Database) -> None:
    from app.config import PositionManagementConfig
    from app.core.clock import ManualClock
    from app.engine.decision_engine import Decision
    from app.engine.position_manager import PositionManager
    from app.risk.limits import EntryPlanSpec, ProfileLimits
    from tests.unit.test_decision_engine import NOW, Setup, engine, request
    from tests.unit.test_paper_execution import paper

    spec = EntryPlanSpec(SplitMode.SAME_PRICE, 3, tp_r=(0.5, 1.0))
    on = Setup(config={"execution": {"entry_plans": True}})
    rec = engine(db, on).decide(request(profile_limits=ProfileLimits(entry_plan=spec)))
    assert rec.decision is Decision.ACCEPT and rec.sizing is not None
    clock = ManualClock(NOW)
    p = paper(db, clock)
    p.place(rec, magic=7_310_000)
    clock.advance(1)
    p.on_quote("EURUSD", 1.09992, 1.10000, clock.now_utc())  # all three parts fill at 1.10000
    assert len(p.broker.positions) == 3
    clock.advance(1)
    p.on_quote("EURUSD", 1.10105, 1.10113, clock.now_utc())  # through the first target (+0.5R = 1.1010)
    assert len(p.broker.positions) == 2
    from tests.strategy_data import EURUSD_SPEC

    pm = PositionManager(
        p, PositionManagementConfig(), {"EURUSD": EURUSD_SPEC}, clock, strategies_by_magic={}
    )
    pm.on_quote("EURUSD", 1.10060, 1.10068, None)
    assert all(
        pos.sl == pytest.approx(1.10000 + 2 * EURUSD_SPEC.point) for pos in p.broker.positions.values()
    )


def test_the_soak_report_flags_limit_parts_left_past_their_lifetime(rig: Rig) -> None:
    from app.engine.demo_report import build_report

    execute(rig, plan_record(rig, parts=2))
    fresh = build_report(rig.db, WED + timedelta(hours=1))
    assert fresh.overdue_limits == 0 and fresh.checks["no limit part left past its lifetime"]
    late = build_report(rig.db, WED + timedelta(hours=5))  # nobody removed it: the supervisor did not run
    assert late.overdue_limits == 1 and not late.checks["no limit part left past its lifetime"]
