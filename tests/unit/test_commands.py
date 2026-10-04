"""Remote commands: single-use TOTP, the engine-side checks, the long-poll client and the cloud queue (TAA-704)."""

from __future__ import annotations

import queue
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pyotp
import pytest
from sqlalchemy import select

from app.core.clock import ManualClock
from app.core.errors import ConfigError
from app.security.hmac_auth import Signer, Verifier
from app.security.totp import SingleUseTotp
from app.storage.audit import AuditLog, verify_chain
from app.storage.database import Database
from app.storage.models import CommandLogRow, OutboxEventRow
from app.sync.client import CloudClient
from app.sync.command_queue import CommandQueue, CommandRefused
from app.sync.commands import (
    COMMANDS_PATH,
    Command,
    CommandFailed,
    CommandPoller,
    CommandProcessor,
    CommandType,
    Outcome,
    Reason,
    drain,
)
from app.sync.outbox import Outbox

NOW = datetime(2026, 10, 4, 12, 0, 10, tzinfo=UTC)
TOTP_SECRET = pyotp.random_base32()
HMAC_SECRET = "h" * 40


def code(clock: ManualClock, offset_steps: int = 0) -> str:
    return pyotp.TOTP(TOTP_SECRET).at(clock.now_utc().timestamp() + 30 * offset_steps)


def raw(ctype: str = "KILL_SWITCH_ACTIVATE", cid: str = "c1", **kw: Any) -> dict[str, Any]:
    created = kw.pop("created_at", NOW)
    out = {
        "id": cid,
        "type": ctype,
        "params": kw.pop("params", {"reason": "test"}),
        "created_by": "owner@example.com",
        "created_at": created.isoformat(),
        "expires_at": kw.pop("expires_at", created + timedelta(seconds=60)).isoformat(),
    }
    return out | kw


class TestTotp:
    def test_a_code_works_once_within_one_step(self) -> None:
        clock = ManualClock(NOW)
        totp = SingleUseTotp(TOTP_SECRET, clock)
        assert totp.verify(code(clock)) is not None
        assert totp.verify(code(clock)) is None  # replay
        assert totp.verify(code(clock, -1)) is not None and totp.verify(code(clock, 1)) is not None
        assert totp.verify(code(clock, -2)) is None and totp.verify(code(clock, 2)) is None

    def test_format_and_secret(self) -> None:
        clock = ManualClock(NOW)
        totp = SingleUseTotp(TOTP_SECRET, clock)
        assert totp.verify(None) is None and totp.verify("12345") is None and totp.verify("abcdef") is None
        with pytest.raises(ConfigError, match="base32"):
            SingleUseTotp("not base32!", clock)

    def test_used_steps_survive_a_restart(self) -> None:
        clock = ManualClock(NOW)
        step = SingleUseTotp(TOTP_SECRET, clock).verify(code(clock))
        assert step is not None
        assert SingleUseTotp(TOTP_SECRET, clock, used_steps=[step]).verify(code(clock)) is None


