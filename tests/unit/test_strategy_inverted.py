"""Inverted setups (owner, 2026-10-09): the original's signal on the other side, exits at its prices."""

from __future__ import annotations

import dataclasses

import pytest

from app.advisory.requirements import pattern_setups
from app.config import AppConfig, InvertedRiskConfig
from app.core.enums import Action, Side
from app.strategy.catalog import INVERTED, ORIGINALS, default_registry
from app.strategy.inverted import inverted
from app.strategy.setups import NecklineBreak
from app.strategy.signal_models import ReasonCode
from tests.unit.test_strategy_setups import DOUBLE, ENTRY, run, sctx

NecklineInverted = inverted(NecklineBreak)


class TestFlip:
    def test_the_other_side_at_the_original_prices(self) -> None:
        original = run(NecklineBreak, sctx(DOUBLE))
        flipped = run(NecklineInverted, sctx(DOUBLE))
        assert original.action is Action.BUY and flipped.action is Action.SELL
        assert flipped.strategy == "setup_neckline_break_inverted"
        assert flipped.stop_loss == pytest.approx(original.take_profit)
        assert flipped.take_profit == pytest.approx(original.stop_loss)
        assert flipped.risk_reward == pytest.approx(1 / original.risk_reward)  # type: ignore[operator]
        assert flipped.reason_codes[-1] == ReasonCode.INVERTED and flipped.signal_id != original.signal_id

    def test_the_entry_takes_the_other_side_of_the_quote(self) -> None:
        ctx = sctx(DOUBLE)
        market = dataclasses.replace(ctx.market, bid=1.1000, ask=1.1002)
        flipped = run(NecklineInverted, dataclasses.replace(ctx, market=market))
        assert flipped.action is Action.SELL and flipped.entry_price == pytest.approx(1.1000)  # the bid

    def test_without_a_quote_the_original_price_stands(self) -> None:
        assert run(NecklineInverted, sctx(DOUBLE)).entry_price == pytest.approx(ENTRY)

    def test_holds_stay_holds_with_the_inverted_name(self) -> None:
        sig = run(NecklineInverted, sctx())
        assert sig.action is Action.HOLD and sig.strategy == "setup_neckline_break_inverted"

    def test_no_target_means_no_inverted_stop(self) -> None:
        sig = run(NecklineInverted, sctx(DOUBLE), target_mode="rr")
        assert sig.is_entry  # an rr target always exists
        strategy = NecklineInverted(NecklineInverted.Params())
        original = run(NecklineBreak, sctx(DOUBLE))
        no_tp = dataclasses.replace(original, take_profit=None)
        orig_eval = NecklineBreak.evaluate
        try:
            NecklineBreak.evaluate = lambda self, ctx: no_tp  # type: ignore[method-assign,assignment]
            held = strategy.evaluate(sctx(DOUBLE))
        finally:
            NecklineBreak.evaluate = orig_eval  # type: ignore[method-assign]
        assert held.action is Action.HOLD and held.reason_codes == (ReasonCode.NO_TARGET.value,)

    def test_should_close_asks_the_original_for_the_opposite_side(self) -> None:
        seen: list[Side] = []

        class Spy(NecklineBreak):
            def should_close(self, ctx, side):  # type: ignore[no-untyped-def]
                seen.append(side)
                return False

        inverted(Spy)(NecklineBreak.Params()).should_close(sctx(DOUBLE), Side.SELL)
        assert seen == [Side.BUY]


class TestCatalog:
    def test_every_original_has_an_inverted_copy_never_advised(self) -> None:
        names = default_registry().names
        assert len(INVERTED) == len(ORIGINALS)
        for orig, inv in zip(ORIGINALS, INVERTED, strict=True):
            assert inv.name == f"{orig.name}_inverted" and inv.name in names
            assert inv.inverted and not inv.advised and inv.original is orig
            assert inv.Params is orig.Params and inv.demo_only
        assert not any(n.endswith("_inverted") for n in pattern_setups(default_registry()))


class TestDecisionLimits:
    def test_inverted_limits_are_bounded_and_off_by_default(self) -> None:
        assert AppConfig().risk.inverted is None
        assert InvertedRiskConfig().min_risk_reward == 0.2
        with pytest.raises(ValueError):
            InvertedRiskConfig(min_risk_reward=1.5)
