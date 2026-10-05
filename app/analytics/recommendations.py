"""Rule-based recommendations from closed trades (PLAN §A16 "Recommendations"; TAA-1004). Pure.

Each recommendation carries its evidence, its sample size and whether that sample is large enough
(:data:`MIN_SAMPLES`); a small sample is shown with a warning, never hidden as if it were proof. A
recommendation **never** changes any configuration: where a rule maps to a bounded backtest change it offers
one (:class:`BacktestChange`, "Backtest this change"), and the owner decides.

Rules (thresholds from §A16):

1. **Restrict a segment:** a segment (strategy, symbol, session, setup, holding style, regime, volatility,
   direction) with ≥ :data:`MIN_SAMPLES` trades whose bootstrap 95 % CI of the mean R lies entirely below 0.
2. **Earlier break-even or a partial TP:** more than 30 % of the losers had MFE ≥ 1R.
3. **Stop may be tight relative to ATR:** more than 30 % of the stop-loss exits were followed by price
   reaching the take-profit within N bars (the caller measures that from bars after the exit; per strategy).
4. **Cost drag:** known costs above 25 % of the P/L before costs (in R), per symbol.
5. **Reduce risk:** the account's drawdown above 50 % of its limit.

Only trades with an R take part (a trade without an initial stop has no R). Hypothetical scopes (backtest,
paper, shadow) are labelled by the caller, as everywhere in analytics.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.analytics.styles import StyleTags, style_tags
from app.analytics.trade_builder import Outcome, Trade
from app.core.enums import ExitReason

MIN_SAMPLES = 30  # a sample this large counts as enough; smaller ones are shown with a warning
MIN_REPORT = 10  # below this a rule says nothing at all
RESAMPLES = 2000
CONFIDENCE = 0.95

GAVE_BACK_SHARE = 0.30
GAVE_BACK_MFE_R = 1.0
TIGHT_STOP_SHARE = 0.30
COST_DRAG_SHARE = 0.25
DRAWDOWN_SHARE = 0.50

SEGMENT_DIMENSIONS: tuple[str, ...] = (
    "strategy",
    "symbol",
    "session",
    "setup",
    "holding",
    "regime",
    "volatility",
    "direction",
)

# the changes a "Backtest this change" job may carry (bounded again by app.backtest.presets.ParameterChange)
EARLIER_BREAK_EVEN_R = 0.75
WIDER_SL_ATR = 2.0
TIGHTER_SPREAD_TO_SL = 0.10


class Kind(StrEnum):
    RESTRICT_SEGMENT = "RESTRICT_SEGMENT"
    EARLIER_BREAK_EVEN = "EARLIER_BREAK_EVEN"
    STOP_TOO_TIGHT = "STOP_TOO_TIGHT"
    COST_DRAG = "COST_DRAG"
    REDUCE_RISK = "REDUCE_RISK"


@dataclass(frozen=True, slots=True)
class Interval:
    mean: float
    low: float
    high: float
    n: int


def bootstrap_mean_ci(
    values: Sequence[float], *, confidence: float = CONFIDENCE, resamples: int = RESAMPLES, seed: int = 0
) -> Interval:
    """Percentile bootstrap CI of the mean, seeded (the same trades always give the same interval)."""
    n = len(values)
    if n == 0:
        raise ValueError("no values")
    mean = sum(values) / n
    if n == 1:
        return Interval(mean, mean, mean, 1)
    rng = random.Random(seed)  # noqa: S311  # nosec B311: a seeded bootstrap, not security
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(resamples))
    tail = (1 - confidence) / 2
    low = means[max(0, math.floor(tail * resamples))]
    high = means[min(resamples - 1, math.ceil((1 - tail) * resamples) - 1)]
    return Interval(round(mean, 4), round(low, 4), round(high, 4), n)


@dataclass(frozen=True, slots=True)
class BacktestChange:
    """A bounded change a cloud backtest job can test (``BacktestRequest``): never applied to live config."""

    # exclude_strategy | exclude_symbol | break_even_trigger_r | sl_atr_multiple | max_spread_to_sl_ratio
    # | risk_percent
    kind: str
    value: float | str
    strategy: str | None = None


@dataclass(frozen=True, slots=True)
class Recommendation:
    kind: Kind
    sample_size: int
    enough: bool  # sample_size >= MIN_SAMPLES; otherwise shown with a sample-size warning
    evidence: Mapping[str, float | int | str]
    segment: tuple[str, str] | None = None  # (dimension, value)
    ci: Interval | None = None
    change: BacktestChange | None = None

    @property
    def key(self) -> str:
        """The translation key of its text (``analytics.recommendation.<KIND>``)."""
        return f"analytics.recommendation.{self.kind.value}"


@dataclass(frozen=True, slots=True)
class AccountFacts:
    drawdown_percent: float
    drawdown_limit_percent: float
    risk_percent: float  # the risk per trade in use


@dataclass(frozen=True, slots=True)
class Inputs:
    trades: Sequence[Trade]
    # trade_id → whether price reached the take-profit within N bars after a stop-loss exit (None: unknown)
    target_after_stop: Mapping[str, bool] = field(default_factory=dict)
    after_stop_bars: int = 20
    account: AccountFacts | None = None


def _rated(trades: Iterable[Trade]) -> list[Trade]:
    return [t for t in trades if t.r_multiple is not None and math.isfinite(t.r_multiple)]


def _segment_value(tags: StyleTags, dimension: str) -> str:
    return str(getattr(tags, dimension))


def restrict_segments(trades: Sequence[Trade], *, seed: int = 0) -> list[Recommendation]:
    rated = _rated(trades)
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for t in rated:
        tags = style_tags(t)
        for dim in SEGMENT_DIMENSIONS:
            groups[(dim, _segment_value(tags, dim))].append(t.r_multiple or 0.0)
    out = []
    for (dim, value), rs in sorted(groups.items()):
        if len(rs) < MIN_SAMPLES or value == "UNKNOWN" or len(rs) == len(rated):
            continue  # too few trades, an unknown bucket, or the whole book (not a segment)
        ci = bootstrap_mean_ci(rs, seed=seed)
        if ci.high >= 0:
            continue
        change = (
            BacktestChange("exclude_strategy", value)
            if dim == "strategy"
            else BacktestChange("exclude_symbol", value)
            if dim == "symbol"
            else None
        )
        out.append(
            Recommendation(
                Kind.RESTRICT_SEGMENT,
                len(rs),
                True,
                {"dimension": dim, "value": value, "mean_r": ci.mean, "ci_low": ci.low, "ci_high": ci.high},
                segment=(dim, value),
                ci=ci,
                change=change,
            )
        )
    return sorted(out, key=lambda r: (r.ci.high if r.ci else 0.0, -r.sample_size))


def earlier_break_even(trades: Sequence[Trade]) -> list[Recommendation]:
    losers = [t for t in _rated(trades) if t.outcome is Outcome.LOSS and t.mfe_r is not None]
    if len(losers) < MIN_REPORT:
        return []
    gave_back = [t for t in losers if (t.mfe_r or 0.0) >= GAVE_BACK_MFE_R - 1e-9]
    share = len(gave_back) / len(losers)
    if share <= GAVE_BACK_SHARE:
        return []
    return [
        Recommendation(
            Kind.EARLIER_BREAK_EVEN,
            len(losers),
            len(losers) >= MIN_SAMPLES,
            {
                "losers": len(losers),
                "gave_back": len(gave_back),
                "share": round(share, 4),
                "mfe_r": GAVE_BACK_MFE_R,
            },
            change=BacktestChange("break_even_trigger_r", EARLIER_BREAK_EVEN_R),
        )
    ]


def stop_too_tight(inputs: Inputs) -> list[Recommendation]:
    by_strategy: dict[str, list[bool]] = defaultdict(list)
    for t in _rated(inputs.trades):
        if t.exit_reason is not ExitReason.STOP_LOSS:
            continue
        reached = inputs.target_after_stop.get(t.trade_id)
        if reached is not None:
            by_strategy[t.strategy].append(reached)
    out = []
    for strategy, seen in sorted(by_strategy.items()):
        if len(seen) < MIN_REPORT:
            continue
        share = sum(seen) / len(seen)
        if share <= TIGHT_STOP_SHARE:
            continue
        out.append(
            Recommendation(
                Kind.STOP_TOO_TIGHT,
                len(seen),
                len(seen) >= MIN_SAMPLES,
                {
                    "strategy": strategy,
                    "stops": len(seen),
                    "reached_target": sum(seen),
                    "share": round(share, 4),
                    "bars": inputs.after_stop_bars,
                },
                segment=("strategy", strategy),
                change=BacktestChange("sl_atr_multiple", WIDER_SL_ATR, strategy=strategy),
            )
        )
    return out


def cost_drag(trades: Sequence[Trade]) -> list[Recommendation]:
    by_symbol: dict[str, list[Trade]] = defaultdict(list)
    for t in _rated(trades):
        if t.cost_r is not None and t.pre_cost_r is not None:
            by_symbol[t.symbol].append(t)
    out = []
    for symbol, ts in sorted(by_symbol.items()):
        if len(ts) < MIN_REPORT:
            continue
        costs = sum(t.cost_r or 0.0 for t in ts)
        gross = sum(abs(t.pre_cost_r or 0.0) for t in ts)
        if gross <= 0:
            continue
        share = costs / gross
        if share <= COST_DRAG_SHARE:
            continue
        out.append(
            Recommendation(
                Kind.COST_DRAG,
                len(ts),
                len(ts) >= MIN_SAMPLES,
                {
                    "symbol": symbol,
                    "cost_r": round(costs, 4),
                    "pre_cost_r": round(gross, 4),
                    "share": round(share, 4),
                },
                segment=("symbol", symbol),
                change=BacktestChange("max_spread_to_sl_ratio", TIGHTER_SPREAD_TO_SL),
            )
        )
    return out


def reduce_risk(account: AccountFacts | None) -> list[Recommendation]:
    if account is None or account.drawdown_limit_percent <= 0:
        return []
    share = account.drawdown_percent / account.drawdown_limit_percent
    if share <= DRAWDOWN_SHARE:
        return []
    return [
        Recommendation(
            Kind.REDUCE_RISK,
            0,
            True,  # a fact about the account, not a sample
            {
                "drawdown_percent": round(account.drawdown_percent, 4),
                "limit_percent": account.drawdown_limit_percent,
                "share": round(share, 4),
            },
            change=BacktestChange("risk_percent", round(account.risk_percent / 2, 4)),
        )
    ]


RULES: tuple[Callable[[Inputs], list[Recommendation]], ...] = (
    lambda i: restrict_segments(i.trades),
    lambda i: earlier_break_even(i.trades),
    stop_too_tight,
    lambda i: cost_drag(i.trades),
    lambda i: reduce_risk(i.account),
)


def recommend(inputs: Inputs) -> list[Recommendation]:
    """Every recommendation the trades support, the account's risk first, then the A16 order."""
    found = [r for rule in RULES for r in rule(inputs)]
    return sorted(found, key=lambda r: (r.kind is not Kind.REDUCE_RISK, not r.enough))


