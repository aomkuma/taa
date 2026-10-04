"""Event outbox: the engine's replication queue to the cloud (PLAN §A13 "Outbox"; TAA-701).

**Events:** ``{event_id (UUIDv7), type, occurred_at_utc, payload}`` rows in the engine database, written in
the same process that changes the state they describe. The cloud upserts by ``event_id``, so a resend after a
lost acknowledgement is harmless.

**Priorities:** 0 = audit, trades, decisions, breakers, kill switch, command results; 1 = snapshots and other
state (the default); 2 = quotes and similar high-rate telemetry. A batch takes the lowest priority first,
then the oldest.

**Coalescing:** an event with a ``coalesce_key`` (``quote:EURUSD``) replaces the still-unsent event with the
same key, so a backlog of quotes collapses to the latest one per symbol.

**Bounded backlog:** above ``sync.max_backlog_events`` pending rows, the oldest priority-2 events and then
priority-1 events are dropped (counted); priority 0 is never dropped.

**Sending** (:class:`OutboxSender`): batches of ≤ ``batch_size`` events and ≤ ``max_batch_bytes`` of payload
every ``flush_interval_seconds``, as one gzipped JSON body signed with HMAC (:mod:`app.security.hmac_auth`).
A 2xx marks the batch SENT, except the events the cloud lists as rejected (schema or audit-chain problems,
TAA-703): those are parked as DEAD at once and logged, since resending the same bytes cannot succeed. A
network error, a 5xx, 401/403, 408 or 429 backs off exponentially (with jitter) up to ``backoff_max_seconds``;
any other 4xx counts an attempt against each event and parks events that reach ``max_attempts`` as DEAD
(logged), so one bad event cannot block the queue. Sending runs on its own thread and never blocks trading.
"""

from __future__ import annotations

import gzip
import json
import logging
import secrets
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum
from typing import Any

from sqlalchemy import delete, func, select, update

from app.config import SyncConfig
from app.core.clock import Clock, ensure_utc
from app.core.ids import new_id
from app.storage.database import Database
from app.storage.models import OutboxEventRow

log = logging.getLogger(__name__)

INGEST_PATH = "/api/v1/ingest/batch"
SCHEMA_VERSION = 1


class Priority(IntEnum):
    CRITICAL = 0
    STATE = 1
    TELEMETRY = 2


