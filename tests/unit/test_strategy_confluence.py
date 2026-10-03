from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.config import AppConfig, ConfluenceConfig, StrategiesConfig, StrategyEntry
from app.core.clock import ManualClock
from app.core.enums import Action, Timeframe
from app.core.errors import ConfigError
from app.evidence.catalog import default_registry as evidence_registry
from app.evidence.confluence import Relation, confluence_score, noisy_or, relation
from app.evidence.framework import ActiveEvidence, Direction, Evidence, EvidenceSnapshot, Family, Tier
from app.evidence.registry import EvidenceEngine
from app.strategy.catalog import default_registry
from app.strategy.context_builder import ContextBuilder
from app.strategy.enrichment import enrich
from app.strategy.signal_models import Signal, StrategyContext
from tests.strategy_data import StubCandles, random_m15, resample
from tests.unit.test_strategy_example import ctx as pullback_ctx
from tests.unit.test_strategy_example import evaluate as evaluate_pullback
from tests.unit.test_strategy_models import BAR, make_context, make_signal

CFG = ConfluenceConfig()


def item(
    detector: str = "momentum.rsi_divergence",
    family: Family = Family.MOMENTUM,
    direction: Direction = Direction.BULL,
    quality: float = 1.0,
    tier: Tier = Tier.T1,
    tf: Timeframe = Timeframe.M15,
    level: float = 1.1,
) -> ActiveEvidence:
    ev = Evidence(
        detector_id=detector,
        detector_version=1,
        family=family,
        tier=tier,
        name=detector,
        i18n_key=f"evidence.{detector}",
        symbol="EURUSD",
        timeframe=tf,
        direction=direction,
        detected_at=BAR,
        quality=quality,
        details=(("level", level),),
    )
    return ActiveEvidence(ev, BAR, 0)


def score(items: list[ActiveEvidence], sign: int = 1, share: float = 0.0, **kw: object) -> float:
    return confluence_score(items, sign, condition_share=share, config=CFG, **kw).total  # type: ignore[arg-type]


class TestConfluenceScore:
    def test_relation(self) -> None:
        assert relation(Direction.BULL, 1) is Relation.SUPPORTS
        assert relation(Direction.BEAR, 1) is Relation.CONFLICTS
        assert relation(Direction.BEAR, -1) is Relation.SUPPORTS
        assert relation(Direction.NEUTRAL, 1) is Relation.NEUTRAL
        assert relation(Direction.BULL, 0) is Relation.NEUTRAL

    def test_core_only(self) -> None:
        assert score([], share=1.0) == pytest.approx(CFG.core_weight)
        assert score([], share=0.5) == pytest.approx(CFG.core_weight / 2)

    def test_one_item_adds_family_weight_times_quality(self) -> None:
        assert score([item(quality=0.5)]) == pytest.approx(8.0 * 0.5)

    def test_tier_scales_quality(self) -> None:
        heuristic = item("elliott.wave", Family.ELLIOTT, tier=Tier.T3)
        assert score([heuristic]) == pytest.approx(4.0 * 0.6)

    def test_correlated_items_are_capped_by_their_family(self) -> None:
        """Five agreeing oscillators never add more than the MOMENTUM weight (double-counting control)."""
        five = [item(f"momentum.x{i}", quality=0.9, level=i) for i in range(5)]
        one = score(five[:1])
        assert score(five) <= 8.0
        assert score(five) < 5 * one
        assert score(five) == pytest.approx(8.0 * noisy_or([0.9] * 5))

    def test_independent_families_add_up(self) -> None:
        fib = item("fib.retracement", Family.FIBONACCI, quality=0.8)
        pattern = item("chart.double_bottom", Family.CHART_PATTERN, tier=Tier.T2, quality=0.8)
        assert score([fib, pattern]) == pytest.approx(12 * 0.8 + 12 * 0.9 * 0.8)

    def test_same_instance_counts_once(self) -> None:
        a = item(quality=0.6)
        assert score([a, a, a]) == pytest.approx(score([a]))

    def test_same_instance_keeps_best_quality(self) -> None:
        low, high = item(quality=0.4), item(quality=0.7)
        assert low.evidence.evidence_id == high.evidence.evidence_id  # quality is not part of the identity
        assert score([low, high]) == pytest.approx(score([high]))

    def test_conflicts_are_penalized(self) -> None:
        support = item("fib.retracement", Family.FIBONACCI)
        against = item("momentum.rsi_divergence", direction=Direction.BEAR, quality=0.5)
        expected = 40 + 12 - 0.75 * 8 * 0.5
        assert score([support, against], share=1.0) == pytest.approx(expected)

    def test_core_family_support_is_not_counted_twice_but_conflict_is(self) -> None:
        trend_up = item("trend.ma_alignment", Family.TREND)
        trend_down = item("structure.choch", Family.TREND, direction=Direction.BEAR, quality=0.5)
        assert score([trend_up], share=1.0, core_families={Family.TREND}) == pytest.approx(40)
        assert score([trend_up], share=1.0) == pytest.approx(55)
        with_conflict = score([trend_up, trend_down], share=1.0, core_families={Family.TREND})
        assert with_conflict == pytest.approx(40 - 0.75 * 15 * 0.5)

    def test_clipped_to_0_100(self) -> None:
        many = [item(f"d{i}", fam, quality=1.0) for i, fam in enumerate(Family)]
        assert score(many, share=1.0) == 100.0
        against = [item(f"d{i}", fam, Direction.BEAR) for i, fam in enumerate(Family)]
        assert score(against) == 0.0

    def test_contributions_explain_the_total(self) -> None:
        c = confluence_score(
            [item("fib.retracement", Family.FIBONACCI), item(direction=Direction.BEAR, quality=0.5)],
            1,
            condition_share=1.0,
            config=CFG,
        )
        rows = dict(c.contributions)
        assert c.contributions[0][0] == "core"
        assert sum(rows.values()) == pytest.approx(c.total)
        assert rows["MOMENTUM"] < 0 < rows["FIBONACCI"]
        assert c.supporting_families == 1

    def test_unknown_family_in_config_is_rejected(self) -> None:
        bad = ConfluenceConfig(family_weights={"ASTROLOGY": 5.0})
        with pytest.raises(ConfigError):
            confluence_score([], 1, condition_share=0.0, config=bad)

    def test_config_bounds(self) -> None:
        with pytest.raises(ValueError):
            ConfluenceConfig(tier_weights={"T1": 2.0})
        with pytest.raises(ValueError):
            ConfluenceConfig(family_weights={"TREND": -1.0})