def as_dict(r: Recommendation) -> dict[str, Any]:
    return {
        "kind": r.kind.value,
        "key": r.key,
        "sample_size": r.sample_size,
        "enough": r.enough,
        "min_samples": MIN_SAMPLES,
        "evidence": dict(r.evidence),
        "segment": None if r.segment is None else {"dimension": r.segment[0], "value": r.segment[1]},
        "ci": None if r.ci is None else {"mean": r.ci.mean, "low": r.ci.low, "high": r.ci.high, "n": r.ci.n},
        "change": None
        if r.change is None
        else {"kind": r.change.kind, "value": r.change.value, "strategy": r.change.strategy},
    }


def request_fields(change: BacktestChange, symbols: Sequence[str]) -> dict[str, Any] | None:
    """The ``BacktestRequest`` fields that test *change* on *symbols* ("Backtest this change"); None when it
    cannot be tested there (excluding the only symbol leaves nothing to run)."""
    if change.kind == "exclude_strategy":
        return {"symbols": list(symbols), "exclude_strategies": [str(change.value)]}
    if change.kind == "exclude_symbol":
        rest = [s for s in symbols if s != change.value]
        return {"symbols": rest} if rest else None
    if change.kind == "risk_percent":
        return {"symbols": list(symbols), "risk_percent": float(change.value)}
    body: dict[str, Any] = {"kind": change.kind, "value": float(change.value)}
    if change.strategy is not None:
        body["strategy"] = change.strategy
    return {"symbols": list(symbols), "change": body}
