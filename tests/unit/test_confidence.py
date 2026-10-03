from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.advisory.confidence import (
    BucketModel,
    Calibration,
    LogisticModel,
    Outcome,
    Query,
    Source,
    WinProbability,
    break_even_probability,
    build_win_probability,
    expected_value_r,
    random_baseline,
    rr_band,
    shapley,
    strength_bucket,
    subset_setup_strength,
    track_records,
    walk_forward,
)
from app.advisory.stats_math import beta_interval, beta_ppf, betainc, brier, log_loss, wilson_interval
from app.config import ConfluenceConfig
from app.evidence.framework import Direction, EvidenceSnapshot, Family
from app.strategy.enrichment import enrich
from app.strategy.signal_models import StrategyContext
from tests.unit.test_strategy_confluence import item
from tests.unit.test_strategy_models import BAR, make_context, make_signal

T0 = datetime(2025, 1, 1, tzinfo=UTC)
FIB = "ev:FIBONACCI:fib.retracement"
WPAT = "ev:CHART_PATTERN:pattern.double_bottom"
RSI = "ev:MOMENTUM:momentum.rsi_divergence"
TREND = "ev:TREND:trend.ma_alignment"


class TestStatsMath:
    def test_betainc_and_quantiles(self) -> None:
        assert betainc(1, 1, 0.3) == pytest.approx(0.3)
        assert betainc(5, 5, 0.5) == pytest.approx(0.5)
        assert betainc(2, 3, 0.4) == pytest.approx(0.5248, abs=1e-4)  # 1 - (1-x)^3 (1+3x) at x = 0.4
        assert beta_ppf(0.5, 2, 2) == pytest.approx(0.5, abs=1e-9)
        samples = np.random.default_rng(1).beta(3, 7, 400_000)
        low, high = beta_interval(3, 7)
        assert low == pytest.approx(np.quantile(samples, 0.05), abs=3e-3)
        assert high == pytest.approx(np.quantile(samples, 0.95), abs=3e-3)

    def test_wilson_and_scores(self) -> None:
        low, high = wilson_interval(5, 10)
        assert low < 0.5 < high and 0.5 - low == pytest.approx(high - 0.5)
        assert wilson_interval(0, 0) == (0.0, 1.0)
        assert brier([1.0, 0.0], [1, 0]) == 0.0 and log_loss([0.5], [1]) == pytest.approx(np.log(2))


class TestBaselines:
    def test_numbers(self) -> None:
        assert random_baseline(2.0) == pytest.approx(100 / 3)
        assert break_even_probability(2.0, 0.1) == pytest.approx(110 / 3)
        assert expected_value_r(50, 2.0, 0.1) == pytest.approx(0.4)
        assert strength_bucket(64.9) == "50-65" and strength_bucket(80) == "80+"
        assert rr_band(1.49) == "<1.5" and rr_band(2.0) == "2-3" and rr_band(5) == "3+"


def outcomes(n: int, p: float, *, seed: int = 0, source: Source = Source.LIVE, **kw: object) -> list[Outcome]:
    rng = np.random.default_rng(seed)
    base = {"strategy": "s", "symbol": "EURUSD", "asset_class": "FOREX_MAJOR", "strength": 70.0, "rr": 2.0}
    base |= kw  # type: ignore[arg-type]
    return [Outcome(win=bool(rng.random() < p), source=source, **base) for _ in range(n)]  # type: ignore[arg-type]


Q = Query("s", "EURUSD", "FOREX_MAJOR", 70.0, 2.0)


