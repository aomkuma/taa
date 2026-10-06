from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from app.broker.models import BrokerPosition
from app.config import RiskConfig
from app.core.enums import Side
from app.risk.checks import CheckKind
from app.risk.exposure_manager import Candidate, ExposureManager
from app.risk.reasons import Reason
from tests.risk_data import XAUUSD_SPEC, TickCalculator, funds
from tests.strategy_data import EURUSD_SPEC

BASE = 7_310_000
GBPUSD_SPEC = dataclasses.replace(EURUSD_SPEC, name="GBPUSD", currency_base="GBP", currency_margin="GBP")
USDJPY_SPEC = dataclasses.replace(
    EURUSD_SPEC,
    name="USDJPY",
    digits=3,
    point=0.001,
    tick_size=0.001,
    tick_value=0.67,
    tick_value_profit=0.67,
    tick_value_loss=0.67,
    currency_base="USD",
    currency_profit="JPY",
    currency_margin="USD",
)
SPECS = {s.name: s for s in (EURUSD_SPEC, GBPUSD_SPEC, USDJPY_SPEC, XAUUSD_SPEC)}
CALC = TickCalculator(*SPECS.values())


def pos(
    symbol: str = "EURUSD",
    side: Side = Side.BUY,
    volume: float = 0.1,
    price: float = 1.1,
    sl: float = 1.098,
    magic: int = BASE,
    ticket: int = 1,
) -> BrokerPosition:
    return BrokerPosition(
        ticket=ticket,
        symbol=symbol,
        side=side,
        volume=volume,
        price_open=price,
        sl=sl,
        tp=0.0,
        price_current=price,
        profit=0.0,
        swap=0.0,
        magic=magic,
        comment="",
        time_utc=datetime(2026, 9, 30, 9, 0, tzinfo=UTC),
        identifier=ticket,
    )


def cand(symbol: str = "GBPUSD", side: Side = Side.BUY, risk: float = 50.0, **kw: float) -> Candidate:
    return Candidate(symbol, side, kw.get("volume", 0.1), kw.get("entry", 1.3), risk, kw.get("margin", 130.0))


def manager(**risk: object) -> ExposureManager:
    return ExposureManager(RiskConfig(**risk), CALC, magic_base=BASE)  # type: ignore[arg-type]


def checks(
    mgr: ExposureManager, positions: list[BrokerPosition], c: Candidate, **kw: float
) -> dict[str, bool]:
    exposure = mgr.snapshot(positions, funds(margin=sum(100.0 for _ in positions)), SPECS)
    return {ch.name: ch.passed for ch in mgr.check(c, exposure, SPECS, **kw)}


class TestSnapshot:
    def test_risk_to_stop_from_the_open_price(self) -> None:
        mgr = manager()
        exposure = mgr.snapshot(
            [pos(), pos("USDJPY", Side.SELL, 0.2, 150.0, 150.3, ticket=2)], funds(), SPECS
        )
        assert [p.risk_to_stop for p in exposure.positions] == pytest.approx([20.0, 0.2 * 300 * 0.67])
        assert exposure.open_risk == pytest.approx(20.0 + 40.2)
        assert exposure.heat_percent == pytest.approx(100 * 60.2 / 10_000)

    def test_stop_beyond_break_even_risks_nothing(self) -> None:
        locked = dataclasses.replace(pos(sl=1.101), price_current=1.103)
        assert manager().snapshot([locked], funds(), SPECS).open_risk == 0.0
        losing = dataclasses.replace(pos(), price_current=1.099)  # floating loss: risk still open -> stop
        assert manager().snapshot([losing], funds(), SPECS).open_risk == pytest.approx(20.0)

    def test_no_stop_or_no_spec_is_unknown_risk(self) -> None:
        exposure = manager().snapshot([pos(sl=0.0), pos("BTCUSD", ticket=2)], funds(), SPECS)
        assert len(exposure.unknown_risk) == 2

    def test_ownership_by_magic(self) -> None:
        mgr = manager()
        assert mgr.is_bot(pos(magic=BASE + 12))
        assert not mgr.is_bot(pos(magic=0))
        assert not mgr.is_bot(pos(magic=BASE + 10_000))

    def test_effective_leverage(self) -> None:
        # 1 lot EURUSD at 1.1: a 1 % move = 1100 ticks x $1 = $1100 -> 11x on $10k
        exposure = manager().snapshot([pos(volume=1.0)], funds(), SPECS)
        assert exposure.effective_leverage == pytest.approx(11.0)


