"""Cloud ingest: envelope and event validation, idempotent upserts, audit-chain continuity (TAA-703)."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select

from app.core.clock import ManualClock
from app.core.ids import new_id
from app.storage.audit import AuditLog, compute_hash, verify_chain
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    AuditReplicaRow,
    DecisionCheckRow,
    EngineCommandRow,
    RiskState,
)
from app.sync.command_queue import CommandQueue
from app.sync.events import MAX_BATCH_EVENTS, SPECS_BY_MODEL, SPECS_BY_TYPE
from app.sync.ingest import BatchError, IngestResult, IngestService, RejectCode, decode_body
from tests.sync_data import sample_rows

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
ENGINE = "eng-1"
CHAIN = f"engine:{ENGINE}"


def ev(event_type: str, payload: dict[str, Any], event_id: str | None = None) -> dict[str, Any]:
    return {
        "event_id": event_id or new_id(),
        "type": event_type,
        "occurred_at_utc": NOW.isoformat(),
        "payload": payload,
    }


def batch(*events: dict[str, Any], engine_id: str = ENGINE) -> dict[str, Any]:
    return {"schema": 1, "engine_id": engine_id, "sent_at_utc": NOW.isoformat(), "events": list(events)}


def risk(hwm: float = 1000.0) -> dict[str, Any]:
    return {
        "account_key": "acct",
        "hwm": hwm,
        "cumulative_cash_flow": 0.0,
        "consecutive_losses": 0,
        "last_loss_at": None,
        "updated_at": NOW.isoformat(),
    }


def codes(result: IngestResult) -> list[str]:
    return [r.code.value for r in result.rejected]


@pytest.fixture
def cloud() -> Database:
    db = Database("sqlite://")
    db.create_all()
    return db


@pytest.fixture
def service(cloud: Database) -> IngestService:
    clock = ManualClock(NOW)
    return IngestService(cloud, clock, CommandQueue(cloud, clock), audit=AuditLog(cloud, "web", clock))


def engine_chain(n: int) -> list[dict[str, Any]]:
    """n audit events of the engine's chain, as the engine sends them."""
    db = Database("sqlite://")
    db.create_all()
    log = AuditLog(db, CHAIN, ManualClock(NOW))
    spec = SPECS_BY_TYPE["audit_event"]
    out = []
    for i in range(n):
        out.append(ev("audit_event", spec.payload(log.append("TEST", "engine", {"i": i, "x": 1.5}))))
    db.dispose()
    return out


def replica(cloud: Database) -> AuditReplicaRow:
    with cloud.session() as sess:
        row = sess.get(AuditReplicaRow, CHAIN)
        assert row is not None
        return row


class TestRows:
    def test_insert_then_newer_update(self, cloud: Database, service: IngestService) -> None:
        first = service.ingest(ENGINE, batch(ev("risk_state", risk(1000.0))))
        assert (first.accepted, first.duplicates, first.rejected) == (1, 0, [])
        service.ingest(ENGINE, batch(ev("risk_state", risk(1100.0))))
        with cloud.session() as sess:
            row = sess.get(RiskState, "acct")
            assert row is not None and row.hwm == 1100.0 and row.updated_at == NOW

    def test_resends_and_late_events_never_roll_back(self, cloud: Database, service: IngestService) -> None:
        old, new = ev("risk_state", risk(1.0)), ev("risk_state", risk(2.0))
        service.ingest(ENGINE, batch(new))
        late = service.ingest(ENGINE, batch(old, new))  # an older event and a resend
        assert (late.accepted, late.duplicates) == (0, 2)
        with cloud.session() as sess:
            assert sess.get(RiskState, "acct").hwm == 2.0  # type: ignore[union-attr]

    def test_integers_are_accepted_for_float_columns(self, cloud: Database, service: IngestService) -> None:
        assert service.ingest(ENGINE, batch(ev("risk_state", risk() | {"hwm": 1000}))).accepted == 1

    def test_natural_keys_replace_local_surrogate_ids(self, cloud: Database, service: IngestService) -> None:
        def check(detail: str) -> dict[str, Any]:
            return {
                "decision_id": "d1",
                "seq": 3,
                "name": "spread",
                "reason": "SPREAD_TOO_WIDE",
                "passed": False,
                "kind": "HARD",
                "value": {"points": 31},
                "threshold": 30,
                "detail": detail,
            }

        service.ingest(ENGINE, batch(ev("decision_check", check("first"))))
        service.ingest(ENGINE, batch(ev("decision_check", check("second"))))
        with cloud.session() as sess:
            rows = list(sess.execute(select(DecisionCheckRow)).scalars())
        assert len(rows) == 1 and rows[0].detail == "second" and rows[0].value == {"points": 31}

    def test_bad_events_are_rejected_one_by_one(self, cloud: Database, service: IngestService) -> None:
        good = ev("risk_state", risk())
        result = service.ingest(
            ENGINE,
            batch(
                ev("no_such_type", {}),
                ev("risk_state", risk() | {"hwm": "lots", "secret": "x"}),
                ev("risk_state", risk(), event_id="not-a-uuid"),
                {"type": "risk_state"},
                good,
            ),
        )
        assert codes(result) == ["UNKNOWN_TYPE", "INVALID_PAYLOAD", "INVALID_EVENT", "INVALID_EVENT"]
        assert result.accepted == 1
        detail = result.rejected[1].detail
        assert "hwm" in detail and "secret" in detail and "lots" not in detail  # values are never echoed
        assert result.rejected[3].event_id == ""

    def test_cloud_only_tables_cannot_be_written(self, service: IngestService) -> None:
        for name in ("user", "session", "engine_command", "outbox_event", "ingest_nonce"):
            assert codes(service.ingest(ENGINE, batch(ev(name, {})))) == ["UNKNOWN_TYPE"]


