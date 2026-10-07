"""Entry-mode variants against ``PLAN`` on the same opportunities (PLAN_LEARNING §L19.3; TAA-L702).

Pure. Input: shadow rows reduced to :class:`VariantOutcome` (one per opportunity × variant). An opportunity
counts once its ``PLAN`` row is ``CLOSED`` and the variant row is ``CLOSED`` or ``MISSED`` (a variant still
``PENDING``/``OPEN`` waits). Per variant:

- the **paired ΔR** = variant R − PLAN R on the same opportunity, a missed entry counting **0 R** (no trade),
  with a seeded bootstrap CI (:func:`app.learning.research.summarize`), overall and per strategy;
- the **fill rate** and the variant's own mean R over its filled trades;
- **avoided losers** (PLAN lost, the variant did not: missed or ≥ 0 R) and **missed winners** (PLAN won, the
  variant did not).

LIVE and REPLAY are never mixed (the caller filters by source). §L19.7 decides what a result allows: a variant
becomes eligible only with a paired ΔR CI above 0 over ≥ 200 live-shadow opportunities.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from app.learning.research import Stat, summarize

PLAN = "PLAN"
CLOSED = "CLOSED"
MISSED = "MISSED"
ELIGIBLE_N = 200  # §L19.7: live-shadow opportunities before a variant may become a default entry mode


@dataclass(frozen=True, slots=True)
class VariantOutcome:
    opportunity_id: str
    variant: str
    status: str
    strategy: str
    symbol: str
    r_net: float | None


@dataclass(frozen=True, slots=True)
class VariantStats:
    variant: str
    opportunities: int  # paired with a closed PLAN
    filled: int
    missed: int
    fill_rate: float | None
    own: Stat  # the variant's filled trades
    plan: Stat  # PLAN on the same opportunities
    paired: Stat  # variant − PLAN, missed = 0 R
    avoided_losers: int
    missed_winners: int
    eligible: bool  # paired CI above 0 with n >= ELIGIBLE_N (shown, never applied here)


def _stats(
    variant: str, pairs: Sequence[tuple[float, float | None]], seed: int, resamples: int
) -> VariantStats:
    """*pairs*: (PLAN R, variant R or None when missed)."""
    filled = [v for _, v in pairs if v is not None]
    paired = summarize([(v or 0.0) - p for p, v in pairs], seed=seed, resamples=resamples)
    return VariantStats(
        variant=variant,
        opportunities=len(pairs),
        filled=len(filled),
        missed=len(pairs) - len(filled),
        fill_rate=round(len(filled) / len(pairs), 4) if pairs else None,
        own=summarize(filled, seed=seed, resamples=resamples),
        plan=summarize([p for p, _ in pairs], seed=seed, resamples=resamples),
        paired=paired,
        avoided_losers=sum(1 for p, v in pairs if p < 0 and (v is None or v >= 0)),
        missed_winners=sum(1 for p, v in pairs if p > 0 and (v is None or v <= 0)),
        eligible=paired.n >= ELIGIBLE_N and paired.low is not None and paired.low > 0,
    )


@dataclass(frozen=True, slots=True)
class EntryModeReport:
    variants: list[VariantStats]
    by_strategy: dict[str, list[VariantStats]]
    waiting: int  # variant rows not resolved yet (PENDING/OPEN) on closed PLAN opportunities

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare(
    outcomes: Iterable[VariantOutcome], *, seed: int = 0, resamples: int = 1000, min_group: int = 1
) -> EntryModeReport:
    by_opp: dict[str, dict[str, VariantOutcome]] = defaultdict(dict)
    for o in outcomes:
        by_opp[o.opportunity_id][o.variant] = o
    pairs: dict[str, list[tuple[float, float | None]]] = defaultdict(list)
    per_strategy: dict[tuple[str, str], list[tuple[float, float | None]]] = defaultdict(list)
    waiting = 0
    for variants in by_opp.values():
        plan = variants.get(PLAN)
        if plan is None or plan.status != CLOSED or plan.r_net is None:
            continue
        for name, row in variants.items():
            if name in (PLAN, "MANAGED"):
                continue
            if row.status == CLOSED and row.r_net is not None:
                value: float | None = row.r_net
            elif row.status == MISSED:
                value = None
            else:
                waiting += row.status not in ("VOID",)
                continue
            pairs[name].append((plan.r_net, value))
            per_strategy[(plan.strategy, name)].append((plan.r_net, value))
    by_strategy: dict[str, list[VariantStats]] = defaultdict(list)
    for (strategy, name), group in sorted(per_strategy.items()):
        if len(group) >= min_group:
            by_strategy[strategy].append(_stats(name, group, seed, resamples))
    return EntryModeReport(
        variants=[_stats(name, group, seed, resamples) for name, group in sorted(pairs.items())],
        by_strategy=dict(by_strategy),
        waiting=waiting,
    )
