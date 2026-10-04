"""Remote commands: protocol, engine-side checks and the long-poll client (PLAN §A13 "Commands"; TAA-704).

A command is ``{id, type, params, created_by, created_at, expires_at, totp?}``. The engine pulls commands
(:class:`CommandPoller`, its own thread) and processes them **on the engine loop**
(:class:`CommandProcessor`), in this order, failing closed:

1. **Parse:** malformed commands are rejected (``INVALID``).
2. **Once:** a command id already in ``command_log`` is not executed again (``DUPLICATE``).
3. **Expiry:** ``expires_at`` at most :data:`MAX_LIFETIME` (120 s) after ``created_at``, not in the past, and
   ``created_at`` not more than 30 s in the future.
4. **Risk-increasing commands are always rejected** (``RISK_INCREASING``): release the kill switch, reset a
   breaker, enable a strategy, change limits or mode. Releasing and raising stay in the local CLI/config.
5. **Allowlist:** only :class:`CommandType` values are known (``NOT_ALLOWED`` otherwise).
6. **TOTP:** POSITION_CLOSE and FLATTEN_ALL need a single-use code verified here against
   ``CONTROL_TOTP_SECRET`` (:mod:`app.security.totp`). Without a configured secret they are refused.
7. **Execute** the engine's handler; an exception is a ``FAILED`` result, never a crash of the loop.

Every outcome is written to ``command_log``, appended to the audit chain (``REMOTE_COMMAND``, without the
code) and emitted as a priority-0 ``command_result`` outbox event: that is how results reach the cloud, signed
and retried like any other event.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from urllib.parse import quote

from sqlalchemy import select

from app.core.clock import Clock, ensure_utc
from app.core.errors import TaaError
from app.security.totp import SingleUseTotp
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import CommandLogRow
from app.sync.outbox import Outbox, Priority

log = logging.getLogger(__name__)

COMMANDS_PATH = "/api/v1/engine/commands"
MAX_LIFETIME = timedelta(seconds=120)
MAX_FUTURE_SKEW = timedelta(seconds=30)


class CommandType(StrEnum):
    """The allowlist: each command only reduces risk or asks for information."""

    KILL_SWITCH_ACTIVATE = "KILL_SWITCH_ACTIVATE"
    STRATEGY_DISABLE = "STRATEGY_DISABLE"
    RESYNC = "RESYNC"
    RESCAN_SUITABILITY = "RESCAN_SUITABILITY"
    POSITION_CLOSE = "POSITION_CLOSE"
    FLATTEN_ALL = "FLATTEN_ALL"


TOTP_REQUIRED = frozenset({CommandType.POSITION_CLOSE, CommandType.FLATTEN_ALL})

# Named explicitly so the rejection reason is clear; anything else unknown is NOT_ALLOWED anyway.
RISK_INCREASING = frozenset(
    {
        "KILL_SWITCH_RELEASE",
        "BREAKER_RESET",
        "STRATEGY_ENABLE",
        "LIMITS_CHANGE",
        "RISK_CHANGE",
        "MODE_CHANGE",
        "CONFIG_CHANGE",
        "LIVE_ENABLE",
    }
)


class Outcome(StrEnum):
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class Reason(StrEnum):
    NONE = ""
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
    EXPIRED = "EXPIRED"
    RISK_INCREASING = "RISK_INCREASING"
    NOT_ALLOWED = "NOT_ALLOWED"
    TOTP_NOT_CONFIGURED = "TOTP_NOT_CONFIGURED"
    TOTP_INVALID = "TOTP_INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    HANDLER_ERROR = "HANDLER_ERROR"


class CommandFailed(TaaError):
    """Raised by a handler when the command was valid but could not be carried out."""


@dataclass(frozen=True, slots=True)
class Command:
    id: str
    type: str
    params: Mapping[str, Any]
    created_by: str
    created_at: datetime
    expires_at: datetime
    totp: str | None = field(default=None, repr=False)

    @property
    def actor(self) -> str:
        return f"cloud:{self.created_by}" if self.created_by else "cloud"


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamps must be ISO 8601 strings")
    return ensure_utc(datetime.fromisoformat(value))  # naive timestamps are rejected


def parse(raw: Mapping[str, Any]) -> Command:
    """A command from its wire form; raises ValueError when malformed."""
    cid, ctype, params = raw.get("id"), raw.get("type"), raw.get("params", {})
    if not isinstance(cid, str) or not 0 < len(cid) <= 64:
        raise ValueError("id must be a non-empty string of at most 64 characters")
    if not isinstance(ctype, str) or not ctype:
        raise ValueError("type must be a non-empty string")
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    created_by = raw.get("created_by", "")
    totp = raw.get("totp")
    if not isinstance(created_by, str) or (totp is not None and not isinstance(totp, str)):
        raise ValueError("created_by and totp must be strings")
    return Command(
        cid,
        ctype,
        dict(params),
        created_by[:128],
        _time(raw.get("created_at")),
        _time(raw.get("expires_at")),
        totp,
    )


@dataclass(frozen=True, slots=True)
class CommandResult:
    command_id: str
    type: str
    outcome: Outcome
    reason: Reason
    detail: str
    at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "type": self.type,
            "outcome": self.outcome.value,
            "reason": self.reason.value,
            "detail": self.detail,
            "at": self.at.isoformat(),
        }


Handler = Callable[[Command], str]  # returns a short detail; raises CommandFailed (or TaaError) on failure


class CommandProcessor:
    def __init__(
        self,
        db: Database,
        clock: Clock,
        handlers: Mapping[CommandType, Handler],
        *,
        totp_secret: str | None = None,
        audit: AuditLog | None = None,
        outbox: Outbox | None = None,
    ) -> None:
        self.db = db
        self.clock = clock
        self.handlers = dict(handlers)
        self.audit = audit
        self.outbox = outbox
        self.totp = None
        if totp_secret:
            self.totp = SingleUseTotp(totp_secret, clock, used_steps=self._recent_steps())

    def _recent_steps(self) -> list[int]:
        since = self.clock.now_utc() - timedelta(minutes=10)
        with self.db.session() as sess:
            return [
                s
                for s in sess.execute(
                    select(CommandLogRow.totp_step).where(
                        CommandLogRow.received_at >= since, CommandLogRow.totp_step.is_not(None)
                    )
                ).scalars()
                if s is not None
            ]

    def process(self, raw: Mapping[str, Any]) -> CommandResult:
        now = self.clock.now_utc()
        try:
            cmd = parse(raw)
        except (ValueError, TypeError) as exc:
            cid = raw.get("id") if isinstance(raw.get("id"), str) else ""
            result = CommandResult(
                str(cid)[:64], str(raw.get("type", ""))[:48], Outcome.REJECTED, Reason.INVALID, str(exc), now
            )
            log.warning("remote command rejected as invalid: %s", exc)
            if cid and not self._seen(str(cid)[:64]):
                self._record(None, result, None, raw)
            return result
        if self._seen(cmd.id):
            log.info("remote command %s already processed", cmd.id)
            return CommandResult(
                cmd.id, cmd.type, Outcome.REJECTED, Reason.DUPLICATE, "already processed", now
            )
        result, step = self._decide(cmd, now)
        self._record(cmd, result, step, raw)
        return result

    def _decide(self, cmd: Command, now: datetime) -> tuple[CommandResult, int | None]:
        def done(outcome: Outcome, reason: Reason, detail: str) -> CommandResult:
            return CommandResult(cmd.id, cmd.type, outcome, reason, detail, self.clock.now_utc())

        if cmd.expires_at - cmd.created_at > MAX_LIFETIME:
            return done(Outcome.REJECTED, Reason.INVALID, "lifetime over 120 s"), None
        if cmd.created_at > now + MAX_FUTURE_SKEW:
            return done(Outcome.REJECTED, Reason.INVALID, "created in the future"), None
        if now > cmd.expires_at:
            return done(Outcome.REJECTED, Reason.EXPIRED, f"expired at {cmd.expires_at.isoformat()}"), None
        if cmd.type in RISK_INCREASING:
            return done(
                Outcome.REJECTED, Reason.RISK_INCREASING, "only the local CLI or config may do this"
            ), None
        try:
            ctype = CommandType(cmd.type)
        except ValueError:
            return done(Outcome.REJECTED, Reason.NOT_ALLOWED, "not on the engine's allowlist"), None
        handler = self.handlers.get(ctype)
        if handler is None:
            return done(Outcome.REJECTED, Reason.UNSUPPORTED, "not available in this engine"), None
        step = None
        if ctype in TOTP_REQUIRED:
            if self.totp is None:
                return done(
                    Outcome.REJECTED, Reason.TOTP_NOT_CONFIGURED, "CONTROL_TOTP_SECRET is not set"
                ), None
            step = self.totp.verify(cmd.totp)
            if step is None:
                return done(
                    Outcome.REJECTED, Reason.TOTP_INVALID, "missing, wrong, expired or reused code"
                ), None
        try:
            detail = handler(cmd)
        except (CommandFailed, TaaError, PermissionError, ValueError, KeyError) as exc:
            return done(Outcome.FAILED, Reason.HANDLER_ERROR, f"{type(exc).__name__}: {exc}"), step
        return done(Outcome.EXECUTED, Reason.NONE, detail), step

    def _seen(self, command_id: str) -> bool:
        with self.db.session() as sess:
            return sess.get(CommandLogRow, command_id) is not None

    def _record(
        self, cmd: Command | None, result: CommandResult, step: int | None, raw: Mapping[str, Any]
    ) -> None:
        params = dict(cmd.params) if cmd is not None else {}
        with self.db.session() as sess:
            sess.add(
                CommandLogRow(
                    command_id=result.command_id,
                    type=result.type,
                    created_by=cmd.created_by if cmd else str(raw.get("created_by", ""))[:128],
                    created_at=cmd.created_at if cmd else None,
                    expires_at=cmd.expires_at if cmd else None,
                    received_at=self.clock.now_utc(),
                    outcome=result.outcome.value,
                    reason=result.reason.value,
                    detail=result.detail[:2000],
                    totp_step=step,
                    params=params,
                )
            )
        payload = result.to_payload()
        if self.audit is not None:
            self.audit.append("REMOTE_COMMAND", cmd.actor if cmd else "cloud", payload | {"params": params})
        if self.outbox is not None:
            self.outbox.emit("command_result", payload, priority=Priority.CRITICAL)
        level = logging.WARNING if result.outcome is not Outcome.EXECUTED else logging.INFO
        log.log(
            level,
            "remote command %s %s: %s %s %s",
            result.command_id,
            result.type,
            result.outcome.value,
            result.reason.value,
            result.detail,
        )


# --- polling ------------------------------------------------------------------------------------------------


class CommandPoller:
    """Long-polls the cloud on its own thread and hands raw commands to the engine loop through *inbox*."""

    def __init__(
        self,
        get_json: Callable[[str, float], tuple[int | None, Any]],
        inbox: queue.Queue[dict[str, Any]],
        *,
        poll_seconds: float = 25.0,
        backoff_max_seconds: float = 60.0,
    ) -> None:
        self.get_json = get_json
        self.inbox = inbox
        self.poll_seconds = poll_seconds
        self.backoff_max_seconds = backoff_max_seconds
        self.cursor: str | None = None
        self.failures = 0
        self.received = 0
        self.last_error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def target(self) -> str:
        return (
            COMMANDS_PATH if self.cursor is None else f"{COMMANDS_PATH}?cursor={quote(self.cursor, safe='')}"
        )

    def poll_once(self) -> int | None:
        """One long poll. Returns the number of commands queued, or None after a failure."""
        status, data = self.get_json(self.target(), self.poll_seconds + 10)
        if status == 204:
            self.failures = 0
            return 0
        if status != 200 or not isinstance(data, dict) or not isinstance(data.get("commands", []), list):
            self.failures += 1
            self.last_error = f"HTTP {status}" if status is not None else "transport error"
            return None
        commands = [c for c in data.get("commands", []) if isinstance(c, dict)]
        for c in commands:
            self.inbox.put(c)
        cursor = data.get("cursor")
        if isinstance(cursor, str) and cursor:
            self.cursor = cursor
        elif commands and isinstance(commands[-1].get("id"), str):
            self.cursor = commands[-1]["id"]
        self.failures = 0
        self.received += len(commands)
        return len(commands)

    def backoff_seconds(self) -> float:
        return min(self.backoff_max_seconds, 2.0 ** min(self.failures, 6))

    def start(self) -> None:
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="command-poller", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                got = self.poll_once()
            except Exception:  # thread boundary: keep polling; commands are optional, trading is not
                log.exception("command poll failed")
                got = None
                self.failures += 1
            if got is None:
                self._stop.wait(self.backoff_seconds())

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None


def drain(
    inbox: queue.Queue[dict[str, Any]], processor: CommandProcessor, limit: int = 20
) -> list[CommandResult]:
    """Process up to *limit* queued commands (called from the engine loop)."""
    out = []
    for _ in range(limit):
        try:
            raw = inbox.get_nowait()
        except queue.Empty:
            break
        out.append(processor.process(raw))
    return out
