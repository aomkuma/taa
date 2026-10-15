"""Entry lanes (owner, 2026-10-15: S1 on M1 next to V1 and F1 on M15; ``config.yaml`` → ``lanes``).

A lane is one entry timeframe with its own symbols, strategies, cooldowns and context
(:class:`app.config.LaneConfig`). The engine's main entry timeframe is the ``main`` lane. Each lane checks for
new closed bars on its own timeframe (its own watermarks) and arbitrates its own signals; each lane's selected
signal then goes through the one decision engine, account and risk budget the engine has.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig
from app.core.clock import Clock
from app.core.enums import Timeframe
from app.evidence.registry import EvidenceEngine
from app.market_data.candle_service import CandleService
from app.market_data.quote_service import QuoteService
from app.strategy.arbitration import SignalArbiter
from app.strategy.catalog import default_registry
from app.strategy.context_builder import ContextBuilder
from app.strategy.registry import StrategySet

MAIN = "main"


@dataclass
class EntryLane:
    name: str
    config: AppConfig  # the engine's config as the lane sees it (AppConfig.for_lane; the main lane: as is)
    strategies: StrategySet
    arbiter: SignalArbiter
    builder: ContextBuilder
    symbols: frozenset[str] | None  # None: every symbol of the engine

    @property
    def entry(self) -> Timeframe:
        return self.config.timeframes.entry

    @property
    def state_key(self) -> str:
        """The ``engine_state`` key of the lane's arbiter cooldowns (the main lane keeps the old key)."""
        return "arbiter_cooldowns" if self.name == MAIN else f"arbiter_cooldowns:{self.name}"

    def trades(self, symbol: str) -> bool:
        return self.symbols is None or symbol in self.symbols


def build_lanes(
    config: AppConfig,
    candles: CandleService,
    clock: Clock,
    quotes: QuoteService,
    evidence: EvidenceEngine | None,
) -> list[EntryLane]:
    """The extra lanes of *config* (the main lane is built by the engine itself)."""
    out = []
    for lane in config.lanes:
        cfg = config.for_lane(lane)
        strategies = default_registry().from_config(cfg.strategies, cfg.timeframes, cfg.evidence.confluence)
        out.append(
            EntryLane(
                lane.name,
                cfg,
                strategies,
                SignalArbiter(cfg.strategies.cooldown_bars),
                ContextBuilder(candles, cfg, clock, quotes, evidence),
                frozenset(lane.symbols),
            )
        )
    return out
