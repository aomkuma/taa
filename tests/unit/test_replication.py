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
    BreakerStateRow,
    DecisionCheckRow,
    OutboxEventRow,
    RiskState,
    ShadowTradeRow,
)
from app.storage.models.base import LOCAL_ENGINE
from app.sync import outbox as outbox_module
from app.sync.events import (
    REPLICAS,
    SNAPSHOT_THROTTLE_SECONDS,
    SPECS_BY_MODEL,
    SPECS_BY_TYPE,
    CommandResultPayload,
    ReplicaSpec,
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
            assert fields == set(spec.column_names) and set(spec.key[1:]) <= fields
            assert not set(spec.exclude) & fields and "engine_id" not in fields  # the cloud sets it
            assert spec.key[0] == "engine_id"
        assert len(SPECS_BY_TYPE) == len(REPLICAS) == len(SPECS_BY_MODEL)

    def test_local_surrogate_ids_are_not_sent(self) -> None:
        assert SPECS_BY_MODEL[AuditEvent].key == ("engine_id", "chain", "seq")
        assert "id" not in SPECS_BY_MODEL[AuditEvent].column_names
        assert SPECS_BY_MODEL[DecisionCheckRow].key == ("engine_id", "decision_id", "seq")
        # no natural key: the engine's id travels as source_id
        assert SPECS_BY_MODEL[BreakerEventRow].key == ("engine_id", "source_id")
        assert SPECS_BY_MODEL[BreakerStateRow].key == ("engine_id", "name", "scope_key")

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
            row = sess.get(RiskState, (LOCAL_ENGINE, "acct"))
            assert row is not None
            row.hwm = 1000.0  # unchanged value: no event
        assert len(outbox_rows(db)) == 1
        with db.session() as sess:
            row = sess.get(RiskState, (LOCAL_ENGINE, "acct"))
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
            sess.get(RiskState, (LOCAL_ENGINE, "acct")).hwm = 3.0  # type: ignore[union-attr]
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
            event.payload["source_id"] == 1 and "id" not in event.payload and "engine_id" not in event.payload
        )
        assert event.payload["metrics"] == {} and event.payload["scope_key"] == ""

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
            assert sess.get(RiskState, (LOCAL_ENGINE, "acct")) is not None
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


class TestVolumeControls:
    """TAA-707: quiet columns and throttled rows."""

    def test_quiet_columns_alone_emit_nothing(self, db: Database) -> None:
        from tests.sync_data import sample_rows

        clock = ManualClock(NOW)
        install_replication(db, clock, CHAIN)
        [shadow] = [r for r in sample_rows() if type(r).__name__ == "ShadowTradeRow"]
        with db.session() as sess:
            sess.add(shadow)
        assert [e.type for e in outbox_rows(db)] == ["shadow_trade"]
        with db.session() as sess:
            row = sess.get(ShadowTradeRow, (LOCAL_ENGINE, "k1:PLAN"))
            assert row is not None
            row.cursor = NOW + timedelta(minutes=5)  # the tracker's M1 cursor
            row.updated_at = NOW + timedelta(minutes=5)
        [event] = outbox_rows(db)
        assert event.payload["cursor"] == shadow.cursor.isoformat()  # unchanged event
        with db.session() as sess:
            row = sess.get(ShadowTradeRow, (LOCAL_ENGINE, "k1:PLAN"))
            assert row is not None
            row.mfe = 0.002
        [event] = outbox_rows(db)  # a real change carries the quiet columns along
        assert event.payload["mfe"] == 0.002
        assert event.payload["cursor"] == (NOW + timedelta(minutes=5)).isoformat()

    def test_throttled_rows_update_at_most_every_interval(self, db: Database) -> None:
        from tests.sync_data import sample_rows

        clock = ManualClock(NOW)
        install_replication(db, clock, CHAIN)
        [snap] = [r for r in sample_rows() if type(r).__name__ == "SuitabilitySnapshotRow"]
        with db.session() as sess:
            sess.add(snap)

        def rewrite(score: float) -> None:
            with db.session() as sess:
                row = sess.merge(snap)
                row.now_score = score

        def sent_scores() -> list[float]:
            events = outbox_rows(db)
            for e in events:  # mark everything sent, so coalescing does not hide what was emitted
                with db.session() as sess:
                    sess.get(OutboxEventRow, e.event_id).status = "SENT"  # type: ignore[union-attr]
            return [e.payload["now_score"] for e in events if e.status == "PENDING"]

        assert sent_scores() == [70.0]  # the insert always goes out
        clock.advance(60)
        rewrite(71.0)
        assert sent_scores() == []  # within the interval
        clock.advance(SNAPSHOT_THROTTLE_SECONDS)
        rewrite(72.0)
        assert sent_scores() == [72.0]
        [event] = [e for e in outbox_rows(db) if e.payload["now_score"] == 72.0]
        assert event.priority == Priority.TELEMETRY and "id" not in event.payload

    def test_advisory_specs(self) -> None:
        assert SPECS_BY_TYPE["opportunity"].priority is Priority.CRITICAL
        assert SPECS_BY_TYPE["suitability_snapshot"].key == ("engine_id", "server", "symbol", "hour")
        assert SPECS_BY_TYPE["shadow_trade"].quiet == ("cursor", "updated_at")
        assert {"symbol_catalog", "calibration_version", "evidence_model_version"} <= set(SPECS_BY_TYPE)

    def test_quiet_columns_must_be_replicated_non_key_columns(self) -> None:
        with pytest.raises(TypeError, match="quiet"):
            ReplicaSpec("bad", RiskState, quiet=("account_key",))


def test_throttle_bookkeeping_forgets_old_rows(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.sync.replication.THROTTLE_KEYS_MAX", 3)
    clock = ManualClock(NOW)
    rep = install_replication(db, clock, CHAIN)
    spec = SPECS_BY_TYPE["suitability_snapshot"]
    for i in range(3):
        assert rep._due(spec, {"server": "s", "symbol": f"S{i}", "hour": NOW.isoformat()}, 0.0, False)
    clock_now = SNAPSHOT_THROTTLE_SECONDS + 1
    assert rep._due(spec, {"server": "s", "symbol": "S9", "hour": NOW.isoformat()}, clock_now, False)
    assert list(rep._last_update) == [f"suitability_snapshot:s|S9|{NOW.isoformat()}"]
