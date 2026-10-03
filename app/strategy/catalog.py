"""Every strategy the code ships. ``config.yaml`` → ``strategies.items`` selects and parameterizes them."""

from __future__ import annotations

from app.strategy.base_strategy import BaseStrategy
from app.strategy.example_strategy import TrendPullback
from app.strategy.registry import StrategyRegistry

STRATEGIES: tuple[type[BaseStrategy], ...] = (TrendPullback,)


def default_registry() -> StrategyRegistry:
    return StrategyRegistry(STRATEGIES)
