from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.config import RiskConfig
from app.core.enums import EntryType, Side
from app.risk.position_sizer import (
    PlanPart,
    PositionSizer,
    SplitMode,
    WeightScheme,
    build_parts,
    weights,
)
from app.risk.reasons import Reason
from tests.risk_data import XAUUSD_SPEC, TickCalculator, funds
from tests.strategy_data import EURUSD_SPEC

RISK = RiskConfig()


def sizer(risk: RiskConfig = RISK, calc: TickCalculator | None = None, **kw: float) -> PositionSizer:
    return PositionSizer(risk, calc or TickCalculator(), **kw)


class TestBudget:
    def test_percent_of_the_lower_of_equity_and_balance(self) -> None:
        assert sizer().risk_budget(funds(10_000, 12_000)) == Decimal(50)
        assert sizer().risk_budget(funds(12_000, 10_000)) == Decimal(50)

    def test_basis_options(self) -> None:
        eq = sizer(RiskConfig(sizing_basis="equity")).risk_budget(funds(12_000, 10_000))
        assert eq == Decimal(60)

    def test_money_cap_and_probation(self) -> None:
        capped = RiskConfig(max_risk_money_per_trade=30)
        assert sizer(capped).risk_budget(funds()) == Decimal(30)
        assert sizer().risk_budget(funds(), probation=True) == Decimal("12.5")

    def test_profile_percent_can_only_lower(self) -> None:
        assert sizer().risk_budget(funds(), risk_percent=0.25) == Decimal(25)
        assert sizer().risk_budget(funds(), risk_percent=1.5) == Decimal(50)


