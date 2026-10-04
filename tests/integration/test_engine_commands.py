"""Remote commands executed by the PAPER engine (TAA-704)."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pyotp
from pydantic import SecretStr
from sqlalchemy import select

from app.cli.__main__ import main
from app.engine.orchestrator import DISABLED_KEY
from app.monitoring.alerts import EventType
from app.storage.database import Database, upgrade_schema
from app.storage.models import CommandLogRow, OutboxEventRow
from app.storage.repositories import EngineStateRepository
from app.strategy.registry import StrategySet
from app.sync.runtime import SyncRuntime
from tests.integration.test_engine_paper import BuyEveryBar, Harness, harness
from tests.integration.test_sync_engine import sync_settings

TOTP_SECRET = pyotp.random_base32()


def rig(tmp_path: Path, *, flatten: bool = False, trade: bool = False) -> Harness:
    h = harness(tmp_path)
    s = sync_settings(tmp_path)
    env = s.env.model_copy(
        update={"CONTROL_TOTP_SECRET": SecretStr(TOTP_SECRET), "KILL_SWITCH_FLATTEN_ALLOWED": flatten}
    )
    h.engine.settings = dataclasses.replace(h.engine.settings, env=env)
    runtime = SyncRuntime.from_settings(
        s, h.db, h.clock, http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(204)))
    )
    runtime.thread.start = lambda: None  # type: ignore[method-assign]
    runtime.thread.stop = lambda timeout=5.0: None  # type: ignore[method-assign]
    assert runtime.poller is not None
    runtime.poller.start = lambda: None  # type: ignore[method-assign]
    runtime.poller.stop = lambda timeout=5.0: None  # type: ignore[method-assign]
    h.engine.sync = runtime
    h.engine.start()
    if trade:
        strategy = BuyEveryBar()
        h.engine.strategies = StrategySet((strategy,))
        h.engine.magic = {strategy.name: 7_310_000}
    return h


def send(
    h: Harness, ctype: str, cid: str, params: dict[str, Any] | None = None, totp: str | None = None
) -> None:
    now = h.clock.now_utc()
    cmd: dict[str, Any] = {
        "id": cid,
        "type": ctype,
        "params": params or {},
        "created_by": "owner",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=60)).isoformat(),
    }
    if totp is not None:
        cmd["totp"] = totp
    assert h.engine.sync is not None
    h.engine.sync.inbox.put(cmd)


def outcome(h: Harness, cid: str) -> tuple[str, str, str]:
    with h.db.session() as sess:
        row = sess.get(CommandLogRow, cid)
        assert row is not None
        return row.outcome, row.reason, row.detail


def until_open(h: Harness, max_cycles: int = 60) -> int:
    """Cycle until the test strategy holds a paper position; returns its ticket."""
    h.engine.running = True
    for _ in range(max_cycles):
        h.engine.cycle()
        if h.engine.paper.broker.positions:
            return next(iter(h.engine.paper.broker.positions))
        h.clock.advance(30)
    raise AssertionError("the test strategy should have opened a paper position")


def closed_reason(h: Harness, ticket: int) -> str | None:
    return next(
        (
            e.params["reason"]
            for e in h.sink.events
            if e.type is EventType.POSITION_CLOSED and e.params["ticket"] == ticket
        ),
        None,
    )


def code(h: Harness) -> str:
    return pyotp.TOTP(TOTP_SECRET).at(h.clock.now_utc().timestamp())


def test_remote_kill_switch(tmp_path: Path) -> None:
    h = rig(tmp_path)
    send(h, "KILL_SWITCH_ACTIVATE", "k1", {"reason": "going on holiday"})
    h.engine.running = True
    h.engine.cycle()
    assert outcome(h, "k1")[0] == "EXECUTED" and h.engine.kill_switch.is_active()
    state = h.engine.kill_switch.state()
    assert state.actor == "cloud:owner" and state.reason == "going on holiday"
    assert EventType.KILL_SWITCH_ACTIVATED in h.types()
    with h.db.session() as sess:
        event = sess.execute(
            select(OutboxEventRow).where(OutboxEventRow.type == "command_result")
        ).scalar_one()
    assert event.payload["command_id"] == "k1" and h.engine.status()["sync"]["pending"] >= 1


def test_risk_increasing_commands_change_nothing(tmp_path: Path) -> None:
    h = rig(tmp_path)
    h.engine.kill_switch.activate("local", "pytest", "cli")
    send(h, "KILL_SWITCH_RELEASE", "r1")
    h.engine.running = True
    h.engine.cycle()
    assert outcome(h, "r1")[:2] == ("REJECTED", "RISK_INCREASING") and h.engine.kill_switch.is_active()


def test_a_disabled_strategy_opens_nothing_until_re_enabled_locally(tmp_path: Path) -> None:
    h = rig(tmp_path, trade=True)
    send(h, "STRATEGY_DISABLE", "s1", {"strategy": "buy_every_bar"})
    h.engine.run(max_cycles=40)
    assert outcome(h, "s1")[0] == "EXECUTED" and h.engine.disabled_strategies() == {"buy_every_bar"}
    assert EventType.POSITION_OPENED not in h.types()
    send(h, "STRATEGY_DISABLE", "s2", {"strategy": "nope"})
    h.engine.running = True
    h.engine.cycle()
    assert outcome(h, "s2")[0] == "FAILED"


def test_position_close_needs_a_fresh_totp(tmp_path: Path) -> None:
    h = rig(tmp_path, trade=True)
    ticket = until_open(h)
    send(h, "STRATEGY_DISABLE", "s", {"strategy": "buy_every_bar"})  # keep it from reopening
    send(h, "POSITION_CLOSE", "c0", {"ticket": ticket})
    h.engine.cycle()
    assert outcome(h, "c0")[:2] == ("REJECTED", "TOTP_INVALID") and ticket in h.engine.paper.broker.positions
    send(h, "POSITION_CLOSE", "c1", {"ticket": ticket}, totp=code(h))
    h.engine.cycle()
    h.clock.advance(30)
    h.engine.cycle()
    assert outcome(h, "c1")[0] == "EXECUTED" and ticket not in h.engine.paper.broker.positions
    assert closed_reason(h, ticket) == "MANUAL"
    send(h, "POSITION_CLOSE", "c2", {"ticket": 999_999}, totp=pyotp.TOTP(TOTP_SECRET).at(h.clock.now_utc()))
    h.engine.cycle()
    assert outcome(h, "c2")[0] == "FAILED"


def test_flatten_needs_local_permission(tmp_path: Path) -> None:
    h = rig(tmp_path, trade=True)
    send(h, "FLATTEN_ALL", "f1", {"reason": "panic"}, totp=code(h))
    h.engine.running = True
    h.engine.cycle()
    assert outcome(h, "f1")[0] == "FAILED" and "FLATTEN" in outcome(h, "f1")[2]
    assert not h.engine.kill_switch.is_active()


def test_flatten_closes_paper_positions(tmp_path: Path) -> None:
    h = rig(tmp_path, flatten=True, trade=True)
    ticket = until_open(h)
    send(h, "FLATTEN_ALL", "f1", {"reason": "panic"}, totp=code(h))
    for _ in range(3):
        h.engine.cycle()
        h.clock.advance(30)
    assert outcome(h, "f1")[0] == "EXECUTED" and h.engine.kill_switch.is_active()
    assert h.engine.paper.broker.positions == {} and closed_reason(h, ticket) == "KILL_SWITCH"


def test_cli_re_enables_a_strategy(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    url = f"sqlite:///{(tmp_path / 'engine.db').as_posix()}"
    upgrade_schema(url)
    db = Database(url)
    from app.core.clock import SystemClock

    EngineStateRepository(db, SystemClock()).save(DISABLED_KEY, {"names": ["a", "b"]})
    env = tmp_path / ".env"
    env.write_text(f"TRADING_MODE=BACKTEST\nENGINE_DB_URL={url}\n", encoding="utf-8")
    assert main(["--env-file", str(env), "strategy", "list"]) == 0
    assert "a, b" in capsys.readouterr().out
    assert main(["--env-file", str(env), "strategy", "enable", "a"]) == 1  # a reason is required
    assert (
        main(["--env-file", str(env), "strategy", "enable", "a", "--reason", "fixed", "--actor", "me"]) == 0
    )
    assert EngineStateRepository(db, SystemClock()).load(DISABLED_KEY) == {"names": ["b"]}
    db.dispose()
