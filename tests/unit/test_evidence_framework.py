from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from typing import Any, ClassVar

import numpy as np
import pandas as pd
import pytest
from pydantic import Field

from app.config import DetectorSettings, EvidenceConfig
from app.core.enums import Timeframe
from app.core.errors import ConfigError, EvidenceError
from app.evidence.framework import (
    Detector,
    DetectorParams,
    Direction,
    Evidence,
    EvidenceContext,
    EvidenceSnapshot,
    Family,
    KeyLevel,
    Tier,
    activate,
)
from app.evidence.registry import DetectorRegistry, EvidenceEngine
from app.indicators.trend import sma
from tests.evidence_harness import assert_no_lookahead, candles, context
from tests.indicator_data import random_ohlc

# --- toy detectors ----------------------------------------------------------------------------------------


class CrossParams(DetectorParams):
    n: int = Field(default=5, ge=2, le=50)


class CrossUp(Detector):
    id = "test.cross_up"
    name = "Close crosses above SMA"
    family = Family.TREND
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = CrossParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        s, c = sma(ctx.close, params.n).to_numpy(), ctx.close.to_numpy()
        return [
            self.make(
                ctx, t, Direction.BULL, 0.5, invalidation=float(s[t]), key_levels=[KeyLevel("sma", s[t])]
            )
            for t in range(1, ctx.n)
            if c[t] > s[t] and c[t - 1] <= s[t - 1]
        ]


class Confirmed(Detector):
    """Depends on CrossUp: a cross still holding two bars later."""

    id = "test.confirmed"
    name = "Confirmed cross"
    family = Family.TREND
    tier = Tier.T1
    depends_on = ("test.cross_up",)

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        c = ctx.close.to_numpy()
        out = []
        for ev in ctx.results("test.cross_up"):
            t = ctx.pos_of(ev.detected_at) + 2
            if t < ctx.n and c[t] > ev.key_levels[0].price:
                out.append(self.make(ctx, t, Direction.BULL, 0.7))
        return out


class Peeker(Detector):
    """Deliberately broken: uses the next bar's close."""

    id = "test.peeker"
    name = "Peeker"
    family = Family.MOMENTUM
    tier = Tier.T1

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        c = ctx.close.to_numpy()
        return [self.make(ctx, t, Direction.BULL, 0.5) for t in range(ctx.n - 1) if c[t + 1] > c[t]]


class Mislabel(Detector):
    id = "test.mislabel"
    name = "Mislabel"
    family = Family.MOMENTUM
    tier = Tier.T1

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        return [dataclasses.replace(self.make(ctx, 0, Direction.BULL, 0.5), family=Family.TREND)]


class Counting(Detector):
    id = "test.counting"
    name = "Counting"
    family = Family.LEVELS
    tier = Tier.T1
    calls = 0

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        Counting.calls += 1
        return []


@pytest.fixture
def ctx() -> EvidenceContext:
    return context(random_ohlc(300, seed=5))


def bars(closes: list[float]) -> EvidenceContext:
    c = np.array(closes, dtype=float)
    idx = pd.date_range(datetime(2026, 9, 30, 10, tzinfo=UTC), periods=len(c), freq="h")
    df = pd.DataFrame({"open": c, "high": c + 0.1, "low": c - 0.1, "close": c, "tick_volume": 100}, index=idx)
    return context(df)


# --- records ----------------------------------------------------------------------------------------------


