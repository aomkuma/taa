"""``GET /api/v1/engine/commands``: the engine's signed long poll over the cloud command queue (TAA-704)."""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.clock import ManualClock
from app.security.hmac_auth import Signer
from app.storage.database import Database
from app.storage.models import EngineCommandRow
from app.sync.client import CloudClient
from app.sync.command_queue import CommandQueue
from app.sync.commands import COMMANDS_PATH, CommandPoller
from app.web.routers import engine as engine_router
from tests.web.conftest import make_app, pair_engine
from tests.web.test_ingest_api import ENGINE, SECRET


@pytest.fixture(autouse=True)
def _short_polls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_router, "LONG_POLL_SECONDS", 0.4)
    monkeypatch.setattr(engine_router, "POLL_INTERVAL_SECONDS", 0.02)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """A file database: the long poll and the tests' own enqueues run on different threads, and the shared
    in-memory connection (StaticPool) would interleave their transactions."""
    database = Database(f"sqlite:///{(tmp_path / 'cloud.db').as_posix()}")
    database.create_all()
    yield database
    database.dispose()


@pytest.fixture
def paired(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[TestClient]:
    app = make_app(db, clock, static_dir)
    pair_engine(app)
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture
def commands(db: Database, clock: ManualClock) -> CommandQueue:
    return CommandQueue(db, clock)


def poll(
    client: TestClient, clock: ManualClock, target: str = COMMANDS_PATH, signed_target: str | None = None
) -> Any:
    headers = Signer(ENGINE, SECRET.encode(), clock).headers("GET", signed_target or target)
    return client.get(target, headers=headers)


def status_of(db: Database, command_id: str) -> str:
    with db.session() as sess:
        row = sess.get(EngineCommandRow, command_id)
        assert row is not None
        return row.status


def test_queued_commands_are_delivered_with_a_cursor(
    paired: TestClient, clock: ManualClock, db: Database, commands: CommandQueue
) -> None:
    a = commands.enqueue(ENGINE, "RESYNC", created_by="owner")
    b = commands.enqueue(ENGINE, "KILL_SWITCH_ACTIVATE", {"reason": "x"}, created_by="owner")
    commands.enqueue("eng-2", "RESYNC", created_by="owner")  # another engine's command
    resp = poll(paired, clock)
    assert resp.status_code == 200 and resp.headers["Cache-Control"] == "no-store"
    body = resp.json()
    assert [c["id"] for c in body["commands"]] == [a["id"], b["id"]] and body["cursor"] == b["id"]
    assert body["commands"][1]["params"] == {"reason": "x"} and "totp" not in body["commands"][0]
    assert status_of(db, a["id"]) == "DELIVERED"
    assert poll(paired, clock, f"{COMMANDS_PATH}?cursor={b['id']}").status_code == 204  # nothing after it
    again = poll(paired, clock).json()  # without a cursor, unanswered commands come again
    assert [c["id"] for c in again["commands"]] == [a["id"], b["id"]]


def test_an_empty_queue_waits_then_answers_204(paired: TestClient, clock: ManualClock) -> None:
    resp = poll(paired, clock)
    assert resp.status_code == 204 and resp.content == b""


def test_a_command_queued_during_the_wait_is_returned(
    paired: TestClient, clock: ManualClock, commands: CommandQueue
) -> None:
    queued: dict[str, Any] = {}
    timer = threading.Timer(0.1, lambda: queued.update(commands.enqueue(ENGINE, "RESYNC", created_by="u")))
    timer.start()
    resp = poll(paired, clock)
    timer.join()
    assert resp.status_code == 200 and resp.json()["commands"][0]["id"] == queued["id"]


def test_expired_and_answered_commands_are_not_delivered(
    paired: TestClient, clock: ManualClock, db: Database, commands: CommandQueue
) -> None:
    old = commands.enqueue(ENGINE, "RESYNC", created_by="u", lifetime=timedelta(seconds=10))
    done = commands.enqueue(ENGINE, "RESYNC", created_by="u")
    commands.record_result(ENGINE, {"command_id": done["id"], "outcome": "EXECUTED"})
    clock.advance(11)
    assert poll(paired, clock).status_code == 204
    assert status_of(db, old["id"]) == "EXPIRED"


def test_the_signature_covers_the_cursor(
    paired: TestClient, clock: ManualClock, commands: CommandQueue
) -> None:
    commands.enqueue(ENGINE, "RESYNC", created_by="u")
    resp = poll(paired, clock, f"{COMMANDS_PATH}?cursor=zzz", signed_target=COMMANDS_PATH)
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "signature_invalid"
    assert paired.get(COMMANDS_PATH).status_code == 401  # unsigned


def test_a_malformed_cursor_is_422(paired: TestClient, clock: ManualClock) -> None:
    assert poll(paired, clock, f"{COMMANDS_PATH}?cursor={'x' * 65}").status_code == 422


def test_an_unregistered_engine_is_refused(client: TestClient, clock: ManualClock) -> None:
    resp = poll(client, clock)
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "signature_invalid"


def test_the_engine_poller_receives_commands(
    paired: TestClient, clock: ManualClock, db: Database, commands: CommandQueue
) -> None:
    """The engine's own CommandPoller and CloudClient against the real route."""
    cloud = CloudClient("https://testserver", Signer(ENGINE, SECRET.encode(), clock), http=paired)
    inbox: queue.Queue[dict[str, Any]] = queue.Queue()
    poller = CommandPoller(cloud.get_json, inbox, poll_seconds=1)
    first = commands.enqueue(ENGINE, "RESYNC", created_by="owner")
    assert poller.poll_once() == 1 and inbox.get_nowait()["id"] == first["id"]
    assert poller.cursor == first["id"]
    assert poller.poll_once() == 0  # 204: nothing new, cursor kept
    second = commands.enqueue(ENGINE, "STRATEGY_DISABLE", {"name": "a"}, created_by="owner")
    assert poller.poll_once() == 1 and inbox.get_nowait()["id"] == second["id"]
    assert poller.failures == 0 and status_of(db, second["id"]) == "DELIVERED"