class TestSingleOrder:
    def test_a9_steps(self) -> None:
        # 20 pips on EURUSD = $200 per lot; slippage allowance 5 points = $5 per lot
        r = sizer().size(EURUSD_SPEC, Side.BUY, 1.10000, 1.09800, funds(), lot_limit=1.0)
        assert r.ok, r.detail
        assert float(r.parts[0].loss_per_lot) == pytest.approx(200, abs=1e-5)  # rounded up past float noise
        assert r.parts[0].cost_per_lot == Decimal(5)
        assert r.volume == Decimal("0.24")  # 50 / 205 = 0.2439 floored
        assert float(r.risk_money) == pytest.approx(49.20)
        assert r.risk_money <= r.budget
        assert float(r.margin_required or 0) == pytest.approx(264.0)  # 0.24 * 100k * 1.1 / 100

    def test_commission_is_a_cost(self) -> None:
        r = sizer(commission_per_lot=7.0).size(EURUSD_SPEC, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0)
        assert r.parts[0].cost_per_lot == Decimal(12)
        assert r.volume == Decimal("0.23")

    def test_sell(self) -> None:
        r = sizer().size(EURUSD_SPEC, Side.SELL, 1.10000, 1.10200, funds(), lot_limit=1.0)
        assert r.ok and r.volume == Decimal("0.24")

    def test_stop_is_rounded_away_from_the_entry(self) -> None:
        r = sizer().size(EURUSD_SPEC, Side.BUY, 1.10000, 1.097996, funds(), lot_limit=1.0)
        assert r.stop_loss == Decimal("1.09799")
        r = sizer().size(EURUSD_SPEC, Side.SELL, 1.10000, 1.102004, funds(), lot_limit=1.0)
        assert r.stop_loss == Decimal("1.10201")

    @pytest.mark.parametrize(
        ("kw", "reason"),
        [
            ({"stop": 1.1010}, Reason.SL_WRONG_SIDE),
            ({"equity": 100.0}, Reason.RISK_BELOW_MIN_LOT),  # $0.50 budget cannot buy 0.01 lot
            ({"equity": 0.0}, Reason.RISK_BELOW_MIN_LOT),
        ],
    )
    def test_rejections(self, kw: dict[str, float], reason: Reason) -> None:
        stop = kw.get("stop", 1.098)
        r = sizer().size(EURUSD_SPEC, Side.BUY, 1.1, stop, funds(kw.get("equity", 10_000.0)), lot_limit=1.0)
        assert not r.ok
        assert r.reason is reason

    def test_never_rounded_up_to_the_minimum(self) -> None:
        # budget $2.04 buys 0.00995 lot: below 0.01, rejected rather than rounded up
        r = sizer().size(EURUSD_SPEC, Side.BUY, 1.1, 1.098, funds(408.0), lot_limit=1.0)
        assert r.reason is Reason.RISK_BELOW_MIN_LOT

    def test_lot_limits(self) -> None:
        r = sizer().size(EURUSD_SPEC, Side.BUY, 1.1, 1.0999, funds(), lot_limit=0.5)
        assert r.volume == Decimal("0.50")
        small_max = dataclasses.replace(EURUSD_SPEC, volume_max=0.3)
        assert sizer().size(small_max, Side.BUY, 1.1, 1.0999, funds(), lot_limit=1.0).volume == Decimal(
            "0.30"
        )

    def test_config_min_lot(self) -> None:
        r = sizer(RiskConfig(min_lot=0.5)).size(EURUSD_SPEC, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0)
        assert r.reason is Reason.RISK_BELOW_MIN_LOT

    def test_broker_calculator_failures(self) -> None:
        calc = TickCalculator()
        calc.profit_none = True
        assert sizer(calc=calc).size(EURUSD_SPEC, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0).reason is (
            Reason.SYMBOL_SPEC_INCONSISTENT
        )
        skewed = sizer(calc=TickCalculator(skew=1.2)).size(
            EURUSD_SPEC, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0
        )
        assert skewed.reason is Reason.SYMBOL_SPEC_INCONSISTENT
        assert "differ" in skewed.detail
        inverted = sizer(calc=TickCalculator(skew=-1.0)).size(
            EURUSD_SPEC, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0
        )
        assert inverted.reason is Reason.SYMBOL_SPEC_INCONSISTENT

    def test_invalid_spec(self) -> None:
        broken = dataclasses.replace(EURUSD_SPEC, volume_step=0.0)
        r = sizer().size(broken, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0)
        assert r.reason is Reason.SYMBOL_SPEC_INCONSISTENT

    def test_margin_checks(self) -> None:
        calc = TickCalculator(leverage=2.0)  # 0.24 lot needs $13,200 margin
        assert sizer(calc=calc).size(EURUSD_SPEC, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0).reason is (
            Reason.MARGIN_INSUFFICIENT
        )
        busy = funds(10_000, margin=1_900)  # level after = 10000 / (1900 + 264) = 462 % < 500 %
        assert sizer().size(EURUSD_SPEC, Side.BUY, 1.1, 1.098, busy, lot_limit=1.0).reason is (
            Reason.MARGIN_LEVEL_TOO_LOW
        )
        calc = TickCalculator()
        calc.margin_none = True
        assert sizer(calc=calc).size(EURUSD_SPEC, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0).reason is (
            Reason.MARGIN_INSUFFICIENT
        )

    def test_gold(self) -> None:
        # $5 stop on 1 lot of 100 oz = $500; budget $50 -> 0.09 lot after costs
        r = sizer().size(XAUUSD_SPEC, Side.BUY, 2400.00, 2395.00, funds(), lot_limit=1.0)
        assert r.ok, r.detail
        assert r.volume == Decimal("0.09")


