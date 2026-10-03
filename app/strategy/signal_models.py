"""Signal and context models of the strategy layer (PLAN §A5, §A7, §A26, §A29).

- :class:`Signal` is what a strategy emits for one symbol at one closed entry-timeframe bar. It carries
  the condition checklist behind it (``conditions`` → ``setup_strength``) and the technical evidence that
  supports or contradicts it. ``score`` is a documented heuristic for ranking, **not a probability**.
- :class:`MarketContext` is the serializable summary of the market at the decision bar (per-timeframe
  state, the bar times used, quote, session, quality flags). It is persisted with every decision.
- :class:`StrategyContext` is what :meth:`BaseStrategy.evaluate` receives: the market context plus
  read-only candle frames with indicator columns. It holds no broker handle and no credentials.

Geometry problems (missing SL, SL on the wrong side, low RR) are *not* rejected here: the decision engine
reports them with exact reason codes (§A8). The models only reject malformed values (naive datetimes, NaN
prices, scores out of range), because those are bugs rather than market outcomes.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

import pandas as pd

from app.core.clock import ensure_utc
from app.core.enums import Action, EntryType, Regime, Session, Side, Timeframe, Trend, VolatilityState
from app.core.errors import TaaError
from app.core.ids import stable_hash
from app.evidence.confluence import Relation
from app.evidence.framework import ActiveEvidence, EvidenceSnapshot
from app.market_data.data_models import SymbolSpec


class SignalError(TaaError):
    """A signal or context record is malformed (a programming error, never a market condition)."""


class ReasonCode(StrEnum):
    """Why a strategy holds, or the main facts behind an entry. PWA text uses ``reason.<code>``."""

    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATA_QUALITY = "DATA_QUALITY"
    NO_SETUP = "NO_SETUP"
    NO_BIAS = "NO_BIAS"
    REGIME_NOT_TRENDING = "REGIME_NOT_TRENDING"
    OUTSIDE_SESSION = "OUTSIDE_SESSION"
    FRIDAY_CUTOFF = "FRIDAY_CUTOFF"
    NEAR_OPPOSING_LEVEL = "NEAR_OPPOSING_LEVEL"
    SL_TOO_FAR = "SL_TOO_FAR"
    RR_TOO_LOW = "RR_TOO_LOW"
    SPREAD_TOO_HIGH = "SPREAD_TOO_HIGH"
    CONFLICT = "CONFLICT"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    DUPLICATE_SIGNAL = "DUPLICATE_SIGNAL"
    LOWER_RANK = "LOWER_RANK"
    STRATEGY_ERROR = "STRATEGY_ERROR"
    DEMO_UNPROVEN = "DEMO_UNPROVEN"  # label on every entry of a demonstration strategy


def _finite(name: str, value: float | None) -> None:
    if value is not None and not math.isfinite(value):
        raise SignalError(f"{name} must be finite (got {value!r})")


def _opt_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _opt_dt(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Sorted keys, no whitespace, no NaN: equal records serialize to equal bytes."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


# --- signal parts -----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Condition:
    """One item of a strategy's checklist. ``weight`` is its share of the setup strength."""

    name: str  # stable code, e.g. "htf_bias"; the PWA label is ``condition.<name>``
    passed: bool
    weight: float = 1.0
    detail: str = ""  # the measured value against its threshold, e.g. "ADX 23.4 >= 20"

    def __post_init__(self) -> None:
        if not self.name:
            raise SignalError("condition needs a name")
        if not (math.isfinite(self.weight) and self.weight > 0):
            raise SignalError(f"condition {self.name}: weight must be > 0 (got {self.weight!r})")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "weight": self.weight, "detail": self.detail}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Condition:
        return cls(str(d["name"]), bool(d["passed"]), float(d["weight"]), str(d["detail"]))


def condition_strength(conditions: Iterable[Condition]) -> float:
    """Weighted share of passed conditions, 0–100 (§A26 setup strength before confluence enrichment)."""
    items = list(conditions)
    total = sum(c.weight for c in items)
    if total <= 0:
        return 0.0
    return 100.0 * sum(c.weight for c in items if c.passed) / total


@dataclass(frozen=True, slots=True)
class SignalEvidence:
    """An active evidence item attached to a signal, classified against the signal's direction."""

    item: ActiveEvidence
    relation: Relation

    def to_dict(self) -> dict[str, Any]:
        return {"item": self.item.to_dict(), "relation": self.relation.value}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> SignalEvidence:
        return cls(ActiveEvidence.from_dict(d["item"]), Relation(d["relation"]))


# --- signal -----------------------------------------------------------------------------------------------