class TestBucketModel:
    def test_no_data_is_the_random_baseline(self) -> None:
        est = BucketModel().fit([]).predict(Q)
        assert est.p == pytest.approx(100 / 3) and est.insufficient and est.calibration is Calibration.NONE
        assert est.low < est.p < est.high

    def test_recovers_a_known_probability_within_its_interval(self) -> None:
        est = BucketModel().fit(outcomes(3000, 0.45, seed=3)).predict(Q)
        assert est.low < 45 < est.high and abs(est.p - 45) < 2.5
        assert not est.insufficient and est.calibration is Calibration.LIVE
        assert est.high - est.low < 4

    def test_thin_leaves_pool_toward_the_asset_class(self) -> None:
        rows = outcomes(400, 0.5, seed=1, symbol="GBPUSD") + outcomes(3, 1.0, symbol="EURUSD")
        est = BucketModel(kappa=20).fit(rows).predict(Q)
        assert 50 < est.p < 70  # 3 wins of 3 barely move a prior near 50%
        assert est.n == 3 and est.n_pooled == 403

    def test_replay_is_a_capped_prior(self) -> None:
        replay = outcomes(1000, 0.8, seed=2, source=Source.REPLAY)
        est = BucketModel(replay_cap=50).fit(replay).predict(Q)
        assert est.n_pooled == pytest.approx(50) and est.calibration is Calibration.REPLAY
        mixed = BucketModel(replay_cap=50).fit(replay + outcomes(500, 0.4, seed=4)).predict(Q)
        assert mixed.calibration is Calibration.MIXED and mixed.p < 50  # live data dominates the capped prior


