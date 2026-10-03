"""Every strategy the code ships. ``config.yaml`` → ``strategies.items`` selects and parameterizes them."""

from __future__ import annotations

from app.strategy.base_strategy import BaseStrategy
from app.strategy.example_strategy import TrendPullback
from app.strategy.registry import StrategyRegistry
from app.strategy.setups import SETUPS

STRATEGIES: tuple[type[BaseStrategy], ...] = (TrendPullback, *SETUPS)


def default_registry() -> StrategyRegistry:
    return StrategyRegistry(STRATEGIES)
