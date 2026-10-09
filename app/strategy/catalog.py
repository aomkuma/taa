"""Every strategy the code ships. ``config.yaml`` → ``strategies.items`` selects and parameterizes them."""

from __future__ import annotations

from app.strategy.base_strategy import BaseStrategy
from app.strategy.example_strategy import TrendPullback
from app.strategy.inverted import inverted
from app.strategy.registry import StrategyRegistry
from app.strategy.setups import SETUPS

ORIGINALS: tuple[type[BaseStrategy], ...] = (TrendPullback, *SETUPS)
# owner, 2026-10-09: every original also as ``<name>_inverted`` (the other side, the same exit prices)
INVERTED: tuple[type[BaseStrategy], ...] = tuple(inverted(c) for c in ORIGINALS)
STRATEGIES: tuple[type[BaseStrategy], ...] = (*ORIGINALS, *INVERTED)


def default_registry() -> StrategyRegistry:
    return StrategyRegistry(STRATEGIES)
