"""Remote commands executed by the PAPER engine (TAA-704)."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pyotp
from pydantic import SecretStr
from sqlalchemy import select, update

from app.advisory.requirements import AdvisoryConfig, content_version
from app.cli.__main__ import main
from app.core.enums import Timeframe
from app.engine.orchestrator import DISABLED_KEY, SNAPSHOT_KEY
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
    assert runtime.advisory is not None
    runtime.advisory.start = lambda: None  # type: ignore[method-assign]
    runtime.advisory.stop = lambda timeout=5.0: None  # type: ignore[method-assign]
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
    assert h.engine.cloud_heartbeat()["disabled_strategies"] == ["buy_every_bar"]  # the PWA's state (TAA-909)
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


def outbox_types(h: Harness) -> list[str]:
    with h.db.session() as sess:
        return list(sess.execute(select(OutboxEventRow.type).order_by(OutboxEventRow.event_id)).scalars())


def test_engine_rows_are_replicated_and_resync_requeues_them(tmp_path: Path) -> None:
    h = rig(tmp_path, trade=True)
    assert h.engine.replicator is not None
    assert EngineStateRepository(h.db, h.clock).load(SNAPSHOT_KEY) is not None
    types = outbox_types(h)
    assert {"audit_event", "run", "config_snapshot"} <= set(types)
    until_open(h)
    types = set(outbox_types(h))
    assert {"decision", "decision_check", "paper_intent", "paper_position"} <= types
    with h.db.session() as sess:  # the cloud has everything; only new changes queue from here
        sess.execute(update(OutboxEventRow).values(status="SENT"))
    send(h, "RESYNC", "rs1")
    h.engine.cycle()
    result, _, detail = outcome(h, "rs1")
    assert result == "EXECUTED" and "rows" in detail and h.engine.resync_requested
    with h.db.session() as sess:
        pending = list(
            sess.execute(select(OutboxEventRow.type).where(OutboxEventRow.status == "PENDING")).scalars()
        )
    assert {"audit_event", "decision", "paper_position", "run"} <= set(pending)
    status = h.engine.status()["replication"]
    assert status["emitted"] > 0 and status["errors"] == 0


def test_the_initial_snapshot_runs_once(tmp_path: Path) -> None:
    h = rig(tmp_path)
    marker = EngineStateRepository(h.db, h.clock).load(SNAPSHOT_KEY)
    assert marker is not None and marker["rows"] > 0
    with h.db.session() as sess:
        sess.execute(update(OutboxEventRow).values(status="SENT"))
    h.engine._initial_snapshot()
    assert "PENDING" not in {r for r in pending_statuses(h)}


def pending_statuses(h: Harness) -> list[str]:
    with h.db.session() as sess:
        return list(sess.execute(select(OutboxEventRow.status)).scalars())


def test_cli_changes_are_replicated_when_sync_is_on(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'engine.db').as_posix()}"
    env = tmp_path / ".env"
    env.write_text(
        "\n".join(
            [
                "TRADING_MODE=BACKTEST",
                f"ENGINE_DB_URL={url}",
                f"KILL_SWITCH_FILE={(tmp_path / 'KILL').as_posix()}",
                "CLOUD_BASE_URL=https://cloud.example",
                "ENGINE_ID=eng-1",
                f"ENGINE_HMAC_SECRET={'k' * 40}",
            ]
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.yaml"
    config.write_text("sync:\n  enabled: true\n", encoding="utf-8")
    assert main(["--env-file", str(env), "--config", str(config), "kill", "--reason", "maintenance"]) == 0
    db = Database(url)
    with db.session() as sess:
        events = list(sess.execute(select(OutboxEventRow)).scalars())
    assert {"audit_event", "kill_switch"} <= {e.type for e in events}
    assert all(e.payload.get("chain", "engine:eng-1") == "engine:eng-1" for e in events)
    db.dispose()


class _Ranking:
    def __init__(self) -> None:
        self.rescans = 0
        self.last_run = None
        self.universe: list[Any] = []

    def request_rescan(self) -> None:
        self.rescans += 1


def test_rescan_suitability(tmp_path: Path) -> None:
    h = rig(tmp_path)
    h.engine.ranking = None
    send(h, "RESCAN_SUITABILITY", "rs-off")
    h.engine.running = True
    h.engine.cycle()
    assert outcome(h, "rs-off")[0] == "FAILED"  # the ranking is switched off in this engine
    ranking = _Ranking()
    h.engine.ranking = ranking  # type: ignore[assignment]
    send(h, "RESCAN_SUITABILITY", "rs-on")
    h.engine._drain_commands()
    assert outcome(h, "rs-on")[0] == "EXECUTED" and ranking.rescans == 1


def test_types_added_later_are_snapshotted_once(tmp_path: Path) -> None:
    h = rig(tmp_path)
    state = EngineStateRepository(h.db, h.clock)
    marker = state.load(SNAPSHOT_KEY)
    assert marker is not None and "opportunity" in marker["types"]
    state.save(SNAPSHOT_KEY, {"types": [t for t in marker["types"] if t != "run"]})  # an older release
    with h.db.session() as sess:
        sess.execute(update(OutboxEventRow).values(status="SENT"))
    h.engine._initial_snapshot()
    assert set(outbox_types_pending(h)) == {"run"}
    assert "run" in (state.load(SNAPSHOT_KEY) or {})["types"]


def outbox_types_pending(h: Harness) -> list[str]:
    with h.db.session() as sess:
        return list(
            sess.execute(select(OutboxEventRow.type).where(OutboxEventRow.status == "PENDING")).scalars()
        )


def test_the_cloud_advisory_config_drives_the_requirements(tmp_path: Path) -> None:
    h = rig(tmp_path)
    local = h.engine.requirements()
    assert h.engine.status()["sync"]["advisory_config"]["source"] == "local"
    content: dict[str, Any] = {
        "favourites": ["XAUUSD"],
        "lists": {},
        "auto_top_n": 0,
        "detectors": ["fib.retracement"],
        "pattern_strategies": [],
        "lifetime_bars": 4,
    }
    remote = AdvisoryConfig(version=content_version(content), **content)
    assert h.engine.sync is not None and h.engine.sync.advisory is not None
    h.engine.sync.advisory.current = remote
    req = h.engine.requirements()
    assert req != local and req.detectors == frozenset({"fib.retracement"}) and req.lifetime_bars == 4
    assert "XAUUSD" in req.symbols or "XAUUSD" not in h.engine.symbols  # unknown symbols are filtered
    h.engine.sync.advisory.current = None
    assert h.engine.requirements() == local  # back to the local fallback


def test_the_engine_streams_closed_candles(tmp_path: Path) -> None:
    h = rig(tmp_path)
    assert h.engine.candle_stream is not None
    h.engine.running = True
    h.engine.cycle()
    assert "candles" in outbox_types(h)
    stream = h.engine.status()["candle_stream"]
    assert stream["events"] >= 2 and stream["failures"] == 0  # entry + higher timeframe per symbol
    # every chart timeframe, not only the strategy's (sync.chart_timeframes defaults to all of them)
    assert set(h.engine.candle_stream.timeframes) == set(Timeframe)
    # and the heartbeat carries each one's forming bar for the chart's live candle
    forming = h.engine.cloud_heartbeat()["forming"]
    assert {(b["symbol"], b["timeframe"]) for b in forming} == {
        (s, tf.value) for s in h.engine.symbols for tf in Timeframe
    }
