"""Two engines with the same local keys replicate into one cloud without touching each other (TAA-709)."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import SyncConfig
from app.core.clock import ManualClock
from app.core.ids import new_id
from app.security.hmac_auth import Signer
from app.storage.audit import AuditLog, verify_chain
from app.storage.database import Database
from app.storage.models import AuditReplicaRow, BreakerStateRow, ReplicaVersionRow
from app.storage.models.base import LOCAL_ENGINE
from app.sync.client import CloudClient
from app.sync.events import REPLICAS, SPECS_BY_MODEL
from app.sync.outbox import INGEST_PATH, Outbox, OutboxSender
from app.sync.replication import install_replication
from app.web.engines import IssuedKey
from tests.sync_data import sample_rows
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, make_app


class Engine:
    """One engine machine: its own database, replication and sender."""

    def __init__(self, issued: IssuedKey, clock: ManualClock, http: TestClient) -> None:
        self.id = issued.engine_id
        self.secret = issued.secret
        self.db = Database("sqlite://")
        self.db.create_all()
        install_replication(self.db, clock, f"engine:{self.id}")
        self.audit = AuditLog(self.db, f"engine:{self.id}", clock)
        cloud = CloudClient("https://testserver", Signer(self.id, issued.secret.encode(), clock), http=http)
        self.sender = OutboxSender(
            Outbox(self.db, clock, SyncConfig(enabled=True)), cloud.post_gzip, self.id, clock
        )

    def flush(self) -> None:
        while self.sender.flush_once():
            pass
        assert self.sender.metrics().rejected_total == 0


@pytest.fixture
def rig(
    db: Database, clock: ManualClock, static_dir: Path
) -> Iterator[tuple[Database, Engine, Engine, TestClient]]:
    app = make_app(db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"})
    auth, registry = app.state.ctx.auth, app.state.ctx.engine.registry
    with TestClient(app, base_url="https://testserver") as http:
        engines = []
        for name, role in (("alice", "OWNER"), ("bob", "SUBSCRIBER")):
            owner = auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
            engines.append(Engine(registry.register(owner, f"{name} pc", actor=name), clock, http))
        yield db, engines[0], engines[1], http


def count(db: Database, model: Any, engine_id: str) -> int:
    with db.session() as sess:
        return int(
            sess.execute(
                select(func.count()).select_from(model).where(model.engine_id == engine_id)
            ).scalar_one()
        )


def test_colliding_local_keys_stay_separate(rig: tuple[Database, Engine, Engine, TestClient]) -> None:
    cloud, a, b, _ = rig
    for engine in (a, b):  # the very same rows on both machines: every key collides
        with engine.db.session() as sess:
            sess.add_all(sample_rows())
        for i in range(3):
            engine.audit.append("TEST", "engine", {"i": i})
        engine.flush()
    for spec in REPLICAS:
        expected = 3 if spec.model.__tablename__ == "audit_events" else 1
        assert count(cloud, spec.model, a.id) == expected, spec.event_type
        assert count(cloud, spec.model, b.id) == expected, spec.event_type
        if spec.event_type != "audit_event":  # the cloud's own web chain is LOCAL_ENGINE
            assert count(cloud, spec.model, LOCAL_ENGINE) == 0, spec.event_type
    for engine in (a, b):
        assert verify_chain(cloud, f"engine:{engine.id}").ok
        with cloud.session() as sess:
            status = sess.get(AuditReplicaRow, f"engine:{engine.id}")
            assert status is not None and status.status == "OK" and status.verified_seq == 3


def test_an_update_from_one_engine_leaves_the_other_alone(
    rig: tuple[Database, Engine, Engine, TestClient],
) -> None:
    cloud, a, b, _ = rig
    for engine in (a, b):
        with engine.db.session() as sess:
            sess.add(BreakerStateRow(name="DAILY_LOSS", scope_key="", state="CLOSED", reason=""))
        engine.flush()
    with a.db.session() as sess:
        row = sess.get(BreakerStateRow, (LOCAL_ENGINE, "DAILY_LOSS", ""))
        assert row is not None
        row.state, row.reason = "OPEN", "limit"
    a.flush()
    with cloud.session() as sess:
        mine = sess.get(BreakerStateRow, (a.id, "DAILY_LOSS", ""))
        theirs = sess.get(BreakerStateRow, (b.id, "DAILY_LOSS", ""))
        assert mine is not None and mine.state == "OPEN"
        assert theirs is not None and theirs.state == "CLOSED"
        versions = sess.execute(
            select(ReplicaVersionRow.engine_id).where(ReplicaVersionRow.type == "breaker")
        )
        assert sorted(versions.scalars()) == sorted([a.id, b.id])


def test_an_engine_cannot_write_into_another_engines_rows(
    rig: tuple[Database, Engine, Engine, TestClient],
) -> None:
    cloud, a, b, http = rig
    with b.db.session() as sess:
        sess.add(BreakerStateRow(name="DAILY_LOSS", scope_key="", state="CLOSED", reason=""))
    b.flush()
    clock = a.sender.clock
    spec = SPECS_BY_MODEL[BreakerStateRow]
    with b.db.session() as sess:  # a complete row, as B's engine sends it
        original = sess.get(BreakerStateRow, (LOCAL_ENGINE, "DAILY_LOSS", ""))
        forged = spec.payload(original) | {"state": "OPEN", "reason": "forged"}
    events = [
        {
            "event_id": new_id(),
            "type": "breaker",
            "occurred_at_utc": clock.now_utc().isoformat(),
            "payload": p,
        }
        for p in (forged | {"engine_id": b.id}, forged)
    ]
    other_chain = AuditLog(Database("sqlite://"), f"engine:{b.id}", clock)
    other_chain.db.create_all()
    audit_spec = next(s for s in REPLICAS if s.event_type == "audit_event")
    events.append(
        {
            "event_id": new_id(),
            "type": "audit_event",
            "occurred_at_utc": clock.now_utc().isoformat(),
            "payload": audit_spec.payload(other_chain.append("FORGED", "a", {})),
        }
    )
    doc = {"schema": 1, "engine_id": a.id, "sent_at_utc": clock.now_utc().isoformat(), "events": events}
    body = gzip.compress(json.dumps(doc).encode())
    headers = Signer(a.id, a.secret.encode(), clock).headers("POST", INGEST_PATH, body)
    resp = http.post(INGEST_PATH, content=body, headers=headers | {"Content-Encoding": "gzip"})
    assert resp.status_code == 200
    assert [r["code"] for r in resp.json()["rejected"]] == ["INVALID_PAYLOAD", "WRONG_CHAIN"]
    assert resp.json()["accepted"] == 1  # the plain one lands in A's own rows
    with cloud.session() as sess:
        theirs = sess.get(BreakerStateRow, (b.id, "DAILY_LOSS", ""))
        mine = sess.get(BreakerStateRow, (a.id, "DAILY_LOSS", ""))
        assert theirs is not None and theirs.state == "CLOSED" and theirs.reason == ""
        assert mine is not None and mine.reason == "forged"
    assert count(cloud, next(s.model for s in REPLICAS if s.event_type == "audit_event"), b.id) == 0


def test_the_snapshot_sends_only_this_engines_rows(rig: tuple[Database, Engine, Engine, TestClient]) -> None:
    _, a, _, _ = rig
    with a.db.session() as sess:
        sess.add(BreakerStateRow(name="DAILY_LOSS", scope_key="", state="CLOSED", reason=""))
        sess.add(BreakerStateRow(engine_id="stray", name="DAILY_LOSS", scope_key="", state="OPEN", reason=""))
    from app.sync.replication import Replicator

    rep = Replicator(a.sender.clock, f"engine:{a.id}")
    a.sender.outbox.purge_sent()
    assert rep.snapshot(a.db, types=["breaker"]) == 1
