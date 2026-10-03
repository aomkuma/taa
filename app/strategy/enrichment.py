"""Confluence enrichment of signals (PLAN §A29 use 1, TAA-307).

Every signal gets all active evidence of every enabled timeframe (the higher timeframes included), each item
classified as supporting, conflicting or neutral relative to the signal's direction. For an entry signal the
setup strength becomes the confluence score (``app/evidence/confluence.py``), which keeps the strategy's
checklist as its core term; a HOLD keeps its checklist strength and gets the evidence as NEUTRAL context.
"""

from __future__ import annotations

import dataclasses

from app.config import ConfluenceConfig
from app.evidence.confluence import confluence_score, dedupe, relation
from app.evidence.framework import Family
from app.strategy.signal_models import Signal, SignalEvidence, StrategyContext, condition_strength


def enrich(
    signal: Signal,
    ctx: StrategyContext,
    config: ConfluenceConfig,
    core_families: frozenset[Family] = frozenset(),
) -> Signal:
    items = dedupe(ctx.all_evidence())
    side = signal.side
    sign = 0 if side is None else side.sign
    attached = tuple(SignalEvidence(item, relation(item.evidence.direction, sign)) for item in items)
    if side is None:
        return dataclasses.replace(signal, evidence=attached)
    score = confluence_score(
        items,
        sign,
        condition_share=condition_strength(signal.conditions) / 100.0,
        config=config,
        core_families=core_families,
    )
    return dataclasses.replace(
        signal, evidence=attached, setup_strength=score.total, confluence=score.contributions
    )
