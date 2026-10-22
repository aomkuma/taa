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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Action, EntryType, Side, Timeframe
from app.core.ids import new_id
from app.evidence.framework import Family
from app.strategy.signal_models import (
    Condition,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    SignalEvidence,
    StrategyContext,
    condition_strength,
)


@dataclass(frozen=True, slots=True)
class PastEntry:
    """An entry the engine accepted earlier (from its stored decisions): what a strategy with an
    ``entry_group`` reads before deciding (e.g. PLAN-1 B2's "second trade of the morning only on the first's
    side"), so the rule survives a restart."""

    at: datetime
    side: Side
    strategy: str


class StrategyParams(BaseModel):
    """Base parameter model; strategies subclass it with bounded fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expiry_bars: int = Field(default=1, ge=1, le=96, description="signal lifetime in entry bars")


class BaseStrategy(ABC):
    name: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    description: ClassVar[str] = ""
    demo_only: ClassVar[bool] = True  # not production-proven; the PWA labels its signals accordingly
    advised: ClassVar[bool] = True  # offered to users as a theory / alert source; False: the bot only
    Params: ClassVar[type[StrategyParams]] = StrategyParams
    # evidence families the checklist already measures: they add no confluence support (TAA-307)
    core_families: ClassVar[frozenset[Family]] = frozenset()
    # the strategies whose accepted entries (the last day's) the engine hands over before each evaluation
    entry_group: ClassVar[tuple[str, ...]] = ()

    def __init__(self, params: StrategyParams | None = None) -> None:
        self.params: Any = params if params is not None else self.Params()
        if not isinstance(self.params, self.Params):
            raise TypeError(f"{self.name} expects {self.Params.__name__}, got {type(self.params).__name__}")

    # contract ------------------------------------------------------------------------------------------

    def required_detectors(self) -> frozenset[str]:
        """The evidence detectors the strategy needs to fire at all (backtests run only these by default)."""
        return frozenset()

    @abstractmethod
    def required_timeframes(self) -> tuple[Timeframe, ...]:
        """Timeframes whose frames ``evaluate`` reads; they must be enabled in ``timeframes:``."""

    @abstractmethod
    def warmup_bars(self) -> int:
        """Closed bars needed per timeframe before the first non-HOLD signal is possible."""

    @abstractmethod
    def evaluate(self, ctx: StrategyContext) -> Signal:
        """One signal for ``ctx.symbol`` at ``ctx.decision_time_utc``."""

    def attach_entries(self, symbol: str, entries: Sequence[PastEntry]) -> None:
        """The ``entry_group``'s accepted entries on *symbol* (the engine reads them from its decision store
        before each evaluation; default: not used)."""
        return None

    def wants_bar(self, at: datetime) -> bool:
        """Whether :meth:`evaluate` can enter at the bar closing at *at* (default: always). A backtest skips
        building the context of a bar no strategy of its lane wants while the lane holds no position or order
        (the result is the same HOLD, faster)."""
        return True

    def should_close(self, ctx: StrategyContext, side: Side) -> bool:
        """Whether an open position of this strategy should be closed at this bar (default: never)."""
        return False

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        """The strategy's own management of *pos* at this closed bar, next to the configured rules (default:
        none). It must hold without its own memory (a restart): *pos* carries the plan's prices."""
        return None

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
        risk_scale: float = 1.0,
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
            risk_scale=risk_scale,
        )
