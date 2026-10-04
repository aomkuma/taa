"""PostgreSQL checks: migrations, schema parity, rev. 4 backfill and ingest (marker ``postgres``).

The URL comes from ``TAA_POSTGRES_URL`` (environment, else the repository ``.env``) or a PostgreSQL
``DATABASE_URL`` (CI). Every test gets a throwaway database created with that role (it needs CREATEDB) and
dropped afterwards, so nothing else on the server is touched.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url

from app.config import REPO_ROOT
from app.core.clock import ManualClock
from app.core.ids import new_id
from app.storage.audit import AuditLog, verify_chain
from app.storage.database import Database, _normalize_url, upgrade_schema
from app.storage.models import AuditReplicaRow, Base, BreakerStateRow
from app.sync.command_queue import CommandQueue
from app.sync.events import SPECS_BY_MODEL, SPECS_BY_TYPE
from app.sync.ingest import IngestService
from tests.sync_data import sample_rows

pytestmark = pytest.mark.postgres

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _base_url() -> str:
    url = os.environ.get("TAA_POSTGRES_URL") or str(
        dotenv_values(REPO_ROOT / ".env").get("TAA_POSTGRES_URL") or ""
    )
    if not url:
        url = os.environ.get("DATABASE_URL", "")
    return url if url.startswith(("postgres://", "postgresql")) else ""


BASE_URL = _base_url()
needs_postgres = pytest.mark.skipif(
    not BASE_URL, reason="no PostgreSQL URL (TAA_POSTGRES_URL / DATABASE_URL)"
)


@pytest.fixture
def pg_url() -> Iterator[str]:
    base = make_url(_normalize_url(BASE_URL))
    name = f"taa_t_{secrets.token_hex(5)}"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield base.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def alembic(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(REPO_ROOT / "app/storage/migrations"))
    cfg.set_main_option("sqlalchemy.url", _normalize_url(url).replace("%", "%%"))
    return cfg


@needs_postgres
def test_audit_chain_on_postgres(pg_url: str) -> None:
    db = Database(pg_url)
    db.create_all()
    audit = AuditLog(db, "ci:postgres")
    for i in range(3):
        audit.append("ci.event", "ci", {"i": i, "nested": {"x": [1, 2]}, "f": 1.5})
    assert audit.verify().ok
    db.dispose()


@needs_postgres
def test_migrations_match_the_models(pg_url: str) -> None:
    upgrade_schema(pg_url)
    db = Database(pg_url)
    insp = inspect(db.engine)
    assert set(insp.get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)
    with db.engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    for name, table in Base.metadata.tables.items():
        assert insp.get_pk_constraint(name)["constrained_columns"] == [c.name for c in table.primary_key], (
            name
        )
    db.dispose()


@needs_postgres
def test_rev4_backfill_and_downgrade(pg_url: str) -> None:
    upgrade_schema(pg_url, "0019")
    db = Database(pg_url)
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, username, password_hash, role, disabled, totp_secret_enc, totp_last_step,"
                " locale, timezone, created_at, password_changed_at, totp_enrolled_at) VALUES ('u1', 'owner', 'x',"
                " 'OWNER', false, 'x', 0, 'th', 'Asia/Bangkok', now(), now(), now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO engines (engine_id, owner_user_id, label, secret_enc, status, created_at)"
                " VALUES ('eng-1', 'u1', 'imported', 'x', 'ACTIVE', now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO breaker_states (name, scope_key, state, latched, reason, opened_day_key,"
                " opened_week_key, trips_day_key, trips_today, healthy_count, metrics, updated_at)"
                " VALUES ('DAILY_LOSS', '', 'CLOSED', false, '', '', '', '', 0, 0, '{}', now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO audit_events (event_id, chain, seq, ts_utc, actor, event_type, payload, prev_hash, hash)"
                " VALUES ('e1', 'engine:eng-1', 1, now(), 'a', 'T', '{}', '0', 'h1'),"
                " ('e2', 'web', 1, now(), 'a', 'T', '{}', '0', 'h2')"
            )
        )
    db.dispose()
    upgrade_schema(pg_url)
    db = Database(pg_url)
    with db.engine.connect() as conn:
        assert conn.execute(text("SELECT engine_id FROM breaker_states")).scalar_one() == "eng-1"
        rows = conn.execute(text("SELECT chain, engine_id FROM audit_events ORDER BY event_id")).all()
        assert [tuple(r) for r in rows] == [("engine:eng-1", "eng-1"), ("web", "local")]
    assert inspect(db.engine).get_pk_constraint("breaker_states")["constrained_columns"] == [
        "engine_id",
        "name",
        "scope_key",
    ]
    db.dispose()
    command.downgrade(alembic(pg_url), "0019")
    command.upgrade(alembic(pg_url), "head")


def _event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"event_id": new_id(), "type": event_type, "occurred_at_utc": NOW.isoformat(), "payload": payload}


@needs_postgres
def test_two_engines_ingest_into_postgres(pg_url: str) -> None:
    upgrade_schema(pg_url)
    cloud = Database(pg_url)
    clock = ManualClock(NOW)
    service = IngestService(cloud, clock, CommandQueue(cloud, clock), audit=AuditLog(cloud, "web", clock))
    engine_db = Database("sqlite://")
    engine_db.create_all()
    events = []
    with engine_db.session() as sess:
        rows = sample_rows()
        sess.add_all(rows)
        sess.flush()
        for row in rows:
            spec = SPECS_BY_MODEL[type(row)]
            events.append((spec.event_type, spec.payload(row)))
    for engine_id in ("eng-a", "eng-b"):  # identical rows from two engines
        chain_db = Database("sqlite://")
        chain_db.create_all()
        log = AuditLog(chain_db, f"engine:{engine_id}", clock)
        audit = [
            _event(
                "audit_event", SPECS_BY_TYPE["audit_event"].payload(log.append("T", "e", {"x": 1.5, "i": i}))
            )
            for i in range(3)
        ]
        doc = {
            "schema": 1,
            "engine_id": engine_id,
            "sent_at_utc": NOW.isoformat(),
            "events": [_event(t, p) for t, p in events] + audit,
        }
        result = service.ingest(engine_id, doc)
        assert result.rejected == [] and result.accepted == len(events) + 3
        assert verify_chain(cloud, f"engine:{engine_id}").ok  # JSONB round trip keeps the hashes
    with cloud.session() as sess:
        states = sess.execute(select(BreakerStateRow.engine_id).order_by(BreakerStateRow.engine_id))
        assert list(states.scalars()) == ["eng-a", "eng-b"]
        status = sess.get(AuditReplicaRow, "engine:eng-b")
        assert status is not None and status.status == "OK"
    cloud.dispose()