def idempotency_key(
    strategy: str, symbol: str, timeframe: Timeframe, bar_close: datetime, action: Action
) -> str:
    """``sha256(strategy|symbol|tf|bar_close_utc|action)`` (§A7).

    At most one signal per strategy, symbol, bar and action.
    """
    return stable_hash(strategy, symbol, timeframe.value, ensure_utc(bar_close).isoformat(), action.value)


@dataclass(frozen=True, slots=True)
class Signal:
    signal_id: str
    strategy: str
    strategy_version: str
    symbol: str
    timeframe: Timeframe  # entry timeframe
    action: Action
    data_timestamp_utc: datetime  # close time of the entry-timeframe bar the signal was computed at
    created_at_utc: datetime
    expires_at_utc: datetime
    entry_type: EntryType = EntryType.MARKET
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    score: float = 0.0  # 0–100 ranking heuristic; NOT a probability
    setup_strength: float = 0.0  # 0–100: checklist share, later blended with confluence (TAA-307)
    conditions: tuple[Condition, ...] = ()
    evidence: tuple[SignalEvidence, ...] = ()
    reason_codes: tuple[str, ...] = ()
    explanation: str = ""
    bar_times: tuple[tuple[Timeframe, datetime], ...] = ()  # last closed bar used per timeframe
    confluence: tuple[tuple[str, float], ...] = ()  # signed setup-strength points per source (TAA-307)

    def __post_init__(self) -> None:
        for name in ("data_timestamp_utc", "created_at_utc", "expires_at_utc"):
            object.__setattr__(self, name, ensure_utc(getattr(self, name)))
        times = sorted(((tf, ensure_utc(t)) for tf, t in self.bar_times), key=lambda p: -p[0].seconds)
        object.__setattr__(self, "bar_times", tuple(times))
        if not (self.signal_id and self.strategy and self.symbol):
            raise SignalError("signal needs signal_id, strategy and symbol")
        if self.expires_at_utc <= self.data_timestamp_utc:
            raise SignalError("signal must expire after its data timestamp")
        for name in ("entry_price", "stop_loss", "take_profit"):
            _finite(name, getattr(self, name))
        for name in ("score", "setup_strength"):
            value = getattr(self, name)
            if not (math.isfinite(value) and 0.0 <= value <= 100.0):
                raise SignalError(f"{name} must be in [0, 100] (got {value!r})")
        if self.action not in (Action.BUY, Action.SELL, Action.HOLD):
            raise SignalError(f"strategies emit BUY, SELL or HOLD, not {self.action}")

    # derived -------------------------------------------------------------------------------------------

    @property
    def idempotency_key(self) -> str:
        return idempotency_key(
            self.strategy, self.symbol, self.timeframe, self.data_timestamp_utc, self.action
        )

    @property
    def is_entry(self) -> bool:
        return self.action.is_entry

    @property
    def side(self) -> Side | None:
        return Side.from_action(self.action) if self.action.is_entry else None

    @property
    def risk_distance(self) -> float | None:
        if self.entry_price is None or self.stop_loss is None:
            return None
        return abs(self.entry_price - self.stop_loss)

    @property
    def risk_reward(self) -> float | None:
        """Reward / risk in price distance; ``None`` when a price is missing or the risk is zero."""
        risk = self.risk_distance
        if risk is None or self.take_profit is None or self.entry_price is None or risk == 0:
            return None
        return abs(self.take_profit - self.entry_price) / risk

    def is_expired(self, now_utc: datetime) -> bool:
        return ensure_utc(now_utc) >= self.expires_at_utc

    @property
    def supporting(self) -> tuple[SignalEvidence, ...]:
        return tuple(e for e in self.evidence if e.relation is Relation.SUPPORTS)

    @property
    def conflicting(self) -> tuple[SignalEvidence, ...]:
        return tuple(e for e in self.evidence if e.relation is Relation.CONFLICTS)

    # serialization -------------------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "idempotency_key": self.idempotency_key,
            "strategy": self.strategy,
            "strategy_version": self.strategy_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "action": self.action.value,
            "data_timestamp_utc": self.data_timestamp_utc.isoformat(),
            "created_at_utc": self.created_at_utc.isoformat(),
            "expires_at_utc": self.expires_at_utc.isoformat(),
            "entry_type": self.entry_type.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "score": self.score,
            "setup_strength": self.setup_strength,
            "conditions": [c.to_dict() for c in self.conditions],
            "evidence": [e.to_dict() for e in self.evidence],
            "reason_codes": list(self.reason_codes),
            "explanation": self.explanation,
            "bar_times": {tf.value: t.isoformat() for tf, t in self.bar_times},
            "confluence": [[name, points] for name, points in self.confluence],
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Signal:
        sig = cls(
            signal_id=d["signal_id"],
            strategy=d["strategy"],
            strategy_version=d["strategy_version"],
            symbol=d["symbol"],
            timeframe=Timeframe(d["timeframe"]),
            action=Action(d["action"]),
            data_timestamp_utc=datetime.fromisoformat(d["data_timestamp_utc"]),
            created_at_utc=datetime.fromisoformat(d["created_at_utc"]),
            expires_at_utc=datetime.fromisoformat(d["expires_at_utc"]),
            entry_type=EntryType(d["entry_type"]),
            entry_price=_opt_float(d["entry_price"]),
            stop_loss=_opt_float(d["stop_loss"]),
            take_profit=_opt_float(d["take_profit"]),
            score=float(d["score"]),
            setup_strength=float(d["setup_strength"]),
            conditions=tuple(Condition.from_dict(c) for c in d["conditions"]),
            evidence=tuple(SignalEvidence.from_dict(e) for e in d["evidence"]),
            reason_codes=tuple(str(r) for r in d["reason_codes"]),
            explanation=d["explanation"],
            bar_times=tuple((Timeframe(tf), datetime.fromisoformat(t)) for tf, t in d["bar_times"].items()),
            confluence=tuple((str(n), float(p)) for n, p in d.get("confluence", [])),
        )
        if d.get("idempotency_key") not in (None, sig.idempotency_key):
            raise SignalError(
                f"idempotency key mismatch for signal {sig.signal_id}: stored record was altered"
            )
        return sig

    @classmethod
    def from_json(cls, text: str) -> Signal:
        return cls.from_dict(json.loads(text))