class TestEvidence:
    def test_make_fills_identity(self, ctx: EvidenceContext) -> None:
        ev = CrossUp().make(ctx, 10, Direction.BULL, 1.7, variant="fast", details={"b": 2, "a": 1})
        assert ev.quality == 1.0  # clipped
        assert ev.i18n_key == "evidence.test.cross_up.fast"
        assert ev.name == "Close crosses above SMA (fast)"
        assert ev.detected_at == ctx.time_at(10)
        assert ev.details == (("a", 1), ("b", 2))
        assert ev.detail("b") == 2

    def test_invalid_records_rejected(self, ctx: EvidenceContext) -> None:
        ev = CrossUp().make(ctx, 10, Direction.BULL, 0.5)
        with pytest.raises(EvidenceError):
            dataclasses.replace(ev, quality=1.5)
        with pytest.raises(EvidenceError):
            dataclasses.replace(ev, invalidation=float("nan"))
        with pytest.raises(ValueError, match="naive"):
            dataclasses.replace(ev, detected_at=datetime(2026, 9, 30, 10))
        with pytest.raises(EvidenceError):
            KeyLevel("x", float("inf"))

    def test_records_are_immutable(self, ctx: EvidenceContext) -> None:
        ev = CrossUp().make(ctx, 10, Direction.BULL, 0.5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ev.quality = 0.9  # type: ignore[misc]

    def test_id_is_stable_and_content_based(self, ctx: EvidenceContext) -> None:
        a = CrossUp().make(ctx, 10, Direction.BULL, 0.5, key_levels=[KeyLevel("x", 1.1)])
        b = CrossUp().make(ctx, 10, Direction.BULL, 0.9, key_levels=[KeyLevel("x", 1.1)])
        c = CrossUp().make(ctx, 11, Direction.BULL, 0.5, key_levels=[KeyLevel("x", 1.1)])
        assert a.evidence_id == b.evidence_id != c.evidence_id

    def test_dict_round_trip_and_tamper_detection(self, ctx: EvidenceContext) -> None:
        ev = CrossUp().make(
            ctx, 10, Direction.BEAR, 0.4, key_levels=[KeyLevel("n", 1.2, ctx.time_at(3))], targets=[1.0]
        )
        assert Evidence.from_dict(ev.to_dict()) == ev
        forged = ev.to_dict() | {"detected_at": ctx.time_at(11).isoformat()}
        with pytest.raises(EvidenceError, match="altered"):
            Evidence.from_dict(forged)


# --- context ----------------------------------------------------------------------------------------------


class TestContext:
    def test_validation(self) -> None:
        df = candles(random_ohlc(20))
        with pytest.raises(EvidenceError, match="columns"):
            EvidenceContext("EURUSD", Timeframe.H1, df.drop(columns=["close_time"]))
        with pytest.raises(EvidenceError, match="timezone"):
            EvidenceContext(
                "EURUSD", Timeframe.H1, df.assign(close_time=df["close_time"].dt.tz_localize(None))
            )
        with pytest.raises(EvidenceError, match="increasing"):
            EvidenceContext("EURUSD", Timeframe.H1, df.iloc[::-1])

    def test_positions_and_times(self, ctx: EvidenceContext) -> None:
        assert ctx.pos_of(ctx.time_at(42)) == 42
        assert ctx.as_of == ctx.time_at(ctx.last_pos)
        with pytest.raises(EvidenceError):
            ctx.pos_of(datetime(2030, 1, 1, tzinfo=UTC))

    def test_memo_and_shared_pivots(self, ctx: EvidenceContext) -> None:
        assert ctx.atr() is ctx.atr()
        assert ctx.zigzag("minor") is ctx.zigzag("minor")
        assert ctx.swings(3) is ctx.swings(3)
        assert ctx.prefix(100).n == 101
        with pytest.raises(ConfigError):
            ctx.zigzag("cosmic")


# --- activation and snapshots -----------------------------------------------------------------------------


class TestActivation:
    def test_age_limit(self) -> None:
        c = bars([1.0] * 10)
        evs = [CrossUp().make(c, 9, Direction.BULL, 0.5), CrossUp().make(c, 5, Direction.BULL, 0.5)]
        active = activate(c, evs, {"test.cross_up": 3})
        assert [(a.age_bars, a.as_of) for a in active] == [(0, c.as_of)]

    def test_close_beyond_invalidation_deactivates(self) -> None:
        c = bars([1.0, 1.0, 1.2, 1.1, 0.95, 1.05])
        bull = CrossUp().make(c, 2, Direction.BULL, 0.5, invalidation=1.0)
        bear = CrossUp().make(c, 2, Direction.BEAR, 0.5, invalidation=1.25)
        kept = activate(c, [bull, bear], {"test.cross_up": 10})
        assert [a.evidence.direction for a in kept] == [Direction.BEAR]  # 0.95 closed below the bull level

    def test_detection_bar_itself_never_invalidates(self) -> None:
        c = bars([1.0, 0.5])
        ev = CrossUp().make(c, 1, Direction.BULL, 0.5, invalidation=1.0)
        assert len(activate(c, [ev], {"test.cross_up": 0})) == 1

    def test_snapshot_round_trip_and_tamper(self, ctx: EvidenceContext) -> None:
        engine = EvidenceEngine(
            DetectorRegistry([CrossUp()]), DetectorRegistry([CrossUp()]).plan(["test.cross_up"])
        )
        snap = engine.evaluate(ctx)
        text = snap.to_json()
        again = EvidenceSnapshot.from_json(text, expected_digest=snap.digest)
        assert again == snap and again.to_json() == text
        data = json.loads(text)
        data["as_of"] = ctx.time_at(5).isoformat()
        with pytest.raises(EvidenceError, match="altered"):
            EvidenceSnapshot.from_json(json.dumps(data), expected_digest=snap.digest)

    def test_snapshot_is_frozen_history(self) -> None:
        """A snapshot taken at bar t is unaffected by evidence that later bars produce."""
        df = random_ohlc(300, seed=5)
        registry = DetectorRegistry([CrossUp()])
        engine = EvidenceEngine(registry, registry.plan(["test.cross_up"]))
        early = engine.evaluate(context(df).prefix(150))
        late = engine.evaluate(context(df))
        assert early.as_of < late.as_of
        assert EvidenceSnapshot.from_json(early.to_json()) == early


# --- registry and engine ----------------------------------------------------------------------------------


class TestRegistry:
    def test_catalog_validation(self) -> None:
        with pytest.raises(EvidenceError, match="duplicate"):
            DetectorRegistry([CrossUp(), CrossUp()])
        with pytest.raises(EvidenceError, match="unknown"):
            DetectorRegistry([Confirmed()])

        class A(Counting):
            id = "test.a"
            depends_on = ("test.b",)

        class B(Counting):
            id = "test.b"
            depends_on = ("test.a",)

        with pytest.raises(EvidenceError, match="cycle"):
            DetectorRegistry([A(), B()])

    def test_plan_adds_prerequisites_first_but_reports_only_requested(self, ctx: EvidenceContext) -> None:
        registry = DetectorRegistry([Confirmed(), CrossUp(), Counting()])
        plan = registry.plan(["test.confirmed"])
        assert plan.order == ("test.cross_up", "test.confirmed")
        out = EvidenceEngine(registry, plan).scan(ctx)
        assert list(out) == ["test.confirmed"] and out["test.confirmed"]

    def test_disabled_detectors_are_never_executed(self, ctx: EvidenceContext) -> None:
        Counting.calls = 0
        registry = DetectorRegistry([CrossUp(), Counting()])
        cfg = EvidenceConfig(detectors={"test.counting": DetectorSettings(enabled=False)})
        engine = EvidenceEngine(registry, registry.plan_from_config(cfg))
        engine.scan(ctx)
        assert Counting.calls == 0 and "test.counting" not in engine.stats
        assert engine.stats["test.cross_up"].calls == 1

    def test_only_narrows_and_default_disabled(self) -> None:
        registry = DetectorRegistry([CrossUp(), Counting()])
        assert registry.plan_from_config(EvidenceConfig(), only=["test.counting"]).outputs == {
            "test.counting"
        }
        off = EvidenceConfig(
            default_enabled=False, detectors={"test.cross_up": DetectorSettings(enabled=True)}
        )
        assert registry.plan_from_config(off).outputs == {"test.cross_up"}

    def test_params_are_validated(self) -> None:
        registry = DetectorRegistry([CrossUp()])
        cfg = EvidenceConfig(detectors={"test.cross_up": DetectorSettings(params={"n": 8})})
        assert registry.plan_from_config(cfg).params["test.cross_up"].n == 8  # type: ignore[attr-defined]
        for bad in ({"n": 1}, {"nn": 5}):
            with pytest.raises(ConfigError, match="invalid params"):
                registry.plan_from_config(
                    EvidenceConfig(detectors={"test.cross_up": DetectorSettings(params=bad)})
                )

    def test_overrides_lay_over_the_config_params(self) -> None:
        registry = DetectorRegistry([CrossUp(), Counting()])
        cfg = EvidenceConfig(
            detectors={"test.cross_up": DetectorSettings(params={"n": 8, "max_age_bars": 7})}
        )
        plan = registry.plan_from_config(cfg, overrides={"test.cross_up": {"n": 5}})
        assert plan.params["test.cross_up"].n == 5  # type: ignore[attr-defined]
        assert plan.params["test.cross_up"].max_age_bars == 7  # kept from config.yaml
        off = EvidenceConfig(detectors={"test.counting": DetectorSettings(enabled=False)})
        assert (
            "test.counting" not in registry.plan_from_config(off, overrides={"test.counting": {}}).outputs
        )  # an override never enables a detector
        with pytest.raises(ConfigError, match="unknown detector"):
            registry.plan_from_config(EvidenceConfig(detectors={"test.typo": DetectorSettings()}))

    def test_params_change_the_digest(self) -> None:
        registry = DetectorRegistry([CrossUp()])
        a = registry.plan(["test.cross_up"])
        b = registry.plan(["test.cross_up"], {"test.cross_up": CrossParams(n=9)})
        assert a.params_digest != b.params_digest

    def test_engine_rejects_mislabelled_records(self, ctx: EvidenceContext) -> None:
        registry = DetectorRegistry([Mislabel()])
        with pytest.raises(EvidenceError, match="labelled"):
            EvidenceEngine(registry, registry.plan(["test.mislabel"])).scan(ctx)


# --- look-ahead harness -----------------------------------------------------------------------------------


class TestHarness:
    def test_causal_detectors_pass(self) -> None:
        assert assert_no_lookahead(CrossUp())
        assert assert_no_lookahead(Confirmed(), catalog=[CrossUp()])

    def test_harness_catches_a_peeking_detector(self) -> None:
        with pytest.raises(AssertionError, match=r"depend on later bars|changed earlier records"):
            assert_no_lookahead(Peeker())
