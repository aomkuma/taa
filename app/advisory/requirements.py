"""Compute requirements: what the engine must scan for the active users (PLAN §A30; TAA-6B3).

"Compute once, personalize per user": the engine never sees a user's preferences, only the union of what they
need:

- **symbols:** the bot's allowlist ∪ every user's favourites and custom lists ∪ the ranking's top N (the
  largest AUTO_TOP_N among users), de-duplicated in that priority and capped
  (``advisory.universe.monitored_cap``);
- **detectors:** the union of the users' enabled detectors (the evidence run plan adds prerequisites and can
  only narrow it further to what the local config enables);
- **strategies:** the strategies enabled in ``config.yaml`` ∪ the pattern setups any user lets alert.

The ``version`` digest changes whenever the content does, so the scanner rebuilds its plan only then. In
Phase 7 the cloud sends these (with an ETag); until then :func:`local_requirements` derives them from the
``config.yaml`` fallback preferences.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from app.advisory.preferences import AdvisoryPreferences, WatchlistKind, local_preferences
from app.advisory.universe import monitored_set
from app.config import AppConfig
from app.core.ids import stable_hash
from app.evidence.registry import DetectorRegistry
from app.strategy.registry import StrategyRegistry
from app.strategy.setups import EvidenceSetup


@dataclass(frozen=True, slots=True)
class ComputeRequirements:
    symbols: tuple[str, ...]
    detectors: frozenset[str]
    strategies: frozenset[str]

    @property
    def version(self) -> str:
        payload = {"s": list(self.symbols), "d": sorted(self.detectors), "t": sorted(self.strategies)}
        return stable_hash(json.dumps(payload, separators=(",", ":")), length=16)


def pattern_setups(strategies: StrategyRegistry) -> list[str]:
    return [n for n in strategies.names if issubclass(strategies.get(n), EvidenceSetup)]


def compute_requirements(
    users: Sequence[AdvisoryPreferences],
    config: AppConfig,
    *,
    ranked: Sequence[str],
    evidence: DetectorRegistry,
    strategies: StrategyRegistry,
    available: Sequence[str] | None = None,
) -> ComputeRequirements:
    favourites: list[str] = []
    lists: dict[str, list[str]] = {}
    top_n = 0
    detectors: set[str] = set()
    allowed_setups: set[str] = set()
    setups = pattern_setups(strategies)
    for i, prefs in enumerate(users):
        for w in prefs.watchlists:
            if w.kind is WatchlistKind.FAVOURITES:
                favourites += w.symbols
            elif w.kind is WatchlistKind.CUSTOM:
                lists[f"{i}:{w.name}"] = w.symbols
            else:
                top_n = max(top_n, w.size or 0)
        detectors |= prefs.theories.enabled_detectors(evidence)
        allowed_setups |= {s for s in setups if prefs.theories.pattern_strategies.get(s, True)}
    symbols = monitored_set(
        allowlist=config.symbols.allowed,
        favourites=favourites,
        lists=lists,
        ranked=ranked,
        auto_top_n=top_n,
        cap=config.advisory.universe.monitored_cap,
        available=available,
    )
    trading = {item.name for item in config.strategies.items if item.enabled}
    return ComputeRequirements(tuple(symbols), frozenset(detectors), frozenset(trading | allowed_setups))


def local_requirements(
    config: AppConfig,
    *,
    ranked: Sequence[str],
    evidence: DetectorRegistry,
    strategies: StrategyRegistry,
    available: Sequence[str] | None = None,
) -> ComputeRequirements:
    """The single local user from ``config.yaml`` → ``advisory.preferences`` (no cloud yet)."""
    return compute_requirements(
        [local_preferences(config)],
        config,
        ranked=ranked,
        evidence=evidence,
        strategies=strategies,
        available=available,
    )