# --- market context ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TimeframeState:
    """What one timeframe says at the decision time (all values from closed bars only)."""

    timeframe: Timeframe
    bar_close_utc: datetime  # close time of the last bar used
    close: float
    trend: Trend
    regime: Regime
    volatility: VolatilityState
    structure: str | None = None  # UP / DOWN / RANGE from confirmed swings
    atr: float | None = None
    atr_percentile: float | None = None
    adx: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    rsi: float | None = None
    ema_fast: float | None = None
    ema_mid: float | None = None
    ema_slow: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "bar_close_utc", ensure_utc(self.bar_close_utc))
        _finite("close", self.close)
        for name in _STATE_FLOATS:
            _finite(name, getattr(self, name))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "timeframe": self.timeframe.value,
            "bar_close_utc": self.bar_close_utc.isoformat(),
            "close": self.close,
            "trend": self.trend.value,
            "regime": self.regime.value,
            "volatility": self.volatility.value,
            "structure": self.structure,
        }
        out.update({name: getattr(self, name) for name in _STATE_FLOATS})
        return out

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> TimeframeState:
        return cls(
            timeframe=Timeframe(d["timeframe"]),
            bar_close_utc=datetime.fromisoformat(d["bar_close_utc"]),
            close=float(d["close"]),
            trend=Trend(d["trend"]),
            regime=Regime(d["regime"]),
            volatility=VolatilityState(d["volatility"]),
            structure=d["structure"],
            **{name: _opt_float(d[name]) for name in _STATE_FLOATS},
        )


_STATE_FLOATS = (
    "atr",
    "atr_percentile",
    "adx",
    "plus_di",
    "minus_di",
    "rsi",
    "ema_fast",
    "ema_mid",
    "ema_slow",
)


