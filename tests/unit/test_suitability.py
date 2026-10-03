from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.advisory.asset_classes import AssetClass
from app.advisory.explanations import TEXTS, explain
from app.advisory.suitability import (
    FactsCalculator,
    Gate,
    GateStatus,
    Suitability,
    SymbolFacts,
    assess,
    collect_facts,
)
from app.broker import mt5_constants as c
from app.broker.gateway import ReadOnlyMT5Gateway
from app.config import RiskConfig, SuitabilityConfig
from app.core.enums import Side
from app.risk.position_sizer import AccountFunds, PositionSizer
from tests.unit.test_market_data import setup

WED = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
CFG = SuitabilityConfig()
RISK = RiskConfig()  # 0.5% per trade


@pytest.fixture(scope="module")
def gateway() -> ReadOnlyMT5Gateway:
    _, _, gw = setup(WED)
    return gw  # type: ignore[no-any-return]


def funds(equity: float, *, margin: float = 0.0, free: float | None = None) -> AccountFunds:
    return AccountFunds(
        equity=equity, balance=equity, margin=margin, margin_free=equity - margin if free is None else free
    )


def facts(gw: ReadOnlyMT5Gateway, symbol: str, atr: float | None, **kw) -> SymbolFacts:  # type: ignore[no-untyped-def]
    spec = kw.pop("spec", None) or gw.symbol_spec(symbol)
    cls = AssetClass.METAL if symbol.startswith("XA") else AssetClass.FOREX_MAJOR
    options = {"tick": gw.tick(symbol), "candles": 500, "now": WED, "market_open": True} | kw
    return collect_facts(spec, cls, gw, CFG, atr=atr, **options)


def run(f: SymbolFacts, equity: float = 10_000.0, risk: RiskConfig = RISK, **kw) -> Suitability:  # type: ignore[no-untyped-def]
    return assess(f, kw.pop("funds", None) or funds(equity), risk, CFG, currency="USD", **kw)


class TestFacts:
    def test_eurusd(self, gateway: ReadOnlyMT5Gateway) -> None:
        f = facts(gateway, "EURUSD", 0.0010)
        spec = f.spec
        spread = spec.spread_points * spec.point
        assert f.side is Side.BUY and not f.problems
        assert f.typical_sl == pytest.approx(1.5 * 0.0010 + spread)
        assert f.loss_per_lot == pytest.approx(f.typical_sl * 100_000)
        assert f.move_1pct_per_lot == pytest.approx(f.price * 0.01 * 100_000)
        assert f.margin_per_lot == pytest.approx(gateway.calc_margin(Side.BUY, "EURUSD", 1.0, f.price))

    def test_calculator_scales_linearly(self, gateway: ReadOnlyMT5Gateway) -> None:
        f = facts(gateway, "EURUSD", 0.0010)
        calc = FactsCalculator(f)
        broker = gateway.calc_profit(Side.SELL, "EURUSD", 0.3, 1.1000, 1.1020)
        assert calc.calc_profit(Side.SELL, "EURUSD", 0.3, 1.1000, 1.1020) == pytest.approx(broker)
        assert calc.calc_margin(Side.BUY, "EURUSD", 0.5, 1.1) == pytest.approx(f.margin_per_lot * 0.5)

    def test_sell_only_symbol_uses_the_bid(self, gateway: ReadOnlyMT5Gateway) -> None:
        spec = dataclasses.replace(gateway.symbol_spec("EURUSD"), trade_mode=c.SYMBOL_TRADE_MODE_SHORTONLY)
        f = facts(gateway, "EURUSD", 0.0010, spec=spec)
        assert f.side is Side.SELL and f.price == gateway.tick("EURUSD").bid  # type: ignore[union-attr]


