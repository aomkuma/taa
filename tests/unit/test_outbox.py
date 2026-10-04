"""Event outbox: schema, priorities, coalescing, batching, backoff, backlog limits and the signed client (TAA-701)."""

from __future__ import annotations

import gzip
import json
import math
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.config import SyncConfig
from app.core.clock import ManualClock
from app.security.hmac_auth import Signer, Verifier
from app.storage.database import Database
from app.storage.models import OutboxEventRow
from app.sync.client import CloudClient
from app.sync.outbox import (
    INGEST_PATH,
    Outbox,
    OutboxSender,
    Priority,
    SenderThread,
    SendResult,
    decode_batch,
    encode_batch,
    priority_of,
)

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
SECRET = "k" * 40
CFG = SyncConfig(
    enabled=True, batch_size=3, backoff_initial_seconds=2, backoff_max_seconds=30, max_attempts=3
)


def rig(db: Database, cfg: SyncConfig = CFG):  # type: ignore[no-untyped-def]
    clock = ManualClock(NOW)
    return Outbox(db, clock, cfg), clock


def rows(db: Database) -> list[OutboxEventRow]:
    with db.session() as sess:
        return list(sess.execute(select(OutboxEventRow).order_by(OutboxEventRow.event_id)).scalars())


class Recorder:
    def __init__(self, *statuses: int | None) -> None:
        self.statuses = list(statuses)
        self.bodies: list[bytes] = []

    def __call__(self, path: str, body: bytes) -> SendResult:
        assert path == INGEST_PATH
        self.bodies.append(body)
        status = self.statuses.pop(0) if self.statuses else 200
        return SendResult(status, "" if status and status < 300 else f"HTTP {status}")


class TestEvents:
    def test_uuid7_ids_priorities_and_json_payloads(self, db: Database) -> None:
        ob, _ = rig(db)
        a = ob.emit("audit_event", {"seq": 1})
        b = ob.emit("opportunity", {"at": NOW})
        c = ob.emit("quote", {"bid": 1.1}, coalesce_key="quote:EURUSD")
        assert [uuid.UUID(x).version for x in (a, b, c)] == [7, 7, 7] and a < b < c
        assert [r.priority for r in rows(db)] == [0, 1, 2]
        assert rows(db)[1].payload == {"at": NOW.isoformat()}  # datetimes travel as ISO 8601
        assert priority_of("trade") is Priority.CRITICAL and priority_of("anything_new") is Priority.STATE

    def test_non_finite_numbers_are_refused(self, db: Database) -> None:
        ob, _ = rig(db)
        with pytest.raises(ValueError):
            ob.emit("decision", {"score": math.nan})

    def test_batches_take_critical_first_then_oldest(self, db: Database) -> None:
        ob, _ = rig(db)
        q = ob.emit("quote", {"n": 0})
        s1 = ob.emit("opportunity", {"n": 1})
        a1 = ob.emit("audit_event", {"n": 2})
        s2 = ob.emit("opportunity", {"n": 3})
        a2 = ob.emit("trade", {"n": 4})
        assert [e.event_id for e in ob.next_batch()] == [a1, a2, s1]
        assert [e.event_id for e in ob.next_batch(10)] == [a1, a2, s1, s2, q]

    def test_quotes_coalesce_while_unsent(self, db: Database) -> None:
        ob, _ = rig(db)
        ob.emit("quote", {"bid": 1.0}, coalesce_key="quote:EURUSD")
        ob.emit("quote", {"bid": 2.0}, coalesce_key="quote:XAUUSD")
        latest = ob.emit("quote", {"bid": 1.1}, coalesce_key="quote:EURUSD")
        pending = rows(db)
        assert len(pending) == 2 and {r.payload["bid"] for r in pending} == {1.1, 2.0}
        ob.mark_sent([latest])
        ob.emit("quote", {"bid": 1.2}, coalesce_key="quote:EURUSD")
        assert len(rows(db)) == 3  # a sent quote is history, not replaced

    def test_wire_format_round_trip(self, db: Database) -> None:
        ob, _ = rig(db)
        ob.emit("audit_event", {"seq": 1}, occurred_at=NOW - timedelta(seconds=5))
        events = ob.next_batch()
        body = encode_batch(events, engine_id="eng-1", sent_at=NOW)
        assert body == encode_batch(events, engine_id="eng-1", sent_at=NOW)  # reproducible (gzip mtime 0)
        doc = decode_batch(body)
        assert doc["schema"] == 1 and doc["engine_id"] == "eng-1" and doc["sent_at_utc"] == NOW.isoformat()
        [ev] = doc["events"]
        assert ev["type"] == "audit_event" and ev["payload"] == {"seq": 1}
        assert ev["occurred_at_utc"] == (NOW - timedelta(seconds=5)).isoformat()


