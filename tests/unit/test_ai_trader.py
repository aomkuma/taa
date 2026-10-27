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
        "weapon": "W09",
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
        "buy_side": "none: every frame down",
        "sell_side": "4004.00 / 4008.00 / 3977.00, 6.8 R",
        "buy_odds": 20,
        "sell_odds": 45,
        "checklist": [{"item": k, "verdict": "pass", "note": "ok"} for k in T.ITEMS],
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
    # R02 is PLAN-1's switch: it no longer stops the AI's trades (owner 2026-10-25, the checklist review)
    assert T.brakes([R01, R02], {"h1_vol": 1.3, "d1_atr20": 50}, step(), frozenset({"R01"})) == ("half", [])


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


def test_the_code_and_the_ai_see_the_same_picture_or_not():
    w07 = {"id": "W07", "kind": "weapon", "when": {"sweep": ["high", "low"]}, "says": "the reclaim"}
    w02 = {"id": "W02", "kind": "weapon", "when": {"session": "asia"}, "says": "Asia B2"}
    w99 = {"id": "W99", "kind": "weapon", "says": "no conditions: never listed as in play"}
    entries = [w07, w02, w99, R01]
    assert T.weapons_in_play(entries, {"sweep": "low", "session": "asia"}) == ["W07", "W02"]
    assert T.weapons_in_play(entries, {"sweep": "none", "session": "none"}) == []
    assert T.same_picture(["W07", "W02"], "W07") is True
    assert T.same_picture(["W07", "W02"], "w02 ") is True  # case and spaces do not matter
    assert T.same_picture(["W07"], "W09") is False  # the AI sees another weapon
    assert T.same_picture(["W07"], "none") is False  # the code sees one, the AI none
    assert T.same_picture([], "none") is True and T.same_picture([], None) is True
    assert T.same_picture([], "W07") is False


R09 = {
    "id": "R09",
    "kind": "rule",
    "action": "stand_aside_against",
    "trend": ["h1_rhythm", "h4_rhythm"],
    "says": "z",
}
R08 = {"id": "R08", "kind": "rule", "action": "stand_aside", "when": {"session": "none"}, "says": "w"}


def test_no_trade_against_both_trend_readings():
    up = {"h1_rhythm": "up", "h4_rhythm": "up", "session": "london"}
    assert T.brakes([R09], up, step(decision="SELL")) == ("none", ["R09"])  # a sell into H1 and H4 up
    assert T.brakes([R09], up, step(decision="BUY")) == ("half", [])  # with them
    mixed = {"h1_rhythm": "up", "h4_rhythm": "none", "session": "london"}
    assert T.brakes([R09], mixed, step(decision="SELL")) == ("half", [])  # only one of them against
    down = {"h1_rhythm": "down", "h4_rhythm": "down", "session": "london"}
    assert T.brakes([R09], down, step(decision="BUY")) == ("none", ["R09"])
    assert T.brakes([R09], down, step(decision="WAIT", size="none")) == ("none", [])  # not an entry
    assert T.brakes([R09], up, step(decision="SELL"), frozenset({"R09"})) == ("half", [])  # suspended


def test_no_new_trade_outside_the_owners_windows():
    assert T.brakes([R08], {"session": "none"}, step(decision="BUY")) == ("none", ["R08"])
    assert T.brakes([R08], {"session": "asia"}, step(decision="BUY")) == ("half", [])
    both = T.brakes([R08, R09], {"session": "none", "h1_rhythm": "up", "h4_rhythm": "up"}, step())
    assert both == ("none", ["R08", "R09"])


def test_shadows_record_the_trade_they_would_stop_without_stopping_it(fixed_prompts: dict[str, Any]):
    # the fixed readings: h1_vol 1.3 (so a shadow copy of R01 would veto); the trade itself is not stopped
    shadow = dict(R01, id="S99", kind="shadow")
    w07 = {"id": "W07", "kind": "weapon", "when": {"h1_vol": "> 1.0"}, "says": "x"}
    rec = T.decide(FakeProvider(ok(step(weapon="W07"))), [shadow, w07], None, T0, "")  # type: ignore[arg-type]
    assert rec["final_size"] == "half" and rec["vetoed_by"] == []
    assert rec["shadow_vetoes"] == ["S99"]
    assert rec["weapons_in_play"] == ["W07"] and rec["same_picture"] is True


