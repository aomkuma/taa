"""The AI trader (app/ai/trader.py, TAA-1804) with a fake provider: trimming, brakes, suspensions, the call's
arguments and what is stored. No real API call; the prompts' text is checked byte for byte against the research
in research/2026-10-23-entry (prompt parity)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pydantic import BaseModel

from app.ai import trader as T
from app.ai.providers import Answer
from app.ai.schema import Status

T0 = pd.Timestamp("2026-10-23T15:16", tz="UTC")
R01 = {"id": "R01", "kind": "rule", "action": "stand_aside", "when": {"h1_vol": "> 1.1"}, "says": "x"}
R02 = {"id": "R02", "kind": "rule", "action": "stand_aside_plan1", "when": {"d1_atr20": "< 60"}, "says": "y"}


def step(**over: Any) -> T.StepDecision:
    base: dict[str, Any] = {
        "decision": "SELL",
        "setup": "a lower high under the broken floor",
        "entry": 4004.0,
        "stop": 4008.0,
        "target": 3977.0,
        "trigger": "an M5 close under 4,004",
        "size": "half",
        "kb_ids": ["P19"],
        "reasons": ["every frame down"],
        "confidence": 66,
        "watch_above": 4006.0,
        "watch_below": 3992.9,
    }
    return T.StepDecision.model_validate(base | over)


class FakeProvider:
    name = "fake"

    def __init__(self, answer: Answer) -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    def assess(self, request: Any) -> Any:  # pragma: no cover - not used
        raise AssertionError

    def ask(
        self,
        key: str,
        system: str,
        content: str,
        output_format: type[BaseModel],
        *,
        model: str | None = None,
        effort: str | None = None,
        cache_system: bool = False,
    ) -> Answer:
        self.calls.append(
            {
                "key": key,
                "system": system,
                "content": content,
                "schema": output_format,
                "model": model,
                "effort": effort,
                "cache_system": cache_system,
            }
        )
        return self.answer


def ok(decision: T.StepDecision) -> Answer:
    return Answer(
        Status.OK, parsed=decision, model="claude-sonnet-5-5", input_tokens=4080, output_tokens=361,
        cost_usd=0.013136, latency_ms=4000.0, created_at=datetime(2026, 10, 23, 15, 16, tzinfo=UTC),
        cache_read_tokens=6830,
    )  # fmt: skip


@pytest.fixture
def fixed_prompts(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The prompts' readings replaced by fixed ones (the prompt text itself is checked by the research parity)."""
    seen: dict[str, Any] = {}

    def prompts(
        entries: Any, fr: Any, as_of: Any, journal: str, off: dict[str, str]
    ) -> tuple[str, str, dict[str, Any]]:
        seen["off"] = off
        return "SYSTEM", "USER " + journal, {"h1_vol": 1.3, "d1_atr20": 74.0}

    monkeypatch.setattr(T, "prompts", prompts)
    return seen


def test_tail_keeps_short_text_and_cuts_at_a_heading():
    assert T.tail("## a\nx", 100) == "## a\nx"
    text = "## one\n" + "a" * 50 + "\n## two\nbb\n### three\ncc"
    # the end "\n## two\nbb\n### three\ncc" is 23 chars; the last 25 start with "aa", so the cut moves to "## two"
    assert T.tail(text, 25) == "(earlier steps left out)\n## two\nbb\n### three\ncc"
    assert T.tail("x" * 30, 10) == "(earlier steps left out)\n" + "x" * 10


def test_brakes_veto_a_new_trade_unless_suspended():
    assert T.brakes([R01], {"h1_vol": 1.3}, step()) == ("none", ["R01"])
    assert T.brakes([R01], {"h1_vol": 1.3}, step(decision="HOLD")) == ("half", [])  # an open trade is managed
    assert T.brakes([R01], {"h1_vol": 1.0}, step(decision="BUY", size="full")) == ("full", [])
    assert T.brakes([R01, R02], {"h1_vol": 1.3, "d1_atr20": 74}, step(), frozenset({"R01"})) == ("half", [])
    assert T.brakes([R01, R02], {"h1_vol": 1.3, "d1_atr20": 50}, step(), frozenset({"R01"})) == (
        "none",
        ["R02"],
    )


def test_suspended_keeps_only_unexpired_rules():
    rows = {"R01": "2026-10-23T22:00:00+00:00", "R02": "2026-10-23T10:00:00+00:00"}
    assert T.suspended(rows, T0) == {"R01": "2026-10-23T22:00:00+00:00"}
    assert T.suspended(rows, pd.Timestamp("2026-10-23T22:00", tz="UTC")) == {}  # expired at its time


def test_decide_calls_with_the_cached_character_and_applies_the_brakes(
    fixed_prompts: dict[str, Any], tmp_path: Path
):
    p = FakeProvider(ok(step()))
    rec = T.decide(
        p, [R01], None, T0, "the journal", model="claude-sonnet-5-5", store=tmp_path, source="watcher"
    )  # type: ignore[arg-type]
    [call] = p.calls
    assert (call["model"], call["effort"], call["cache_system"]) == ("claude-sonnet-5-5", "medium", True)
    assert call["schema"] is T.StepDecision
    assert (call["system"], call["content"]) == ("SYSTEM", "USER the journal")
    assert rec["status"] == "OK"
    assert rec["source"] == "watcher"
    assert rec["final_size"] == "none"
    assert rec["vetoed_by"] == ["R01"]
    assert rec["decision"]["decision"] == "SELL"
    assert rec["tokens"] == {"input": 4080, "cache_write": 0, "cache_read": 6830, "output": 361}
    assert rec["cost_usd"] == 0.013136
    raw = sorted(x.name for x in (tmp_path / "raw").iterdir())
    assert raw == [
        "2026-10-23_2216_1_system.txt",
        "2026-10-23_2216_2_user.txt",
        "2026-10-23_2216_3_answer.json",
    ]
    assert (tmp_path / "raw" / "2026-10-23_2216_2_user.txt").read_text(encoding="utf-8") == "USER the journal"
    assert (tmp_path / "raw" / "2026-10-23_2216_1_system.txt").read_text(encoding="utf-8") == "SYSTEM"
    [line] = (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(line) == rec


def test_decide_with_a_suspension_marks_the_trade(fixed_prompts: dict[str, Any]):
    p = FakeProvider(ok(step()))
    rec = T.decide(p, [R01], None, T0, "", suspensions={"R01": "2026-10-23T22:00:00+00:00"})  # type: ignore[arg-type]
    assert fixed_prompts["off"] == {"R01": "2026-10-23T22:00:00+00:00"}
    assert rec["final_size"] == "half"
    assert rec["vetoed_by"] == []
    assert rec["suspended_applying"] == ["R01"]


def test_decide_without_an_answer_records_the_status(fixed_prompts: dict[str, Any], tmp_path: Path):
    p = FakeProvider(Answer(Status.TIMEOUT, detail="timed out"))
    rec = T.decide(p, [R01], None, T0, "", store=tmp_path)  # type: ignore[arg-type]
    assert rec["status"] == "TIMEOUT"
    assert "decision" not in rec
    assert "final_size" not in rec
    assert rec["source"] == "manual"