class TestSizingGates:
    def test_small_account_excludes_xauusd_with_required_equity(self, gateway: ReadOnlyMT5Gateway) -> None:
        f = facts(gateway, "XAUUSD", 5.0)
        r = run(f, equity=100.0)
        assert not r.eligible and r.failed == (Gate.G2_MIN_LOT,)
        g2 = r.gate(Gate.G2_MIN_LOT)
        assert g2.key == "g2.min_lot_risk"
        # 0.01 lot x (100 USD per 1.00 move x (1.5 x 5.0 + spread) + 5 points of slippage allowance)
        assert f.typical_sl == pytest.approx(7.5 + f.spec.spread_points * 0.01)
        assert r.min_lot_risk == pytest.approx(Decimal("0.01") * (Decimal(str(f.typical_sl * 100)) + 5))
        assert r.risk_budget == Decimal("0.5")
        assert r.min_lot_risk is not None and r.required_equity == r.min_lot_risk * 200  # / 0.5%
        assert r.lot is None and r.margin is not None  # G3 is still judged at the minimum lot
        figure = f"{float(r.required_equity):,.2f}"
        assert f"needs equity ≥ {figure} USD" in explain(g2.key, g2.params)
        assert f"อย่างน้อย {figure} USD" in explain(g2.key, g2.params, "th")

    def test_required_equity_is_the_boundary(self, gateway: ReadOnlyMT5Gateway) -> None:
        f = facts(gateway, "XAUUSD", 5.0)
        required = run(f, equity=100.0).required_equity
        assert required is not None
        assert run(f, equity=float(required) - 1).gate(Gate.G2_MIN_LOT).status is GateStatus.FAIL
        r = run(f, equity=float(required))
        assert r.gate(Gate.G2_MIN_LOT).passed and r.lot == Decimal("0.01")

    def test_money_cap_below_min_lot_risk(self, gateway: ReadOnlyMT5Gateway) -> None:
        risk = RISK.model_copy(update={"max_risk_money_per_trade": 5.0})
        r = run(facts(gateway, "XAUUSD", 5.0), equity=1_000_000.0, risk=risk)
        g2 = r.gate(Gate.G2_MIN_LOT)
        assert g2.key == "g2.cap" and r.required_equity is None and g2.params["cap"] == 5.0

    def test_risk_sized_lot_matches_the_engine_sizer(self, gateway: ReadOnlyMT5Gateway) -> None:
        f = facts(gateway, "EURUSD", 0.0010)
        r = run(f, equity=10_000.0)
        assert r.eligible, [g.detail for g in r.gates if not g.passed]
        assert f.price is not None and f.typical_sl is not None
        direct = PositionSizer(RISK, gateway).size(
            f.spec, Side.BUY, f.price, f.price - f.typical_sl, funds(10_000.0), lot_limit=RISK.max_lot
        )
        assert r.lot == direct.volume == Decimal("0.3")
        assert r.risk_money is not None and r.risk_money <= r.risk_budget  # type: ignore[operator]
        assert r.effective_leverage == pytest.approx(0.3 * f.price * 1000 * 100 / 10_000)

    def test_user_risk_percent_only_lowers(self, gateway: ReadOnlyMT5Gateway) -> None:
        f = facts(gateway, "EURUSD", 0.0010)
        assert run(f, risk_percent=0.25).risk_budget == Decimal("25")
        assert run(f, risk_percent=2.0).risk_budget == Decimal("50")


class TestMarginCostStopsGates:
    def test_margin_with_buffer(self, gateway: ReadOnlyMT5Gateway) -> None:
        f = facts(gateway, "EURUSD", 0.0010)
        r = run(f, funds=funds(10_000.0, margin=9_700.0, free=300.0))
        g3 = r.gate(Gate.G3_MARGIN)
        assert g3.key == "g3.margin" and g3.params["available"] == 90.0  # 30% of 300
        assert r.margin is not None and g3.params["margin"] == pytest.approx(float(r.margin) * 2, abs=0.01)

    def test_projected_margin_level(self, gateway: ReadOnlyMT5Gateway) -> None:
        f = facts(gateway, "EURUSD", 0.0010)
        r = run(f, funds=funds(10_000.0, margin=1_950.0, free=8_050.0))
        g3 = r.gate(Gate.G3_MARGIN)
        assert g3.key == "g3.margin_level" and g3.params["level"] < 500

    def test_cost_share_of_the_stop(self, gateway: ReadOnlyMT5Gateway) -> None:
        tight = facts(gateway, "EURUSD", 0.0010, median_spread=0.0004)
        r = run(tight)
        assert r.gate(Gate.G4_COST).key == "g4.cost" and r.cost_ratio == pytest.approx(0.4 / 1.9)
        assert run(facts(gateway, "EURUSD", 0.0010)).gate(Gate.G4_COST).passed

    def test_stops_level(self, gateway: ReadOnlyMT5Gateway) -> None:
        spec = dataclasses.replace(gateway.symbol_spec("EURUSD"), stops_level=80)  # 0.0008 vs stop ~0.0016
        f = facts(gateway, "EURUSD", 0.0010, spec=spec)
        g5 = run(f).gate(Gate.G5_STOPS_LEVEL)
        assert g5.key == "g5.stops_level" and g5.params["stops_distance"] == 0.0008
        assert f.typical_sl is not None and g5.params["typical_sl"] == round(f.typical_sl, 5)
        spec = dataclasses.replace(spec, stops_level=70)
        assert run(facts(gateway, "EURUSD", 0.0010, spec=spec)).gate(Gate.G5_STOPS_LEVEL).passed


