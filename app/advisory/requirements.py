"""Compute requirements: what the engine must scan for the active users (PLAN §A30; TAA-6B3).

"Compute once, personalize per user": the engine never sees a user's preferences, only the union of what they
need:

- **symbols:** the bot's allowlist ∪ every user's favourites and custom lists ∪ the ranking's top N (the
  largest AUTO_TOP_N among users), de-duplicated in that priority and capped
  (``advisory.universe.monitored_cap``);
- **detectors:** the union of the users' enabled detectors (the evidence run plan adds prerequisites and can
  only narrow it further to what the local config enables);
- **strategies:** the strategies enabled in ``config.yaml`` ∪ the pattern setups any user lets alert;
- **lifetime_bars:** the longest signal lifetime any user wants (market windows use it; a user's own shorter
  lifetime is applied by the personalizer).

The ``version`` digest changes whenever the content does, so the scanner rebuilds its plan only then.

**Two steps** (TAA-707): :func:`advisory_config` folds the users' preferences into an :class:`AdvisoryConfig`
(the cloud serves it at ``GET /api/v1/engine/advisory-config``); :func:`requirements_from_config` combines it
on the engine with what only the engine knows: the allowlist, the current ranking and the broker's symbols.
Unknown detector or setup names in a cloud config are logged and skipped, so a newer cloud cannot widen what
this engine runs. :func:`local_requirements` is the same path over the ``config.yaml`` fallback preferences.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.advisory.preferences import AdvisoryPreferences, WatchlistKind, local_preferences
from app.advisory.universe import monitored_set
from app.config import AppConfig
from app.core.ids import stable_hash
from app.evidence.registry import DetectorRegistry
from app.strategy.registry import StrategyRegistry
from app.strategy.setups import EvidenceSetup

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ComputeRequirements:
    symbols: tuple[str, ...]
    detectors: frozenset[str]
    strategies: frozenset[str]
    lifetime_bars: int = 2

    @property
    def version(self) -> str:
        payload = {
            "s": list(self.symbols),
            "d": sorted(self.detectors),
            "t": sorted(self.strategies),
            "l": self.lifetime_bars,
        }
        return stable_hash(json.dumps(payload, separators=(",", ":")), length=16)


def pattern_setups(strategies: StrategyRegistry) -> list[str]:
    return [n for n in strategies.names if issubclass(strategies.get(n), EvidenceSetup)]


class AdvisoryConfig(BaseModel):
    """What the users need computed, without any user's identity or preferences (the wire format)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1, max_length=64)
    favourites: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(default=[], max_length=500)
    lists: dict[
        Annotated[str, Field(min_length=1, max_length=96)],
        list[Annotated[str, Field(min_length=1, max_length=32)]],
    ] = Field(default={}, max_length=200)
    auto_top_n: int = Field(default=0, ge=0, le=500)
    detectors: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(default=[], max_length=1000)
    pattern_strategies: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(
        default=[], max_length=200
    )
    lifetime_bars: int = Field(default=2, ge=1, le=50)

    @field_validator("lists")
    @classmethod
    def _list_sizes(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if any(len(symbols) > 500 for symbols in value.values()):
            raise ValueError("a list holds at most 500 symbols")
        return value


def content_version(content: dict[str, Any]) -> str:
    return stable_hash(json.dumps(content, sort_keys=True, separators=(",", ":")), length=16)


def advisory_config(
    users: Sequence[AdvisoryPreferences], *, evidence: DetectorRegistry, strategies: StrategyRegistry
) -> AdvisoryConfig:
    """The union of the users' needs; ``version`` is a digest of the content (the HTTP ETag)."""
    favourites: list[str] = []
    lists: dict[str, list[str]] = {}
    top_n = 0
    detectors: set[str] = set()
    allowed_setups: set[str] = set()
    setups = pattern_setups(strategies)
    for i, prefs in enumerate(users):
        for w in prefs.watchlists:
            if w.kind is WatchlistKind.FAVOURITES:
                favourites += [s for s in w.symbols if s not in favourites]
            elif w.kind is WatchlistKind.CUSTOM:
                lists[f"{i}:{w.name}"] = list(w.symbols)
            else:
                top_n = max(top_n, w.size or 0)
        detectors |= prefs.theories.enabled_detectors(evidence)
        allowed_setups |= {s for s in setups if prefs.theories.pattern_strategies.get(s, True)}
    content: dict[str, Any] = {
        "favourites": favourites,
        "lists": lists,
        "auto_top_n": top_n,
        "detectors": sorted(detectors),
        "pattern_strategies": sorted(allowed_setups),
        "lifetime_bars": max((p.alerts.signal_lifetime_bars for p in users), default=2),
    }
    return AdvisoryConfig(version=content_version(content), **content)


def requirements_from_config(
    remote: AdvisoryConfig,
    config: AppConfig,
    *,
    ranked: Sequence[str],
    evidence: DetectorRegistry,
    strategies: StrategyRegistry,
    available: Sequence[str] | None = None,
) -> ComputeRequirements:
    symbols = monitored_set(
        allowlist=config.symbols.allowed,
        favourites=remote.favourites,
        lists=remote.lists,
        ranked=ranked,
        auto_top_n=remote.auto_top_n,
        cap=config.advisory.universe.monitored_cap,
        available=available,
    )
    known = set(evidence.ids)
    setups = set(pattern_setups(strategies))
    unknown = sorted((set(remote.detectors) - known) | (set(remote.pattern_strategies) - setups))
    if unknown:
        log.warning("advisory config %s names unknown detectors/setups, skipped: %s", remote.version, unknown)
    trading = {item.name for item in config.strategies.items if item.enabled}
    return ComputeRequirements(
        tuple(symbols),
        frozenset(set(remote.detectors) & known),
        frozenset(trading | (set(remote.pattern_strategies) & setups)),
        remote.lifetime_bars,
    )


def compute_requirements(
    users: Sequence[AdvisoryPreferences],
    config: AppConfig,
    *,
    ranked: Sequence[str],
    evidence: DetectorRegistry,
    strategies: StrategyRegistry,
    available: Sequence[str] | None = None,
) -> ComputeRequirements:
    return requirements_from_config(
        advisory_config(users, evidence=evidence, strategies=strategies),
        config,
        ranked=ranked,
        evidence=evidence,
        strategies=strategies,
        available=available,
    )


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