@dataclass(frozen=True, slots=True)
class MarketContext:
    """The market at one decision bar of one symbol. Persisted with every decision record."""

    symbol: str
    decision_time_utc: datetime  # close time of the entry-timeframe bar being evaluated
    entry_timeframe: Timeframe
    higher_timeframe: Timeframe
    states: tuple[TimeframeState, ...]  # one per enabled timeframe, longest first
    session: Session = Session.OFF
    bid: float | None = None
    ask: float | None = None
    spread_points: float | None = None
    quote_time_utc: datetime | None = None
    quality_flags: tuple[str, ...] = ()
    support_levels: tuple[float, ...] = ()  # nearest S/R zone centres below / above the close (entry TF)
    resistance_levels: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_time_utc", ensure_utc(self.decision_time_utc))
        if self.quote_time_utc is not None:
            object.__setattr__(self, "quote_time_utc", ensure_utc(self.quote_time_utc))
        tfs = [s.timeframe for s in self.states]
        if len(set(tfs)) != len(tfs):
            raise SignalError("market context has duplicate timeframe states")
        for tf in (self.entry_timeframe, self.higher_timeframe):
            if tf not in tfs:
                raise SignalError(f"market context lacks the {tf} state")
        for state in self.states:
            if state.bar_close_utc > self.decision_time_utc:
                raise SignalError(f"{state.timeframe} bar closes after the decision time (look-ahead)")
        for name in ("bid", "ask", "spread_points"):
            _finite(name, getattr(self, name))
        object.__setattr__(self, "states", tuple(sorted(self.states, key=lambda s: -s.timeframe.seconds)))

    def state(self, tf: Timeframe) -> TimeframeState:
        for s in self.states:
            if s.timeframe is tf:
                return s
        raise SignalError(f"market context has no {tf} state")

    @property
    def entry(self) -> TimeframeState:
        return self.state(self.entry_timeframe)

    @property
    def higher(self) -> TimeframeState:
        return self.state(self.higher_timeframe)

    @property
    def trend(self) -> Trend:
        """The bias: the higher timeframe's trend."""
        return self.higher.trend

    @property
    def regime(self) -> Regime:
        return self.higher.regime

    @property
    def volatility(self) -> VolatilityState:
        return self.entry.volatility

    @property
    def atr(self) -> float | None:
        return self.entry.atr

    @property
    def adx(self) -> float | None:
        return self.higher.adx

    @property
    def bar_times(self) -> dict[Timeframe, datetime]:
        return {s.timeframe: s.bar_close_utc for s in self.states}

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "decision_time_utc": self.decision_time_utc.isoformat(),
            "entry_timeframe": self.entry_timeframe.value,
            "higher_timeframe": self.higher_timeframe.value,
            "states": [s.to_dict() for s in self.states],
            "session": self.session.value,
            "bid": self.bid,
            "ask": self.ask,
            "spread_points": self.spread_points,
            "quote_time_utc": None if self.quote_time_utc is None else self.quote_time_utc.isoformat(),
            "quality_flags": list(self.quality_flags),
            "support_levels": list(self.support_levels),
            "resistance_levels": list(self.resistance_levels),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> MarketContext:
        return cls(
            symbol=d["symbol"],
            decision_time_utc=datetime.fromisoformat(d["decision_time_utc"]),
            entry_timeframe=Timeframe(d["entry_timeframe"]),
            higher_timeframe=Timeframe(d["higher_timeframe"]),
            states=tuple(TimeframeState.from_dict(s) for s in d["states"]),
            session=Session(d["session"]),
            bid=_opt_float(d["bid"]),
            ask=_opt_float(d["ask"]),
            spread_points=_opt_float(d["spread_points"]),
            quote_time_utc=_opt_dt(d["quote_time_utc"]),
            quality_flags=tuple(d["quality_flags"]),
            support_levels=tuple(float(x) for x in d["support_levels"]),
            resistance_levels=tuple(float(x) for x in d["resistance_levels"]),
        )

    @property
    def digest(self) -> str:
        return stable_hash(self.to_json())

    @classmethod
    def from_json(cls, text: str) -> MarketContext:
        return cls.from_dict(json.loads(text))


# --- strategy input ---------------------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class StrategyContext:
    """Everything a strategy may read. Pure data: no gateway, no database, no secrets.

    ``frames[tf]`` holds closed candles indexed by bar close time (UTC) up to the decision time, with the
    indicator columns the context builder computed (see ``FRAME_COLUMNS`` in ``context_builder``). Strategies
    must treat them as read-only; the builder hands every strategy its own copy.
    """

    market: MarketContext
    frames: Mapping[Timeframe, pd.DataFrame]
    now_utc: datetime  # wall-clock time of the evaluation (signal ``created_at``)
    spec: SymbolSpec | None = None  # broker spec snapshot (data only)
    evidence: Mapping[Timeframe, EvidenceSnapshot] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "now_utc", ensure_utc(self.now_utc))
        object.__setattr__(self, "frames", MappingProxyType(dict(self.frames)))
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))
        for tf, frame in self.frames.items():
            if len(frame) and pd.Timestamp(frame.index[-1]) > pd.Timestamp(self.market.decision_time_utc):
                raise SignalError(f"{tf} frame extends past the decision time (look-ahead)")

    @property
    def symbol(self) -> str:
        return self.market.symbol

    @property
    def decision_time_utc(self) -> datetime:
        return self.market.decision_time_utc

    def frame(self, tf: Timeframe) -> pd.DataFrame:
        try:
            return self.frames[tf]
        except KeyError:
            raise SignalError(f"strategy context has no {tf} frame") from None

    def all_evidence(self) -> list[ActiveEvidence]:
        """Active evidence of every timeframe, longest timeframe first."""
        out: list[ActiveEvidence] = []
        for tf in sorted(self.evidence, key=lambda t: -t.seconds):
            out.extend(self.evidence[tf].items)
        return out
