"""Every strategy the code ships. ``config.yaml`` → ``strategies.items`` selects and parameterizes them."""

from __future__ import annotations

from app.strategy.base_strategy import BaseStrategy
from app.strategy.example_strategy import TrendPullback
from app.strategy.registry import StrategyRegistry
from app.strategy.setups import SETUPS

# the inverted copies (``<name>_inverted``, 2026-10-09) were removed on 2026-10-14 (owner): a counter-trend
# trigger is faded inside its own setup instead (``fade_counter_trend``, SETUP_REVIEW §16)
STRATEGIES: tuple[type[BaseStrategy], ...] = (TrendPullback, *SETUPS)


def default_registry() -> StrategyRegistry:
    return StrategyRegistry(STRATEGIES)
