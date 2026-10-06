"""The owner's entry plan drives the bot's orders (PLAN §A31/§A33; TAA-1207)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.advisory.preferences import AdvisoryPreferences, EntryPlanPreferences, TradingProfile
from app.config import AppConfig
from app.core.clock import ManualClock
from app.core.enums import EntryType, Side
from app.engine.decision_engine import Decision
from app.engine.risk_limits import RiskLimitSelector
from app.risk.limits import EntryPlanSpec, ProfileLimits, RiskProfileDoc
from app.risk.position_sizer import SplitMode, WeightScheme, build_parts
from app.storage.database import Database
from tests.unit.test_decision_engine import NOW, Setup, engine, request
from tests.unit.test_strategy_models import make_context

SCALE_IN = EntryPlanSpec(SplitMode.SCALE_IN, 5, WeightScheme.EQUAL, 0.5, 0.01)
SAME_PRICE = EntryPlanSpec(SplitMode.SAME_PRICE, 3, WeightScheme.EQUAL, 0.5, None, (1.0, 1.5))
ON = Setup(config={"execution": {"entry_plans": True}})


def limits(plan: EntryPlanSpec | None) -> ProfileLimits:
    return ProfileLimits(entry_plan=plan)


class TestSpec:
    def test_the_profile_plan_becomes_the_engine_spec(self) -> None:
        prefs = AdvisoryPreferences(
            entry_plan=EntryPlanPreferences(mode=SplitMode.SAME_PRICE, parts=3, partial_tp_r=[1.0, 1.5, 3.0])
        )
        plan = prefs.engine_limits().entry_plan
        assert plan == EntryPlanSpec(SplitMode.SAME_PRICE, 3, WeightScheme.EQUAL, 0.5, None, (1.0, 1.5))

    def test_a_single_plan_is_left_out_and_keeps_the_profile_version(self) -> None:
        prefs = AdvisoryPreferences()
        assert prefs.engine_limits().entry_plan is None
        assert prefs.engine_limits().version() == TradingProfile().resolve().limits().version()

    @pytest.mark.parametrize(
        "kw",
        [
            {"mode": SplitMode.SINGLE, "parts": 2},
            {"mode": SplitMode.SCALE_IN, "parts": 1},
            {"mode": SplitMode.SCALE_IN, "parts": 6},
            {"mode": SplitMode.SCALE_IN, "parts": 2, "spacing_atr": 0.0},
            {"mode": SplitMode.SAME_PRICE, "parts": 3, "tp_r": (1.0,)},
            {"mode": SplitMode.SAME_PRICE, "parts": 3, "tp_r": (2.0, 1.0)},
        ],
    )
    def test_incoherent_plans_are_refused(self, kw: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            EntryPlanSpec(**kw)

    def test_the_wire_document_round_trips_and_changes_the_version(self) -> None:
        base = TradingProfile().resolve().limits()
        with_plan = ProfileLimits(**{**base.to_dict(), "entry_plan": SCALE_IN})
        doc = RiskProfileDoc.of(with_plan)
        assert doc.limits() == with_plan
        assert doc.version != base.version()
        assert RiskProfileDoc.model_validate_json(doc.model_dump_json()).limits() == with_plan

    def test_an_incoherent_document_plan_is_refused_on_the_engine(self) -> None:
        doc = RiskProfileDoc.of(TradingProfile().resolve().limits())
        raw = doc.model_dump() | {"entry_plan": {"mode": "SCALE_IN", "parts": 1}}
        bad = RiskProfileDoc.model_validate(raw)
        with pytest.raises(ValueError):
            bad.limits()
        with pytest.raises(ValidationError):
            RiskProfileDoc.model_validate(doc.model_dump() | {"entry_plan": {"parts": 9}})

    def test_the_local_fallback_carries_the_plan(self) -> None:
        cfg = AppConfig()
        prefs = {"entry_plan": {"mode": "SCALE_IN", "parts": 5, "lot_unit": 0.01}}
        cfg = cfg.model_copy(update={"advisory": cfg.advisory.model_copy(update={"preferences": prefs})})
        selector = RiskLimitSelector(cfg, None, None, ManualClock(NOW))
        assert selector.current().limits.entry_plan == SCALE_IN


class TestBuildParts:
    def test_same_price_takes_profit_at_the_profile_levels(self) -> None:
        parts = build_parts(SplitMode.SAME_PRICE, Side.BUY, 1.1, 1.098, 1.104, k=3, tp_r=(1.0, 1.5))
        assert [p.take_profit for p in parts] == [Decimal("1.102"), Decimal("1.103"), Decimal("1.104")]

    def test_without_levels_it_keeps_the_whole_r_steps(self) -> None:
        parts = build_parts(SplitMode.SAME_PRICE, Side.SELL, 1.1, 1.102, 1.094, k=3)
        assert [p.take_profit for p in parts] == [Decimal("1.098"), Decimal("1.096"), Decimal("1.094")]


class TestDecision:
    def test_the_engine_switch_off_keeps_one_order(self, db: Database) -> None:
        record = engine(db).decide(request(profile_limits=limits(SCALE_IN)))
        assert record.decision is Decision.ACCEPT
        assert record.sizing is not None and len(record.sizing.parts) == 1

    def test_scale_in_sizes_a_market_part_and_limits_toward_the_stop(self, db: Database) -> None:
        market = make_context(quality_flags=())
        record = engine(db, ON).decide(request(market=market, profile_limits=limits(SCALE_IN)))
        assert record.decision is Decision.ACCEPT, [c.reason_code for c in record.failed]
        sizing = record.sizing
        assert sizing is not None and market.atr is not None
        kinds = [p.part.order_type for p in sizing.parts]
        assert kinds[0] is EntryType.MARKET and set(kinds[1:]) == {EntryType.LIMIT}
        levels = [float(p.part.entry) for p in sizing.parts]
        assert levels == sorted(levels, reverse=True)  # a BUY scales in below the market part
        assert all(level > 1.098 for level in levels)  # every level above the stop
        assert all(p.volume % Decimal("0.01") == 0 and p.taps == int(p.volume * 100) for p in sizing.parts)
        assert sizing.risk_money <= sizing.budget  # every part filled stays within the budget
        assert len({p.volume for p in sizing.parts}) == 1  # equal weights

    def test_scale_in_without_an_atr_sends_one_order_and_says_so(self, db: Database) -> None:
        market = _without_atr(make_context(quality_flags=()))
        record = engine(db, ON).decide(request(market=market, profile_limits=limits(SCALE_IN)))
        # the decision may still fail checks that need an ATR; the sizing itself is one order
        assert record.sizing is not None and record.sizing.ok and len(record.sizing.parts) == 1
        assert "ATR" in record.sizing.detail

    def test_same_price_parts_carry_their_own_targets(self, db: Database) -> None:
        record = engine(db, ON).decide(request(profile_limits=limits(SAME_PRICE)))
        assert record.decision is Decision.ACCEPT, [c.reason_code for c in record.failed]
        assert record.sizing is not None
        targets = [p.part.take_profit for p in record.sizing.parts]
        assert targets == [Decimal("1.1020"), Decimal("1.1030"), Decimal("1.1040")]
        assert {p.part.order_type for p in record.sizing.parts} == {EntryType.MARKET}


def _without_atr(market: Any) -> Any:
    import dataclasses

    states = tuple(dataclasses.replace(s, atr=None) for s in market.states)
    return dataclasses.replace(market, states=states)


class TestExposure:
    """A plan counts as one position; resting limit parts add their risk to heat (owner, 2026-10-06)."""

    @staticmethod
    def order(ticket: int = 50, sl: float = 1.098, magic: int = 7_310_000) -> Any:
        from datetime import UTC, datetime

        from app.broker import mt5_constants as c
        from app.broker.models import BrokerOrder

        return BrokerOrder(
            ticket,
            "EURUSD",
            Side.BUY,
            c.ORDER_TYPE_BUY_LIMIT,
            0.1,
            1.099,
            sl,
            1.104,
            magic,
            "taa:x",
            datetime(2026, 9, 30, 9, 0, tzinfo=UTC),
            None,
        )

    def test_the_parts_of_one_plan_count_once(self) -> None:
        from tests.risk_data import funds
        from tests.unit.test_exposure_manager import SPECS, cand, manager, pos

        book = [pos(ticket=1), pos(ticket=2, price=1.099), pos(ticket=3, price=1.0985)]
        m = manager(max_open_positions=2, max_positions_per_symbol=1)
        exposure = m.snapshot(book, funds(), SPECS, groups={1: "plan-a", 2: "plan-a", 3: "plan-a"})
        checks = {ch.name: ch for ch in m.check(cand(), exposure, SPECS)}
        assert checks["max_open_positions"].passed and checks["max_open_positions"].value == 2
        same = {ch.name: ch for ch in m.check(cand("EURUSD"), exposure, SPECS)}
        assert not same["max_positions_per_symbol"].passed  # a new signal waits until the plan ends
        alone = m.snapshot(book, funds(), SPECS)  # without plans every position counts
        assert not {ch.name: ch for ch in m.check(cand(), alone, SPECS)}["max_open_positions"].passed

    def test_resting_orders_add_to_heat(self) -> None:
        from tests.risk_data import funds
        from tests.unit.test_exposure_manager import SPECS, manager, pos

        m = manager()
        bare = m.snapshot([pos()], funds(), SPECS)
        with_order = m.snapshot([pos()], funds(), SPECS, pending=[self.order()])
        assert with_order.open_risk == pytest.approx(bare.open_risk + 10.0)  # 0.1 lot, 10 pips
        no_stop = m.snapshot([pos()], funds(), SPECS, pending=[self.order(sl=0.0)])
        assert no_stop.open_risk == bare.open_risk
        manual = manager(foreign_positions_policy="halt").snapshot(
            [], funds(), SPECS, pending=[self.order(magic=0)]
        )
        assert manual.open_risk == 0.0  # foreign orders count only under "count"

    def test_the_decision_sees_resting_orders_and_plans(self, db: Database) -> None:
        from app.engine.decision_engine import AccountState
        from tests.risk_data import funds
        from tests.unit.test_exposure_manager import pos
        from tests.unit.test_loss_tracker import status

        book = (pos(ticket=1, symbol="GBPUSD"), pos(ticket=2, symbol="GBPUSD"))
        account = AccountState(funds(), book, status(), (self.order(),), {1: "p", 2: "p"})
        record = engine(db).decide(
            request(account=account, profile_limits=ProfileLimits(max_open_positions=2))
        )
        checks = {ch.name: ch for ch in record.checks}
        assert checks["max_open_positions"].passed  # GBPUSD's two parts are one trade
        heat = checks["max_total_open_risk"].value
        assert heat is not None and float(heat) > 0


def test_the_heartbeat_reports_the_plan_in_use() -> None:
    from app.sync.heartbeat import RiskLimits

    cfg = AppConfig()
    prefs = {"entry_plan": {"mode": "SCALE_IN", "parts": 5, "lot_unit": 0.01}}
    cfg = cfg.model_copy(
        update={
            "advisory": cfg.advisory.model_copy(update={"preferences": prefs}),
            "execution": cfg.execution.model_copy(update={"entry_plans": True}),
        }
    )
    selector = RiskLimitSelector(cfg, None, None, ManualClock(NOW))
    selector.current()
    snapshot = selector.snapshot()
    assert snapshot is not None
    report = RiskLimits.model_validate(snapshot)  # the cloud's strict heartbeat model accepts it
    assert report.entry_plans_enabled is True and report.entry_plan is not None
    assert (report.entry_plan.mode, report.entry_plan.parts, report.entry_plan.lot_unit) == (
        "SCALE_IN",
        5,
        0.01,
    )