def synthetic(n: int, seed: int = 0, *, informative: bool = True) -> list[Outcome]:
    """Outcomes where Fibonacci and the W pattern help, RSI divergence against the trade hurts."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        feats = {
            FIB: float(rng.random() < 0.5),
            WPAT: float(rng.random() < 0.3),
            RSI: -float(rng.random() < 0.3),
        }
        z = -0.7 + (1.2 * feats[FIB] + 0.9 * feats[WPAT] + 0.8 * feats[RSI] if informative else 0.0)
        win = bool(rng.random() < 1 / (1 + np.exp(-z)))
        rows.append(
            Outcome("s", "EURUSD", "FOREX_MAJOR", 70.0, 2.0, win, features=feats, at=T0 + timedelta(hours=i))
        )
    return rows


class TestEvidenceModel:
    def test_irls_recovers_coefficients(self) -> None:
        rng = np.random.default_rng(5)
        x = rng.normal(size=(20_000, 2))
        y = (rng.random(20_000) < 1 / (1 + np.exp(-(0.3 + 1.5 * x[:, 0] - 0.8 * x[:, 1])))).astype(float)
        m = LogisticModel.fit(["a", "b"], x, y, l2=1e-6)
        assert m.intercept == pytest.approx(0.3, abs=0.06)
        assert m.coef == pytest.approx([1.5, -0.8], abs=0.06)
        strong = LogisticModel.fit(["a", "b"], x, y, l2=1e5)
        assert np.all(np.abs(strong.coef) < np.abs(m.coef))  # the penalty shrinks

    def test_selection_prefers_the_model_that_wins_out_of_sample(self) -> None:
        assert walk_forward(synthetic(3000, 1), min_group=50).use_evidence
        assert not walk_forward(synthetic(3000, 2, informative=False), min_group=50).use_evidence

    def test_bucket_only_says_needs_more_history(self) -> None:
        wp = build_win_probability(synthetic(600, 3, informative=False), min_group=50)
        assert not wp.uses_evidence
        exp = wp.explain(Query("s", "EURUSD", "FOREX_MAJOR", 70.0, 2.0, features={FIB: 1.0}))
        assert exp.contributions is None and exp.base_rate is None and exp.estimate.source == "bucket"


@pytest.fixture(scope="module")
def wp() -> WinProbability:
    model = build_win_probability(synthetic(4000, 7), min_group=50)
    assert model.uses_evidence
    return model


class TestAttribution:
    def test_contributions_sum_to_p_minus_base(self, wp: WinProbability) -> None:
        q = Query("s", "EURUSD", "FOREX_MAJOR", 70.0, 2.0, features={FIB: 1.0, WPAT: 1.0, RSI: -1.0})
        exp = wp.explain(q)
        assert exp.base_rate is not None and exp.contributions is not None
        assert sum(c.points for c in exp.contributions) == pytest.approx(
            exp.estimate.p - exp.base_rate, abs=1e-9
        )
        by = {c.feature: c.points for c in exp.contributions}
        assert by[FIB] > 0 and by[WPAT] > 0 and by[RSI] < 0
        assert exp.top(1)[0].feature == FIB and exp.estimate.source == "evidence"

    def test_disabled_theories_are_neutral_and_not_explained(self, wp: WinProbability) -> None:
        q = Query("s", "EURUSD", "FOREX_MAJOR", 70.0, 2.0, features={FIB: 1.0, WPAT: 1.0, RSI: -1.0})
        full = wp.explain(q)
        subset = wp.explain(q, enabled_detectors={"fib.retracement"})
        assert subset.contributions is not None and [c.feature for c in subset.contributions] == [FIB]
        assert subset.base_rate == pytest.approx(full.base_rate)
        assert subset.estimate.p != pytest.approx(full.estimate.p)

    def test_sampling_is_exactly_efficient_for_many_players(self) -> None:
        players = [f"ev:F{i}:d{i}" for i in range(14)]
        weights = {p: (i - 6) / 10 for i, p in enumerate(players)}

        def value(s: frozenset[str]) -> float:
            z = sum(weights[p] for p in s)
            return 100 / (1 + np.exp(-z))

        phi = shapley(value, players, permutations=300, seed=42)
        assert sum(phi.values()) == pytest.approx(value(frozenset(players)) - value(frozenset()), abs=1e-9)
        assert phi == shapley(value, players, permutations=300, seed=42)  # seeded: reproducible

    def test_exact_shapley_of_an_additive_game(self) -> None:
        phi = shapley(lambda s: 10.0 * ("a" in s) + 3.0 * ("b" in s), ["a", "b"])
        assert phi == {"a": pytest.approx(10.0), "b": pytest.approx(3.0)}


class TestTrackRecords:
    def test_hit_rate_ci_and_lift(self) -> None:
        rows = [
            Outcome("s", "EURUSD", "FX", 70, 2, True, features={FIB: 1.0}),
            Outcome("s", "EURUSD", "FX", 70, 2, True, features={FIB: 1.0}),
            Outcome("s", "EURUSD", "FX", 70, 2, False, features={FIB: 1.0, RSI: -1.0}),
            Outcome("s", "EURUSD", "FX", 70, 2, False, features={}),
        ]
        rec = track_records(rows, group=lambda o: o.asset_class)
        fib = rec[(FIB, "FX")]
        assert (fib.n, fib.hits) == (3, 2) and fib.hit_rate == pytest.approx(200 / 3)
        assert fib.base_rate == 50 and fib.lift == pytest.approx(4 / 3)
        assert fib.low < fib.hit_rate < fib.high
        assert (RSI, "FX") not in rec  # conflicting evidence is not a supporting record


class TestSubsetStrength:
    def test_only_enabled_families_count(self) -> None:
        cfg = ConfluenceConfig()
        fib = item("fib.retracement", Family.FIBONACCI)
        trend = item("trend.ma_alignment", Family.TREND, direction=Direction.BULL)
        snap = EvidenceSnapshot("EURUSD", fib.evidence.timeframe, BAR, (fib, trend), (), "digest")
        ctx = StrategyContext(make_context(), {}, BAR, None, {snap.timeframe: snap})
        sig = enrich(make_signal(evidence=()), ctx, cfg)
        everything = subset_setup_strength(sig, set(Family), cfg)
        only_fib = subset_setup_strength(sig, {Family.FIBONACCI}, cfg)
        nothing = subset_setup_strength(sig, set(), cfg)
        assert everything == pytest.approx(sig.setup_strength)
        assert nothing < only_fib < everything
        assert nothing == pytest.approx(40 * 2 / 3)  # the checklist alone