class TestChecks:
    def test_clean_book_passes_everything(self) -> None:
        result = checks(manager(), [], cand())
        assert all(result.values()), result

    def test_every_check_is_an_account_rule(self) -> None:
        mgr = manager()
        out = mgr.check(cand(), mgr.snapshot([], funds(), SPECS), SPECS)
        assert {c.kind for c in out} == {CheckKind.ACCOUNT}
        assert len({c.name for c in out}) == len(out)

    @pytest.mark.parametrize(
        ("positions", "candidate", "risk", "failing"),
        [
            ([pos(ticket=i) for i in range(3)], cand("USDJPY", entry=150.0), {}, "max_open_positions"),
            ([pos()], cand("EURUSD", entry=1.1), {"max_positions_per_symbol": 2}, None),
            ([pos()], cand("EURUSD", entry=1.1), {}, "max_positions_per_symbol"),
            (
                [pos(side=Side.SELL, sl=1.102)],
                cand("EURUSD", entry=1.1),
                {"max_positions_per_symbol": 2},
                "conflicting_position",
            ),
            ([pos()], cand("GBPUSD"), {}, "correlation_group"),  # EURUSD and GBPUSD long together
            ([pos(sl=0.0)], cand("USDJPY", entry=150.0), {}, "unknown_position_risk"),
        ],
    )
    def test_portfolio_rules(
        self,
        positions: list[BrokerPosition],
        candidate: Candidate,
        risk: dict[str, object],
        failing: str | None,
    ) -> None:
        result = checks(manager(**risk), positions, candidate)
        assert [name for name, ok in result.items() if not ok] == ([failing] if failing else [])

    def test_opposite_side_in_a_group_is_allowed(self) -> None:
        result = checks(manager(), [pos()], cand("GBPUSD", Side.SELL))
        assert result["correlation_group"]

    def test_currency_direction_count(self) -> None:
        # long EUR (EURUSD), long GBP (GBPUSD), short JPY... all three are short USD except USDJPY BUY
        book = [pos(), pos("GBPUSD", price=1.3, sl=1.298, ticket=2)]
        mgr = manager(max_open_positions=5, correlation_groups={})
        result = checks(mgr, book, cand("XAUUSD", entry=2400.0))  # a third USD short
        assert not result["currency_direction"]
        assert checks(mgr, book, cand("USDJPY", entry=150.0))["currency_direction"]  # USD long is fine

    def test_portfolio_heat_includes_manual_positions(self) -> None:
        manual = pos(volume=0.5, magic=0)  # $100 to the stop
        result = checks(manager(), [manual], cand("USDJPY", entry=150.0, risk=60.0))
        assert not result["max_total_open_risk"]  # (100 + 60) / 10k = 1.6 % > 1.5 %
        exposure = manager().snapshot([manual], funds(), SPECS)
        out = {c.name: c for c in manager().check(cand("USDJPY", entry=150.0, risk=60.0), exposure, SPECS)}
        assert out["max_total_open_risk"].value == pytest.approx(1.6)
        assert out["max_total_open_risk"].reason is Reason.MAX_TOTAL_OPEN_RISK

    def test_profile_heat_can_only_lower_the_limit(self) -> None:
        assert not checks(manager(), [], cand(risk=80.0), max_heat_percent=0.5)["max_total_open_risk"]
        assert checks(manager(), [], cand(risk=80.0), max_heat_percent=5.0)["max_total_open_risk"]
        assert not checks(manager(), [], cand(risk=200.0), max_heat_percent=5.0)["max_total_open_risk"]

    def test_foreign_policy(self) -> None:
        manual = pos("USDJPY", Side.SELL, price=150.0, sl=150.3, magic=0)
        halting = manager(foreign_positions_policy="halt")
        assert not checks(halting, [manual], cand())["foreign_positions"]
        assert checks(manager(), [manual], cand())["foreign_positions"]
        # with "halt", foreign positions are not counted toward limits (entries are blocked anyway)
        exposure = halting.snapshot([manual], funds(), SPECS)
        assert exposure.counted == ()

    def test_margin_and_leverage(self) -> None:
        assert not checks(manager(), [], cand(margin=3_500.0))["margin_utilization"]  # 35 % > 30 %
        big = cand("EURUSD", volume=1.0, entry=1.1)  # 11x > 10x
        assert checks(manager(), [], big)["effective_leverage"]  # no cap by default: margin decides
        assert not checks(manager(max_effective_leverage=10.0), [], big)["effective_leverage"]