class TestPlans:
    def test_weights(self) -> None:
        assert weights(WeightScheme.EQUAL, 3) == [1, 1, 1]
        assert weights(WeightScheme.FRONT_LOADED, 3) == [3, 2, 1]
        assert weights(WeightScheme.BACK_LOADED, 3) == [1, 2, 3]

    def test_same_price_staggers_take_profits(self) -> None:
        parts = build_parts(SplitMode.SAME_PRICE, Side.BUY, 1.1, 1.098, 1.106, k=3)
        assert [p.take_profit for p in parts] == [Decimal("1.102"), Decimal("1.104"), Decimal("1.106")]
        assert {p.entry for p in parts} == {Decimal("1.1")}
        capped = build_parts(SplitMode.SAME_PRICE, Side.BUY, 1.1, 1.098, 1.103, k=3)
        assert [p.take_profit for p in capped] == [Decimal("1.102"), Decimal("1.103"), Decimal("1.103")]
        sell = build_parts(SplitMode.SAME_PRICE, Side.SELL, 1.1, 1.102, 1.094, k=2)
        assert [p.take_profit for p in sell] == [Decimal("1.098"), Decimal("1.094")]

    def test_scale_in_levels_stop_short_of_the_stop(self) -> None:
        parts = build_parts(SplitMode.SCALE_IN, Side.BUY, 1.1, 1.098, 1.106, k=5, atr=0.001, spacing_atr=0.5)
        assert [p.entry for p in parts] == [
            Decimal("1.1"),
            Decimal("1.0995"),
            Decimal("1.0990"),
            Decimal("1.0985"),
        ]
        assert [p.order_type for p in parts] == [EntryType.MARKET] + [EntryType.LIMIT] * 3
        with pytest.raises(ValueError):
            build_parts(SplitMode.SCALE_IN, Side.BUY, 1.1, 1.098, 1.106, k=2)

    def test_same_price_plan_with_taps(self) -> None:
        parts = build_parts(SplitMode.SAME_PRICE, Side.BUY, 1.1, 1.098, 1.106, k=3)
        r = sizer().size_plan(EURUSD_SPEC, Side.BUY, parts, 1.098, funds(), lot_limit=1.0, lot_unit=0.02)
        assert r.ok, r.detail
        assert [p.volume for p in r.parts] == [Decimal("0.08")] * 3  # u = 50 / 615 = 0.0813
        assert [p.taps for p in r.parts] == [4, 4, 4]
        assert r.risk_money <= r.budget

    def test_scale_in_budget_counts_every_part_filled(self) -> None:
        parts = build_parts(
            SplitMode.SCALE_IN, Side.BUY, 1.1, 1.098, 1.106, k=3, scheme=WeightScheme.FRONT_LOADED, atr=0.001
        )
        r = sizer().size_plan(EURUSD_SPEC, Side.BUY, parts, 1.098, funds(), lot_limit=1.0)
        assert r.ok, r.detail
        losses = [p.loss_per_lot for p in r.parts]
        assert [float(x) for x in losses] == pytest.approx([200, 150, 100], abs=1e-5)  # deeper: less per lot
        # u = 50 / (3 * 205 + 2 * 155 + 1 * 105) = 0.0485 -> 0.14 / 0.09 / 0.04
        assert [p.volume for p in r.parts] == [Decimal("0.14"), Decimal("0.09"), Decimal("0.04")]
        assert r.risk_money <= r.budget

    def test_drops_the_deepest_part_before_giving_up(self) -> None:
        parts = build_parts(
            SplitMode.SAME_PRICE, Side.BUY, 1.1, 1.098, 1.106, k=3, scheme=WeightScheme.FRONT_LOADED
        )
        # budget $10: u = 10 / (6 * 205) = 0.0081 -> 0.02/0.01/0.00, so the third is dropped;
        # then u = 10 / (5 * 205) = 0.0098 -> 0.02/0.01
        r = sizer().size_plan(EURUSD_SPEC, Side.BUY, parts, 1.098, funds(2_000), lot_limit=1.0)
        assert r.ok, r.detail
        assert r.dropped_parts == 1
        assert [p.volume for p in r.parts] == [Decimal("0.02"), Decimal("0.01")]

    def test_lot_unit_must_be_a_step_multiple(self) -> None:
        r = sizer().size_plan(
            EURUSD_SPEC,
            Side.BUY,
            [PlanPart(Decimal("1.1"), Decimal(1))],
            1.098,
            funds(),
            lot_limit=1.0,
            lot_unit=0.015,
        )
        assert r.reason is Reason.VOLUME_INVALID


def test_fake_mt5_gateway_is_a_calculator() -> None:
    from tests.unit.test_market_data import setup

    _, _, gateway = setup(datetime(2026, 9, 30, 10, 0, tzinfo=UTC))
    spec = gateway.symbol_spec("EURUSD")
    r = PositionSizer(RISK, gateway).size(spec, Side.BUY, 1.1, 1.098, funds(), lot_limit=1.0)
    assert r.ok, r.detail
    assert r.risk_money <= r.budget
