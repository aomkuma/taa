"""Strategy base class (PLAN §A7).

A strategy is a pure function of a :class:`StrategyContext`: no broker, no database, no credentials, no
execution and no wall-clock reads (``ctx.now_utc`` is the evaluation time). It returns exactly one
:class:`Signal` per call: BUY, SELL or HOLD with reason codes. Parameters come from ``config.yaml`` →
``strategies.items[].params`` and are validated by the strategy's ``Params`` model (unknown keys are errors).

Every strategy in Milestone 1 is a demonstration: ``demo_only = True`` is shown next to its signals, and
nothing here claims profitability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import timedelta
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Action, EntryType, Timeframe
from app.core.ids import new_id
from app.evidence.framework import Family
from app.strategy.signal_models import (
    Condition,
    ReasonCode,
    Signal,
    SignalEvidence,
    StrategyContext,
    condition_strength,
)


class StrategyParams(BaseModel):
    """Base parameter model; strategies subclass it with bounded fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expiry_bars: int = Field(default=1, ge=1, le=96, description="signal lifetime in entry bars")


class BaseStrategy(ABC):
    name: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    description: ClassVar[str] = ""
    demo_only: ClassVar[bool] = True  # not production-proven; the PWA labels its signals accordingly
    Params: ClassVar[type[StrategyParams]] = StrategyParams
    # evidence families the checklist already measures: they add no confluence support (TAA-307)
    core_families: ClassVar[frozenset[Family]] = frozenset()

    def __init__(self, params: StrategyParams | None = None) -> None:
        self.params: Any = params if params is not None else self.Params()
        if not isinstance(self.params, self.Params):
            raise TypeError(f"{self.name} expects {self.Params.__name__}, got {type(self.params).__name__}")

    # contract ------------------------------------------------------------------------------------------

    @abstractmethod
    def required_timeframes(self) -> tuple[Timeframe, ...]:
        """Timeframes whose frames ``evaluate`` reads; they must be enabled in ``timeframes:``."""

    @abstractmethod
    def warmup_bars(self) -> int:
        """Closed bars needed per timeframe before the first non-HOLD signal is possible."""

    @abstractmethod
    def evaluate(self, ctx: StrategyContext) -> Signal:
        """One signal for ``ctx.symbol`` at ``ctx.decision_time_utc``."""

    # signal builders -----------------------------------------------------------------------------------

    def _base(self, ctx: StrategyContext, action: Action) -> dict[str, Any]:
        market = ctx.market
        tf = market.entry_timeframe
        return {
            "signal_id": new_id(),
            "strategy": self.name,
            "strategy_version": self.version,
            "symbol": market.symbol,
            "timeframe": tf,
            "action": action,
            "data_timestamp_utc": market.decision_time_utc,
            "created_at_utc": ctx.now_utc,
            "expires_at_utc": market.decision_time_utc
            + timedelta(seconds=tf.seconds * self.params.expiry_bars),
            "bar_times": tuple(market.bar_times.items()),
        }

    def hold(
        self,
        ctx: StrategyContext,
        *reasons: ReasonCode | str,
        conditions: Iterable[Condition] = (),
        explanation: str = "",
    ) -> Signal:
        conds = tuple(conditions)
        return Signal(
            **self._base(ctx, Action.HOLD),
            setup_strength=condition_strength(conds),
            conditions=conds,
            reason_codes=tuple(str(r) for r in reasons) or (ReasonCode.NO_SETUP.value,),
            explanation=explanation,
        )

    def entry(
        self,
        ctx: StrategyContext,
        action: Action,
        *,
        entry_price: float,
        stop_loss: float,
        take_profit: float | None,
        conditions: Iterable[Condition],
        score: float,
        reasons: Iterable[ReasonCode | str] = (),
        explanation: str = "",
        entry_type: EntryType = EntryType.MARKET,
        evidence: Iterable[SignalEvidence] = (),
    ) -> Signal:
        if not action.is_entry:
            raise ValueError(f"entry() needs BUY or SELL, not {action}")
        conds = tuple(conditions)
        labels = [*reasons, *([ReasonCode.DEMO_UNPROVEN] if self.demo_only else [])]
        return Signal(
            **self._base(ctx, action),
            entry_type=entry_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            score=min(100.0, max(0.0, score)),
            setup_strength=condition_strength(conds),
            conditions=conds,
            evidence=tuple(evidence),
            reason_codes=tuple(str(r) for r in labels),
            explanation=explanation,
        )
