"""The AI assessment contract, schema v1.0 (PLAN R21; TAA-1301).

The AI layer is **veto-only** and optional: it may say a proposed entry looks wrong, never that a trade
should be larger, and nothing is ever executed from its text.

- :class:`AssessmentInput` carries **numeric market facts only** (the signal's geometry, each timeframe's
  closed-bar state, the session and spread). No account data, no balances, no credentials, no free text from
  outside the engine (PLAN §A20 "AI misuse or prompt injection").
- :class:`AssessmentV1` is the only answer accepted: a strict Pydantic schema (``extra="forbid"``) that also
  echoes the bar it judged, so an answer about another bar is refused (:func:`validate`).
- :class:`Assessment` is what the engine records for every call, whether it produced an answer or not.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.clock import ensure_utc
from app.strategy.signal_models import MarketContext, Signal

SCHEMA_VERSION = "1.0"
MAX_REASONS = 5
MAX_REASON_CHARS = 200


class Verdict(StrEnum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
    UNSURE = "UNSURE"


class Status(StrEnum):
    OK = "OK"  # a valid answer
    REFUSED = "REFUSED"  # stop_reason refusal (the whole fallback chain declined)
    TRUNCATED = "TRUNCATED"  # stop_reason max_tokens
    INVALID = "INVALID"  # the answer failed the schema or the bar check
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"  # API or transport error
    BUDGET = "BUDGET"  # the daily call or cost budget is used up; no call was made
    SKIPPED = "SKIPPED"  # no provider (AI off)


def _num(value: float | None) -> float | None:
    return None if value is None or not math.isfinite(value) else round(float(value), 6)


class AssessmentV1(BaseModel):
    """The model's answer. ``bar_close_utc`` must repeat the input's, verbatim."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    bar_close_utc: str = Field(min_length=10, max_length=40)
    verdict: Verdict
    confidence: int = Field(ge=0, le=100, description="0-100: how sure the verdict is")
    reasons: list[str] = Field(max_length=MAX_REASONS, description="short, factual, from the input only")


@dataclass(frozen=True, slots=True)
class AssessmentInput:
    signal_key: str  # idempotency key: strategy/symbol/bar/side (the per-candle cache key)
    bar_close_utc: str
    payload: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(self.payload, sort_keys=True, separators=(",", ":"))


def build_input(signal: Signal, market: MarketContext) -> AssessmentInput:
    """The numeric facts of one proposed entry (no account data)."""
    bar = ensure_utc(market.decision_time_utc).isoformat()
    states = [
        {
            "timeframe": s.timeframe.value,
            "close": _num(s.close),
            "trend": s.trend.value,
            "regime": s.regime.value,
            "volatility": s.volatility.value,
            "structure": s.structure,
            "atr": _num(s.atr),
            "atr_percentile": _num(s.atr_percentile),
            "adx": _num(s.adx),
            "rsi": _num(s.rsi),
            "ema_fast": _num(s.ema_fast),
            "ema_mid": _num(s.ema_mid),
            "ema_slow": _num(s.ema_slow),
        }
        for s in market.states
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "bar_close_utc": bar,
        "symbol": signal.symbol,
        "side": signal.side.value if signal.side is not None else None,
        "strategy": signal.strategy,
        "entry": _num(signal.entry_price),
        "stop_loss": _num(signal.stop_loss),
        "take_profit": _num(signal.take_profit),
        "score": _num(signal.score),
        "setup_strength": _num(signal.setup_strength),
        "reason_codes": list(signal.reason_codes)[:20],
        "conditions": [{"name": c.name, "passed": c.passed} for c in signal.conditions][:20],
        "session": market.session.value,
        "spread_points": _num(market.spread_points),
        "support_levels": [_num(x) for x in market.support_levels[:5]],
        "resistance_levels": [_num(x) for x in market.resistance_levels[:5]],
        "timeframes": states,
    }
    return AssessmentInput(signal.idempotency_key, bar, payload)


@dataclass(frozen=True, slots=True)
class Assessment:
    status: Status
    signal_key: str
    verdict: Verdict | None = None
    confidence: int | None = None
    reasons: tuple[str, ...] = ()
    model: str | None = None  # the model that answered (a fallback model when one served)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float | None = None
    detail: str = ""
    created_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def answered(self) -> bool:
        return self.status is Status.OK and self.verdict is not None


def validate(raw: Any, expected: AssessmentInput) -> AssessmentV1:
    """Parse and check an answer: the schema, then the bar it judged. Raises ``ValueError``."""
    try:
        answer = raw if isinstance(raw, AssessmentV1) else AssessmentV1.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(
            f"the answer does not match schema {SCHEMA_VERSION}: {exc.error_count()} errors"
        ) from exc
    if answer.bar_close_utc != expected.bar_close_utc:
        raise ValueError(f"the answer judged bar {answer.bar_close_utc}, not {expected.bar_close_utc}")
    reasons = [r.strip()[:MAX_REASON_CHARS] for r in answer.reasons if r.strip()]
    return answer.model_copy(update={"reasons": reasons})
