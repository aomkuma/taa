"""The AI layer's contract and providers with a fake Anthropic client (TAA-1301/1302). No real API call."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import anthropic
import httpx2
import pytest

from app.ai.providers import FALLBACK_BETA, AnthropicProvider, NullProvider, cost_usd
from app.ai.schema import AssessmentV1, Status, Verdict, build_input, validate
from app.core.clock import ManualClock
from tests.unit.test_strategy_models import make_context, make_signal

CLOCK = ManualClock(datetime(2026, 9, 30, 10, 0, tzinfo=UTC))


def request() -> Any:
    return build_input(make_signal(), make_context())


def answer(**over: Any) -> AssessmentV1:
    base: dict[str, Any] = {
        "schema_version": "1.0",
        "bar_close_utc": request().bar_close_utc,
        "verdict": "DISAGREE",
        "confidence": 72,
        "reasons": ["H1 trend is down against a BUY", "  stop inside one ATR  "],
    }
    return AssessmentV1.model_validate(base | over)


@dataclass
class Usage:
    input_tokens: int = 1200
    output_tokens: int = 300


@dataclass
class Response:
    parsed_output: Any = None
    stop_reason: str = "end_turn"
    model: str = "claude-opus-5-5"
    usage: Usage = field(default_factory=Usage)
    stop_details: Any = None


class FakeClient:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []
        self.init: dict[str, Any] = {}

        outer = self

        class _Messages:
            def parse(self, **kw: Any) -> Any:
                outer.calls.append(kw)
                if isinstance(outer.result, Exception):
                    raise outer.result
                return outer.result

        class _Beta:
            messages = _Messages()

        self.beta = _Beta()


def provider(result: Any) -> tuple[AnthropicProvider, FakeClient]:
    fake = FakeClient(result)

    def factory(**kw: Any) -> FakeClient:
        fake.init = kw
        return fake

    return AnthropicProvider("sk-test", CLOCK, client_factory=factory), fake


class TestContract:
    def test_the_input_is_numeric_market_facts_without_account_data(self) -> None:
        req = request()
        text = req.to_json()
        assert req.payload["schema_version"] == "1.0" and req.payload["symbol"] == "EURUSD"
        assert {s["timeframe"] for s in req.payload["timeframes"]} == {"M15", "H1"}
        for forbidden in ("equity", "balance", "login", "password", "account", "lot", "volume"):
            assert forbidden not in text
        assert req.signal_key == make_signal().idempotency_key

    def test_validate_checks_the_schema_and_the_bar(self) -> None:
        ok = validate(answer(), request())
        assert ok.verdict is Verdict.DISAGREE and ok.reasons[1] == "stop inside one ATR"
        with pytest.raises(ValueError, match="judged bar"):
            validate(answer(bar_close_utc="2026-01-01T00:00:00+00:00"), request())
        for bad in ({"confidence": 101}, {"verdict": "BUY_MORE"}, {"size": 2}, {"schema_version": "2.0"}):
            raw = answer().model_dump() | bad
            with pytest.raises(ValueError, match="schema"):
                validate(raw, request())

    def test_null_provider_skips(self) -> None:
        result = NullProvider(CLOCK).assess(request())
        assert result.status is Status.SKIPPED and not result.answered


class TestAnthropicProvider:
    def test_a_structured_answer_with_fallbacks_low_effort_and_cost(self) -> None:
        p, fake = provider(Response(parsed_output=answer()))
        result = p.assess(request())
        assert result.status is Status.OK and result.verdict is Verdict.DISAGREE and result.confidence == 72
        assert result.cost_usd == cost_usd("claude-opus-5-5", 1200, 300) == 0.0108
        [call] = fake.calls
        assert call["model"] == "claude-opus-5-5" and call["output_format"] is AssessmentV1
        assert call["fallbacks"] == "default" and call["betas"] == [FALLBACK_BETA]
        assert call["output_config"] == {"effort": "low"}
        assert fake.init["max_retries"] == 1 and fake.init["timeout"] == 20.0

    @pytest.mark.parametrize(
        ("response", "status"),
        [
            (Response(stop_reason="refusal"), Status.REFUSED),
            (Response(stop_reason="max_tokens"), Status.TRUNCATED),
            (Response(parsed_output=None), Status.INVALID),
        ],
    )
    def test_anything_but_a_valid_answer_is_not_an_answer(self, response: Response, status: Status) -> None:
        p, _ = provider(response)
        result = p.assess(request())
        assert result.status is status and not result.answered and result.input_tokens == 1200

    def test_timeouts_and_api_errors_never_raise(self) -> None:
        req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        p, _ = provider(anthropic.APITimeoutError(request=req))
        assert p.assess(request()).status is Status.TIMEOUT
        p, _ = provider(anthropic.APIConnectionError(request=req))
        assert p.assess(request()).status is Status.ERROR


class TestCachedCalls:
    """TAA-1804: per-call model / effort and a cached system prompt (the AI trader's character)."""

    def test_defaults_are_unchanged(self) -> None:
        p, fake = provider(Response(parsed_output=answer()))
        p.ask("k", "SYS", "{}", AssessmentV1)
        [call] = fake.calls
        assert call["system"] == "SYS"
        assert call["model"] == "claude-opus-5-5"
        assert call["output_config"] == {"effort": "low"}

    def test_model_effort_and_the_cached_system_prompt(self) -> None:
        @dataclass
        class CachedUsage:
            input_tokens: int = 4080
            output_tokens: int = 361
            cache_creation_input_tokens: int = 0
            cache_read_input_tokens: int = 6830

        p, fake = provider(Response(parsed_output=answer(), model="claude-sonnet-5-5", usage=CachedUsage()))  # type: ignore[arg-type]
        got = p.ask(
            "k", "SYS", "{}", AssessmentV1, model="claude-sonnet-5-5", effort="medium", cache_system=True
        )
        [call] = fake.calls
        assert call["model"] == "claude-sonnet-5-5"
        assert call["output_config"] == {"effort": "medium"}
        assert call["system"] == [
            {"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral", "ttl": "1h"}}
        ]
        # Sonnet 5.5 at 2 / 10 USD per million: 4,080 x 2 + 361 x 10 + 6,830 x 0.2 = 8,160 + 3,610 + 1,366 = 13,136
        assert got.cost_usd == 0.013136
        assert (got.cache_read_tokens, got.cache_write_tokens) == (6830, 0)

    def test_a_cache_write_costs_twice_the_input_rate(self) -> None:
        # 4,080 x 2 + 357 x 10 + 6,830 x 4 = 8,160 + 3,570 + 27,320 = 39,050 -> 0.03905 USD (measured 2026-10-23)
        assert cost_usd("claude-sonnet-5-5", 4080, 357, cache_write=6830) == 0.03905
        assert cost_usd("claude-sonnet-5-5", 4080, 361, cache_read=6830) == 0.013136
        assert cost_usd("unknown-model", 1, 1, 1, 1) == 0.0
