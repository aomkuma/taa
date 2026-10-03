from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import Field

from app.config import StrategiesConfig, StrategyEntry, TimeframesConfig
from app.core.enums import Action, Timeframe
from app.core.errors import ConfigError
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.registry import StrategyRegistry
from app.strategy.signal_models import Condition, ReasonCode, Signal, StrategyContext
from tests.unit.test_strategy_models import BAR, make_context


class BuyParams(StrategyParams):
    rr: float = Field(default=2.0, gt=0, le=10)


class AlwaysBuy(BaseStrategy):
    name = "always_buy"
    Params = BuyParams

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return (Timeframe.H1, Timeframe.M15)

    def warmup_bars(self) -> int:
        return 50

    def evaluate(self, ctx: StrategyContext) -> Signal:
        entry = ctx.market.entry.close
        return self.entry(
            ctx,
            Action.BUY,
            entry_price=entry,
            stop_loss=entry - 0.001,
            take_profit=entry + 0.001 * self.params.rr,
            conditions=(Condition("a", True, 3.0), Condition("b", False)),
            score=150.0,
            reasons=("TEST",),
        )


class Broken(BaseStrategy):
    name = "broken"

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return (Timeframe.M15,)

    def warmup_bars(self) -> int:
        return 10

    def evaluate(self, ctx: StrategyContext) -> Signal:
        raise RuntimeError("bug")


class Liar(AlwaysBuy):
    """Returns a signal for another bar: must be rejected at the plugin boundary."""

    name = "liar"

    def evaluate(self, ctx: StrategyContext) -> Signal:
        sig = super().evaluate(ctx)
        return dataclasses.replace(
            sig,
            data_timestamp_utc=sig.data_timestamp_utc - timedelta(minutes=15),
            strategy=self.name,
        )


class NeedsM5(AlwaysBuy):
    name = "needs_m5"

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return (Timeframe.M5,)


class Greedy(AlwaysBuy):
    name = "greedy"

    def warmup_bars(self) -> int:
        return 10_000


REGISTRY = StrategyRegistry([AlwaysBuy, Broken, Liar, NeedsM5, Greedy])
TFS = TimeframesConfig()


def sctx() -> StrategyContext:
    return StrategyContext(make_context(), {}, BAR + timedelta(seconds=4))


def strategies(*items: StrategyEntry, expiry: int = 1) -> StrategiesConfig:
    return StrategiesConfig(items=list(items), signal_expiry_bars=expiry)


class TestBaseStrategy:
    def test_entry_builder_fills_ids_times_and_strength(self) -> None:
        sig = AlwaysBuy().evaluate(sctx())
        assert sig.strategy == "always_buy"
        assert sig.data_timestamp_utc == BAR
        assert sig.created_at_utc == BAR + timedelta(seconds=4)
        assert sig.expires_at_utc == BAR + timedelta(minutes=15)
        assert sig.setup_strength == pytest.approx(75.0)
        assert sig.score == 100.0  # clipped
        assert sig.risk_reward == pytest.approx(2.0)
        assert dict(sig.bar_times)[Timeframe.H1] == datetime(2026, 9, 30, 10, 0, tzinfo=UTC)

    def test_hold_defaults_to_no_setup(self) -> None:
        hold = AlwaysBuy().hold(sctx())
        assert hold.action is Action.HOLD
        assert hold.reason_codes == ("NO_SETUP",)

    def test_signal_ids_are_unique_but_keys_stable(self) -> None:
        a, b = AlwaysBuy().evaluate(sctx()), AlwaysBuy().evaluate(sctx())
        assert a.signal_id != b.signal_id
        assert a.idempotency_key == b.idempotency_key

    def test_params_type_is_checked(self) -> None:
        with pytest.raises(TypeError):
            AlwaysBuy(StrategyParams())


class TestRegistry:
    def test_builds_enabled_strategies_with_params(self) -> None:
        cfg = strategies(
            StrategyEntry(name="always_buy", params={"rr": 3.0}),
            StrategyEntry(name="broken", enabled=False),
            expiry=4,
        )
        built = REGISTRY.from_config(cfg, TFS)
        assert built.names == ["always_buy"]
        strat = built.strategies[0]
        assert strat.params.rr == 3.0
        assert strat.params.expiry_bars == 4
        assert built.evaluate(sctx())[0].expires_at_utc == BAR + timedelta(hours=1)

    def test_per_strategy_expiry_overrides_global(self) -> None:
        cfg = strategies(StrategyEntry(name="always_buy", params={"expiry_bars": 2}), expiry=4)
        assert REGISTRY.from_config(cfg, TFS).strategies[0].params.expiry_bars == 2

    @pytest.mark.parametrize(
        ("items", "match"),
        [
            ([StrategyEntry(name="nope")], "unknown strategy"),
            ([StrategyEntry(name="always_buy", params={"rr": -1})], "invalid params"),
            ([StrategyEntry(name="always_buy", params={"typo": 1})], "invalid params"),
            ([StrategyEntry(name="always_buy"), StrategyEntry(name="always_buy")], "twice"),
            ([StrategyEntry(name="needs_m5")], "not enabled"),
            ([StrategyEntry(name="greedy")], "warm-up"),
            # a disabled entry is still validated: a typo must not hide until someone enables it
            ([StrategyEntry(name="always_buy", enabled=False, params={"typo": 1})], "invalid params"),
        ],
    )
    def test_config_errors(self, items: list[StrategyEntry], match: str) -> None:
        with pytest.raises(ConfigError, match=match):
            REGISTRY.from_config(strategies(*items), TFS)

    def test_duplicate_class_names_are_rejected(self) -> None:
        with pytest.raises(ConfigError):
            StrategyRegistry([AlwaysBuy, AlwaysBuy])


class TestPluginBoundary:
    def test_exception_becomes_hold(self, caplog: pytest.LogCaptureFixture) -> None:
        built = REGISTRY.from_config(
            strategies(StrategyEntry(name="broken"), StrategyEntry(name="always_buy")), TFS
        )
        with caplog.at_level(logging.ERROR):
            signals = built.evaluate(sctx())
        assert signals[0].action is Action.HOLD
        assert signals[0].reason_codes == (ReasonCode.STRATEGY_ERROR.value,)
        assert signals[1].action is Action.BUY  # the other strategy still ran
        assert any(r.exc_info for r in caplog.records)

    def test_foreign_signal_becomes_hold(self) -> None:
        built = REGISTRY.from_config(strategies(StrategyEntry(name="liar")), TFS)
        sig = built.evaluate(sctx())[0]
        assert sig.action is Action.HOLD
        assert sig.reason_codes == (ReasonCode.STRATEGY_ERROR.value,)
        assert sig.data_timestamp_utc == BAR


class TestIsolation:
    def test_strategy_context_holds_values_only(self) -> None:
        fields = {f.name for f in dataclasses.fields(StrategyContext)}
        assert fields == {"market", "frames", "now_utc", "spec", "evidence"}

    def test_strategy_gets_only_its_params(self) -> None:
        strat = AlwaysBuy()
        assert set(vars(strat)) == {"params"}