def snapshot(tf: Timeframe, *items: ActiveEvidence) -> EvidenceSnapshot:
    return EvidenceSnapshot("EURUSD", tf, BAR, tuple(items), (), "digest")


class TestEnrichment:
    def context(self, *snaps: EvidenceSnapshot) -> StrategyContext:
        return StrategyContext(make_context(), {}, BAR, None, {s.timeframe: s for s in snaps})

    def test_attaches_every_timeframe_with_relations(self) -> None:
        htf = item("trend.ma_alignment", Family.TREND, tf=Timeframe.H1)
        against = item(direction=Direction.BEAR)
        neutral = item("volatility.squeeze", Family.VOLATILITY_VOLUME, Direction.NEUTRAL)
        ctx = self.context(snapshot(Timeframe.H1, htf), snapshot(Timeframe.M15, against, neutral))
        sig = enrich(make_signal(evidence=()), ctx, CFG)
        relations = {e.item.evidence.detector_id: e.relation for e in sig.evidence}
        assert relations == {
            "trend.ma_alignment": Relation.SUPPORTS,
            "momentum.rsi_divergence": Relation.CONFLICTS,
            "volatility.squeeze": Relation.NEUTRAL,
        }
        # make_signal: conditions weigh 2 passed of 3 -> core 40 * 2/3
        assert sig.setup_strength == pytest.approx(40 * 2 / 3 + 15 - 0.75 * 8)
        assert Signal.from_json(sig.to_json()) == sig

    def test_hold_keeps_its_checklist_strength(self) -> None:
        hold = make_signal(
            action=Action.HOLD, entry_price=None, stop_loss=None, take_profit=None, evidence=()
        )
        sig = enrich(hold, self.context(snapshot(Timeframe.M15, item())), CFG)
        assert sig.setup_strength == hold.setup_strength
        assert sig.confluence == ()
        assert {e.relation for e in sig.evidence} == {Relation.NEUTRAL}

    def test_strategy_set_enriches_with_core_families(self) -> None:
        trend = item("trend.ma_alignment", Family.TREND, tf=Timeframe.H1)
        fib = item("fib.retracement", Family.FIBONACCI)
        base = pullback_ctx()
        ctx = StrategyContext(
            base.market,
            base.frames,
            base.now_utc,
            base.spec,
            {Timeframe.H1: snapshot(Timeframe.H1, trend), Timeframe.M15: snapshot(Timeframe.M15, fib)},
        )
        built = default_registry().from_config(
            StrategiesConfig(items=[StrategyEntry(name="example_trend_pullback")]), AppConfig().timeframes
        )
        sig = built.evaluate(ctx)[0]
        assert sig.action is Action.BUY
        assert evaluate_pullback(base).setup_strength == 100.0  # checklist only
        assert sig.setup_strength == pytest.approx(40 + 12)  # TREND is core: no extra support from it
        assert dict(sig.confluence) == {"core": 40.0, "FIBONACCI": 12.0}


class TestBuilderEvidence:
    def test_each_timeframe_is_scanned_up_to_the_decision_time(self) -> None:
        m15 = random_m15(900, seed=11)
        frames = {Timeframe.M15: m15, Timeframe.H1: resample(m15, Timeframe.H1)}
        now = datetime(2026, 9, 8, 10, 20, tzinfo=UTC)
        cfg = AppConfig()
        engine = EvidenceEngine(evidence_registry(), evidence_registry().plan_from_config(cfg.evidence))
        builder = ContextBuilder(StubCandles(frames, now), cfg, ManualClock(now), evidence=engine)
        ctx = builder.build("EURUSD")
        assert set(ctx.evidence) == {Timeframe.M15, Timeframe.H1}
        assert ctx.evidence[Timeframe.M15].as_of == datetime(2026, 9, 8, 10, 15, tzinfo=UTC)
        assert ctx.evidence[Timeframe.H1].as_of == datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
        for snap in ctx.evidence.values():
            assert all(a.evidence.detected_at <= snap.as_of for a in snap.items)
        assert ctx.all_evidence(), "a random walk of 900 bars should leave some active evidence"
        h1_close = pd.Timestamp(ctx.frame(Timeframe.H1).index[-1]).to_pydatetime()
        assert h1_close <= ctx.decision_time_utc < h1_close + timedelta(hours=1)
