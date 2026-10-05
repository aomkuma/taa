"""AI providers (PLAN R21; TAA-1301/1302).

- :class:`AIProvider` is the protocol the engine calls: one :class:`~app.ai.schema.AssessmentInput` in, one
  :class:`~app.ai.schema.Assessment` out, never an exception. Every failure becomes a status that the veto
  gate treats as HOLD (``AI_UNAVAILABLE``).
- :class:`NullProvider` answers ``SKIPPED`` (no AI).
- :class:`AnthropicProvider` asks Claude through the official SDK with structured outputs
  (``client.beta.messages.parse`` with the :class:`~app.ai.schema.AssessmentV1` model). It uses low effort,
  a short timeout with one retry and server-side ``fallbacks: "default"``. A refusal or a ``max_tokens`` stop
  becomes HOLD, and usage and cost are logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

from app.ai.schema import Assessment, AssessmentInput, AssessmentV1, Status, validate
from app.core.clock import Clock

log = logging.getLogger(__name__)

# $ per million tokens (input, output), first-party Claude API rates; unknown models are logged without a cost
PRICES: Mapping[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_TOKENS = 4000

SYSTEM_PROMPT = (
    "You review one proposed trade entry of an automated trading engine before it is placed. The "
    "input is a JSON object of numeric market facts at one closed bar: the signal's entry, stop-loss "
    "and take-profit, its strategy, score, reason codes and checklist, and per-timeframe trend, "
    "regime, volatility, ADX, RSI, ATR and moving averages, the session and the spread. Judge only "
    "from these facts. Answer with the verdict AGREE when the entry is consistent with the facts, "
    "DISAGREE when the facts argue against it (for example the higher timeframe trend opposes it, the "
    "stop sits inside noise, the target is unrealistic for the volatility, or the spread is large "
    "against the stop), and UNSURE when the facts are mixed. Confidence is 0-100. Give at most five "
    "short, factual reasons that cite the input. Repeat bar_close_utc exactly as given and set "
    "schema_version to 1.0. You cannot change the trade's size; you can only agree or object."
)


def cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> float:
    price = PRICES.get(model or "")
    if price is None:
        return 0.0
    return round(input_tokens * price[0] / 1_000_000 + output_tokens * price[1] / 1_000_000, 6)


class AIProvider(Protocol):
    name: str

    def assess(self, request: AssessmentInput) -> Assessment: ...


class NullProvider:
    name = "none"

    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def assess(self, request: AssessmentInput) -> Assessment:
        return Assessment(
            Status.SKIPPED, request.signal_key, created_at=self.clock.now_utc(), detail="AI is off"
        )


class AnthropicProvider:
    """Claude through the Anthropic SDK. *client_factory* builds the client (tests inject a fake)."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        clock: Clock,
        *,
        model: str = "claude-opus-5-5",
        effort: str = "low",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.clock = clock
        if client_factory is None:
            import anthropic

            client_factory = anthropic.Anthropic
        # a short timeout and one retry: an assessment is only useful while its bar is current
        self.client = client_factory(api_key=api_key, timeout=timeout_seconds, max_retries=1)

    def assess(self, request: AssessmentInput) -> Assessment:
        started = time.perf_counter()
        now = self.clock.now_utc()

        def done(status: Status, detail: str = "", **kw: Any) -> Assessment:
            latency = round((time.perf_counter() - started) * 1000, 1)
            result = Assessment(
                status, request.signal_key, latency_ms=latency, created_at=now, detail=detail[:500], **kw
            )
            log.info(
                "AI %s %s: %s %s conf=%s tokens=%s/%s cost=$%.4f %sms %s",
                request.signal_key[:12],
                result.model or self.model,
                status.value,
                result.verdict.value if result.verdict else "-",
                result.confidence,
                result.input_tokens,
                result.output_tokens,
                result.cost_usd,
                latency,
                detail[:120],
            )
            return result

        try:
            import anthropic
        except ImportError:  # pragma: no cover - the engine requirements pin it
            return done(Status.ERROR, "the anthropic package is not installed")
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": request.to_json()}],
                output_format=AssessmentV1,
                output_config=cast(Any, {"effort": self.effort}),
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APITimeoutError as exc:
            return done(Status.TIMEOUT, str(exc))
        except anthropic.APIError as exc:  # status, rate-limit and connection errors alike: HOLD
            return done(Status.ERROR, f"{type(exc).__name__}: {exc}")
        usage = getattr(response, "usage", None)
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
        model = str(getattr(response, "model", self.model))
        spend: dict[str, Any] = {
            "model": model,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cost_usd": cost_usd(model, tokens_in, tokens_out),
        }
        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details is not None else None
            return done(Status.REFUSED, f"refusal ({category})", **spend)
        if stop == "max_tokens":
            return done(Status.TRUNCATED, "max_tokens", **spend)
        try:
            answer = validate(getattr(response, "parsed_output", None), request)
        except ValueError as exc:
            return done(Status.INVALID, str(exc), **spend)
        return done(
            Status.OK,
            verdict=answer.verdict,
            confidence=answer.confidence,
            reasons=tuple(answer.reasons),
            **spend,
        )