def test_the_stop_check_compares_the_ais_stop_with_the_codes():
    f = {"sell_stop_beyond": 4134.33, "buy_stop_beyond": 4119.43}
    # 2026-07-08 14:05: the AI's stop 4126.10 sat on the pool, short of the code's 4134.33
    assert T.stop_check(step(decision="SELL", stop=4126.1), f) == {
        "ai": 4126.1,
        "code": 4134.33,
        "beyond": False,
    }
    assert T.stop_check(step(decision="SELL", stop=4134.33), f)["beyond"] is True  # type: ignore[index]
    assert T.stop_check(step(decision="BUY", stop=4119.0), f)["beyond"] is True  # type: ignore[index]
    assert T.stop_check(step(decision="BUY", stop=4120.0), f)["beyond"] is False  # type: ignore[index]
    assert T.stop_check(step(decision="WAIT", stop=None, size="none"), f) is None
    assert T.stop_check(step(decision="SELL"), {}) is None  # no map (too few bars)


def test_a_rule_with_a_side_stops_only_that_side():
    # R08 (owner 2026-10-25): no SELL in a bull regime; the buys and the other regimes are untouched
    bull = {"id": "R08", "kind": "rule", "action": "stand_aside", "when": {"d1_regime": "up"}, "side": "SELL"}
    assert T.brakes([bull], {"d1_regime": "up"}, step(decision="SELL")) == ("none", ["R08"])
    assert T.brakes([bull], {"d1_regime": "up"}, step(decision="BUY")) == ("half", [])  # the other side
    assert T.brakes([bull], {"d1_regime": "none"}, step(decision="SELL")) == ("half", [])  # not a bull regime
    assert T.brakes([bull], {"d1_regime": None}, step(decision="SELL")) == ("half", [])  # unknown never holds
    assert T.brakes([bull], {"d1_regime": "up"}, step(decision="SELL"), frozenset({"R08"})) == ("half", [])


def test_rule_vetoes_per_side_and_the_code_s_stops_stay_out_of_the_readings():
    bull = {"id": "R08", "kind": "rule", "action": "stand_aside", "when": {"d1_regime": "up"}, "side": "SELL"}
    assert T.rule_vetoes([bull], {"d1_regime": "up"}, "SELL") == ["R08"]
    assert T.rule_vetoes([bull], {"d1_regime": "up"}, "BUY") == []
    assert T.rule_vetoes([bull], {"d1_regime": "up"}, "SELL", frozenset({"R08"})) == []
    ts = pd.Timestamp("2026-07-09 03:00", tz="UTC")
    text = T.content(ts, "", {"price": 1.0, "sell_stop_beyond": 2.0}, [], "", 1.0, "", "")
    assert "sell_stop_beyond" not in text and "THE EDGE" not in text
    assert "take-profit point quick (P09, C5)" in T.CHARACTER and "liquidity pool" not in T.CHARACTER


def test_outside_the_windows_only_a_really_clean_picture_passes():
    # R09 (owner 2026-10-25): the windows filter, unless the AI rates the trade at least 70
    r09 = {
        "id": "R09",
        "kind": "rule",
        "action": "stand_aside",
        "when": {"session": "none"},
        "unless_confidence": 70,
    }
    outside = {"session": "none"}
    assert T.brakes([r09], outside, step(decision="BUY", confidence=69)) == ("none", ["R09"])
    assert T.brakes([r09], outside, step(decision="BUY", confidence=70)) == ("half", [])  # really clean
    assert T.brakes([r09], {"session": "ny"}, step(decision="BUY", confidence=10)) == ("half", [])  # inside
    both = T.brakes([r09, R08], outside, step(decision="SELL", confidence=90))  # R08 here has no exception
    assert both == ("none", ["R08"])
    assert "a trade every day" in T.CHARACTER and "R09" in T.CHARACTER


