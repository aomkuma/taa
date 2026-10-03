"""Confluence score: how much the active evidence agrees with a trade direction (PLAN §A29, TAA-307).

``setup strength = core + Σ_families support − penalty × Σ_families conflict``, clipped to 0–100, in points:

- **Core:** ``core_weight × condition_share``, the strategy's own checklist (its weighted share of passed
  conditions).
- **Family support:** within a family, supporting items combine by noisy-OR, ``s = 1 − Π(1 − t·q)`` with
  ``q`` the item quality and ``t`` its tier weight. The family adds ``family_weight × s`` points, so it can
  never add more than its weight however many correlated items fire (five oscillators are not five votes).
- **Family conflict:** the same noisy-OR over contradicting items, subtracted with ``conflict_penalty``.

Double-counting controls:

1. The same evidence instance (``evidence_id``) found twice counts once, at its best quality.
2. Correlated items share one capped family term (noisy-OR).
3. Families the strategy's checklist already measures (``core_families``, e.g. TREND for a trend strategy)
   add no *support*: the core term already holds them. Their *conflicts* still count.

This is a deterministic, documented heuristic, **not a probability**; win probability with per-theory
attribution is Phase 6B/6C work.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.config import ConfluenceConfig
from app.core.errors import ConfigError
from app.evidence.framework import ActiveEvidence, Direction, Family, Tier


class Relation(StrEnum):
    """How a piece of evidence relates to a trade direction."""

    SUPPORTS = "SUPPORTS"
    CONFLICTS = "CONFLICTS"
    NEUTRAL = "NEUTRAL"


def relation(direction: Direction, side_sign: int) -> Relation:
    """*side_sign* is +1 for a BUY, -1 for a SELL and 0 when there is no trade direction (HOLD)."""
    if side_sign == 0 or direction is Direction.NEUTRAL:
        return Relation.NEUTRAL
    return Relation.SUPPORTS if direction.sign == side_sign else Relation.CONFLICTS


@dataclass(frozen=True, slots=True)
class FamilyScore:
    family: Family
    support: float  # noisy-OR of supporting items, 0..1
    conflict: float  # noisy-OR of conflicting items, 0..1
    support_points: float
    conflict_points: float  # already multiplied by the penalty
    n_support: int
    n_conflict: int
    core: bool  # support ignored because the strategy's checklist covers this family


@dataclass(frozen=True, slots=True)
class Confluence:
    core_points: float
    families: tuple[FamilyScore, ...]
    total: float  # 0..100

    @property
    def contributions(self) -> tuple[tuple[str, float], ...]:
        """Signed points per source (``core`` first, then families by size), for explanations."""
        rows = [
            (f.family.value, round(f.support_points - f.conflict_points, 4))
            for f in self.families
            if f.support_points or f.conflict_points
        ]
        rows.sort(key=lambda r: (-abs(r[1]), r[0]))
        return (("core", round(self.core_points, 4)), *rows)

    @property
    def supporting_families(self) -> int:
        return sum(1 for f in self.families if f.n_support and not f.core)


def _weights(config: ConfluenceConfig) -> tuple[dict[Family, float], dict[Tier, float]]:
    try:
        families = {Family(k): v for k, v in config.family_weights.items()}
        tiers = {Tier(k): v for k, v in config.tier_weights.items()}
    except ValueError as exc:
        raise ConfigError(f"evidence.confluence: {exc}") from exc
    return families, tiers


def noisy_or(values: Iterable[float]) -> float:
    product = 1.0
    for v in values:
        product *= 1.0 - min(1.0, max(0.0, v))
    return 1.0 - product


def dedupe(items: Iterable[ActiveEvidence]) -> list[ActiveEvidence]:
    """One record per ``evidence_id`` (the highest quality wins), in a stable order."""
    best: dict[str, ActiveEvidence] = {}
    for item in items:
        key = item.evidence.evidence_id
        if key not in best or item.evidence.quality > best[key].evidence.quality:
            best[key] = item
    return sorted(
        best.values(), key=lambda a: (a.evidence.family, a.evidence.detector_id, a.evidence.evidence_id)
    )


def confluence_score(
    items: Sequence[ActiveEvidence],
    side_sign: int,
    *,
    condition_share: float,
    config: ConfluenceConfig,
    core_families: Iterable[Family] = (),
) -> Confluence:
    if not (math.isfinite(condition_share) and 0.0 <= condition_share <= 1.0):
        raise ValueError(f"condition_share must be in [0, 1] (got {condition_share!r})")
    family_w, tier_w = _weights(config)
    core_set = frozenset(core_families)
    by_family: dict[Family, tuple[list[float], list[float]]] = {}
    for item in dedupe(items):
        ev = item.evidence
        rel = relation(ev.direction, side_sign)
        if rel is Relation.NEUTRAL:
            continue
        support, conflict = by_family.setdefault(ev.family, ([], []))
        (support if rel is Relation.SUPPORTS else conflict).append(tier_w.get(ev.tier, 0.0) * ev.quality)
    scores = []
    for family in sorted(by_family):
        support, conflict = by_family[family]
        weight = family_w.get(family, 0.0)
        s, c = noisy_or(support), noisy_or(conflict)
        is_core = family in core_set
        scores.append(
            FamilyScore(
                family=family,
                support=s,
                conflict=c,
                support_points=0.0 if is_core else weight * s,
                conflict_points=config.conflict_penalty * weight * c,
                n_support=len(support),
                n_conflict=len(conflict),
                core=is_core,
            )
        )
    core_points = config.core_weight * condition_share
    raw = core_points + sum(f.support_points - f.conflict_points for f in scores)
    return Confluence(core_points, tuple(scores), min(100.0, max(0.0, raw)))
