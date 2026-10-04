from __future__ import annotations

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, update

from app.risk.kill_switch import KillMode, KillSwitch
from app.storage.audit import AuditLog, verify_chain
from app.storage.database import Database, resolve_db_url, upgrade_schema
from app.storage.models import AuditEvent, Base, KillSwitchEvent


def test_audit_chain_appends_and_verifies(db: Database, clock) -> None:  # type: ignore[no-untyped-def]
    audit = AuditLog(db, "engine:test", clock)
    for i in range(5):
        audit.append("test.event", "tester", {"i": i})
    report = audit.verify()
    assert report.ok and report.events_checked == 5


def test_audit_detects_tampering(db: Database, clock) -> None:  # type: ignore[no-untyped-def]
    audit = AuditLog(db, "engine:test", clock)
    for i in range(4):
        audit.append("test.event", "tester", {"i": i})
    with db.session() as sess:
        sess.execute(update(AuditEvent).where(AuditEvent.seq == 2).values(payload={"i": 999}))
    report = verify_chain(db, "engine:test")
    assert not report.ok and report.first_bad_seq == 2


def test_audit_detects_deletion(db: Database, clock) -> None:  # type: ignore[no-untyped-def]
    audit = AuditLog(db, "c", clock)
    for i in range(3):
        audit.append("e", "a", {"i": i})
    with db.session() as sess:
        sess.query(AuditEvent).filter(AuditEvent.seq == 3).delete()
    assert not verify_chain(db, "c").ok


def test_chains_are_independent(db: Database, clock) -> None:  # type: ignore[no-untyped-def]
    AuditLog(db, "a", clock).append("e", "x")
    AuditLog(db, "b", clock).append("e", "x")
    assert verify_chain(db, "a").ok and verify_chain(db, "b").ok


def test_migrations_match_models(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    upgrade_schema(url)
    database = Database(url)
    insp = inspect(database.engine)
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    with database.engine.connect() as conn:  # columns, types, indexes, unique constraints
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    for name, table in Base.metadata.tables.items():  # autogenerate does not compare primary keys
        assert insp.get_pk_constraint(name)["constrained_columns"] == [c.name for c in table.primary_key], (
            name
        )
    database.dispose()


def test_resolve_db_url() -> None:
    assert resolve_db_url("sqlite:///data/x.db").endswith("/data/x.db")
    assert resolve_db_url("sqlite:///data/x.db") != "sqlite:///data/x.db"
    assert resolve_db_url("postgresql://u@h/taa") == "postgresql://u@h/taa"
    assert resolve_db_url("sqlite://") == "sqlite://"


class TestKillSwitch:
    def test_activate_and_release(self, tmp_path: Path, db: Database, clock) -> None:  # type: ignore[no-untyped-def]
        audit = AuditLog(db, "engine:t", clock)
        ks = KillSwitch(tmp_path / "KILL_SWITCH", db, audit, clock)
        assert not ks.is_active()
        state = ks.activate("drill", "ops", "cli")
        assert state.active and state.mode is KillMode.HALT and state.reason == "drill"
        ks.release("drill over", "ops", "cli")
        assert not ks.is_active()
        with db.session() as sess:
            assert [e.action for e in sess.query(KillSwitchEvent).order_by(KillSwitchEvent.id)] == [
                "ACTIVATE",
                "RELEASE",
            ]
        assert audit.verify().events_checked == 2

    def test_remote_release_forbidden(self, tmp_path: Path) -> None:
        ks = KillSwitch(tmp_path / "K")
        ks.activate("x", "ops", "remote")
        with pytest.raises(PermissionError):
            ks.release("no", "attacker", "remote")
        assert ks.is_active()

    def test_flatten_requires_permission(self, tmp_path: Path) -> None:
        with pytest.raises(PermissionError):
            KillSwitch(tmp_path / "K").activate("x", "ops", "cli", KillMode.FLATTEN)

    def test_garbage_file_still_active(self, tmp_path: Path) -> None:
        path = tmp_path / "K"
        path.write_text("not json {{", encoding="utf-8")
        state = KillSwitch(path).state()
        assert state.active and state.mode is KillMode.HALT

    def test_manual_empty_file_counts(self, tmp_path: Path) -> None:
        path = tmp_path / "K"
        path.touch()
        assert KillSwitch(path).state().active

    def test_reason_required(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            KillSwitch(tmp_path / "K").activate("  ", "ops", "cli")


def test_run_repository(db: Database, clock) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.storage.models import Run
    from app.storage.repositories import RunRepository

    repo = RunRepository(db, clock)
    repo.start("r1", "engine", "PAPER", "abc")
    repo.save_config_snapshot("abc", {"k": 1})
    repo.save_config_snapshot("abc", {"k": 1})  # idempotent
    clock.advance(60)
    repo.finish("r1", "STOPPED")
    latest = repo.latest("engine")
    assert latest is not None and latest.status == "STOPPED" and latest.ended_at is not None
    rows, total = repo.page(select(Run), limit=10)
    assert total == 1 and rows[0].run_id == "r1"
