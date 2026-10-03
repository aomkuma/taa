"""Soft scores S1–S9, Overall/Now scores and the ranking order (PLAN §A25; TAA-6A4).

Every score is 0–100, higher is better:

- **S1 Sizing granularity:** x = risk budget / min-lot risk; ``log2(x)`` scaled 1× → 0, 16× → 100.
- **S2 Cost efficiency:** ``1 − cost ratio / max_spread_to_sl_ratio`` (cost ratio from G4).
- **S3 Leverage/margin comfort:** mean of ``1 − L / max_effective_leverage`` and ``1 − margin share`` (G3).
- **S4 Liquidity now:** ρ = this hour-of-week's tick volume / the symbol's median; ``ρ / 2`` (a typical hour
  scores 50); no data (e.g. the market is closed) → 0.
- **S5 Volatility regime:** ATR percentile; 100 inside 20–80, falling linearly to 0 at 0 and at 100.
- **S6 Regime fit:** a preferred regime → 100, UNCLEAR → 50, any other → 0.
- **S7 Diversification:** ``1 − max |correlation|`` with the open exposure and the higher-ranked picks.
- **S8 Historical edge:** ``50 + 50 × shrunk / edge_full_scale_r`` with ``shrunk = n / (n + prior) × mean R``
  of shadow/replay outcomes; neutral 50 below ``edge_min_trades``.
- **S9 Holding cost:** q = swap per night / loss at the typical stop; a swap credit → 100, else
  ``1 − q / swap_max_fraction``.

Unknown inputs give a neutral 50 with a flag, except S1–S4, where "unknown" means "not usable now" and scores
0. **Overall** is the weighted mean of S1, S2, S3, S8, S9 (structural); **Now** of all nine.

**Ranking:** eligible symbols first, then Now, Overall and the symbol name (a deterministic order). Eligible
symbols are picked greedily: each pick's S7 counts correlation with the open exposure *and* with the picks
above it, so the top of the list is diversified.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

import pandas as pd

from app.advisory.correlations import max_correlation
from app.advisory.suitability import Suitability, SymbolFacts
from app.broker import mt5_constants as c
from app.config import RiskConfig, ScoringConfig
from app.core.enums import Regime, Side
from app.market_data.data_models import SymbolSpec


class Score(StrEnum):
    S1_SIZING = "S1"
    S2_COST = "S2"
    S3_LEVERAGE = "S3"
    S4_LIQUIDITY = "S4"
    S5_VOLATILITY = "S5"
    S6_REGIME = "S6"
    S7_DIVERSIFICATION = "S7"
    S8_EDGE = "S8"
    S9_HOLDING_COST = "S9"


OVERALL = (Score.S1_SIZING, Score.S2_COST, Score.S3_LEVERAGE, Score.S8_EDGE, Score.S9_HOLDING_COST)
NOW = tuple(Score)
NEUTRAL = 50.0


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x)) * 100.0


@dataclass(frozen=True, slots=True)
class EdgeEstimate:
    trades: int
    expectancy_r: float


@dataclass(frozen=True, slots=True)
class DynamicMetrics:
    liquidity_ratio: float | None = None
    atr_percentile: float | None = None  # 0–100
    regime: Regime | None = None
    edge: EdgeEstimate | None = None


# --- single scores -----------------------------------------------------------------------------------------


def sizing_score(s: Suitability) -> float:
    if s.risk_budget is None or not s.min_lot_risk or s.min_lot_risk <= 0:
        return 0.0
    x = float(s.risk_budget / s.min_lot_risk)
    return 0.0 if x <= 1 else _clamp(math.log2(x) / 4)


def cost_score(s: Suitability, risk: RiskConfig) -> float:
    return 0.0 if s.cost_ratio is None else _clamp(1 - s.cost_ratio / risk.max_spread_to_sl_ratio)


def leverage_score(s: Suitability, risk: RiskConfig) -> float:
    if s.effective_leverage is None or s.margin_share is None:
        return 0.0
    leverage = max(0.0, 1 - s.effective_leverage / risk.max_effective_leverage)
    share = max(0.0, 1 - s.margin_share)
    return _clamp((leverage + share) / 2)


def liquidity_score(ratio: float | None) -> float:
    return 0.0 if ratio is None or not math.isfinite(ratio) else _clamp(ratio / 2)


def volatility_score(percentile: float | None) -> float | None:
    if percentile is None or not math.isfinite(percentile):
        return None
    if percentile < 20:
        return _clamp(percentile / 20)
    if percentile > 80:
        return _clamp((100 - percentile) / 20)
    return 100.0


def regime_score(regime: Regime | None, preferred: Sequence[Regime]) -> float | None:
    if regime is None:
        return None
    if regime in preferred:
        return 100.0
    return NEUTRAL if regime is Regime.UNCLEAR else 0.0


def diversification_score(max_abs_correlation: float | None) -> float:
    return 100.0 if max_abs_correlation is None else _clamp(1 - max_abs_correlation)


def edge_score(edge: EdgeEstimate | None, config: ScoringConfig) -> float | None:
    if edge is None or edge.trades < config.edge_min_trades or not math.isfinite(edge.expectancy_r):
        return None
    shrunk = edge.trades / (edge.trades + config.edge_prior_trades) * edge.expectancy_r
    return _clamp(0.5 + 0.5 * shrunk / config.edge_full_scale_r)


def swap_per_night(spec: SymbolSpec, side: Side) -> float | None:
    """Swap of one lot held overnight, account currency (negative = a cost); None for an unknown mode."""
    swap = spec.swap_long if side is Side.BUY else spec.swap_short
    if spec.swap_mode == c.SYMBOL_SWAP_MODE_DISABLED:
        return 0.0
    if spec.swap_mode == c.SYMBOL_SWAP_MODE_POINTS:
        return swap * spec.point / spec.tick_size * spec.tick_value
    if spec.swap_mode == c.SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT:
        return swap
    return None  # symbol/margin currency, interest and reopen modes need conversions the ranking skips


def holding_cost_score(facts: SymbolFacts, config: ScoringConfig) -> float | None:
    swap = swap_per_night(facts.spec, facts.side)
    if swap is None or not facts.loss_per_lot:
        return None
    if swap >= 0:
        return 100.0
    return _clamp(1 - (-swap / facts.loss_per_lot) / config.swap_max_fraction)


# --- combination -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Candidate:
    facts: SymbolFacts
    suitability: Suitability
    metrics: DynamicMetrics = field(default_factory=DynamicMetrics)

    @property
    def symbol(self) -> str:
        return self.facts.symbol


@dataclass(frozen=True, slots=True)
class RankedSymbol:
    symbol: str
    eligible: bool
    overall: float
    now: float
    scores: Mapping[Score, float]
    flags: tuple[str, ...]  # neutral defaults: insufficient_history, unknown_volatility, ...
    correlation: float | None  # S7's max |correlation|
    correlated_with: str | None
    suitability: Suitability
    rank: int = 0


def weighted(scores: Mapping[Score, float], names: Sequence[Score], config: ScoringConfig) -> float:
    total = sum(config.weights[n.value] for n in names)
    if total <= 0:
        return 0.0
    return round(sum(scores[n] * config.weights[n.value] for n in names) / total, 2)


def score_candidate(
    candidate: Candidate,
    config: ScoringConfig,
    risk: RiskConfig,
    *,
    correlations: pd.DataFrame | None = None,
    against: Sequence[str] = (),
) -> RankedSymbol:
    """All nine scores; S7 against the symbols in *against* (open exposure, and picks above it)."""
    s, m = candidate.suitability, candidate.metrics
    flags: list[str] = []

    def neutral(value: float | None, flag: str) -> float:
        if value is None:
            flags.append(flag)
            return NEUTRAL
        return value

    corr, partner = max_correlation(correlations, candidate.symbol, against)
    scores = {
        Score.S1_SIZING: sizing_score(s),
        Score.S2_COST: cost_score(s, risk),
        Score.S3_LEVERAGE: leverage_score(s, risk),
        Score.S4_LIQUIDITY: liquidity_score(m.liquidity_ratio),
        Score.S5_VOLATILITY: neutral(volatility_score(m.atr_percentile), "unknown_volatility"),
        Score.S6_REGIME: neutral(regime_score(m.regime, config.preferred_regimes), "unknown_regime"),
        Score.S7_DIVERSIFICATION: diversification_score(corr),
        Score.S8_EDGE: neutral(edge_score(m.edge, config), "insufficient_history"),
        Score.S9_HOLDING_COST: neutral(holding_cost_score(candidate.facts, config), "unknown_swap"),
    }
    return RankedSymbol(
        symbol=candidate.symbol,
        eligible=s.eligible,
        overall=weighted(scores, OVERALL, config),
        now=weighted(scores, NOW, config),
        scores=scores,
        flags=tuple(flags),
        correlation=corr,
        correlated_with=partner,
        suitability=s,
    )


def _order(r: RankedSymbol) -> tuple[float, float, str]:
    return (-r.now, -r.overall, r.symbol)


def rank(
    candidates: Sequence[Candidate],
    config: ScoringConfig,
    risk: RiskConfig,
    *,
    correlations: pd.DataFrame | None = None,
    exposure: Sequence[str] = (),
) -> list[RankedSymbol]:
    """Eligible symbols first (greedy, diversified), then the rest; ranks start at 1."""
    eligible = [c for c in candidates if c.suitability.eligible]
    picked: list[RankedSymbol] = []
    while eligible:
        against = [*exposure, *(p.symbol for p in picked)]
        scored = [
            score_candidate(c, config, risk, correlations=correlations, against=against) for c in eligible
        ]
        best = min(scored, key=_order)
        picked.append(best)
        eligible = [c for c in eligible if c.symbol != best.symbol]
    rest = sorted(
        (
            score_candidate(c, config, risk, correlations=correlations, against=exposure)
            for c in candidates
            if not c.suitability.eligible
        ),
        key=_order,
    )
    return [replace(r, rank=i) for i, r in enumerate([*picked, *rest], start=1)]
