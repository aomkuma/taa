"""The per-engine change feed behind the live stream: sequence numbers, coalescing, retention, reads (TAA-804)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select

from app.core.clock import ManualClock
from app.core.ids import new_id
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import StreamEventRow, StreamHeadRow
from app.sync.command_queue import CommandQueue
from app.sync.events import SPECS_BY_MODEL, SPECS_BY_TYPE
from app.sync.ingest import IngestService
from app.sync.stream import OMIT, TOPIC_OF_TYPE, TOPICS, Bounds, StreamEntry, StreamLog, entry_for
from tests.sync_data import sample_rows

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
ENGINE = "eng-1"


def entry(key: str, topic: str = "positions", kind: str = "paper_position", **item: Any) -> StreamEntry:
    return StreamEntry(topic, kind, key, {"key": key, **item})


@pytest.fixture
def cloud() -> Database:
    db = Database("sqlite://")
    db.create_all()
    return db


@pytest.fixture
def log(cloud: Database) -> StreamLog:
    return StreamLog(cloud, ManualClock(NOW), keep=5)


def append(log: StreamLog, engine_id: str, *entries: StreamEntry) -> int | None:
    with log.db.session() as sess:
        return log.append(sess, engine_id, entries)


class TestAppend:
    def test_sequence_numbers_count_per_engine(self, log: StreamLog) -> None:
        assert append(log, ENGINE, entry("a"), entry("b")) == 2
        assert append(log, ENGINE, entry("c")) == 3
        assert append(log, "eng-2", entry("a")) == 1
        events, cursor, _ = log.read(ENGINE, 0, TOPICS, 10)
        assert [(e.seq, e.key) for e in events] == [(1, "a"), (2, "b"), (3, "c")] and cursor == 3
        assert [e.seq for e in log.read("eng-2", 0, TOPICS, 10)[0]] == [1]

    def test_the_newest_change_of_a_row_wins_and_keeps_its_place(self, log: StreamLog) -> None:
        append(log, ENGINE, entry("a", v=1), entry("b"), entry("a", v=2), entry("a", "status", "risk_state"))
        events = log.read(ENGINE, 0, TOPICS, 10)[0]
        assert [(e.type, e.key, e.item.get("v")) for e in events] == [
            ("paper_position", "b", None),
            ("paper_position", "a", 2),
            ("risk_state", "a", None),
        ]

    def test_nothing_to_append_takes_no_number(self, log: StreamLog) -> None:
        assert append(log, ENGINE) is None
        with log.db.session() as sess:
            assert sess.scalar(select(func.count()).select_from(StreamHeadRow)) == 0
        assert log.bounds(ENGINE) == Bounds(floor=1, head=0)

    def test_only_the_newest_events_are_kept(self, log: StreamLog) -> None:
        for i in range(8):
            append(log, ENGINE, entry(f"k{i}"))
        append(log, "eng-2", entry("x"))
        with log.db.session() as sess:
            kept = sess.scalars(
                select(StreamEventRow.seq)
                .where(StreamEventRow.engine_id == ENGINE)
                .order_by(StreamEventRow.seq)
            ).all()
        assert kept == [4, 5, 6, 7, 8]
        bounds = log.bounds(ENGINE)
        assert bounds == Bounds(floor=4, head=8)
        assert [bounds.resumable(c) for c in (2, 3, 8, 9)] == [False, True, True, False]
        assert log.bounds("eng-2") == Bounds(floor=1, head=1)  # another engine's events are untouched


class TestRead:
    def test_topics_filter_and_the_cursor_moves_to_the_head(self, log: StreamLog) -> None:
        append(log, ENGINE, entry("a"), entry("d1", "decisions", "decision"), entry("b"))
        events, cursor, _ = log.read(ENGINE, 0, ("decisions",), 10)
        assert [e.key for e in events] == ["d1"] and cursor == 3  # the positions events are not rescanned
        events, cursor, _ = log.read(ENGINE, 3, TOPICS, 10)
        assert events == [] and cursor == 3

    def test_a_full_page_continues_after_its_last_event(self, log: StreamLog) -> None:
        append(log, ENGINE, entry("a"), entry("b"), entry("c"))
        events, cursor, _ = log.read(ENGINE, 0, TOPICS, 2)
        assert [e.seq for e in events] == [1, 2] and cursor == 2
        events, cursor, _ = log.read(ENGINE, cursor, TOPICS, 2)
        assert [e.seq for e in events] == [3] and cursor == 3

    def test_an_event_serializes_with_its_time(self, log: StreamLog) -> None:
        append(log, ENGINE, entry("a", price=1.1))
        [event] = log.read(ENGINE, 0, TOPICS, 1)[0]
        assert event.to_dict() == {
            "seq": 1,
            "type": "paper_position",
            "key": "a",
            "at": NOW.isoformat(),
            "item": {"key": "a", "price": 1.1},
        }


class TestEntries:
    def test_every_streamed_type_is_a_replicated_table_on_a_known_topic(self) -> None:
        assert set(TOPIC_OF_TYPE) <= set(SPECS_BY_TYPE)
        assert set(TOPIC_OF_TYPE.values()) <= set(TOPICS)
        for kind, columns in OMIT.items():
            assert set(columns) <= set(SPECS_BY_TYPE[kind].column_names)

    def test_a_streamed_row_leaves_out_the_engine_and_large_documents(self) -> None:
        values = {"engine_id": ENGINE, "decision_id": "d1", "signal": {}, "market": {}, "plan": [], "at": NOW}
        e = entry_for("decision", "d1", values)
        assert e == StreamEntry("decisions", "decision", "d1", {"decision_id": "d1", "at": NOW.isoformat()})
        assert entry_for("audit_event", "engine:x|1", {"seq": 1}) is None
        assert entry_for("symbol_catalog", "EURUSD", {}) is None


def sample_events() -> dict[str, dict[str, Any]]:
    """One wire event per replicated table, from rows flushed to an engine database (defaults filled in)."""
    engine = Database("sqlite://")
    engine.create_all()
    with engine.session() as sess:
        rows = sample_rows()
        sess.add_all(rows)
        sess.flush()
        return {type_of(r): row_event(type_of(r), r) for r in rows}


def row_event(event_type: str, row: Any) -> dict[str, Any]:
    return {
        "event_id": new_id(),
        "type": event_type,
        "occurred_at_utc": NOW.isoformat(),
        "payload": SPECS_BY_TYPE[event_type].payload(row),
    }


class TestIngest:
    @pytest.fixture
    def service(self, cloud: Database) -> IngestService:
        clock = ManualClock(NOW)
        return IngestService(cloud, clock, CommandQueue(cloud, clock))

    def batch(self, *events: dict[str, Any]) -> dict[str, Any]:
        return {"schema": 1, "engine_id": ENGINE, "sent_at_utc": NOW.isoformat(), "events": list(events)}

    def test_applied_rows_of_streamed_types_reach_the_feed(self, service: IngestService) -> None:
        events = sample_events()
        result = service.ingest(ENGINE, self.batch(*events.values()))
        assert result.accepted == len(events) and not result.rejected
        streamed = service.stream.read(ENGINE, 0, TOPICS, 100)[0]
        assert sorted(e.type for e in streamed) == sorted(t for t in events if t in TOPIC_OF_TYPE)
        [decision] = [e for e in streamed if e.type == "decision"]
        assert decision.topic == "decisions" and decision.key == "d1" and "signal" not in decision.item
        assert decision.item["symbol"] == "EURUSD" and "engine_id" not in decision.item

    def test_resends_and_rejected_events_stream_nothing(self, service: IngestService) -> None:
        event = sample_events()["paper_position"]
        service.ingest(ENGINE, self.batch(event))
        assert service.stream.bounds(ENGINE).head == 1
        bad = event | {"event_id": new_id(), "payload": event["payload"] | {"volume": "x"}}
        result = service.ingest(ENGINE, self.batch(event, bad))
        assert result.duplicates == 1 and len(result.rejected) == 1
        assert service.stream.bounds(ENGINE).head == 1

    def test_a_failed_batch_streams_nothing(
        self, service: IngestService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        position = sample_events()["paper_position"]

        def boom(*_args: Any) -> None:
            raise RuntimeError("database gone")

        monkeypatch.setattr(service, "_advance", boom)
        audit = {"event_id": new_id(), "type": "audit_event", "occurred_at_utc": NOW.isoformat()}
        with pytest.raises(RuntimeError):  # the audit event forces _advance after the row was applied
            service.ingest(
                ENGINE,
                self.batch(position, audit | {"payload": audit_payload()}),
            )
        assert service.stream.bounds(ENGINE) == Bounds(floor=1, head=0)


def type_of(row: Any) -> str:
    return SPECS_BY_MODEL[type(row)].event_type


def audit_payload() -> dict[str, Any]:
    db = Database("sqlite://")
    db.create_all()
    event = AuditLog(db, f"engine:{ENGINE}", ManualClock(NOW)).append("T", "e", {})
    return SPECS_BY_TYPE["audit_event"].payload(event)