class TestSender:
    def test_a_successful_send_marks_the_batch(self, db: Database) -> None:
        ob, clock = rig(db)
        for i in range(4):
            ob.emit("audit_event", {"i": i})
        transport = Recorder()
        sender = OutboxSender(ob, transport, "eng-1", clock, jitter=lambda: 1.0)
        assert sender.flush_once() == 3 and sender.flush_once() == 1 and sender.flush_once() == 0
        assert len(transport.bodies) == 2 and len(decode_batch(transport.bodies[0])["events"]) == 3
        m = sender.metrics()
        assert m.pending_total == 0 and m.sent_total == 4 and m.last_success_at == NOW
        assert {r.status for r in rows(db)} == {"SENT"}

    def test_transport_errors_back_off_exponentially(self, db: Database) -> None:
        ob, clock = rig(db)
        ob.emit("audit_event", {})

        def down(path: str, body: bytes) -> SendResult:
            raise httpx.ConnectError("offline")

        sender = OutboxSender(ob, down, "eng-1", clock, jitter=lambda: 1.0)
        delays = []
        for _ in range(6):
            assert sender.flush_once() == 0
            delays.append(sender.next_attempt_at - clock.monotonic())
            assert sender.flush_once() == 0  # not due yet: no request at all
            clock.advance(delays[-1])
        assert delays == [2, 4, 8, 16, 30, 30] and sender.consecutive_failures == 6
        assert (
            "ConnectError" in sender.last_error and rows(db)[0].attempts == 0
        )  # retryable: no attempt burnt
        sender.transport = Recorder(200)
        assert sender.flush_once() == 1 and sender.consecutive_failures == 0

    def test_rejected_events_are_parked_as_dead(self, db: Database) -> None:
        ob, clock = rig(db)
        ob.emit("decision", {"bad": True})
        sender = OutboxSender(ob, Recorder(422, 422, 422), "eng-1", clock, jitter=lambda: 1.0)
        for _ in range(3):
            sender.flush_once()
            clock.advance(60)
        [row] = rows(db)
        assert row.status == "DEAD" and row.attempts == 3 and row.last_error == "HTTP 422"
        assert sender.metrics().dead == 1 and ob.next_batch() == []

    def test_events_the_cloud_refuses_are_parked_at_once(self, db: Database) -> None:
        ob, clock = rig(db)
        good, bad = ob.emit("decision", {"n": 1}), ob.emit("decision", {"n": 2})

        def answer(path: str, body: bytes) -> SendResult:
            return SendResult(200, "", {bad: "INVALID_PAYLOAD: hwm: float_type", "unknown-id": "x"})

        sender = OutboxSender(ob, answer, "eng-1", clock, jitter=lambda: 1.0)
        assert sender.flush_once() == 2  # both answered: the drain loop carries on
        by_id = {r.event_id: r for r in rows(db)}
        assert by_id[good].status == "SENT" and by_id[bad].status == "DEAD"
        assert "INVALID_PAYLOAD" in by_id[bad].last_error
        m = sender.metrics()
        assert (m.sent_total, m.rejected_total, m.dead, m.consecutive_failures) == (1, 1, 1, 0)

    def test_batches_respect_the_byte_budget(self, db: Database) -> None:
        cfg = CFG.model_copy(update={"batch_size": 10, "max_batch_bytes": 64_000})
        ob, _ = rig(db, cfg)
        ids = [ob.emit("decision", {"blob": "x" * 30_000}) for _ in range(3)]
        assert [e.event_id for e in ob.next_batch()] == ids[:2]
        ob.mark_sent(ids[:2])
        big = ob.emit("decision", {"blob": "y" * 100_000})  # alone over budget: still sent, by itself
        assert [e.event_id for e in ob.next_batch()] == [ids[2]]
        ob.mark_sent([ids[2]])
        assert [e.event_id for e in ob.next_batch()] == [big]

    def test_auth_and_rate_limits_do_not_burn_attempts(self, db: Database) -> None:
        ob, clock = rig(db)
        ob.emit("decision", {})
        sender = OutboxSender(ob, Recorder(401, 429, 503), "eng-1", clock, jitter=lambda: 1.0)
        for _ in range(3):
            sender.flush_once()
            clock.advance(60)
        assert rows(db)[0].attempts == 0 and rows(db)[0].status == "PENDING"

    def test_backlog_drops_quotes_then_state_never_critical(self, db: Database) -> None:
        cfg = CFG.model_copy(update={"max_backlog_events": 4})
        ob, _ = rig(db, cfg)
        for i in range(3):
            ob.emit("audit_event", {"i": i})
        for i in range(2):
            ob.emit("opportunity", {"i": i})
        for i in range(2):
            ob.emit("quote", {"i": i}, coalesce_key=f"quote:{i}")
        assert ob.enforce_backlog() == 3
        kept = rows(db)
        assert [r.type for r in kept] == ["audit_event"] * 3 + ["opportunity"]
        assert kept[-1].payload == {"i": 1}  # the newest state event survives
        for i in range(3):
            ob.emit("audit_event", {"i": 10 + i})
        ob.enforce_backlog()
        assert sum(r.type == "audit_event" for r in rows(db)) == 6 and ob.dropped_total == 4

    def test_sent_rows_are_purged_after_retention(self, db: Database) -> None:
        ob, clock = rig(db)
        sent = ob.emit("audit_event", {})
        ob.emit("audit_event", {})
        ob.mark_sent([sent])
        clock.advance(23 * 3600)
        assert ob.purge_sent() == 0
        clock.advance(3600)
        assert ob.purge_sent() == 1 and len(rows(db)) == 1

    def test_metrics_report_the_oldest_pending_age(self, db: Database) -> None:
        ob, clock = rig(db)
        ob.emit("audit_event", {})
        clock.advance(90)
        ob.emit("quote", {}, coalesce_key="quote:X")
        m = OutboxSender(ob, Recorder(), "eng-1", clock).metrics()
        assert m.pending == {0: 1, 2: 1} and m.oldest_pending_age_seconds == 90


