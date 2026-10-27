"""The day's plan (app/ai/plan.py; owner 2026-10-25, KB P26): when it is due, what it writes to the journal and
the store, a failed answer, and the watcher writing it before any decision of the window."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pydantic import BaseModel

from app.ai import plan as P
from app.ai import watcher as w
from app.ai.providers import Answer
from app.ai.schema import Status

# Mon 2026-07-06 (US summer): 07:01 Thai = 00:01 UTC (Asia), 13:00 Thai = 06:00 UTC (London), 19:00 Thai =
# 12:00 UTC = 08:00 New York (NY)
ASIA = pd.Timestamp("2026-07-06T00:01", tz="UTC")
LONDON = pd.Timestamp("2026-07-06T06:00", tz="UTC")
NY = pd.Timestamp("2026-07-06T12:00", tz="UTC")
NOON = pd.Timestamp("2026-07-06T04:00", tz="UTC")  # 11:00 Thai: no window


def a_plan() -> P.DayPlan:
    return P.DayPlan(
        condition="D1 down, a three-day bounce; H1 up; volatility low",
        big_levels=[P.Level(price=4195.37, frame="D1", role="resistance", what="Friday's high")],
        intraday_levels=[P.Level(price=4177.3, frame="M5", role="support", what="equal lows x2")],
        trend_today="a range under the 4,194-4,200 cluster until London",
        opportunities=["a sell at the cluster", "a buy at 4,170-4,177"],
        edge_side="both",
        edge_why="each at its own level",
        scenarios=[
            P.Scenario(
                name="A",
                side="SELL",
                where="turn",
                entry=4195.0,
                trigger="an M5 close back under 4,195",
                stop=4203.0,
                take_profit=4178.0,
                why="D1 down, Friday's high",
            )
        ],
        releases="none; Asia 07-09, London 13-15, NY 19:00-22:30 Thai",
        readiness=[{"item": "A1", "verdict": "pass", "note": "d1_big down"}],  # type: ignore[list-item]
        summary_th="ขาลงบน D1 เด้งสามวัน",
    )


class FakeProvider:
    name = "fake"

    def __init__(self, answer: Answer) -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    def ask(self, key: str, system: str, content: str, output_format: type[BaseModel], **kw: Any) -> Answer:
        self.calls.append({"key": key, "content": content, "format": output_format, **kw})
        return self.answer


def ok(plan: P.DayPlan) -> Answer:
    return Answer(
        Status.OK, parsed=plan, model="claude-sonnet-5-5", cost_usd=0.0, latency_ms=900.0,
        created_at=datetime(2026, 7, 6, 0, 1, tzinfo=UTC),
    )  # fmt: skip


def test_a_plan_is_due_once_per_window_of_the_thai_day():
    assert P.plan_due(ASIA, None) == "morning"
    assert P.plan_due(ASIA, "2026-07-06:morning") is None  # written already today
    assert P.plan_due(ASIA, "2026-07-03:morning") == "morning"  # Friday's does not count
    assert P.plan_due(LONDON, "2026-07-06:morning") == "london"
    assert P.plan_due(NY, "2026-07-06:london") == "ny"
    assert P.plan_due(NOON, None) is None  # outside the windows: no plan
    assert P.plan_key(NY, "ny") == "2026-07-06:ny"


def test_the_plan_goes_to_the_journal_and_the_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        P, "plan_inputs", lambda fr, as_of: ("INPUTS", {"h1_vol": 0.63, "release_min": 5010.0})
    )
    monkeypatch.setattr(P, "readiness_facts", lambda f, as_of, fr: ["bars current: yes"])
    monkeypatch.setattr(P.lq, "structure_now", lambda *a: None)
    monkeypatch.setattr(P.kn, "m5_frame", lambda m1, as_of: None)
    monkeypatch.setattr(P, "rule_vetoes", lambda entries, f, side: [])
    monkeypatch.setattr(P, "system_prompt", lambda entries: "SYSTEM")
    journal = tmp_path / "journal.md"
    journal.write_text("# journal\n", encoding="utf-8")
    p = FakeProvider(ok(a_plan()))
    fr = type("Fr", (), {"m1": None, "m15": None, "d1": None, "h1": None, "releases": ()})()
    rec = P.make_plan(p, [], fr, ASIA, "morning", store=tmp_path, journal=journal)  # type: ignore[arg-type]
    assert rec["status"] == "OK" and rec["plan"]["edge_side"] == "both"
    [call] = p.calls
    assert call["key"] == "plan-morning-202607060001" and call["format"] is P.DayPlan
    assert call["content"].startswith("THE MORNING PLAN (P26)") and call["content"].endswith("INPUTS")
    assert "- A1 [WEIGHTED]: " in call["content"] and "- B1" not in call["content"]  # the forest items only
    text = journal.read_text(encoding="utf-8")
    assert "## Mon 06 Jul 2026 - the morning plan (07:01 Thai, written by the AI, P26)" in text
    assert "- intraday levels (M15 / M5): 4177.30 M5 support (equal lows x2)" in text
    assert "- scenarios:" in text
    assert "- A (SELL, turn): an M5 close back under 4,195; stop 4203.0, take-profit 4178.0" in text
    assert "- readiness (A1-A8): failed none; bars current: yes" in text
    [row] = [json.loads(x) for x in (tmp_path / "plans.jsonl").read_text(encoding="utf-8").splitlines()]
    assert row["kind"] == "morning" and row["facts"] == ["bars current: yes"]
    assert (
        (tmp_path / "raw" / "2026-07-06_0701_plan_morning_2_user.txt")
        .read_text(encoding="utf-8")
        .endswith("INPUTS")
    )


def test_a_failed_answer_writes_nothing_to_the_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(P, "plan_inputs", lambda fr, as_of: ("INPUTS", {}))
    monkeypatch.setattr(P, "system_prompt", lambda entries: "SYSTEM")
    journal = tmp_path / "journal.md"
    p = FakeProvider(Answer(Status.TIMEOUT, detail="timed out"))
    rec = P.make_plan(p, [], None, LONDON, "london", store=tmp_path, journal=journal)  # type: ignore[arg-type]
    assert rec["status"] == "TIMEOUT" and "plan" not in rec
    assert not journal.exists()
    assert json.loads((tmp_path / "plans.jsonl").read_text(encoding="utf-8"))["status"] == "TIMEOUT"


def test_the_watcher_writes_the_plan_before_the_window_s_first_decision(tmp_path: Path):
    order: list[str] = []

    def plan(now: pd.Timestamp, kind: str) -> dict[str, Any]:
        order.append(f"plan {kind}")
        return {}

    def decide(as_of: pd.Timestamp, text: str, model: str | None, effort: str = "medium") -> dict[str, Any]:
        order.append("decide")
        return {"status": "OK", "decision": {"decision": "WAIT"}}

    watcher = w.AIWatcher(
        tmp_path, frames=lambda: None, decide=decide, journal=lambda: "",  # type: ignore[arg-type, return-value]
        entries=lambda: [], plan=plan,
    )  # fmt: skip
    watcher._behaviours = lambda now: set()  # type: ignore[method-assign]
    watcher.on_bar(ASIA, [])
    watcher.on_bar(ASIA + pd.Timedelta(minutes=1), [])
    assert order == ["plan morning", "decide"]  # once, and first
    assert (
        json.loads((tmp_path / "watch_state.json").read_text(encoding="utf-8"))["last_plan"]
        == "2026-07-06:morning"
    )
    again = w.AIWatcher(
        tmp_path, frames=lambda: None, decide=decide, journal=lambda: "",  # type: ignore[arg-type, return-value]
        entries=lambda: [], plan=plan,
    )  # fmt: skip
    again._behaviours = lambda now: set()  # type: ignore[method-assign]
    again.on_bar(ASIA + pd.Timedelta(minutes=2), [])
    assert order.count("plan morning") == 1  # a restart remembers it
    again.on_bar(LONDON, [])
    assert order[-2:] == ["plan london", "decide"]  # London: the update, then the window's check


def test_the_plan_s_scenarios_become_checked_orders():
    rec = {
        "as_of": "2026-07-06T00:00:00+00:00",
        "kind": "morning",
        "valid_until": P.window_end(pd.Timestamp("2026-07-06T00:00", tz="UTC"), "morning").isoformat(),
        "map_stops": {"SELL": 4206.0, "BUY": 4165.0},
        "vetoes": {"BUY": [], "SELL": []},
        "plan": {
            "scenarios": [
                {"name": "A", "side": "SELL", "where": "turn", "entry": 4197.5, "stop": 4204.5, "take_profit": 4185.0,
                 "trigger": "price reaches 4,197.50", "why": "D1 down"},
                {"name": "B", "side": "BUY", "where": "turn", "entry": 4178.0, "stop": 4172.0, "take_profit": 4186.0,
                 "trigger": "an M5 close back over 4,177.16", "why": "the sweep"},
                {"name": "C", "side": "SELL", "where": "go on", "entry": 4176.0, "stop": 4182.0, "take_profit": 4172.0,
                 "trigger": "an M5 close under 4,177", "why": "the break"},
                {"name": "D", "side": "BUY", "where": "turn", "entry": None, "stop": 4160.0, "take_profit": 4170.0,
                 "trigger": "?", "why": "no entry"},
            ]
        },
    }  # fmt: skip
    orders = P.plan_orders(rec)
    # C's 4.00 take-profit used to be refused by the 5 USD floor; that floor is off since 2026-10-27
    assert P.MIN_TAKE_PROFIT == 0.0
    assert [o.key[-1] for o in orders] == ["A", "B", "C"]
    a, b, _c = orders
    assert a.stop == 4206.0  # out to the map's stop past the liquidate zone (C4)
    assert b.stop == 4165.0 and b.risk_scale == 0.5 and b.kb_ids == ("P26",)
    assert a.valid_until == datetime(2026, 7, 6, 2, 0, tzinfo=UTC)  # 09:00 Thai: the Asia window's end
    # D is left out: it has no entry price
    rec["vetoes"] = {"BUY": ["R01"], "SELL": []}
    assert [o.key[-1] for o in P.plan_orders(rec)] == ["A", "C"]  # a rule in force stops the buys now
    assert P.plan_orders({"as_of": rec["as_of"], "kind": "morning"}) == []  # a failed plan: no orders
    # owner 2026-10-26 (a trend needs the orders with it): with D1 down, the buy B is not placed; with D1 up,
    # the sell A is not; with no D1 regime both are
    rec["vetoes"] = {"BUY": [], "SELL": []}
    assert [o.key[-1] for o in P.plan_orders(rec | {"d1_side": "down"})] == ["A", "C"]  # A and C sell
    assert [o.key[-1] for o in P.plan_orders(rec | {"d1_side": "up"})] == ["B"]
    assert [o.key[-1] for o in P.plan_orders(rec | {"d1_side": "none"})] == ["A", "B", "C"]


def test_window_ends():
    assert P.window_end(LONDON, "london") == pd.Timestamp("2026-07-06T08:00", tz="UTC")  # 15:00 Thai
    assert P.window_end(NY, "ny") == pd.Timestamp("2026-07-06T15:30", tz="UTC")  # 11:30 New York (EDT)


def test_plan_orders_expire_an_hour_before_a_release():
    # ISSUES 17 (R07): the NY plan written 19:00 Thai, a release at 19:30 Thai -> no orders (18:30 is past)
    base = {
        "kind": "ny", "map_stops": {}, "vetoes": {"BUY": [], "SELL": []},
        "plan": {"scenarios": [{"name": "A", "side": "SELL", "where": "turn", "entry": 4159.0, "stop": 4164.0,
                                "take_profit": 4151.0, "trigger": "t", "why": "w"}]},
    }  # fmt: skip
    rec = dict(base, as_of=NY.isoformat(), valid_until=P.window_end(NY, "ny").isoformat(),
               next_release=(NY + pd.Timedelta(minutes=30)).isoformat())  # fmt: skip
    assert P.plan_orders(rec) == []
    rec["next_release"] = (NY + pd.Timedelta(hours=2)).isoformat()  # 21:00 Thai: the orders end at 20:00
    [o] = P.plan_orders(rec)
    assert o.valid_until == (NY + pd.Timedelta(hours=1)).to_pydatetime()


def test_a_failed_plan_is_retried_after_ten_minutes(tmp_path: Path):
    calls: list[str] = []

    def plan(now: pd.Timestamp, kind: str) -> dict[str, Any]:
        calls.append(f"{now:%H:%M}")
        return {"status": "ERROR"} if len(calls) == 1 else {"status": "OK", "plan": {"scenarios": []}}

    def decide(as_of: pd.Timestamp, text: str, model: str | None, effort: str = "medium") -> dict[str, Any]:
        return {"status": "OK", "decision": {"decision": "WAIT"}}

    watcher = w.AIWatcher(
        tmp_path, frames=lambda: None, decide=decide, journal=lambda: "",  # type: ignore[arg-type, return-value]
        entries=lambda: [], plan=plan,
    )  # fmt: skip
    watcher._behaviours = lambda now: set()  # type: ignore[method-assign]
    for minutes in (0, 5, 10, 11):
        watcher.on_bar(ASIA + pd.Timedelta(minutes=minutes), [])
    assert calls == ["00:01", "00:11"]  # failed at 00:01 UTC, asked again 10 minutes later, then done