class Status(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    DEAD = "DEAD"


PRIORITIES: dict[str, Priority] = {
    "audit_event": Priority.CRITICAL,
    "trade": Priority.CRITICAL,
    "deal": Priority.CRITICAL,
    "order_intent": Priority.CRITICAL,
    "decision": Priority.CRITICAL,
    "breaker": Priority.CRITICAL,
    "kill_switch": Priority.CRITICAL,
    "command_result": Priority.CRITICAL,
    "engine_event": Priority.CRITICAL,
    "quote": Priority.TELEMETRY,
    "heartbeat": Priority.TELEMETRY,
}


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat()
    return str(value)  # Decimal, enums and the like


def priority_of(event_type: str) -> Priority:
    return PRIORITIES.get(event_type, Priority.STATE)


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    type: str
    occurred_at: datetime
    payload: Mapping[str, Any]

    def to_wire(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "occurred_at_utc": ensure_utc(self.occurred_at).isoformat(),
            "payload": dict(self.payload),
        }


def encode_batch(events: list[Event], *, engine_id: str, sent_at: datetime) -> bytes:
    """The gzipped JSON body of one ingest request (canonical key order, so a body is reproducible)."""
    doc = {
        "schema": SCHEMA_VERSION,
        "engine_id": engine_id,
        "sent_at_utc": ensure_utc(sent_at).isoformat(),
        "events": [e.to_wire() for e in events],
    }
    raw = json.dumps(
        doc, sort_keys=True, separators=(",", ":"), allow_nan=False, default=_json_default
    ).encode()
    return gzip.compress(raw, mtime=0)


def decode_batch(body: bytes) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(gzip.decompress(body))
    return data


@dataclass(frozen=True, slots=True)
class BacklogMetrics:
    pending: dict[int, int]  # by priority
    dead: int
    oldest_pending_age_seconds: float | None
    sent_total: int
    rejected_total: int
    dropped_total: int
    failed_sends: int
    consecutive_failures: int
    last_error: str
    last_success_at: datetime | None

    @property
    def pending_total(self) -> int:
        return sum(self.pending.values())


class Outbox:
    def __init__(self, db: Database, clock: Clock, config: SyncConfig) -> None:
        self.db = db
        self.clock = clock
        self.config = config
        self.dropped_total = 0
        self._lock = threading.Lock()  # emit() can be called from the engine loop and helper threads

    def emit(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        occurred_at: datetime | None = None,
        coalesce_key: str | None = None,
        priority: Priority | None = None,
    ) -> str:
        now = self.clock.now_utc()
        event_id = new_id()
        row = OutboxEventRow(
            event_id=event_id,
            type=event_type,
            priority=int(priority if priority is not None else priority_of(event_type)),
            occurred_at=ensure_utc(occurred_at or now),
            created_at=now,
            payload=json.loads(json.dumps(dict(payload), default=_json_default, allow_nan=False)),
            coalesce_key=coalesce_key,
            status=Status.PENDING.value,
            attempts=0,
            last_error="",
        )
        with self._lock, self.db.session() as sess:
            if coalesce_key is not None:
                sess.execute(
                    delete(OutboxEventRow).where(
                        OutboxEventRow.coalesce_key == coalesce_key,
                        OutboxEventRow.status == Status.PENDING.value,
                    )
                )
            sess.add(row)
        return event_id

    def next_batch(self, limit: int | None = None) -> list[Event]:
        """The next events to send: lowest priority first, then oldest, within the count and byte budgets
        (the first event always goes, however large, so an oversized event fails visibly instead of
        blocking the queue)."""
        with self.db.session() as sess:
            rows = sess.execute(
                select(OutboxEventRow)
                .where(OutboxEventRow.status == Status.PENDING.value)
                .order_by(OutboxEventRow.priority, OutboxEventRow.event_id)
                .limit(limit or self.config.batch_size)
            ).scalars()
            events: list[Event] = []
            size = 0
            for r in rows:
                size += len(json.dumps(r.payload, separators=(",", ":")))
                if events and size > self.config.max_batch_bytes:
                    break
                events.append(Event(r.event_id, r.type, ensure_utc(r.occurred_at), dict(r.payload)))
            return events

    def mark_sent(self, event_ids: list[str]) -> None:
        now = self.clock.now_utc()
        with self.db.session() as sess:
            sess.execute(
                update(OutboxEventRow)
                .where(OutboxEventRow.event_id.in_(event_ids))
                .values(status=Status.SENT.value, sent_at=now)
            )

    def mark_dead(self, rejected: Mapping[str, str]) -> None:
        """Park events the cloud refused for good (event id → reason) as DEAD."""
        with self.db.session() as sess:
            for event_id, reason in rejected.items():
                sess.execute(
                    update(OutboxEventRow)
                    .where(OutboxEventRow.event_id == event_id)
                    .values(
                        status=Status.DEAD.value,
                        attempts=OutboxEventRow.attempts + 1,
                        last_error=f"rejected by the cloud: {reason}"[:500],
                    )
                )
        for event_id, reason in rejected.items():
            log.error("outbox event %s rejected by the cloud and parked as DEAD: %s", event_id, reason)

    def mark_rejected(self, event_ids: list[str], error: str) -> int:
        """Count an attempt against each event; park those at ``max_attempts`` as DEAD. Returns dead count."""
        with self.db.session() as sess:
            sess.execute(
                update(OutboxEventRow)
                .where(OutboxEventRow.event_id.in_(event_ids))
                .values(attempts=OutboxEventRow.attempts + 1, last_error=error[:500])
            )
            dead = list(
                sess.execute(
                    select(OutboxEventRow.event_id).where(
                        OutboxEventRow.event_id.in_(event_ids),
                        OutboxEventRow.attempts >= self.config.max_attempts,
                    )
                ).scalars()
            )
            if dead:
                sess.execute(
                    update(OutboxEventRow)
                    .where(OutboxEventRow.event_id.in_(dead))
                    .values(status=Status.DEAD.value)
                )
        for event_id in dead:
            log.error(
                "outbox event %s parked as DEAD after %d attempts: %s",
                event_id,
                self.config.max_attempts,
                error,
            )
        return len(dead)

    def enforce_backlog(self) -> int:
        """Drop the oldest priority-2, then priority-1 pending events above the cap (never priority 0)."""
        dropped = 0
        with self._lock, self.db.session() as sess:
            pending = sess.execute(
                select(func.count())
                .select_from(OutboxEventRow)
                .where(OutboxEventRow.status == Status.PENDING.value)
            ).scalar_one()
            excess = pending - self.config.max_backlog_events
            for prio in (Priority.TELEMETRY, Priority.STATE):
                if excess <= 0:
                    break
                ids = list(
                    sess.execute(
                        select(OutboxEventRow.event_id)
                        .where(
                            OutboxEventRow.status == Status.PENDING.value,
                            OutboxEventRow.priority == int(prio),
                        )
                        .order_by(OutboxEventRow.event_id)
                        .limit(excess)
                    ).scalars()
                )
                if ids:
                    sess.execute(delete(OutboxEventRow).where(OutboxEventRow.event_id.in_(ids)))
                    dropped += len(ids)
                    excess -= len(ids)
        if dropped:
            self.dropped_total += dropped
            log.warning(
                "outbox backlog over %d: dropped %d low-priority events",
                self.config.max_backlog_events,
                dropped,
            )
        return dropped

    def purge_sent(self) -> int:
        cutoff = self.clock.now_utc() - timedelta(hours=self.config.sent_retention_hours)
        with self.db.session() as sess:
            result = sess.execute(
                delete(OutboxEventRow).where(
                    OutboxEventRow.status == Status.SENT.value, OutboxEventRow.sent_at <= cutoff
                )
            )
        return int(getattr(result, "rowcount", 0) or 0)

    def counts(self) -> tuple[dict[int, int], int, datetime | None]:
        with self.db.session() as sess:
            pending = {
                int(p): int(n)
                for p, n in sess.execute(
                    select(OutboxEventRow.priority, func.count())
                    .where(OutboxEventRow.status == Status.PENDING.value)
                    .group_by(OutboxEventRow.priority)
                ).all()
            }
            dead = sess.execute(
                select(func.count())
                .select_from(OutboxEventRow)
                .where(OutboxEventRow.status == Status.DEAD.value)
            ).scalar_one()
            oldest = sess.execute(
                select(func.min(OutboxEventRow.created_at)).where(
                    OutboxEventRow.status == Status.PENDING.value
                )
            ).scalar_one()
        return pending, int(dead), None if oldest is None else ensure_utc(oldest)


# --- sending ------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SendResult:
    status: int | None  # HTTP status, or None for a transport error
    error: str = ""
    rejected: Mapping[str, str] = field(default_factory=dict)  # 2xx: event id → why the cloud refused it


Transport = Callable[[str, bytes], SendResult]  # (path, gzipped body) -> result; signs and posts

RETRYABLE = {401, 403, 408, 425, 429}


@dataclass
class OutboxSender:
    outbox: Outbox
    transport: Transport
    engine_id: str
    clock: Clock
    jitter: Callable[[], float] = field(default=lambda: 0.5 + secrets.SystemRandom().random() / 2)
    sent_total: int = 0
    rejected_total: int = 0
    failed_sends: int = 0
    consecutive_failures: int = 0
    last_error: str = ""
    last_success_at: datetime | None = None
    next_attempt_at: float = 0.0  # monotonic

    def backoff_seconds(self) -> float:
        cfg = self.outbox.config
        base = min(
            cfg.backoff_max_seconds, cfg.backoff_initial_seconds * 2 ** max(0, self.consecutive_failures - 1)
        )
        return base * self.jitter()

    def flush_once(self) -> int:
        """Send one batch if due. Returns the number of events the cloud answered (stored or refused)."""
        if self.clock.monotonic() < self.next_attempt_at:
            return 0
        self.outbox.enforce_backlog()
        events = self.outbox.next_batch()
        if not events:
            return 0
        body = encode_batch(events, engine_id=self.engine_id, sent_at=self.clock.now_utc())
        ids = [e.event_id for e in events]
        try:
            result = self.transport(INGEST_PATH, body)
        except Exception as exc:  # transport boundary: never let a network problem escape into the engine
            result = SendResult(None, f"{type(exc).__name__}: {exc}")
        if result.status is not None and 200 <= result.status < 300:
            sent = set(ids)
            rejected = {i: r for i, r in result.rejected.items() if i in sent}
            if rejected:
                self.outbox.mark_dead(rejected)
                self.rejected_total += len(rejected)
            self.outbox.mark_sent([i for i in ids if i not in rejected])
            self.sent_total += len(ids) - len(rejected)
            self.consecutive_failures = 0
            self.last_success_at = self.clock.now_utc()
            self.next_attempt_at = 0.0
            return len(ids)
        self.failed_sends += 1
        self.consecutive_failures += 1
        self.last_error = result.error or f"HTTP {result.status}"
        if result.status is not None and 400 <= result.status < 500 and result.status not in RETRYABLE:
            self.outbox.mark_rejected(ids, self.last_error)
        self.next_attempt_at = self.clock.monotonic() + self.backoff_seconds()
        log.warning(
            "outbox send failed (%s); next attempt in %.1fs",
            self.last_error,
            self.next_attempt_at - self.clock.monotonic(),
        )
        return 0

    def drain(self, max_batches: int = 100_000) -> int:
        """Send until the queue is empty or a send fails (tools such as the history upload). Returns events
        answered; check ``consecutive_failures`` afterwards."""
        total = 0
        for _ in range(max_batches):
            self.next_attempt_at = 0.0  # a tool retries on its own schedule, not the backoff's
            sent = self.flush_once()
            if sent == 0:
                break
            total += sent
        return total

    def metrics(self) -> BacklogMetrics:
        pending, dead, oldest = self.outbox.counts()
        age = None if oldest is None else (self.clock.now_utc() - oldest).total_seconds()
        return BacklogMetrics(
            pending=pending,
            dead=dead,
            oldest_pending_age_seconds=age,
            sent_total=self.sent_total,
            rejected_total=self.rejected_total,
            dropped_total=self.outbox.dropped_total,
            failed_sends=self.failed_sends,
            consecutive_failures=self.consecutive_failures,
            last_error=self.last_error,
            last_success_at=self.last_success_at,
        )


class SenderThread:
    """Runs :meth:`OutboxSender.flush_once` on a daemon thread every ``flush_interval_seconds``."""

    def __init__(self, sender: OutboxSender, interval: float, *, purge_every: float = 3600.0) -> None:
        self.sender = sender
        self.interval = interval
        self.purge_every = purge_every
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="outbox-sender", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        next_purge = 0.0
        while not self._stop.is_set():
            try:
                while self.sender.flush_once():  # drain a backlog without waiting between full batches
                    if self._stop.is_set():
                        return
                now = self.sender.clock.monotonic()
                if now >= next_purge:
                    self.sender.outbox.purge_sent()
                    next_purge = now + self.purge_every
            except Exception:  # thread boundary: log and keep going; the engine keeps trading regardless
                log.exception("outbox sender loop failed")
            self._stop.wait(self.interval)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