def test_the_checklist_gaps_of_a_new_trade():
    # owner 2026-10-25: the AI answers every item A1 .. C9 before a new trade; the code records the gaps
    answers = [{"item": k, "verdict": "pass", "note": "ok"} for k in T.ITEMS if k not in ("B3", "C5")]
    answers[0] = {"item": "a1 ", "verdict": "fail", "note": "the H4 trend is against it"}  # case / spaces
    gaps = T.checklist_gaps(step(checklist=answers))
    assert gaps == {"failed": ["A1"], "missing": ["B3", "C5"]}
    assert T.checklist_gaps(step(checklist=[])) == {"failed": [], "missing": list(T.ITEMS)}


def test_a_release_within_the_hour_allows_only_the_news_weapon():
    r07 = {"id": "R07", "kind": "rule", "action": "news_weapon_only", "when": {"release_min": "<= 60"}}
    near = {"release_min": 25.0}
    assert T.brakes([r07], near, step(decision="BUY", weapon="W07")) == ("none", ["R07"])
    assert T.brakes([r07], near, step(decision="BUY", weapon=" w01")) == ("half", [])  # the straddle
    assert T.brakes([r07], {"release_min": 61.0}, step(decision="BUY", weapon="W07")) == ("half", [])
    assert T.brakes([r07], near, step(decision="BUY", weapon="W07"), frozenset({"R07"})) == ("half", [])
    assert T.brakes([r07], near, step(decision="WAIT", size="none")) == ("none", [])  # not an entry


def test_the_system_prompt_carries_the_checklist():
    text = T.system_prompt([])
    assert "THE DECISION CHECKLIST (answer every item before a new trade):" in text
    assert "- C5 [HARD; AI (the 5 USD floor: code)]: Is the take-profit point the next swing" in text
    assert "- A1 [WEIGHTED; AI]: " in text and " -- yes: " in text


def test_hard_checklist_items_the_take_profit_floor_and_shadow_weapons():
    # owner 2026-10-25: a failed or unanswered HARD item stops the trade; a WEIGHTED one does not
    fail = [{"item": k, "verdict": "fail" if k in ("C4", "A1") else "pass", "note": "x"} for k in T.ITEMS]
    assert T.brakes([], {}, step(checklist=fail)) == ("none", ["checklist C4"])  # A1 is WEIGHTED
    some = [{"item": k, "verdict": "pass", "note": "x"} for k in T.ITEMS if k != "C9"]
    assert T.brakes([], {}, step(checklist=some)) == ("none", ["checklist C9"])  # unanswered = failed
    # C5's fixed take-profit floor is OFF (owner 2026-10-27: it rejected 1 of 496 signals over 2023-2026 and
    # 0 of 17 entry decisions in the Jul 2026 replay), so a 4.90 USD target passes
    assert T.MIN_TAKE_PROFIT == 0.0
    assert T.brakes([], {}, step(target=3999.1)) == ("half", [])
    # the brake itself still works when a floor is set
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(T, "MIN_TAKE_PROFIT", 5.0)
        assert T.brakes([], {}, step(target=3999.1)) == ("none", ["C5 under 5 USD"])
    assert T.brakes([], {}, step(target=3999.0)) == ("half", [])  # exactly 5.00
    # a weapon still in shadow status: full becomes half; a real one keeps full
    weapons = [
        {"id": "W09", "kind": "weapon", "status": "shadow"},
        {"id": "W01", "kind": "weapon", "status": "real"},
    ]
    assert T.brakes(weapons, {}, step(size="full")) == ("half", [])
    assert T.brakes(weapons, {}, step(size="full", weapon="W01")) == ("full", [])
    assert T.brakes(weapons, {}, step(decision="WAIT", size="none", checklist=[])) == ("none", [])


