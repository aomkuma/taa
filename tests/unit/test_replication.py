"""Replicated event schemas and the engine-side replication hook (TAA-703)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.clock import ManualClock
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    Base,
    BreakerEventRow,
    DecisionCheckRow,
    OutboxEventRow,
    RiskState,
)
from app.sync import outbox as outbox_module
from app.sync.events import (
    REPLICAS,
    SPECS_BY_MODEL,
    SPECS_BY_TYPE,
    CommandResultPayload,
    WireBatch,
    json_safe,
)
from app.sync.outbox import Priority
from app.sync.replication import Replicator, install_replication

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
CHAIN = "engine:eng-1"


def outbox_rows(db: Database) -> list[OutboxEventRow]:
    with db.session() as sess:
        return list(sess.execute(select(OutboxEventRow).order_by(OutboxEventRow.event_id)).scalars())


def risk_state(**over: Any) -> RiskState:
    values: dict[str, Any] = {
        "account_key": "acct",
        "hwm": 1000.0,
        "cumulative_cash_flow": 0.0,
        "consecutive_losses": 0,
        "last_loss_at": None,
        "updated_at": NOW,
    }
    return RiskState(**(values | over))


@pytest.fixture
def rep(db: Database) -> Replicator:
    return install_replication(db, ManualClock(NOW), CHAIN)


class TestSchemas:
    def test_every_spec_builds_a_schema_from_its_columns(self) -> None:
        for spec in REPLICAS:
            fields = set(spec.schema.model_fields)
            assert fields == set(spec.column_names) and set(spec.key) <= fields
            assert not set(spec.exclude) & fields
        assert len(SPECS_BY_TYPE) == len(REPLICAS) == len(SPECS_BY_MODEL)

    def test_local_surrogate_ids_are_not_sent(self) -> None:
        assert SPECS_BY_MODEL[AuditEvent].key == ("chain", "seq")
        assert "id" not in SPECS_BY_MODEL[AuditEvent].column_names
        assert SPECS_BY_MODEL[DecisionCheckRow].key == ("decision_id", "seq")
        assert SPECS_BY_MODEL[BreakerEventRow].key == ("id",)  # no natural key: the engine's id is kept

    def test_payload_round_trips_through_validation(self) -> None:
        spec = SPECS_BY_MODEL[RiskState]
        payload = spec.payload(risk_state(last_loss_at=NOW - timedelta(hours=1)))
        assert payload["updated_at"] == NOW.isoformat() and payload["last_loss_at"].endswith("+00:00")
        values = spec.values(payload)
        assert values["last_loss_at"] == NOW - timedelta(hours=1) and values["last_loss_at"].tzinfo is UTC

    @pytest.mark.parametrize(
        ("change", "error"),
        [
            ({"extra": 1}, "extra_forbidden"),
            ({"hwm": "1000"}, "float_type"),
            ({"hwm": None}, "float_type"),
            ({"consecutive_losses": 1.5}, "int_type"),
            ({"consecutive_losses": 2**31}, "less_than"),
            ({"updated_at": "2026-10-04T12:00:00"}, "timezone_aware"),
            ({"account_key": "x" * 33}, "string_too_long"),
        ],
    )
    def test_payloads_are_strict(self, change: dict[str, Any], error: str) -> None:
        spec = SPECS_BY_MODEL[RiskState]
        payload = spec.payload(risk_state()) | change
        with pytest.raises(ValidationError) as exc:
            spec.values(payload)
        assert error in {e["type"] for e in exc.value.errors()}

    def test_every_column_is_required(self) -> None:
        spec = SPECS_BY_MODEL[RiskState]
        payload = spec.payload(risk_state())
        del payload["cumulative_cash_flow"]
        with pytest.raises(ValidationError):
            spec.values(payload)

    def test_non_finite_floats_travel_as_null(self) -> None:
        assert json_safe({"a": [math.nan, math.inf, 1.5], "t": NOW}) == {
            "a": [None, None, 1.5],
            "t": NOW.isoformat(),
        }

    def test_envelope_and_command_result(self) -> None:
        batch = WireBatch.model_validate(
            {
                "schema": outbox_module.SCHEMA_VERSION,
                "engine_id": "e",
                "sent_at_utc": NOW.isoformat(),
                "events": [],
            }
        )
        assert batch.schema_version == 1
        with pytest.raises(ValidationError):
            WireBatch.model_validate(
                {"schema": 2, "engine_id": "e", "sent_at_utc": NOW.isoformat(), "events": []}
            )
        with pytest.raises(ValidationError):
            CommandResultPayload.model_validate(
                {
                    "command_id": "c",
                    "type": "RESYNC",
                    "outcome": "QUEUED",
                    "reason": "",
                    "detail": "",
                    "at": NOW,
                }
            )

    def test_priorities(self) -> None:
        assert SPECS_BY_TYPE["audit_event"].priority is Priority.CRITICAL
        assert SPECS_BY_TYPE["decision"].priority is Priority.CRITICAL
        assert SPECS_BY_TYPE["risk_state"].priority is Priority.STATE


class TestHook:
    def test_inserts_and_changes_become_events_in_the_same_transaction(
        self, db: Database, rep: Replicator
    ) -> None:
        with db.session() as sess:
            sess.add(risk_state())
        with db.session() as sess:
            row = sess.get(RiskState, "acct")
            assert row is not None
            row.hwm = 1000.0  # unchanged value: no event
        assert len(outbox_rows(db)) == 1
        with db.session() as sess:
            row = sess.get(RiskState, "acct")
            assert row is not None
            row.hwm = 1100.0
        [event] = outbox_rows(db)  # the unsent predecessor was replaced
        assert event.type == "risk_state" and event.payload["hwm"] == 1100.0
        assert event.priority == Priority.STATE and event.coalesce_key == "risk_state:acct"
        assert rep.emitted == 2 and rep.errors == 0

    def test_a_rolled_back_change_leaves_no_event(self, db: Database, rep: Replicator) -> None:
        def write_then_fail() -> None:
            with db.session() as sess:
                sess.add(risk_state())
                sess.flush()
                raise RuntimeError("abort")

        with pytest.raises(RuntimeError):
            write_then_fail()
        assert outbox_rows(db) == []

    def test_sent_events_are_history_not_replaced(self, db: Database, rep: Replicator) -> None:
        with db.session() as sess:
            sess.add(risk_state())
        [first] = outbox_rows(db)
        with db.session() as sess:
            first_row = sess.get(OutboxEventRow, first.event_id)
            assert first_row is not None
            first_row.status = "SENT"
        with db.session() as sess:
            sess.get(RiskState, "acct").hwm = 3.0  # type: ignore[union-attr]
        events = outbox_rows(db)
        assert [e.status for e in events] == ["SENT", "PENDING"] and events[1].payload["hwm"] == 3.0
        assert events[0].payload["hwm"] == 1000.0

    def test_autoincrement_ids_and_defaults_are_captured(self, db: Database, rep: Replicator) -> None:
        with db.session() as sess:
            sess.add(
                BreakerEventRow(
                    ts_utc=NOW,
                    name="DAILY_LOSS",
                    action="TRIP",
                    severity="CRITICAL",
                    actor="engine",
                    reason="r",
                )
            )
        [event] = outbox_rows(db)
        assert (
            event.payload["id"] == 1 and event.payload["metrics"] == {} and event.payload["scope_key"] == ""
        )

    def test_audit_appends_replicate_only_the_engine_chain(self, db: Database, rep: Replicator) -> None:
        AuditLog(db, CHAIN, ManualClock(NOW)).append("ENGINE_START", "engine", {"n": 1})
        AuditLog(db, "engine:local", ManualClock(NOW)).append("OLD", "engine", {})
        [event] = outbox_rows(db)
        assert event.type == "audit_event" and event.payload["chain"] == CHAIN and event.payload["seq"] == 1
        assert "id" not in event.payload and event.coalesce_key == f"audit_event:{CHAIN}|1"

    def test_unreplicated_tables_are_ignored(self, db: Database, rep: Replicator) -> None:
        outbox = outbox_module.Outbox(db, ManualClock(NOW), outbox_module.SyncConfig(enabled=True))
        outbox.emit("command_result", {"command_id": "c"})
        assert [e.type for e in outbox_rows(db)] == ["command_result"]

    def test_a_failing_hook_never_blocks_the_write(
        self, db: Database, rep: Replicator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_args: Any) -> str:
            raise RuntimeError("outbox unavailable")

        monkeypatch.setattr("app.sync.replication.write_event", boom)
        with db.session() as sess:
            sess.add(risk_state())
        with db.session() as sess:
            assert sess.get(RiskState, "acct") is not None
        assert rep.errors == 1 and outbox_rows(db) == []

    def test_install_is_idempotent(self, db: Database, rep: Replicator) -> None:
        assert install_replication(db, ManualClock(NOW), CHAIN) is rep
        with db.session() as sess:
            sess.add(risk_state())
        assert len(outbox_rows(db)) == 1  # one listener, one event


class TestSnapshot:
    def test_snapshot_queues_every_row_including_older_ones(self, db: Database) -> None:
        audit = AuditLog(db, CHAIN, ManualClock(NOW))
        for i in range(3):
            audit.append("E", "engine", {"i": i})
        with db.session() as sess:
            sess.add(risk_state())
            sess.add_all(
                DecisionCheckRow(
                    decision_id="d1", seq=i, name="n", reason="OK", passed=True, kind="HARD", detail=""
                )
                for i in range(1200)
            )
        rep = install_replication(db, ManualClock(NOW), CHAIN)
        assert outbox_rows(db) == []  # written before replication was installed
        assert rep.snapshot(db) == 3 + 1 + 1200
        events = outbox_rows(db)
        assert sorted({e.type for e in events}) == ["audit_event", "decision_check", "risk_state"]
        assert [e.payload["seq"] for e in events if e.type == "audit_event"] == [1, 2, 3]
        assert rep.snapshot(db, types=["risk_state"]) == 1
        assert len(outbox_rows(db)) == 1204  # the re-sent row replaced its unsent predecessor


def test_model_registry_covers_only_mapped_tables() -> None:
    tables = set(Base.metadata.tables)
    assert all(spec.model.__tablename__ in tables for spec in REPLICAS)
