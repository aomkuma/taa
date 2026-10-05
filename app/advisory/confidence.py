"""Setup strength and explainable win probability (PLAN §A26, §A29, §A30; TAA-6B2).

Two numbers per opportunity:

- **Setup strength (0–100)** is the confluence score (TAA-307). :func:`subset_setup_strength` recomputes it
  over only the families a user enabled.
- **Win probability** = calibrated P(TP before SL), in percent.

**Bucket model** (:class:`BucketModel`, always available): a hierarchical Beta-binomial over
``strategy × symbol × strength bucket × RR band``, pooled by empirical Bayes with pseudo-count κ (default 20)
toward ``strategy × asset class × RR band`` → ``strategy × RR band`` → the random baseline ``1 / (1 + RR)``.
Each level's posterior mean is the next level's prior mean. REPLAY outcomes count at most ``replay_cap``
pseudo-trades per cell (§A27). The estimate carries a 90% credible interval, the leaf *n* and an
"insufficient data" flag when the ``strategy × asset class × RR band`` cell has fewer than ``min_trades``.

**Evidence model** (:class:`LogisticModel`): L2-regularized logistic regression fitted by IRLS (numpy only) on
named features. Conventions: ``ev:<FAMILY>:<detector_id>`` = quality × alignment (+ supports, − conflicts);
``ctx:n_families`` = the number of distinct supporting families, derived from the ``ev:`` features present;
any other ``ctx:`` feature (RR band, session, regime, HTF alignment one-hots) is context. It is used only
when walk-forward CV shows it beats the bucket model on both Brier score (by at least the relative
``margin``, so a model without real signal never wins on noise) and log loss (:func:`walk_forward`);
otherwise the bucket p is shown and contributions read "needs more history".

**Attribution:** Shapley values in probability space over the active ``ev:`` features. A player that is
"absent" takes its training mean (neutral imputation, also used for detectors a user disabled), and
``ctx:n_families`` is recomputed from the players present. The base rate is the value with no players, so the
contributions add up to ``p − base rate`` exactly (exact enumeration up to 10 players, seeded permutation
sampling above, which is still exactly efficient).
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from collections.abc import Callable, Collection, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import numpy as np

from app.advisory.stats_math import beta_interval, brier, log_loss, wilson_interval
from app.config import ConfluenceConfig
from app.evidence.confluence import Relation, confluence_score
from app.evidence.framework import Family
from app.strategy.signal_models import MarketContext, Signal, condition_strength

# --- baselines ----------------------------------------------------------------------------------------------


def random_baseline(rr: float) -> float:
    """P(TP first) of a random entry with this reward:risk, in percent (driftless random walk)."""
    return 100.0 / (1.0 + rr)


def break_even_probability(rr: float, cost_r: float = 0.0) -> float:
    """``(1 + c) / (1 + RR)`` in percent (R28): below it the expected value is negative."""
    return (1 + cost_r) / (1 + rr) * 100


def expected_value_r(p_percent: float, rr: float, cost_r: float = 0.0) -> float:
    """``EV(R) = p (RR + 1) − 1 − c``."""
    return p_percent / 100 * (rr + 1) - 1 - cost_r


# --- setup strength over a theory subset --------------------------------------------------------------------


def subset_setup_strength(
    signal: Signal,
    enabled: Collection[Family],
    config: ConfluenceConfig,
    core_families: Iterable[Family] = (),
) -> float:
    """The confluence score using only evidence of the *enabled* families (the checklist always counts)."""
    side = signal.side
    if side is None:
        return 0.0
    items = [e.item for e in signal.evidence if e.item.evidence.family in enabled]
    score = confluence_score(
        items,
        side.sign,
        condition_share=condition_strength(signal.conditions) / 100.0,
        config=config,
        core_families=core_families,
    )
    return score.total


# --- outcomes and buckets -----------------------------------------------------------------------------------


class Source(StrEnum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"


STRENGTH_EDGES = (50.0, 65.0, 80.0)
STRENGTH_LABELS = ("<50", "50-65", "65-80", "80+")
RR_EDGES = (1.5, 2.0, 3.0)
RR_LABELS = ("<1.5", "1.5-2", "2-3", "3+")


def _band(value: float, edges: Sequence[float], labels: Sequence[str]) -> str:
    for edge, label in zip(edges, labels, strict=False):
        if value < edge:
            return label
    return labels[-1]


def strength_bucket(strength: float) -> str:
    return _band(strength, STRENGTH_EDGES, STRENGTH_LABELS)


def rr_band(rr: float) -> str:
    """Rounded to 0.01 first, so a planned 2.0 computed as 1.99999 stays in the 2-3 band."""
    return _band(round(rr, 2), RR_EDGES, RR_LABELS)


def signal_features(signal: Signal, market: MarketContext) -> dict[str, float]:
    """Model features of an opportunity at signal time (stored with it, reused by training and replay).

    Per detector: the strongest supporting quality minus the strongest conflicting quality; context one-hots
    for the RR band, session and entry-TF regime; and whether the higher timeframe's trend agrees.
    """
    support: dict[str, float] = {}
    conflict: dict[str, float] = {}
    for e in signal.evidence:
        ev = e.item.evidence
        key = f"ev:{ev.family.value}:{ev.detector_id}"
        if e.relation is Relation.SUPPORTS:
            support[key] = max(support.get(key, 0.0), ev.quality)
        elif e.relation is Relation.CONFLICTS:
            conflict[key] = max(conflict.get(key, 0.0), ev.quality)
    features = {k: support.get(k, 0.0) - conflict.get(k, 0.0) for k in sorted(set(support) | set(conflict))}
    rr = signal.risk_reward
    if rr is not None:
        features[f"ctx:rr={rr_band(rr)}"] = 1.0
    features[f"ctx:session={market.session.value}"] = 1.0
    features[f"ctx:regime={market.entry.regime.value}"] = 1.0
    side = signal.side
    trend = market.higher.trend.value
    aligned = side is not None and trend == ("BULLISH" if side.sign > 0 else "BEARISH")
    features["ctx:htf_aligned"] = 1.0 if aligned else 0.0
    return features


@dataclass(frozen=True, slots=True)
class Outcome:
    """A resolved shadow or replay trade (TP first = win), with the features recorded at signal time."""

    strategy: str
    symbol: str
    asset_class: str
    strength: float
    rr: float
    win: bool
    source: Source = Source.LIVE
    features: Mapping[str, float] = field(default_factory=dict)
    at: datetime | None = None
    timeframe: str = ""


@dataclass(frozen=True, slots=True)
class Query:
    """What the probability is asked for: one opportunity's facts."""

    strategy: str
    symbol: str
    asset_class: str
    strength: float
    rr: float
    cost_r: float = 0.0
    features: Mapping[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class _Cell:
    live_wins: float = 0.0
    live_n: float = 0.0
    replay_wins: float = 0.0
    replay_n: float = 0.0

    def add(self, o: Outcome) -> None:
        if o.source is Source.REPLAY:
            self.replay_wins += o.win
            self.replay_n += 1
        else:
            self.live_wins += o.win
            self.live_n += 1

    def counts(self, replay_cap: float) -> tuple[float, float]:
        f = min(1.0, replay_cap / self.replay_n) if self.replay_n > 0 else 0.0
        return self.live_wins + f * self.replay_wins, self.live_n + f * self.replay_n


class Calibration(StrEnum):
    NONE = "NONE"
    REPLAY = "REPLAY"  # "backtest-calibrated"
    LIVE = "LIVE"
    MIXED = "MIXED"


@dataclass(frozen=True, slots=True)
class ProbabilityEstimate:
    p: float  # percent
    low: float  # 90% interval, percent
    high: float
    n: float  # effective outcomes in the leaf cell
    n_pooled: float  # ... in the strategy × asset class × RR band cell
    insufficient: bool
    calibration: Calibration
    source: str = "bucket"  # or "evidence"


class BucketModel:
    def __init__(self, *, kappa: float = 20.0, min_trades: int = 30, replay_cap: float = 50.0) -> None:
        self.kappa = kappa
        self.min_trades = min_trades
        self.replay_cap = replay_cap
        self.cells: dict[tuple[Hashable, ...], _Cell] = defaultdict(_Cell)

    @staticmethod
    def keys(
        strategy: str, symbol: str, asset_class: str, strength: float, rr: float
    ) -> list[tuple[Hashable, ...]]:
        band = rr_band(rr)
        return [
            ("strategy", strategy, band),
            ("class", strategy, asset_class, band),
            ("leaf", strategy, symbol, strength_bucket(strength), band),
        ]

    def fit(self, outcomes: Iterable[Outcome]) -> BucketModel:
        self.cells.clear()
        for o in outcomes:
            for key in self.keys(o.strategy, o.symbol, o.asset_class, o.strength, o.rr):
                self.cells[key].add(o)
        return self

    def posterior(self, q: Query) -> tuple[float, float]:
        """Beta(a, b) of the leaf cell after pooling down the hierarchy."""
        mean = random_baseline(q.rr) / 100
        a = b = 1.0
        for key in self.keys(q.strategy, q.symbol, q.asset_class, q.strength, q.rr):
            cell = self.cells.get(key)
            wins, n = cell.counts(self.replay_cap) if cell else (0.0, 0.0)
            a = self.kappa * mean + wins
            b = self.kappa * (1 - mean) + (n - wins)
            mean = a / (a + b)
        return a, b

    def mean(self, q: Query) -> float:
        """The posterior mean in [0, 1] (no interval: cheap enough for cross-validation loops)."""
        a, b = self.posterior(q)
        return a / (a + b)

    def predict(self, q: Query) -> ProbabilityEstimate:
        a, b = self.posterior(q)
        low, high = beta_interval(a, b, 0.9)
        keys = self.keys(q.strategy, q.symbol, q.asset_class, q.strength, q.rr)
        leaf, pooled = self.cells.get(keys[2]), self.cells.get(keys[1])
        n_leaf = leaf.counts(self.replay_cap)[1] if leaf else 0.0
        n_pooled = pooled.counts(self.replay_cap)[1] if pooled else 0.0
        if pooled is None or (pooled.live_n == 0 and pooled.replay_n == 0):
            calibration = Calibration.NONE
        elif pooled.live_n == 0:
            calibration = Calibration.REPLAY
        elif pooled.replay_n == 0:
            calibration = Calibration.LIVE
        else:
            calibration = Calibration.MIXED
        return ProbabilityEstimate(
            p=100 * a / (a + b),
            low=100 * low,
            high=100 * high,
            n=n_leaf,
            n_pooled=n_pooled,
            insufficient=n_pooled < self.min_trades,
            calibration=calibration,
        )


# --- evidence model -----------------------------------------------------------------------------------------

N_FAMILIES = "ctx:n_families"


def is_player(name: str) -> bool:
    return name.startswith("ev:")


def feature_family(name: str) -> str:
    """``ev:FIBONACCI:fib.retracement`` → ``FIBONACCI``."""
    return name.split(":", 2)[1]


def supporting_families(features: Mapping[str, float]) -> int:
    return len({feature_family(k) for k, v in features.items() if is_player(k) and v > 0})


def with_derived(features: Mapping[str, float]) -> dict[str, float]:
    return dict(features) | {N_FAMILIES: float(supporting_families(features))}


def _sigmoid(z: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


@dataclass(frozen=True)
class LogisticModel:
    names: tuple[str, ...]
    coef: np.ndarray
    intercept: float
    means: np.ndarray  # training means, for neutral imputation
    l2: float
    n: int
    active: np.ndarray | None = None  # training share of rows where each feature is > 0

    @classmethod
    def fit(
        cls,
        names: Sequence[str],
        x: np.ndarray,
        y: np.ndarray,
        weights: np.ndarray | None = None,
        *,
        l2: float = 1.0,
        max_iter: int = 100,
        tol: float = 1e-9,
    ) -> LogisticModel:
        """Iteratively reweighted least squares with an L2 penalty on the coefficients (not the intercept)."""
        n, d = x.shape
        w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
        design = np.hstack([np.ones((n, 1)), x])
        penalty = l2 * np.eye(d + 1)
        penalty[0, 0] = 0.0
        beta = np.zeros(d + 1)
        for _ in range(max_iter):
            p = np.asarray(_sigmoid(design @ beta))
            s = np.clip(p * (1 - p), 1e-9, None) * w
            gradient = design.T @ (w * (y - p)) - penalty @ beta
            hessian = design.T @ (design * s[:, None]) + penalty
            step = np.linalg.solve(hessian, gradient)
            beta = beta + step
            if float(np.max(np.abs(step))) < tol:
                break
        means = np.average(x, axis=0, weights=w) if n else np.zeros(d)
        active = np.average((x > 0).astype(float), axis=0, weights=w) if n else np.zeros(d)
        return cls(tuple(names), beta[1:], float(beta[0]), means, l2, n, active)

    def vector(self, features: Mapping[str, float]) -> np.ndarray:
        return np.array([features.get(name, 0.0) for name in self.names], dtype=float)

    def predict(self, features: Mapping[str, float]) -> float:
        """P(win) in [0, 1] for named features (missing names count as 0)."""
        return float(_sigmoid(self.intercept + float(self.vector(features) @ self.coef)))

    def mean_of(self, name: str) -> float:
        return float(self.means[self.names.index(name)]) if name in self.names else 0.0

    def active_rate(self, name: str) -> float:
        if self.active is None or name not in self.names:
            return 0.0
        return float(self.active[self.names.index(name)])


def design_matrix(names: Sequence[str], rows: Sequence[Mapping[str, float]]) -> np.ndarray:
    return np.array([[r.get(n, 0.0) for n in names] for r in rows], dtype=float).reshape(
        len(rows), len(names)
    )


def feature_names(outcomes: Iterable[Outcome]) -> list[str]:
    names = {k for o in outcomes for k in o.features}
    names.add(N_FAMILIES)
    return sorted(names)


def fit_logistic(
    outcomes: Sequence[Outcome], *, l2: float = 1.0, replay_weight: float = 0.5
) -> LogisticModel | None:
    if not outcomes:
        return None
    names = feature_names(outcomes)
    rows = [with_derived(o.features) for o in outcomes]
    x = design_matrix(names, rows)
    y = np.array([float(o.win) for o in outcomes])
    w = np.array([replay_weight if o.source is Source.REPLAY else 1.0 for o in outcomes])
    return LogisticModel.fit(names, x, y, w, l2=l2)


GroupKey = Callable[[Outcome | Query], Hashable]


def default_group(item: Outcome | Query) -> Hashable:
    return (item.strategy, item.asset_class)


@dataclass
class EvidenceModelSet:
    """One model per group (strategy × asset class by default) with a pooled fallback for thin groups."""

    models: dict[Hashable, LogisticModel]
    pooled: LogisticModel | None
    group: GroupKey = default_group

    @classmethod
    def fit(
        cls,
        outcomes: Sequence[Outcome],
        *,
        group: GroupKey = default_group,
        min_group: int = 200,
        l2: float = 1.0,
        replay_weight: float = 0.5,
    ) -> EvidenceModelSet:
        by_group: dict[Hashable, list[Outcome]] = defaultdict(list)
        for o in outcomes:
            by_group[group(o)].append(o)
        models = {
            k: m
            for k, rows in by_group.items()
            if len(rows) >= min_group and (m := fit_logistic(rows, l2=l2, replay_weight=replay_weight))
        }
        return cls(models, fit_logistic(outcomes, l2=l2, replay_weight=replay_weight), group)

    def model_for(self, q: Query) -> LogisticModel | None:
        return self.models.get(self.group(q), self.pooled)


# --- model selection ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CVReport:
    folds: int
    n_test: int
    brier_bucket: float
    brier_evidence: float
    log_loss_bucket: float
    log_loss_evidence: float
    margin: float = 0.0  # required relative Brier improvement of the evidence model
    # out-of-sample (p_bucket, p_evidence, outcome) per test row, for reliability data; not persisted
    predictions: tuple[tuple[float, float, float], ...] = field(default=(), compare=False, repr=False)

    @property
    def use_evidence(self) -> bool:
        return (
            self.n_test > 0
            and self.brier_evidence < self.brier_bucket * (1 - self.margin)
            and self.log_loss_evidence <= self.log_loss_bucket
        )


def _query(o: Outcome) -> Query:
    return Query(o.strategy, o.symbol, o.asset_class, o.strength, o.rr, features=o.features)


def walk_forward(
    outcomes: Sequence[Outcome],
    *,
    folds: int = 5,
    bucket: Callable[[], BucketModel] = BucketModel,
    l2: float = 1.0,
    min_group: int = 200,
    margin: float = 0.0,
) -> CVReport:
    """Expanding-window CV in time order: train on everything before a fold, test on the fold (LIVE only)."""
    ordered = sorted(outcomes, key=lambda o: (o.at is None, o.at.timestamp() if o.at else 0.0))
    chunks = np.array_split(np.arange(len(ordered)), folds + 1)
    pb: list[float] = []
    pe: list[float] = []
    ys: list[float] = []
    for k in range(1, folds + 1):
        train = [ordered[i] for c in chunks[:k] for i in c]
        test = [ordered[i] for i in chunks[k] if ordered[i].source is Source.LIVE]
        if not train or not test:
            continue
        bm = bucket().fit(train)
        em = EvidenceModelSet.fit(train, l2=l2, min_group=min_group)
        for o in test:
            q = _query(o)
            pb.append(bm.mean(q))
            model = em.model_for(q)
            pe.append(model.predict(with_derived(o.features)) if model else pb[-1])
            ys.append(float(o.win))
    return CVReport(
        folds,
        len(ys),
        brier(pb, ys),
        brier(pe, ys),
        log_loss(pb, ys),
        log_loss(pe, ys),
        margin,
        tuple(zip(pb, pe, ys, strict=True)),
    )


# --- attribution --------------------------------------------------------------------------------------------


def shapley(
    value: Callable[[frozenset[str]], float],
    players: Sequence[str],
    *,
    exact_max: int = 10,
    permutations: int = 2000,
    seed: int = 0,
) -> dict[str, float]:
    """Shapley values of *value* over *players*; they sum to ``value(all) − value(∅)``."""
    players = list(players)
    k = len(players)
    if k == 0:
        return {}
    cache: dict[frozenset[str], float] = {}

    def v(s: frozenset[str]) -> float:
        if s not in cache:
            cache[s] = value(s)
        return cache[s]

    phi = dict.fromkeys(players, 0.0)
    if k <= exact_max:
        fact = [math.factorial(i) for i in range(k + 1)]
        for player in players:
            others = [p for p in players if p != player]
            for size in range(k):
                weight = fact[size] * fact[k - size - 1] / fact[k]
                for subset in itertools.combinations(others, size):
                    base = frozenset(subset)
                    phi[player] += weight * (v(base | {player}) - v(base))
        return phi
    rng = np.random.default_rng(seed)
    for _ in range(permutations):
        order = [players[i] for i in rng.permutation(k)]
        s: frozenset[str] = frozenset()
        before = v(s)
        for player in order:
            s = s | {player}
            after = v(s)
            phi[player] += after - before
            before = after
    return {p: total / permutations for p, total in phi.items()}


@dataclass(frozen=True, slots=True)
class Contribution:
    feature: str
    family: str
    detector: str
    points: float  # percentage points of win probability


@dataclass(frozen=True, slots=True)
class Explanation:
    estimate: ProbabilityEstimate
    base_rate: float | None  # percent; None when the bucket model is used
    contributions: tuple[Contribution, ...] | None  # None: "needs more history"
    random_baseline: float
    break_even: float
    ev_r: float

    def top(self, n: int = 3) -> tuple[Contribution, ...]:
        if not self.contributions:
            return ()
        return tuple(sorted(self.contributions, key=lambda c: (-abs(c.points), c.feature))[:n])


@dataclass
class WinProbability:
    """The bucket model, an optional evidence model, and the CV verdict that chooses between them."""

    bucket: BucketModel
    evidence: EvidenceModelSet | None = None
    report: CVReport | None = None
    shapley_seed: int = 0

    @property
    def uses_evidence(self) -> bool:
        return self.evidence is not None and self.report is not None and self.report.use_evidence

    def explain(
        self, q: Query, enabled_detectors: Collection[str] | None = None, *, contributions: bool = True
    ) -> Explanation:
        """*enabled_detectors* (a user's theory subset): other ``ev:`` features are neutrally imputed.
        ``contributions=False`` skips the Shapley split (lists need only the %; ``contributions`` is None)."""
        estimate = self.bucket.predict(q)
        model = self.evidence.model_for(q) if self.uses_evidence and self.evidence else None
        base: float | None = None
        parts: tuple[Contribution, ...] | None = None
        if model is not None:
            active = {
                k: v
                for k, v in q.features.items()
                if is_player(k)
                and v != 0
                and (enabled_detectors is None or k.split(":", 2)[2] in enabled_detectors)
            }
            context = {k: v for k, v in q.features.items() if not is_player(k)}

            def enabled(name: str) -> bool:
                return enabled_detectors is None or name.split(":", 2)[2] in enabled_detectors

            def value(present: frozenset[str]) -> float:
                feats = dict(context)
                imputed = 0.0  # expected supporting families of the imputed players
                for name in model.names:
                    if not is_player(name):
                        continue
                    if name in present:
                        feats[name] = active[name]
                    elif name in active or not enabled(name):  # left out of the coalition, or disabled
                        feats[name] = model.mean_of(name)
                        imputed += model.active_rate(name)
                    else:
                        feats[name] = 0.0  # enabled and did not fire: an observed zero, not a missing value
                feats[N_FAMILIES] = supporting_families({k: active[k] for k in present}) + imputed
                return 100 * model.predict(feats)

            p = value(frozenset(active))
            if contributions:
                phi = shapley(value, sorted(active), seed=self.shapley_seed)
                base = value(frozenset())
                parts = tuple(
                    Contribution(name, feature_family(name), name.split(":", 2)[2], points)
                    for name, points in phi.items()
                )
            estimate = ProbabilityEstimate(
                p=p,
                low=estimate.low,  # the bucket interval stays the honest uncertainty statement
                high=estimate.high,
                n=estimate.n,
                n_pooled=estimate.n_pooled,
                insufficient=estimate.insufficient,
                calibration=estimate.calibration,
                source="evidence",
            )
        return Explanation(
            estimate=estimate,
            base_rate=base,
            contributions=parts,
            random_baseline=random_baseline(q.rr),
            break_even=break_even_probability(q.rr, q.cost_r),
            ev_r=expected_value_r(estimate.p, q.rr, q.cost_r),
        )


def build_win_probability(
    outcomes: Sequence[Outcome],
    *,
    kappa: float = 20.0,
    min_trades: int = 30,
    replay_cap: float = 50.0,
    folds: int = 5,
    l2: float = 1.0,
    min_group: int = 200,
    seed: int = 0,
    margin: float = 0.0,
) -> WinProbability:
    bucket = BucketModel(kappa=kappa, min_trades=min_trades, replay_cap=replay_cap).fit(outcomes)
    if not any(o.features for o in outcomes):
        return WinProbability(bucket, shapley_seed=seed)
    report = walk_forward(
        outcomes,
        folds=folds,
        bucket=lambda: BucketModel(kappa=kappa, min_trades=min_trades, replay_cap=replay_cap),
        l2=l2,
        min_group=min_group,
        margin=margin,
    )
    evidence = EvidenceModelSet.fit(outcomes, l2=l2, min_group=min_group) if report.use_evidence else None
    return WinProbability(bucket, evidence, report, seed)


# --- per-theory track record --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrackRecord:
    feature: str
    group: Hashable
    n: int
    hits: int
    hit_rate: float  # percent
    low: float  # Wilson 90%, percent
    high: float
    base_rate: float  # percent, same group
    lift: float  # hit rate / base rate (1.0 = no better than the group's average)


def track_records(
    outcomes: Iterable[Outcome],
    *,
    group: Callable[[Outcome], Hashable] = lambda o: (o.asset_class, o.timeframe),
) -> dict[tuple[str, Hashable], TrackRecord]:
    """Standalone hit rate of each supporting ``ev:`` feature per group, with Wilson CI and lift."""
    base: dict[Hashable, list[int]] = defaultdict(lambda: [0, 0])
    per: dict[tuple[str, Hashable], list[int]] = defaultdict(lambda: [0, 0])
    for o in outcomes:
        g = group(o)
        base[g][0] += o.win
        base[g][1] += 1
        for name, value in o.features.items():
            if is_player(name) and value > 0:
                per[(name, g)][0] += o.win
                per[(name, g)][1] += 1
    out = {}
    for (name, g), (hits, n) in per.items():
        b_hits, b_n = base[g]
        rate = hits / n
        b_rate = b_hits / b_n
        low, high = wilson_interval(hits, n)
        out[(name, g)] = TrackRecord(
            name,
            g,
            n,
            hits,
            100 * rate,
            100 * low,
            100 * high,
            100 * b_rate,
            rate / b_rate if b_rate else math.nan,
        )
    return out