class TestEnvelope:
    @pytest.mark.parametrize(
        "doc",
        [
            [],
            {"schema": 2, "engine_id": ENGINE, "sent_at_utc": NOW.isoformat(), "events": []},
            {"schema": 1, "engine_id": ENGINE, "sent_at_utc": "2026-10-04T12:00:00", "events": []},
            {"schema": 1, "engine_id": ENGINE, "sent_at_utc": NOW.isoformat(), "events": [], "x": 1},
            batch(engine_id="eng-2"),
            batch(*[ev("risk_state", risk())] * (MAX_BATCH_EVENTS + 1)),
        ],
    )
    def test_unusable_batches_are_refused_whole(self, service: IngestService, doc: Any) -> None:
        with pytest.raises(BatchError):
            service.ingest(ENGINE, doc)

    def test_decode_body(self) -> None:
        doc = batch(ev("risk_state", risk()))
        assert decode_body(gzip.compress(json.dumps(doc).encode())) == doc
        bad = [
            json.dumps(doc).encode(),  # not gzip
            gzip.compress(b'{"x": NaN}'),
            gzip.compress(b"\xff\xfe"),
            gzip.compress(b"{}") + b"junk",
            gzip.compress(b"{}" * 1000)[:-8],  # truncated
        ]
        for body in bad:
            with pytest.raises(BatchError):
                decode_body(body)
        with pytest.raises(BatchError, match="exceeds"):
            decode_body(gzip.compress(b" " * 5000 + b"{}"), max_bytes=4096)  # a small body, large output