def test_the_prompt_leaves_out_the_method_principles_and_shortens_lessons():
    entries = [
        {"id": "P01", "kind": "principle", "says": "the goal"},
        {"id": "P25", "kind": "principle", "says": "my loop of work"},
        {"id": "L99", "kind": "lesson", "says": "First sentence here. A long second one that is left out."},
    ]
    text = T.system_prompt(entries)
    assert "- P01: the goal" in text and "P25" not in text
    assert "- L99: First sentence here." in text and "second one" not in text
    assert T.first_sentence("x" * 400).endswith("...") and len(T.first_sentence("x" * 400)) == T.LESSON_CHARS


def test_a_wait_with_its_pending_order_is_braked_and_handed_over(fixed_prompts: dict[str, Any]):
    # ISSUES 26 (07-07): 'wait for a retest of 4150 to sell' and no order; the WAIT now carries it
    from app.engine.ai_trader import order_from

    d = step(decision="WAIT", size="none", wait_order="SELL", entry=4150.0, stop=4158.0, target=4140.0)
    p = FakeProvider(ok(d))
    rec = T.decide(p, [], None, T0, "")  # type: ignore[arg-type]
    assert rec["order_side"] == "SELL" and rec["final_size"] == "half" and rec["vetoed_by"] == []
    order = order_from(rec, 30)
    assert order is not None and order.side.value == "SELL" and (order.entry, order.stop) == (4150.0, 4158.0)
    # braked like an entry: R01 (h1_vol 1.3 in the fixed readings) stops it
    rec = T.decide(FakeProvider(ok(d)), [R01], None, T0, "")  # type: ignore[arg-type]
    assert rec["final_size"] == "none" and rec["vetoed_by"] == ["R01"] and order_from(rec, 30) is None
    plain = T.decide(FakeProvider(ok(step(decision="WAIT", size="none"))), [], None, T0, "")  # type: ignore[arg-type]
    assert "order_side" not in plain and order_from(plain, 30) is None


def test_c4_moves_a_short_stop_out_past_the_zone_or_vetoes(monkeypatch: pytest.MonkeyPatch):
    # ISSUES 33 (07-08 07:25): the AI's stop sat inside the liquidate zone. The code's stop (the map's) is
    # where it goes: moved out when the trade still pays 0.2 R, else vetoed
    def readings(beyond: float) -> None:
        def prompts(*_: Any) -> tuple[str, str, dict[str, Any]]:
            return "SYSTEM", "USER", {"h1_vol": 1.3, "sell_stop_beyond": beyond, "buy_stop_beyond": 3950.0}

        monkeypatch.setattr(T, "prompts", prompts)

    d = step()  # SELL 4,004, stop 4,008, target 3,977: reward 27
    readings(4006.0)  # the AI's stop already past the code's: untouched
    rec = T.decide(FakeProvider(ok(d)), [], None, T0, "")  # type: ignore[arg-type]
    assert rec["decision"]["stop"] == 4008.0 and "stop_widened" not in rec and rec["final_size"] == "half"
    readings(4139.0)  # risk 135, 0.2 x 135 = 27 <= 27: moved out
    rec = T.decide(FakeProvider(ok(d)), [], None, T0, "")  # type: ignore[arg-type]
    assert rec["decision"]["stop"] == 4139.0 and rec["stop_widened"] == {"from": 4008.0, "to": 4139.0}
    assert rec["final_size"] == "half" and rec["map_stops_now"] == {"SELL": 4139.0, "BUY": 3950.0}
    readings(4140.0)  # risk 136, 27.2 > 27: vetoed
    rec = T.decide(FakeProvider(ok(d)), [], None, T0, "")  # type: ignore[arg-type]
    assert rec["final_size"] == "none" and "C4 stop inside the liquidate zone" in rec["vetoed_by"]
    assert rec["decision"]["stop"] == 4008.0
    # a WAIT with its pending sell is checked the same way
    w = step(decision="WAIT", size="none", wait_order="SELL")
    readings(4010.0)
    rec = T.decide(FakeProvider(ok(w)), [], None, T0, "")  # type: ignore[arg-type]
    assert rec["decision"]["stop"] == 4010.0 and rec["final_size"] == "half"
