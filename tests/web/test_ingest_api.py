"""``POST /api/v1/ingest/batch``: HMAC authentication, body handling and the engine → cloud round trip (TAA-703)."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.config import SyncConfig, WebSettings
from app.core.clock import ManualClock
from app.core.ids import new_id
from app.security.hmac_auth import Signer
from app.storage.audit import AuditLog, verify_chain
from app.storage.database import Database
from app.storage.models import AuditReplicaRow, BreakerStateRow, OutboxEventRow, RiskState
from app.sync.client import CloudClient
from app.sync.outbox import INGEST_PATH, Outbox, OutboxSender
from app.sync.replication import install_replication
from tests.web.conftest import DEV_ENV, ENGINE_ID, ENGINE_SECRET, make_app, pair_engine

ENGINE = ENGINE_ID
SECRET = ENGINE_SECRET
OLD_SECRET = "engine-hmac-secret-previous-0123456789ab"
PAIRED = DEV_ENV | {"ENGINE_ID": ENGINE, "ENGINE_HMAC_SECRET": SECRET}


def body_of(doc: Any) -> bytes:
    return gzip.compress(json.dumps(doc).encode())


def batch(clock: ManualClock, *events: dict[str, Any], engine_id: str = ENGINE) -> dict[str, Any]:
    return {
        "schema": 1,
        "engine_id": engine_id,
        "sent_at_utc": clock.now_utc().isoformat(),
        "events": list(events),
    }


def risk_event(clock: ManualClock, hwm: float = 1000.0) -> dict[str, Any]:
    now = clock.now_utc().isoformat()
    return {
        "event_id": new_id(),
        "type": "risk_state",
        "occurred_at_utc": now,
        "payload": {
            "account_key": "acct",
            "hwm": hwm,
            "cumulative_cash_flow": 0.0,
            "consecutive_losses": 0,
            "last_loss_at": None,
            "updated_at": now,
        },
    }


def post(
    client: TestClient,
    clock: ManualClock,
    body: bytes,
    *,
    secret: str = SECRET,
    engine_id: str = ENGINE,
    gzip_header: bool = True,
) -> Any:
    headers = Signer(engine_id, secret.encode(), clock).headers("POST", INGEST_PATH, body)
    if gzip_header:
        headers["Content-Encoding"] = "gzip"
    return client.post(INGEST_PATH, content=body, headers=headers | {"Content-Type": "application/json"})


@pytest.fixture
def paired(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[TestClient]:
    app = make_app(db, clock, static_dir)
    pair_engine(app, ENGINE, SECRET, OLD_SECRET)
    with TestClient(app, base_url="https://testserver") as client:
        yield client


class TestAuthentication:
    def test_a_signed_batch_is_stored(self, paired: TestClient, clock: ManualClock, db: Database) -> None:
        resp = post(paired, clock, body_of(batch(clock, risk_event(clock))))
        assert resp.status_code == 200
        assert resp.json() == {"accepted": 1, "duplicates": 0, "rejected": []}
        assert resp.headers["Cache-Control"] == "no-store"
        with db.session() as sess:
            assert sess.get(RiskState, "acct") is not None
        info = paired.app.state.ctx.engine.registry.get(ENGINE)  # type: ignore[attr-defined]
        assert info.first_seen_at == clock.now_utc() == info.last_seen_at  # the PWA shows "connected"

    def test_the_previous_secret_works_during_a_rotation(
        self, paired: TestClient, clock: ManualClock
    ) -> None:
        assert post(paired, clock, body_of(batch(clock)), secret=OLD_SECRET).status_code == 200

    def test_forged_replayed_and_stale_requests_are_refused(
        self, paired: TestClient, clock: ManualClock, db: Database
    ) -> None:
        body = body_of(batch(clock, risk_event(clock)))
        cases = []
        cases.append(paired.post(INGEST_PATH, content=body, headers={"Content-Encoding": "gzip"}))  # unsigned
        cases.append(post(paired, clock, body, secret="x" * 40))  # wrong secret
        cases.append(post(paired, clock, body, engine_id="eng-2"))  # unknown engine
        headers = Signer(ENGINE, SECRET.encode(), clock).headers("POST", INGEST_PATH, body)
        headers["Content-Encoding"] = "gzip"
        tampered = body_of(batch(clock, risk_event(clock, hwm=1.0)))
        cases.append(paired.post(INGEST_PATH, content=tampered, headers=headers))  # body swapped
        assert paired.post(INGEST_PATH, content=body, headers=headers).status_code == 200
        cases.append(paired.post(INGEST_PATH, content=body, headers=headers))  # replayed nonce
        stale = Signer(ENGINE, SECRET.encode(), clock).headers("POST", INGEST_PATH, body)
        clock.advance(301)
        cases.append(paired.post(INGEST_PATH, content=body, headers=stale | {"Content-Encoding": "gzip"}))
        for resp in cases:
            assert resp.status_code == 401
            assert resp.json()["error"]["code"] == "signature_invalid"
        with db.session() as sess:
            assert sess.get(RiskState, "acct").hwm == 1000.0  # type: ignore[union-attr]

    def test_the_signature_covers_the_query_string(self, paired: TestClient, clock: ManualClock) -> None:
        body = body_of(batch(clock))
        headers = Signer(ENGINE, SECRET.encode(), clock).headers("POST", INGEST_PATH, body)
        resp = paired.post(INGEST_PATH + "?x=1", content=body, headers=headers | {"Content-Encoding": "gzip"})
        assert resp.status_code == 401

    def test_an_unregistered_engine_is_refused(self, client: TestClient, clock: ManualClock) -> None:
        resp = post(client, clock, body_of(batch(clock)))
        assert resp.status_code == 401 and resp.json()["error"]["code"] == "signature_invalid"

    def test_a_web_session_is_not_enough(self, paired: TestClient) -> None:
        assert paired.post(INGEST_PATH, content=b"{}").status_code == 401


class TestBodies:
    def test_the_body_must_be_gzip(self, paired: TestClient, clock: ManualClock) -> None:
        resp = post(paired, clock, json.dumps(batch(clock)).encode(), gzip_header=False)
        assert resp.status_code == 415
        resp = post(paired, clock, b"not gzip at all")
        assert resp.status_code == 400 and resp.json()["error"]["code"] == "invalid_batch"

    def test_an_invalid_envelope_is_422(self, paired: TestClient, clock: ManualClock) -> None:
        resp = post(paired, clock, body_of(batch(clock, engine_id="eng-2")))
        assert resp.status_code == 422 and resp.json()["error"]["code"] == "invalid_batch"
        assert "different engine" in resp.json()["error"]["message"]

    def test_bad_events_come_back_as_rejected(self, paired: TestClient, clock: ManualClock) -> None:
        bad = risk_event(clock) | {"type": "users"}
        resp = post(paired, clock, body_of(batch(clock, bad, risk_event(clock))))
        assert resp.status_code == 200 and resp.json()["accepted"] == 1
        assert resp.json()["rejected"] == [
            {"event_id": bad["event_id"], "code": "UNKNOWN_TYPE", "detail": "users"}
        ]

    def test_ingest_takes_larger_bodies_than_other_routes(
        self, paired: TestClient, clock: ManualClock
    ) -> None:
        big = gzip.compress(json.dumps(batch(clock)).encode() + b" " * 200_000, compresslevel=0)
        assert len(big) > 64 * 1024
        assert post(paired, clock, big).status_code == 200
        huge = b"\0" * (8 * 1024 * 1024 + 1)
        resp = post(paired, clock, huge)
        assert resp.status_code == 413 and resp.json()["error"]["code"] == "request_too_large"
        assert paired.post("/api/v1/auth/login", content=b"x" * (64 * 1024 + 1)).status_code == 413


def test_engine_rows_reach_the_cloud(tmp_path: Path, clock: ManualClock, static_dir: Path) -> None:
    """The whole path: ORM writes on the engine → outbox → signed gzip POST → cloud tables."""
    engine_db = Database(f"sqlite:///{(tmp_path / 'engine.db').as_posix()}")
    engine_db.create_all()
    cloud_db = Database(f"sqlite:///{(tmp_path / 'cloud.db').as_posix()}")
    cloud_db.create_all()
    chain = f"engine:{ENGINE}"
    replicator = install_replication(engine_db, clock, chain)
    audit = AuditLog(engine_db, chain, clock)
    for i in range(3):
        audit.append("ENGINE_START", "engine", {"i": i})
    with engine_db.session() as sess:
        sess.add(
            BreakerStateRow(
                name="DAILY_LOSS", scope_key="", state="OPEN", reason="limit", updated_at=clock.now_utc()
            )
        )
    outbox = Outbox(engine_db, clock, SyncConfig(enabled=True))
    outbox.emit("not_a_cloud_type", {"x": 1})

    app = make_app(cloud_db, clock, static_dir)
    pair_engine(app, ENGINE, SECRET)
    with TestClient(app, base_url="https://testserver") as http:
        cloud = CloudClient("https://testserver", Signer(ENGINE, SECRET.encode(), clock), http=http)
        sender = OutboxSender(outbox, cloud.post_gzip, ENGINE, clock)
        assert sender.flush_once() == 5
        with engine_db.session() as sess:
            state = sess.get(BreakerStateRow, ("DAILY_LOSS", ""))
            assert state is not None
            state.state = "CLOSED"
        assert sender.flush_once() == 1

    assert replicator.errors == 0
    m = sender.metrics()
    assert (m.sent_total, m.rejected_total, m.dead, m.pending_total) == (5, 1, 1, 0)
    with engine_db.session() as sess:
        dead = sess.execute(select(OutboxEventRow).where(OutboxEventRow.status == "DEAD")).scalar_one()
        assert dead.type == "not_a_cloud_type" and "UNKNOWN_TYPE" in dead.last_error
    with cloud_db.session() as sess:
        state = sess.get(BreakerStateRow, ("DAILY_LOSS", ""))
        assert state is not None and state.state == "CLOSED" and state.reason == "limit"
        status = sess.get(AuditReplicaRow, chain)
        assert status is not None and (status.status, status.verified_seq) == ("OK", 3)
    assert verify_chain(cloud_db, chain).ok
    engine_db.dispose()
    cloud_db.dispose()


class TestSettings:
    def test_engine_id_and_secret_come_together(self) -> None:
        with pytest.raises(ValidationError, match="set together"):
            WebSettings.model_validate(DEV_ENV | {"ENGINE_ID": ENGINE})
        with pytest.raises(ValidationError, match="set together"):
            WebSettings.model_validate(DEV_ENV | {"ENGINE_HMAC_SECRET": SECRET})
        with pytest.raises(ValidationError, match="needs ENGINE_HMAC_SECRET"):
            WebSettings.model_validate(DEV_ENV | {"ENGINE_HMAC_SECRET_PREVIOUS": OLD_SECRET})

    def test_secrets_must_be_long(self) -> None:
        with pytest.raises(ValidationError, match="at least 32"):
            WebSettings.model_validate(DEV_ENV | {"ENGINE_ID": ENGINE, "ENGINE_HMAC_SECRET": "short"})
        with pytest.raises(ValidationError, match="at least 32"):
            WebSettings.model_validate(PAIRED | {"ENGINE_HMAC_SECRET_PREVIOUS": "short"})

    def test_unpaired_is_the_default(self) -> None:
        settings = WebSettings.model_validate(DEV_ENV)
        assert settings.ENGINE_ID is None and settings.ENGINE_HMAC_SECRET is None