class TestClient:
    def server(self, clock: ManualClock, status: int = 200):  # type: ignore[no-untyped-def]
        verifier = Verifier.single("eng-1", SECRET, clock)
        seen: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = request.content
            target = request.url.raw_path.decode()
            verifier.verify(request.method, target, dict(request.headers), body)
            seen.append(
                {
                    "encoding": request.headers.get("content-encoding"),
                    "doc": json.loads(gzip.decompress(body)),
                }
            )
            return httpx.Response(status)

        return httpx.Client(transport=httpx.MockTransport(handler)), seen

    def test_signed_gzipped_ingest_is_accepted(self, db: Database) -> None:
        ob, clock = rig(db)
        ob.emit("audit_event", {"seq": 7})
        http, seen = self.server(clock)
        client = CloudClient("https://cloud.example", Signer("eng-1", SECRET.encode(), clock), http=http)
        sender = OutboxSender(ob, client.post_gzip, "eng-1", clock)
        assert sender.flush_once() == 1
        assert seen[0]["encoding"] == "gzip" and seen[0]["doc"]["events"][0]["payload"] == {"seq": 7}

    def test_rejections_in_the_answer_are_reported(self, db: Database) -> None:
        clock = ManualClock(NOW)
        answer = {
            "accepted": 1,
            "duplicates": 0,
            "rejected": [{"event_id": "e2", "code": "UNKNOWN_TYPE", "detail": "x"}],
        }
        http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=answer)))
        client = CloudClient("https://cloud.example", Signer("eng-1", SECRET.encode(), clock), http=http)
        assert client.post_gzip(INGEST_PATH, b"").rejected == {"e2": "UNKNOWN_TYPE: x"}
        odd = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"not json")))
        client = CloudClient("https://cloud.example", Signer("eng-1", SECRET.encode(), clock), http=odd)
        assert client.post_gzip(INGEST_PATH, b"") == SendResult(200, "")

    def test_server_errors_and_transport_failures(self, db: Database) -> None:
        clock = ManualClock(NOW)
        http, _ = self.server(clock, status=500)
        client = CloudClient("https://cloud.example", Signer("eng-1", SECRET.encode(), clock), http=http)
        assert client.post_gzip(INGEST_PATH, gzip.compress(b"{}")) == SendResult(500, "HTTP 500")

        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("slow")

        down = CloudClient(
            "https://cloud.example",
            Signer("eng-1", SECRET.encode(), clock),
            http=httpx.Client(transport=httpx.MockTransport(boom)),
        )
        result = down.post_gzip(INGEST_PATH, b"")
        assert result.status is None and "ConnectTimeout" in result.error


def test_sender_thread_drains_in_the_background(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = Database(f"sqlite:///{(tmp_path / 'e.db').as_posix()}")
    db.create_all()
    ob, clock = rig(db)
    for i in range(7):
        ob.emit("audit_event", {"i": i})
    transport = Recorder()
    thread = SenderThread(OutboxSender(ob, transport, "eng-1", clock), interval=0.05)
    thread.start()
    deadline = time.monotonic() + 5
    while ob.next_batch() and time.monotonic() < deadline:
        time.sleep(0.02)
    thread.stop()
    assert ob.next_batch() == [] and len(transport.bodies) == 3  # 3 + 3 + 1, back to back
    db.dispose()
