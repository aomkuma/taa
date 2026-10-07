"""Strategy registry: builds the enabled strategies from ``config.yaml`` and runs them safely (PLAN §A7).

- The catalog is the set of strategy classes the code ships. ``strategies.items`` selects and parameterizes
  them; an unknown name, a duplicate entry, invalid params, a timeframe that is not enabled or a warm-up
  longer than ``timeframes.warmup_bars`` is a :class:`ConfigError` at startup.
- :meth:`StrategySet.evaluate` attaches the context's evidence to every signal (TAA-307). It is also the
  plugin boundary: an exception inside a strategy, or a signal that does not belong to the context it was
  given, becomes HOLD (``STRATEGY_ERROR``) and is logged with its traceback. One faulty strategy never
  stops the others or the engine loop.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.config import ConfluenceConfig, StrategiesConfig, TimeframesConfig
from app.core.errors import ConfigError
from app.strategy.base_strategy import BaseStrategy
from app.strategy.enrichment import enrich
from app.strategy.signal_models import ReasonCode, Signal, StrategyContext

log = logging.getLogger(__name__)


class StrategyRegistry:
    def __init__(self, catalog: Iterable[type[BaseStrategy]]) -> None:
        self._classes: dict[str, type[BaseStrategy]] = {}
        for cls in catalog:
            if cls.name in self._classes:
                raise ConfigError(f"duplicate strategy name {cls.name!r}")
            self._classes[cls.name] = cls

    @property
    def names(self) -> list[str]:
        return sorted(self._classes)

    def get(self, name: str) -> type[BaseStrategy]:
        try:
            return self._classes[name]
        except KeyError:
            raise ConfigError(f"unknown strategy {name!r}; available: {self.names}") from None

    def create(self, name: str, raw_params: dict[str, object], expiry_bars: int) -> BaseStrategy:
        cls = self.get(name)
        try:
            params = cls.Params.model_validate({"expiry_bars": expiry_bars, **raw_params})
        except ValidationError as exc:
            raise ConfigError(f"invalid params for strategy {name}: {exc}") from exc
        return cls(params)

    def from_config(
        self,
        strategies: StrategiesConfig,
        timeframes: TimeframesConfig,
        confluence: ConfluenceConfig | None = None,
    ) -> StrategySet:
        seen: set[str] = set()
        built: list[BaseStrategy] = []
        for item in strategies.items:
            if item.name in seen:
                raise ConfigError(f"strategy {item.name!r} is listed twice")
            seen.add(item.name)
            strategy = self.create(item.name, item.params, strategies.signal_expiry_bars)
            missing = [tf for tf in strategy.required_timeframes() if tf not in timeframes.enabled]
            if missing:
                raise ConfigError(f"strategy {item.name} needs timeframes {missing} that are not enabled")
            if strategy.warmup_bars() > timeframes.warmup_bars:
                raise ConfigError(
                    f"strategy {item.name} needs {strategy.warmup_bars()} warm-up bars; "
                    f"timeframes.warmup_bars is {timeframes.warmup_bars}"
                )
            if item.enabled:
                built.append(strategy)
        return StrategySet(tuple(built), confluence or ConfluenceConfig())


@dataclass(frozen=True)
class StrategySet:
    strategies: Sequence[BaseStrategy]
    confluence: ConfluenceConfig = field(default_factory=ConfluenceConfig)

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.strategies]

    def required_detectors(self) -> frozenset[str]:
        return frozenset().union(*(s.required_detectors() for s in self.strategies))

    def evaluate(self, ctx: StrategyContext) -> list[Signal]:
        """One signal per strategy, enriched with the context's evidence (confluence setup strength)."""
        return [
            enrich(self._evaluate_one(s, ctx), ctx, self.confluence, s.core_families) for s in self.strategies
        ]

    @staticmethod
    def _evaluate_one(strategy: BaseStrategy, ctx: StrategyContext) -> Signal:
        try:
            signal = strategy.evaluate(ctx)
        except Exception:  # plugin boundary: a strategy bug must fail closed, not stop the loop
            log.exception("strategy %s failed on %s at %s", strategy.name, ctx.symbol, ctx.decision_time_utc)
            return strategy.hold(ctx, ReasonCode.STRATEGY_ERROR, explanation="strategy raised an exception")
        problem = _mismatch(strategy, ctx, signal)
        if problem:
            log.error("strategy %s returned an invalid signal: %s", strategy.name, problem)
            return strategy.hold(ctx, ReasonCode.STRATEGY_ERROR, explanation=problem)
        return signal


def _mismatch(strategy: BaseStrategy, ctx: StrategyContext, signal: object) -> str:
    if not isinstance(signal, Signal):
        return f"expected a Signal, got {type(signal).__name__}"
    if signal.strategy != strategy.name:
        return f"signal is labelled {signal.strategy!r}"
    if signal.symbol != ctx.symbol:
        return f"signal is for {signal.symbol}, context is {ctx.symbol}"
    if signal.data_timestamp_utc != ctx.decision_time_utc:
        return "signal timestamp differs from the decision bar"
    if signal.timeframe is not ctx.market.entry_timeframe:
        return f"signal timeframe {signal.timeframe} is not the entry timeframe"
    return ""