class Engine:
    """Records handler calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def handler(self, name: str, *, fail: bool = False):  # type: ignore[no-untyped-def]
        def run(cmd: Command) -> str:
            self.calls.append((name, dict(cmd.params)))
            if fail:
                raise CommandFailed("no such position")
            return f"{name} done"

        return run


def processor(db: Database, *, secret: str | None = TOTP_SECRET, outbox: bool = True):  # type: ignore[no-untyped-def]
    clock = ManualClock(NOW)
    engine = Engine()
    handlers = {t: engine.handler(t.value) for t in CommandType}
    handlers[CommandType.POSITION_CLOSE] = engine.handler("POSITION_CLOSE")
    from app.config import SyncConfig

    box = Outbox(db, clock, SyncConfig()) if outbox else None
    proc = CommandProcessor(
        db, clock, handlers, totp_secret=secret, audit=AuditLog(db, "engine:test", clock), outbox=box
    )
    return proc, clock, engine


class TestProcessor:
    def test_an_allowed_command_runs_and_is_recorded_everywhere(self, db: Database) -> None:
        proc, _, engine = processor(db)
        result = proc.process(raw())
        assert (result.outcome, result.reason, result.detail) == (
            Outcome.EXECUTED,
            Reason.NONE,
            "KILL_SWITCH_ACTIVATE done",
        )
        assert engine.calls == [("KILL_SWITCH_ACTIVATE", {"reason": "test"})]
        with db.session() as sess:
            log = sess.get(CommandLogRow, "c1")
            event = sess.execute(select(OutboxEventRow)).scalar_one()
        assert log is not None and log.outcome == "EXECUTED" and log.created_by == "owner@example.com"
        assert (
            event.type == "command_result" and event.priority == 0 and event.payload["outcome"] == "EXECUTED"
        )
        assert verify_chain(db, "engine:test").ok

    def test_each_id_runs_once(self, db: Database) -> None:
        proc, _, engine = processor(db)
        proc.process(raw())
        again = proc.process(raw())
        assert again.reason is Reason.DUPLICATE and len(engine.calls) == 1

    @pytest.mark.parametrize(
        "ctype", ["KILL_SWITCH_RELEASE", "BREAKER_RESET", "STRATEGY_ENABLE", "LIMITS_CHANGE", "MODE_CHANGE"]
    )
    def test_risk_increasing_commands_are_always_rejected(self, db: Database, ctype: str) -> None:
        proc, _, engine = processor(db)
        result = proc.process(raw(ctype, totp="123456"))
        assert (
            result.outcome is Outcome.REJECTED
            and result.reason is Reason.RISK_INCREASING
            and engine.calls == []
        )

    def test_unknown_commands_are_not_allowed(self, db: Database) -> None:
        proc, _, engine = processor(db)
        assert proc.process(raw("SEND_ORDER")).reason is Reason.NOT_ALLOWED and engine.calls == []

    def test_expiry_rules(self, db: Database) -> None:
        proc, _, engine = processor(db)
        assert proc.process(raw(cid="late", created_at=NOW - timedelta(seconds=90))).reason is Reason.EXPIRED
        long = raw(cid="long", expires_at=NOW + timedelta(seconds=121))
        assert proc.process(long).reason is Reason.INVALID
        future = raw(cid="future", created_at=NOW + timedelta(minutes=5))
        assert proc.process(future).reason is Reason.INVALID
        assert engine.calls == []

    def test_malformed_commands(self, db: Database) -> None:
        proc, _, engine = processor(db)
        assert proc.process({"type": "RESYNC"}).reason is Reason.INVALID
        naive = raw(cid="naive") | {"created_at": "2026-10-04T12:00:00"}
        assert proc.process(naive).reason is Reason.INVALID
        assert proc.process(raw(cid="p", params=["x"])).reason is Reason.INVALID
        assert engine.calls == []
        with db.session() as sess:  # with an id, the rejection is on record
            assert sess.get(CommandLogRow, "naive") is not None

    def test_totp_protected_commands(self, db: Database) -> None:
        proc, clock, engine = processor(db)
        close = {"ticket": 7}
        assert proc.process(raw("POSITION_CLOSE", "a", params=close)).reason is Reason.TOTP_INVALID
        assert (
            proc.process(raw("POSITION_CLOSE", "b", params=close, totp="000000")).reason
            is Reason.TOTP_INVALID
        )
        good = code(clock)
        assert proc.process(raw("POSITION_CLOSE", "c", params=close, totp=good)).outcome is Outcome.EXECUTED
        assert proc.process(raw("FLATTEN_ALL", "d", totp=good)).reason is Reason.TOTP_INVALID  # single use
        assert [c[0] for c in engine.calls] == ["POSITION_CLOSE"]
        with db.session() as sess:
            row = sess.get(CommandLogRow, "c")
            assert row is not None and row.totp_step is not None
            assert all(
                "totp" not in (e.payload.get("params") or {})
                for e in sess.execute(select(OutboxEventRow)).scalars()
            )

    def test_a_code_used_before_a_restart_stays_used(self, db: Database) -> None:
        proc, clock, _ = processor(db)
        good = code(clock)
        proc.process(raw("POSITION_CLOSE", "a", params={"ticket": 1}, totp=good))
        restarted, _, engine = processor(db)
        assert restarted.process(raw("FLATTEN_ALL", "b", totp=good)).reason is Reason.TOTP_INVALID
        assert engine.calls == []

    def test_without_a_secret_protected_commands_are_refused(self, db: Database) -> None:
        proc, clock, engine = processor(db, secret=None)
        result = proc.process(raw("FLATTEN_ALL", totp=code(clock)))
        assert result.reason is Reason.TOTP_NOT_CONFIGURED and engine.calls == []
        assert proc.process(raw("RESYNC", "r")).outcome is Outcome.EXECUTED  # unprotected ones still work

    def test_a_failing_handler_is_a_failed_result(self, db: Database) -> None:
        proc, clock, engine = processor(db)
        proc.handlers[CommandType.POSITION_CLOSE] = engine.handler("POSITION_CLOSE", fail=True)
        result = proc.process(raw("POSITION_CLOSE", params={"ticket": 9}, totp=code(clock)))
        assert result.outcome is Outcome.FAILED and "no such position" in result.detail

    def test_a_missing_handler_is_unsupported(self, db: Database) -> None:
        proc, _, _ = processor(db)
        del proc.handlers[CommandType.RESCAN_SUITABILITY]
        assert proc.process(raw("RESCAN_SUITABILITY")).reason is Reason.UNSUPPORTED

    def test_drain_takes_a_bounded_number(self, db: Database) -> None:
        proc, _, _ = processor(db)
        inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        for i in range(5):
            inbox.put(raw("RESYNC", f"r{i}"))
        assert len(drain(inbox, proc, limit=3)) == 3 and inbox.qsize() == 2


class TestPoller:
    def test_commands_go_to_the_inbox_and_the_cursor_advances(self) -> None:
        responses: list[tuple[int | None, Any]] = [
            (200, {"commands": [raw("RESYNC", "a"), raw("RESYNC", "b")], "cursor": "b"}),
            (204, None),
            (500, None),
            (None, None),
        ]
        targets: list[tuple[str, float]] = []

        def get_json(target: str, timeout: float) -> tuple[int | None, Any]:
            targets.append((target, timeout))
            return responses.pop(0)

        inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        poller = CommandPoller(get_json, inbox, poll_seconds=25)
        assert poller.poll_once() == 2 and inbox.qsize() == 2 and poller.cursor == "b"
        assert poller.poll_once() == 0
        assert poller.poll_once() is None and poller.failures == 1 and poller.backoff_seconds() == 2
        assert poller.poll_once() is None and poller.failures == 2 and poller.last_error == "transport error"
        assert targets[0] == (COMMANDS_PATH, 35) and targets[1][0] == f"{COMMANDS_PATH}?cursor=b"

    def test_a_malformed_response_is_a_failure(self) -> None:
        poller = CommandPoller(lambda t, s: (200, {"commands": "nope"}), queue.Queue())
        assert poller.poll_once() is None


class TestQueue:
    def test_enqueue_refuses_what_the_engine_would_refuse(self, db: Database) -> None:
        q = CommandQueue(db, ManualClock(NOW))
        for ctype in ("KILL_SWITCH_RELEASE", "SEND_ORDER"):
            with pytest.raises(CommandRefused):
                q.enqueue("eng-1", ctype, created_by="u")
        with pytest.raises(CommandRefused, match="120"):
            q.enqueue("eng-1", "RESYNC", created_by="u", lifetime=timedelta(seconds=300))
        with pytest.raises(CommandRefused, match="TOTP"):
            q.enqueue("eng-1", "FLATTEN_ALL", created_by="u")

    def test_delivery_cursor_results_and_expiry(self, db: Database) -> None:
        clock = ManualClock(NOW)
        q = CommandQueue(db, clock)
        a = q.enqueue("eng-1", "KILL_SWITCH_ACTIVATE", {"reason": "x"}, created_by="u")
        b = q.enqueue("eng-1", "FLATTEN_ALL", created_by="u", totp="123456")
        q.enqueue("eng-2", "RESYNC", created_by="u")
        got = q.pending("eng-1")
        assert [c["id"] for c in got] == [a["id"], b["id"]] and got[1]["totp"] == "123456"
        assert q.pending("eng-1", cursor=a["id"])[0]["id"] == b["id"]
        assert q.record_result(
            "eng-1", {"command_id": a["id"], "outcome": "EXECUTED", "reason": "", "detail": "ok"}
        )
        assert not q.record_result("eng-2", {"command_id": b["id"], "outcome": "EXECUTED"})  # not its command
        assert [c["id"] for c in q.pending("eng-1")] == [b["id"]]
        clock.advance(121)
        assert q.pending("eng-1") == []
        row = q.get(b["id"])
        assert row is not None and row.status == "EXPIRED" and row.totp is None

    def test_end_to_end_over_signed_http(self, db: Database) -> None:
        """Cloud queue → HMAC-verified long poll → engine processor → command_result back through the outbox."""
        clock = ManualClock(NOW)
        q = CommandQueue(db, clock)
        verifier = Verifier.single("eng-1", HMAC_SECRET, clock)

        def handler(request: httpx.Request) -> httpx.Response:
            target = request.url.raw_path.decode()
            ok = verifier.verify(request.method, target, dict(request.headers), request.content)
            cursor = request.url.params.get("cursor")
            commands = q.pending(ok.engine_id, cursor)
            if not commands:
                return httpx.Response(204)
            return httpx.Response(200, json={"commands": commands, "cursor": commands[-1]["id"]})

        client = CloudClient(
            "https://cloud.example",
            Signer("eng-1", HMAC_SECRET.encode(), clock),
            http=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        poller = CommandPoller(client.get_json, inbox)
        proc, _, engine = processor(db)
        proc.clock = clock
        sent = q.enqueue("eng-1", "POSITION_CLOSE", {"ticket": 3}, created_by="owner", totp=code(clock))
        assert poller.poll_once() == 1 and poller.poll_once() == 0
        [result] = drain(inbox, proc)
        assert result.outcome is Outcome.EXECUTED and engine.calls == [("POSITION_CLOSE", {"ticket": 3})]
        with db.session() as sess:
            event = sess.execute(
                select(OutboxEventRow).where(OutboxEventRow.type == "command_result")
            ).scalar_one()
        assert q.record_result("eng-1", event.payload)  # what the ingest API will do with the event
        row = q.get(sent["id"])
        assert row is not None and row.status == "EXECUTED" and row.totp is None
