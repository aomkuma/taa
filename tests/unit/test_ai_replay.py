"""Replay providers (app/ai/replay.py, TAA-1807): answers stored by the hash of everything the model is given,
asked once; the Claude CLI's JSON result parsed into an Answer; the CLI run with no tools, settings or MCP
servers (it must not read the stored prices); the history adapter returns only bars closed by the clock."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pydantic import BaseModel

from app.ai.providers import Answer
from app.ai.replay import ClaudeCLIProvider, ReplayProvider, input_hash, parse_cli
from app.ai.schema import Status
from app.core.clock import ManualClock
from app.core.enums import Timeframe
from app.engine.ai_replay import AIReplay, HistoryCandles
from app.strategy.ai_lane import AITrader

T = datetime(2026, 10, 23, 14, 48, tzinfo=UTC)


class Out(BaseModel):
    decision: str
    confidence: int


class Wider(Out):
    weapon: str


class Inner:
    """Answers OK (or ``status``) and counts its calls."""

    name = "inner"

    def __init__(self, status: Status = Status.OK) -> None:
        self.status = status
        self.calls: list[str] = []

    def assess(self, request: Any) -> Any:
        raise NotImplementedError

    def ask(self, key: str, system: str, content: str, output_format: type[BaseModel], **kw: Any) -> Answer:
        self.calls.append(content)
        parsed = Out(decision="SELL", confidence=66) if self.status is Status.OK else None
        return Answer(self.status, parsed=parsed, model="claude-sonnet-5-5", input_tokens=10, cost_usd=0.012)


def test_the_hash_covers_everything_the_model_is_given():
    base = input_hash("sys", "user", Out, "claude-sonnet-5-5", "medium")
    assert base == input_hash("sys", "user", Out, "claude-sonnet-5-5", "medium")  # repeatable
    assert len({
        base,
        input_hash("sys!", "user", Out, "claude-sonnet-5-5", "medium"),
        input_hash("sys", "user!", Out, "claude-sonnet-5-5", "medium"),
        input_hash("sys", "user", Wider, "claude-sonnet-5-5", "medium"),  # one more answer field
        input_hash("sys", "user", Out, "claude-opus-5-5", "medium"),
        input_hash("sys", "user", Out, "claude-sonnet-5-5", "low"),
    }) == 6  # fmt: skip


def test_asked_once_then_replayed_from_the_store(tmp_path: Path):
    inner = Inner()
    p = ReplayProvider(tmp_path, ManualClock(T), inner)
    first = p.ask("step-1", "sys", "user", Out, model="m", effort="medium")
    assert first.status is Status.OK and inner.calls == ["user"]
    (stored,) = tmp_path.glob("*.json")
    assert stored.stem == input_hash("sys", "user", Out, "m", "medium")
    row = json.loads(stored.read_text(encoding="utf-8"))
    assert row["parsed"] == {"decision": "SELL", "confidence": 66} and row["cost_usd"] == 0.012
    again = p.ask("step-2", "sys", "user", Out, model="m", effort="medium")  # another label, the same input
    assert inner.calls == ["user"]  # not asked again
    assert again.parsed == Out(decision="SELL", confidence=66) and again.cost_usd == 0.012
    assert again.status is Status.OK and again.created_at == T
    p.ask("step-3", "sys", "other", Out, model="m", effort="medium")
    assert inner.calls == ["user", "other"]
    assert (p.hits, p.misses) == (1, 2)


def test_a_failure_is_not_stored_and_no_inner_answers_skipped(tmp_path: Path):
    p = ReplayProvider(tmp_path, ManualClock(T), Inner(Status.TIMEOUT))
    assert p.ask("k", "sys", "user", Out).status is Status.TIMEOUT
    assert not list(tmp_path.glob("*.json"))  # asked again next time
    bare = ReplayProvider(tmp_path, ManualClock(T))
    ans = bare.ask("k", "sys", "user", Out)
    assert ans.status is Status.SKIPPED and ans.parsed is None


def cli_out(**over: Any) -> str:
    out: dict[str, Any] = {
        "is_error": False,
        "result": "{}",
        "structured_output": {"decision": "WAIT", "confidence": 70},
        "modelUsage": {
            "claude-haiku-5-5": {"inputTokens": 1209, "outputTokens": 21, "costUSD": 0.0001},  # the CLI's own
            "claude-sonnet-5-5": {
                "inputTokens": 2,
                "outputTokens": 412,
                "cacheCreationInputTokens": 2052,
                "cacheReadInputTokens": 7,
                "costUSD": 0.0123321,
            },
        },
    }
    out.update(over)
    return json.dumps(out)


def test_the_cli_result_parsed_with_the_models_own_usage():
    a = parse_cli(cli_out(), Out, "claude-sonnet-5-5", T, 5709.6)
    assert a.status is Status.OK and a.parsed == Out(decision="WAIT", confidence=70)
    assert (a.input_tokens, a.output_tokens, a.cache_write_tokens, a.cache_read_tokens) == (2, 412, 2052, 7)
    assert a.cost_usd == 0.012332 and a.latency_ms == 5709.6 and a.model == "claude-sonnet-5-5"


def test_cli_errors_become_statuses():
    assert parse_cli("not json", Out, "m", T, 1.0, "boom").status is Status.ERROR
    err = parse_cli(cli_out(is_error=True, result="Not logged in"), Out, "claude-sonnet-5-5", T, 1.0)
    assert err.status is Status.ERROR and err.detail == "Not logged in"
    empty = parse_cli(
        cli_out(is_error=True, result="", terminal_reason="api_error", api_error_status=529),
        Out, "claude-sonnet-5-5", T, 1.0, "overloaded\n",
    )  # fmt: skip
    assert empty.detail == "api_error; 529; overloaded"  # an empty result still says why
    assert parse_cli(cli_out(structured_output=None), Out, "claude-sonnet-5-5", T, 1.0).status is Status.ERROR
    bad = parse_cli(cli_out(structured_output={"decision": "WAIT"}), Out, "claude-sonnet-5-5", T, 1.0)
    assert bad.status is Status.INVALID


def test_the_cli_runs_with_nothing_but_the_prompt():
    cmd = ClaudeCLIProvider(Path("claude.exe"), ManualClock(T)).command(
        Path("sys.txt"), {"type": "object"}, "claude-sonnet-5-5", "medium"
    )
    flags = dict(zip(cmd[1:], [*cmd[2:], None], strict=True))
    assert cmd[0] == "claude.exe" and "-p" in cmd
    assert flags["--tools"] == ""  # no tools: it cannot open the stored prices
    assert flags["--setting-sources"] == ""  # no settings, hooks or CLAUDE.md
    assert "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd
    assert (flags["--model"], flags["--effort"]) == ("claude-sonnet-5-5", "medium")
    assert flags["--system-prompt-file"] == "sys.txt" and flags["--json-schema"] == '{"type": "object"}'


def bars(start: str, n: int, minutes: int) -> pd.DataFrame:
    t = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=n, freq=f"{minutes}min")
    return pd.DataFrame({"open_time": t, "close_time": t + pd.Timedelta(minutes=minutes), "close": range(n)})


def test_history_candles_are_the_last_bars_closed_by_the_clock():
    clock = ManualClock(datetime(2026, 10, 23, 15, 3, 30, tzinfo=UTC))
    h = HistoryCandles({Timeframe.M1: bars("2026-10-23T15:00", 10, 1)}, clock)
    got = h.closed_candles("XAUUSD", Timeframe.M1, 2)
    # 15:03:30: the bars opened 15:00, 15:01, 15:02 have closed (15:03 is forming): the last two
    assert got.df.close.tolist() == [1, 2] and got.fetched_at_utc == clock.now_utc()
    clock.set(datetime(2026, 10, 23, 15, 4, tzinfo=UTC))  # the 15:03 bar closes at 15:04 exactly
    assert h.closed_candles("XAUUSD", Timeframe.M1, 2).df.close.tolist() == [2, 3]
    clock.set(datetime(2026, 10, 23, 14, 0, tzinfo=UTC))
    assert h.closed_candles("XAUUSD", Timeframe.M1, 2).df.empty


class StubLane:
    def __init__(self, rec: dict[str, Any] | None) -> None:
        self.cfg = type("Cfg", (), {"symbol": "XAUUSD"})()
        self.rec = rec
        self.ticked_at: list[datetime] = []
        self.clock: ManualClock | None = None
        self.m1: Any = None

    def tick(self) -> bool:
        assert self.clock is not None
        self.ticked_at.append(self.clock.now_utc())
        return True

    def take_decision(self) -> dict[str, Any] | None:
        rec, self.rec = self.rec, None
        return rec

    def take_plan_orders(self) -> list[Any] | None:
        return None


def test_a_step_sets_the_clock_ticks_and_hands_the_decision_over():
    rec = {
        "as_of": T.isoformat(),
        "final_size": "half",
        "decision": {"decision": "SELL", "entry": 4005.0, "stop": 4013.0, "target": 3977.0, "confidence": 66},
    }
    lane, clock = StubLane(rec), ManualClock(datetime(2000, 1, 1, tzinfo=UTC))
    lane.clock = clock
    replay = AIReplay(lane, clock)  # type: ignore[arg-type]
    s = AITrader()
    assert replay.step(T, s) == "order"
    assert lane.ticked_at == [T]  # the lane read the bars at the bar close
    order = s.pending("XAUUSD")
    assert order is not None and order.valid_until == datetime(2026, 10, 23, 15, 18, tzinfo=UTC)  # 30 min
    assert replay.step(T, s) is None  # nothing new
    assert [(at, done) for at, _, done in replay.decisions] == [(T, "order")]


def test_the_live_cost_reads_the_system_prompt_from_the_warm_cache(tmp_path: Path):
    from app.ai.replay import live_cost

    # 3,000 input tokens, the system prompt 2/3 of the characters: 2,000 cached at 0.2 USD / M (Sonnet 2.0 / 10),
    # 1,000 fresh at 2.0 USD / M, 400 out at 10 USD / M = 0.0004 + 0.002 + 0.004
    assert live_cost("claude-sonnet-5-5", "s" * 200, "u" * 100, 3000, 400) == 0.0064
    p = ReplayProvider(tmp_path, ManualClock(T), Inner(), spend="api")
    a = p.ask("k", "s" * 200, "u" * 100, Out, model="claude-sonnet-5-5")
    assert a.cost_usd == live_cost("claude-sonnet-5-5", "s" * 200, "u" * 100, 10, 0)  # the inner's 10 tokens
    (stored,) = tmp_path.glob("*.json")
    assert json.loads(stored.read_text(encoding="utf-8"))["cost_usd"] == 0.012  # the answerer's own kept
    again = p.ask("k", "s" * 200, "u" * 100, Out, model="claude-sonnet-5-5")
    assert again.cost_usd == a.cost_usd


def test_answers_on_the_plan_cost_the_cap_nothing(tmp_path: Path):
    p = ReplayProvider(tmp_path, ManualClock(T), Inner(), spend="none")
    assert p.ask("k", "sys", "user", Out).cost_usd == 0.0
    assert p.ask("k", "sys", "user", Out).cost_usd == 0.0  # replayed
    (stored,) = tmp_path.glob("*.json")
    assert json.loads(stored.read_text(encoding="utf-8"))["cost_usd"] == 0.012


def test_a_cli_error_is_retried_once(monkeypatch):
    from app.ai import replay

    calls: list[int] = []

    def once(self, system, content, output_format, used, level):
        calls.append(1)
        status = Status.ERROR if len(calls) == 1 else Status.OK
        return Answer(status, parsed=Out(decision="WAIT", confidence=1) if status is Status.OK else None)

    monkeypatch.setattr(replay.ClaudeCLIProvider, "_once", once)
    monkeypatch.setattr(replay.time, "sleep", lambda s: None)
    p = ClaudeCLIProvider(Path("claude.exe"), ManualClock(T))
    assert p.ask("k", "sys", "user", Out).status is Status.OK and len(calls) == 2
    calls.clear()
    monkeypatch.setattr(
        replay.ClaudeCLIProvider, "_once", lambda *a: Answer(Status.ERROR) if not calls.append(1) else None
    )
    assert (
        p.ask("k", "sys", "user", Out).status is Status.ERROR and len(calls) == 2
    )  # once more, then the error


def test_live_events_report_a_trade_when_it_opens_and_when_it_closes():
    # owner 2026-10-25: report the trade at once, not at the day's end
    from types import SimpleNamespace

    from app.core.enums import ExitReason, Side
    from app.engine.ai_replay import live_events

    t0 = datetime(2026, 7, 6, 0, 2, tzinfo=UTC)
    pos = [(Side.BUY, 4177.5, 4168.9, 4184.9, t0)]
    held, rows = live_events(set(), pos, [], t0)
    assert rows == [
        {"event": "OPEN", "at": t0.isoformat(), "side": "BUY", "entry": 4177.5, "sl": 4168.9, "tp": 4184.9}
    ]
    held, rows = live_events(held, pos, [], t0)
    assert rows == []  # still open: nothing new
    closed = SimpleNamespace(
        entry_price=4177.5, sl_initial=4168.9, tp_initial=4184.9, exit_price=4184.9, side=Side.BUY,
        entry_time=t0, exit_time=t0,
        exit_reason=ExitReason.TAKE_PROFIT, profit=7.4, commission=0.0, swap=0.0, volume=0.01,
    )  # fmt: skip
    held, rows = live_events(held, [], [closed], t0)
    assert held == set() and rows[0]["event"] == "CLOSE" and rows[0]["reason"] == ExitReason.TAKE_PROFIT.value
    assert abs(rows[0]["r"] - (4184.9 - 4177.5) / 8.6) < 1e-9 and rows[0]["usd"] == 7.4


def test_three_failed_ai_calls_in_a_row_stop_the_replay():
    # ISSUES 19: the quota ran out mid-day on 07-06 and the replay went on without the AI

    from app.engine import ai_replay as ar

    class Lane:
        cfg = type("Cfg", (), {"symbol": "XAUUSD"})()
        store = Path(".")
        position = ""

        def tick(self) -> bool:
            return True

        def take_plan_orders(self) -> None:
            return None

        def take_decision(self) -> dict[str, Any]:
            return {"status": "ERROR", "detail": "429"}

    rp = ar.AIReplay(Lane(), ManualClock(datetime(2026, 7, 6, tzinfo=UTC)))  # type: ignore[arg-type]
    t = datetime(2026, 7, 6, 1, 0, tzinfo=UTC)
    rp.step(t, None)
    rp.step(t, None)
    with pytest.raises(RuntimeError, match="3 AI calls failed in a row"):
        rp.step(t, None)


def test_a_trade_opened_and_closed_inside_one_step_reports_both():
    from types import SimpleNamespace

    from app.core.enums import ExitReason, Side
    from app.engine.ai_replay import live_events

    t0 = datetime(2026, 7, 6, 0, 1, 22, tzinfo=UTC)
    x = SimpleNamespace(
        entry_price=4179.0, sl_initial=4170.5, tp_initial=4186.0, exit_price=4170.48, side=Side.BUY,
        entry_time=t0, exit_time=t0, exit_reason=ExitReason.STOP_LOSS, profit=-8.52, commission=0.0, swap=0.0,
        volume=0.01,
    )  # fmt: skip
    _, rows = live_events(set(), [], [x], t0)
    assert [r["event"] for r in rows] == ["OPEN", "CLOSE"]


def test_a_step_notes_the_positions_and_a_take_profit_blocks_its_side(tmp_path: Path):
    # ISSUES 30: the replay hands the strategy its positions every step; one gone at its target blocks the side
    from datetime import timedelta

    from app.core.enums import Side

    lane, clock = StubLane(None), ManualClock(datetime(2000, 1, 1, tzinfo=UTC))
    lane.clock = clock
    lane.store = tmp_path  # type: ignore[attr-defined]
    replay = AIReplay(lane, clock)  # type: ignore[arg-type]
    s = AITrader()
    opened = T - timedelta(minutes=5)
    lane.m1 = pd.DataFrame(
        {"high": [4006.0, 4004.0, 4001.0], "low": [4003.0, 4000.0, 3994.0]},
        index=pd.date_range(opened, periods=3, freq="1min"),
    )
    replay.step(T, s, [(Side.SELL, 4005.0, 4013.0, 3995.0, opened)])
    assert not s.blocked("XAUUSD", Side.SELL, T)
    replay.step(T + timedelta(minutes=1), s, [])
    assert s.blocked("XAUUSD", Side.SELL, T) and not s.blocked("XAUUSD", Side.BUY, T)
    # the 3,994 bar opened at T - 3 min, closed at T - 2 min: blocked until T + 28 min
    assert s.blocked("XAUUSD", Side.SELL, T + timedelta(minutes=27, seconds=59))
    assert not s.blocked("XAUUSD", Side.SELL, T + timedelta(minutes=28))


def test_a_step_reads_the_signal_at_an_armed_order_s_level(tmp_path: Path):
    # owner 2026-10-26: an armed order fills only after a signal at its level; the replay reads it every step
    from datetime import timedelta

    from app.core.enums import Side
    from app.strategy.ai_lane import AIOrder

    lane, clock = StubLane(None), ManualClock(datetime(2000, 1, 1, tzinfo=UTC))
    lane.clock = clock
    lane.store = tmp_path  # type: ignore[attr-defined]
    replay = AIReplay(lane, clock)  # type: ignore[arg-type]
    s = AITrader()
    o = AIOrder(
        side=Side.SELL, entry=4105.0, stop=4112.0, target=4090.0, risk_scale=0.5, setup="plan", reasons=(),
        kb_ids=(), confidence=60, decided_at=T - timedelta(hours=1), valid_until=T + timedelta(hours=1), key="p",
    )  # fmt: skip
    s.set_plan_orders("XAUUSD", [o])
    from tests.unit.test_strategy_confirm import SWEEP

    T5 = T + timedelta(minutes=2)  # 14:50, on an M5 boundary
    lane.m1 = SWEEP.set_axis(
        SWEEP.index + (T5 - datetime(2026, 7, 8, 1, 0, tzinfo=UTC))
    )  # the M5 sweep at T5
    assert s.on_quote("XAUUSD", T5 - timedelta(minutes=1), 4100.0, 4100.3) is None  # a limit above the price
    assert s.on_quote("XAUUSD", T5 + timedelta(seconds=20), 4105.2, 4105.5) is None  # armed
    replay.step(T5 + timedelta(minutes=5), s)
    assert s.confirmation("p") is None
    replay.step(T5 + timedelta(minutes=10), s)
    assert s.confirmation("p") == "M5 sweep"


# --- the Codex CLI (owner 2026-10-26: "the AI now on Sonnet to use GPT-6-Luna when running tests") ---


class Small(BaseModel):
    decision: str
    entry: float | None = None
    size: str = "none"
    notes: list[str] = []


def test_strict_schema_closes_objects_and_makes_optional_fields_nullable():
    from app.ai.replay import strict_schema

    s = strict_schema(Small.model_json_schema())
    assert s["additionalProperties"] is False
    assert s["required"] == ["decision", "entry", "size", "notes"]  # every property, in order
    assert s["properties"]["decision"] == {"title": "Decision", "type": "string"}  # required: unchanged
    # 'entry' allowed null already (float | None): kept as is, its default dropped
    assert s["properties"]["entry"] == {"anyOf": [{"type": "number"}, {"type": "null"}], "title": "Entry"}
    # 'size' had a default only: nullable now, the default gone
    assert s["properties"]["size"] == {"anyOf": [{"title": "Size", "type": "string"}, {"type": "null"}]}
    assert "default" not in str(s)


def test_unstrict_drops_the_nulls_the_model_does_not_allow():
    from app.ai.replay import unstrict

    schema = Small.model_json_schema()
    raw = {"decision": "WAIT", "entry": None, "size": None, "notes": None}
    # entry allows null (kept); size and notes do not (dropped, so their defaults apply)
    assert unstrict(raw, schema, {}) == {"decision": "WAIT", "entry": None}
    assert Small.model_validate(unstrict(raw, schema, {})) == Small(decision="WAIT")


def ev(**kw: Any) -> str:
    return json.dumps(kw)


def test_parse_codex_reads_the_answer_and_refuses_a_tool_call():
    from app.ai.replay import parse_codex

    schema = Small.model_json_schema()
    ok_events = "\n".join([
        ev(type="thread.started"), ev(type="item.completed", item={"type": "agent_message", "text": "{}"}),
        ev(type="turn.completed", usage={"input_tokens": 1800, "cached_input_tokens": 1200, "output_tokens": 90}),
    ])  # fmt: skip
    a = parse_codex(ok_events, '{"decision": "SELL", "entry": 4105.0, "size": "half", "notes": []}', schema,
                    Small, "gpt-6-luna", T, 5000.0)  # fmt: skip
    assert a.status.value == "OK" and a.parsed == Small(decision="SELL", entry=4105.0, size="half")
    assert (a.input_tokens, a.cache_read_tokens, a.output_tokens, a.cost_usd) == (1800, 1200, 90, 0.0)
    # a command run by the answerer: it could have read the stored prices - refused, whatever it answered
    tool = ev(type="item.completed", item={"type": "command_execution", "command": "dir"}) + "\n" + ok_events
    assert (
        parse_codex(tool, '{"decision": "SELL"}', schema, Small, "gpt-6-luna", T, 1.0).status.value == "ERROR"
    )
    # a failed turn and an answer outside the schema
    failed = ev(type="turn.failed", error={"message": "Invalid schema"})
    b = parse_codex(failed, "", schema, Small, "gpt-6-luna", T, 1.0)
    assert b.status.value == "ERROR" and "Invalid schema" in b.detail
    c = parse_codex(ok_events, '{"entry": 1.0}', schema, Small, "gpt-6-luna", T, 1.0)
    assert c.status.value == "INVALID"


def test_the_codex_command_is_read_only_and_keeps_no_session():
    from app.ai.replay import CodexCLIProvider

    cmd = CodexCLIProvider(Path("codex.exe"), ManualClock(T)).command(
        Path("F"), Path("s.json"), Path("a.json"), "gpt-6-luna", "low"
    )
    assert cmd[:4] == ["codex.exe", "exec", "-m", "gpt-6-luna"]
    assert 'model_reasoning_effort="low"' in cmd and cmd[cmd.index("-s") : cmd.index("-s") + 2] == [
        "-s",
        "read-only",
    ]
    assert "--ephemeral" in cmd and cmd[cmd.index("-C") + 1] == "F" and cmd[-1] == "-"