class TestTradableAndData:
    @pytest.mark.parametrize(
        ("change", "key"),
        [
            ({"trade_mode": c.SYMBOL_TRADE_MODE_DISABLED}, "g1.trade_disabled"),
            ({"trade_mode": c.SYMBOL_TRADE_MODE_CLOSEONLY}, "g1.no_direction"),
            ({"volume_step": 0.0}, "g1.spec_invalid"),
            ({"execution_mode": c.SYMBOL_TRADE_EXECUTION_MARKET, "filling_mode": 0}, "g1.no_filling"),
            ({"tick_value_loss": 3.0}, "g1.spec_inconsistent"),
        ],
    )
    def test_g1(self, gateway: ReadOnlyMT5Gateway, change: dict[str, object], key: str) -> None:
        spec = dataclasses.replace(gateway.symbol_spec("EURUSD"), **change)  # type: ignore[arg-type]
        r = run(facts(gateway, "EURUSD", 0.0010, spec=spec))
        assert r.gate(Gate.G1_TRADABLE).key == key and not r.eligible
        for gate in (Gate.G2_MIN_LOT, Gate.G3_MARGIN, Gate.G4_COST, Gate.G5_STOPS_LEVEL):
            assert r.gate(gate).status is GateStatus.NOT_EVALUATED

    def test_no_quote_and_no_atr(self, gateway: ReadOnlyMT5Gateway) -> None:
        r = run(facts(gateway, "EURUSD", 0.0010, tick=None))
        assert r.gate(Gate.G6_DATA).key == "g6.no_quote"
        assert r.gate(Gate.G2_MIN_LOT).status is GateStatus.NOT_EVALUATED
        r = run(facts(gateway, "EURUSD", None))
        assert r.gate(Gate.G6_DATA).key == "g6.no_atr" and r.gate(Gate.G1_TRADABLE).passed
        assert r.failed == (Gate.G6_DATA,) and not r.eligible

    def test_stale_quote_only_matters_while_open(self, gateway: ReadOnlyMT5Gateway) -> None:
        later = WED + timedelta(minutes=10)
        r = run(facts(gateway, "EURUSD", 0.0010, now=later))
        assert r.gate(Gate.G6_DATA).key == "g6.stale_quote" and r.gate(Gate.G6_DATA).params["age"] >= 600
        assert run(facts(gateway, "EURUSD", 0.0010, now=later, market_open=False)).gate(Gate.G6_DATA).passed

    def test_few_candles(self, gateway: ReadOnlyMT5Gateway) -> None:
        g6 = run(facts(gateway, "EURUSD", 0.0010, candles=50)).gate(Gate.G6_DATA)
        assert g6.key == "g6.few_candles" and g6.params == {"candles": 50, "required": 200}


class TestExplanations:
    def test_every_key_has_both_languages_and_renders(self, gateway: ReadOnlyMT5Gateway) -> None:
        for key, texts in TEXTS.items():
            assert set(texts) == {"en", "th"}, key
        results = [
            run(facts(gateway, "XAUUSD", 5.0), equity=100.0),
            run(facts(gateway, "EURUSD", 0.0010)),
            run(facts(gateway, "EURUSD", 0.0010, median_spread=0.0004, candles=10)),
        ]
        for r in results:
            for g in r.gates:
                assert g.key in TEXTS
                for language in ("en", "th"):
                    assert "{" not in explain(g.key, g.params, language)  # type: ignore[arg-type]

    def test_unknown_key_renders_as_itself(self) -> None:
        assert explain("g9.nope") == "g9.nope"