class TestAuditContinuity:
    def test_in_order_events_verify(self, cloud: Database, service: IngestService) -> None:
        events = engine_chain(5)
        assert service.ingest(ENGINE, batch(*events[:2])).accepted == 2
        service.ingest(ENGINE, batch(*events[2:]))
        status = replica(cloud)
        assert (status.status, status.verified_seq, status.max_seq) == ("OK", 5, 5)
        assert verify_chain(cloud, CHAIN).ok  # the cloud copy verifies with the same code as the engine

    def test_a_gap_heals_when_the_missing_event_arrives(
        self, cloud: Database, service: IngestService
    ) -> None:
        events = engine_chain(4)
        service.ingest(ENGINE, batch(events[0], events[2], events[3]))
        status = replica(cloud)
        assert (status.status, status.verified_seq, status.max_seq, status.detail) == (
            "GAP",
            1,
            4,
            "missing seq 2",
        )
        service.ingest(ENGINE, batch(events[1]))
        assert (replica(cloud).status, replica(cloud).verified_seq) == ("OK", 4)

    def test_resends_are_duplicates(self, cloud: Database, service: IngestService) -> None:
        events = engine_chain(2)
        service.ingest(ENGINE, batch(*events))
        again = service.ingest(ENGINE, batch(*events))
        assert (again.accepted, again.duplicates, again.rejected) == (0, 2, [])
        assert replica(cloud).status == "OK"

    def test_tampered_content_breaks_the_chain(self, cloud: Database, service: IngestService) -> None:
        events = engine_chain(2)
        events[1]["payload"]["payload"] = {"i": 1, "x": 9.9}
        result = service.ingest(ENGINE, batch(*events))
        assert codes(result) == ["HASH_MISMATCH"] and result.accepted == 1
        status = replica(cloud)
        assert (status.status, status.first_bad_seq) == ("BROKEN", 2)
        with cloud.session() as sess:  # alerted on the web audit chain
            alert = sess.execute(select(AuditEvent).where(AuditEvent.chain == "web")).scalar_one()
        assert alert.event_type == "AUDIT_REPLICA_BROKEN" and alert.payload["seq"] == 2

    def test_a_different_event_at_a_held_seq_breaks_the_chain(
        self, cloud: Database, service: IngestService
    ) -> None:
        service.ingest(ENGINE, batch(*engine_chain(1)))
        forked = engine_chain(1)[0]  # another valid event claiming seq 1
        assert codes(service.ingest(ENGINE, batch(forked))) == ["AUDIT_CONFLICT"]
        assert replica(cloud).status == "BROKEN"

    def test_a_broken_link_is_found_when_advancing(self, cloud: Database, service: IngestService) -> None:
        events = engine_chain(3)
        p = events[2]["payload"]
        p["prev_hash"] = "f" * 64  # self-consistent event, wrong link
        p["hash"] = compute_hash(
            p["prev_hash"],
            chain=CHAIN,
            seq=3,
            event_id=p["event_id"],
            ts_utc=datetime.fromisoformat(p["ts_utc"]),
            actor=p["actor"],
            event_type=p["event_type"],
            payload=p["payload"],
        )
        result = service.ingest(ENGINE, batch(*events))
        assert result.accepted == 3
        status = replica(cloud)
        assert (status.status, status.verified_seq, status.first_bad_seq) == ("BROKEN", 2, 3)

    def test_only_the_signing_engines_chain_is_accepted(
        self, cloud: Database, service: IngestService
    ) -> None:
        AuditLog(cloud, "web", ManualClock(NOW)).append("LOGIN", "owner", {})
        events = engine_chain(1)
        injected = json.loads(json.dumps(events[0]))
        injected["payload"]["chain"] = "web"
        result = service.ingest("eng-2", batch(*events, injected, engine_id="eng-2"))
        assert codes(result) == ["WRONG_CHAIN", "WRONG_CHAIN"]
        with cloud.session() as sess:
            assert sess.execute(select(func.count()).select_from(AuditEvent)).scalar_one() == 1
        assert verify_chain(cloud, "web").ok

    def test_audit_seq_must_be_positive(self, service: IngestService) -> None:
        event = engine_chain(1)[0]
        event["payload"]["seq"] = 0
        assert codes(service.ingest(ENGINE, batch(event))) == ["INVALID_PAYLOAD"]


class TestCommandResults:
    def result(self, command_id: str, outcome: str = "EXECUTED") -> dict[str, Any]:
        return ev(
            "command_result",
            {
                "command_id": command_id,
                "type": "RESYNC",
                "outcome": outcome,
                "reason": "",
                "detail": "resync queued (3 rows)",
                "at": (NOW + timedelta(seconds=1)).isoformat(),
            },
        )

    def test_a_result_closes_its_command_once(self, cloud: Database, service: IngestService) -> None:
        queued = service.commands.enqueue(ENGINE, "RESYNC", created_by="owner")
        event = self.result(queued["id"])
        assert service.ingest(ENGINE, batch(event)).accepted == 1
        again = service.ingest(ENGINE, batch(event, self.result(queued["id"], "FAILED")))
        assert again.duplicates == 1 and again.accepted == 1  # a newer event is applied, a resend is not
        with cloud.session() as sess:
            row = sess.get(EngineCommandRow, queued["id"])
            assert row is not None and row.status == "FAILED" and row.result["detail"].startswith("resync")

    def test_unknown_or_foreign_commands_are_rejected(self, service: IngestService) -> None:
        foreign = service.commands.enqueue("eng-2", "RESYNC", created_by="owner")
        result = service.ingest(ENGINE, batch(self.result("nope"), self.result(foreign["id"])))
        assert codes(result) == [RejectCode.UNKNOWN_COMMAND.value] * 2

    def test_invalid_results_are_rejected(self, service: IngestService) -> None:
        assert codes(service.ingest(ENGINE, batch(self.result("c", "QUEUED")))) == ["INVALID_PAYLOAD"]


def test_every_row_spec_round_trips(cloud: Database, service: IngestService) -> None:
    """Each replicated table accepts a payload produced by the engine-side serializer."""
    engine = Database("sqlite://")
    engine.create_all()
    events = []
    with engine.session() as sess:
        rows = sample_rows()
        sess.add_all(rows)
        sess.flush()
        for row in rows:
            spec = SPECS_BY_MODEL[type(row)]
            events.append(ev(spec.event_type, spec.payload(row)))
    result = service.ingest(ENGINE, batch(*events))
    assert result.rejected == [] and result.accepted == len(events)
    covered = {type(r) for r in rows} | {AuditEvent}
    assert covered == set(SPECS_BY_MODEL)  # a new replicated table needs a sample row in tests/sync_data.py
