"""The live stream: SSE format, topics, heartbeats, reconnect-safe cursors, ownership and limits (TAA-804)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.clock import ManualClock, ensure_utc
from app.storage.database import Database
from app.storage.models import SessionRow
from app.sync.stream import TOPICS, StreamEntry, StreamLog
from app.web.stream import EventStream, StreamSlots, StreamTiming, sse
from tests.web.conftest import (
    DEV_ENV,
    ENGINE_ID,
    PASSWORD,
    TOTP_SECRET,
    login,
    make_app,
    pair_engine,
)
from tests.web.test_ingest_api import batch, body_of, post, risk_event

Message = dict[str, Any]


def parse(text: str) -> list[Message]:
    """SSE blocks as dicts: ``event``/``id``/``retry``, ``data`` decoded from JSON, comments as ``comment``."""
    out: list[Message] = []
    for block in text.split("\n\n"):
        if not block:
            continue
        msg: Message = {}
        for line in block.split("\n"):
            name, _, value = line.partition(": ")
            if name == "":
                msg["comment"] = value
            elif name == "data":
                msg["data"] = json.loads(value)
            else:
                msg[name] = value
        out.append(msg)
    return out


def entry(key: str, topic: str = "positions", kind: str = "paper_position") -> StreamEntry:
    return StreamEntry(topic, kind, key, {"ticket": key})


def append(db: Database, clock: ManualClock, *entries: StreamEntry, engine_id: str = ENGINE_ID) -> None:
    log = StreamLog(db, clock)
    with db.session() as sess:
        log.append(sess, engine_id, entries)


@pytest.fixture
def app(db: Database, clock: ManualClock, static_dir: Path) -> FastAPI:
    app = make_app(db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"})
    pair_engine(app)
    app.state.ctx.streams.timing = StreamTiming(stream_seconds=0.0)  # one pass, then the server closes
    return app


@pytest.fixture
def client(app: FastAPI, clock: ManualClock) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver") as test_client:
        assert login(test_client, clock).status_code == 200
        yield test_client


def stream(client: TestClient, query: str = "", **headers: str) -> list[Message]:
    resp = client.get(f"/api/v1/engines/{ENGINE_ID}/stream{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return parse(resp.text)


class TestStreamApi:
    def test_a_fresh_stream_starts_at_the_head(
        self, client: TestClient, db: Database, clock: ManualClock
    ) -> None:
        append(db, clock, entry("1"), entry("2"))
        resp = client.get(f"/api/v1/engines/{ENGINE_ID}/stream")
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["cache-control"] == "no-store" and resp.headers["x-accel-buffering"] == "no"
        assert "content-security-policy" in resp.headers
        assert parse(resp.text) == [
            {"retry": "3000"},
            {"event": "ready", "id": "2", "data": {"cursor": 2, "resumed": False}},
        ]

    def test_a_cursor_resumes_after_it(self, client: TestClient, db: Database, clock: ManualClock) -> None:
        append(db, clock, entry("1"), entry("d1", "decisions", "decision"), entry("3"))
        messages = stream(client, "?cursor=1")
        assert messages[1] == {"event": "ready", "id": "1", "data": {"cursor": 1, "resumed": True}}
        assert [(m["event"], m["id"], m["data"]["key"]) for m in messages[2:]] == [
            ("decisions", "2", "d1"),
            ("positions", "3", "3"),
        ]
        assert messages[3]["data"] == {
            "seq": 3,
            "type": "paper_position",
            "key": "3",
            "at": clock.now_utc().isoformat(),
            "item": {"ticket": "3"},
        }

    def test_last_event_id_wins_over_the_query_cursor(
        self, client: TestClient, db: Database, clock: ManualClock
    ) -> None:
        append(db, clock, entry("1"), entry("2"), entry("3"))
        messages = stream(client, "?cursor=0", **{"Last-Event-ID": "2"})
        assert [m.get("id") for m in messages[1:]] == ["2", "3"]

    def test_topics_filter_the_events(self, client: TestClient, db: Database, clock: ManualClock) -> None:
        append(
            db, clock, entry("1"), entry("d1", "decisions", "decision"), entry("k", "status", "kill_switch")
        )
        messages = stream(client, "?cursor=0&topics=status,decisions")
        assert [m["event"] for m in messages[2:]] == ["decisions", "status"]

    @pytest.mark.parametrize("cursor", ["0", "9"])
    def test_an_unusable_cursor_resets_the_client(
        self, client: TestClient, db: Database, clock: ManualClock, cursor: str
    ) -> None:
        log = StreamLog(db, clock, keep=2)
        for key in "abcd":
            with db.session() as sess:
                log.append(sess, ENGINE_ID, [entry(key)])
        messages = stream(client, f"?cursor={cursor}")  # 0: pruned (kept 3-4); 9: ahead of the head
        assert messages[1:] == [{"event": "reset", "id": "4", "data": {"cursor": 4}}]

    @pytest.mark.parametrize(
        ("query", "headers"),
        [
            ("?topics=quotes,trades", {}),
            ("?topics=,", {}),
            ("?cursor=-1", {}),
            ("?cursor=1e3", {}),
            ("", {"Last-Event-ID": "abc"}),
        ],
    )
    def test_unusable_parameters_are_400(
        self, client: TestClient, query: str, headers: dict[str, str]
    ) -> None:
        resp = client.get(f"/api/v1/engines/{ENGINE_ID}/stream{query}", headers=headers)
        assert resp.status_code == 400 and resp.json()["error"]["code"] == "invalid_query"

    def test_only_the_owner_can_stream_an_engine(
        self, app: FastAPI, client: TestClient, clock: ManualClock
    ) -> None:
        ctx = app.state.ctx
        bob = ctx.auth.create_user("bob", PASSWORD, TOTP_SECRET, role="SUBSCRIBER")
        theirs = ctx.engine.registry.register(bob, "bob pc", actor="bob").engine_id
        resp = client.get(f"/api/v1/engines/{theirs}/stream")
        assert resp.status_code == 404 and resp.json()["error"]["code"] == "engine_not_found"
        client.cookies.clear()
        resp = client.get(f"/api/v1/engines/{ENGINE_ID}/stream")
        assert resp.status_code == 401 and resp.json()["error"]["code"] == "unauthenticated"

    def test_opening_a_stream_does_not_keep_the_session_alive(
        self, client: TestClient, db: Database, clock: ManualClock
    ) -> None:
        def last_seen() -> datetime:
            with db.session() as sess:
                [row] = sess.scalars(select(SessionRow)).all()
                return ensure_utc(row.last_seen_at)

        before = last_seen()
        clock.advance(5 * 60)
        stream(client)  # the browser reopens streams on its own: no activity
        assert last_seen() == before
        clock.advance(26 * 60)  # 31 min idle: the stream route sees the session gone
        resp = client.get(f"/api/v1/engines/{ENGINE_ID}/stream")
        assert resp.status_code == 401 and resp.json()["error"]["code"] == "unauthenticated"

    def test_a_real_request_still_refreshes_the_idle_timer(
        self, client: TestClient, db: Database, clock: ManualClock
    ) -> None:
        clock.advance(5 * 60)
        assert client.get(f"/api/v1/engines/{ENGINE_ID}/status").status_code == 200
        with db.session() as sess:
            [row] = sess.scalars(select(SessionRow)).all()
            assert ensure_utc(row.last_seen_at) == clock.now_utc()

    def test_open_streams_per_user_are_capped(self, app: FastAPI, client: TestClient) -> None:
        hub = app.state.ctx.streams
        hub.slots = StreamSlots(limit=1)
        stream(client)
        stream(client)  # the first stream's slot was released when it ended
        [owner] = [u for u in app.state.ctx.auth.list_users() if u.username == "owner"]
        assert hub.slots.acquire(owner.id) is not None  # another tab holds the only slot
        resp = client.get(f"/api/v1/engines/{ENGINE_ID}/stream")
        assert resp.status_code == 429 and resp.json()["error"]["code"] == "too_many_streams"


def test_a_signed_batch_reaches_the_stream(client: TestClient, clock: ManualClock) -> None:
    resp = post(client, clock, body_of(batch(clock, risk_event(clock, hwm=1234.0))), engine_id=ENGINE_ID)
    assert resp.status_code == 200 and resp.json()["accepted"] == 1
    [event] = stream(client, "?cursor=0")[2:]
    assert event["event"] == "status" and event["data"]["type"] == "risk_state"
    assert event["data"]["item"]["hwm"] == 1234.0 and "engine_id" not in event["data"]["item"]


class TestSlots:
    def test_a_lease_lapses_and_release_is_idempotent(self) -> None:
        now = [0.0]
        slots = StreamSlots(limit=2, lease_seconds=10.0, monotonic=lambda: now[0])
        a, b = slots.acquire("u"), slots.acquire("u")
        assert a is not None and b is not None and slots.acquire("u") is None
        slots.release("u", a)
        slots.release("u", a)
        c = slots.acquire("u")
        assert c is not None and slots.acquire("u") is None
        now[0] = 10.0  # both leases lapsed (a connection that never released its slot)
        assert slots.acquire("u") is not None


def run(stream_: EventStream) -> list[Message]:
    async def collect() -> list[str]:
        return [m async for m in stream_.messages()]

    return parse("".join(asyncio.run(collect())))


class Ticker:
    """A fake monotonic clock that moves on every sleep, running *on_sleep* hooks in order."""

    def __init__(self, *on_sleep: Callable[[], None]) -> None:
        self.now = 0.0
        self.hooks = list(on_sleep)

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        if self.hooks:
            self.hooks.pop(0)()


def event_stream(
    db: Database,
    clock: ManualClock,
    ticker: Ticker,
    *,
    cursor: int | None = 0,
    topics: tuple[str, ...] = TOPICS,
    alive: Callable[[], bool] = lambda: True,
    keep: int = 5000,
    **timing: float,
) -> EventStream:
    return EventStream(
        StreamLog(db, clock, keep=keep),
        ENGINE_ID,
        topics,
        cursor,
        alive=alive,
        timing=StreamTiming(
            **({"poll_seconds": 1.0, "heartbeat_seconds": 15.0, "stream_seconds": 60.0} | timing)
        ),
        monotonic=ticker.monotonic,
        sleep=ticker.sleep,
    )


class TestEventStream:
    def test_changes_arrive_while_the_stream_is_open(self, db: Database, clock: ManualClock) -> None:
        ticker = Ticker(
            lambda: append(db, clock, entry("a")), lambda: append(db, clock, entry("b"), entry("c"))
        )
        messages = run(event_stream(db, clock, ticker, stream_seconds=5.0))
        assert [(m.get("event"), m.get("id")) for m in messages[2:]] == [
            ("positions", "1"),
            ("positions", "2"),
            ("positions", "3"),
        ]

    def test_heartbeats_move_the_cursor_past_other_topics(self, db: Database, clock: ManualClock) -> None:
        ticker = Ticker(lambda: append(db, clock, entry("d1", "decisions", "decision"), entry("a")))
        messages = run(
            event_stream(db, clock, ticker, topics=("status",), heartbeat_seconds=2.0, stream_seconds=4.0)
        )
        assert messages[1]["event"] == "ready"
        pings = [m for m in messages if "comment" in m]
        assert pings == [{"comment": "ping", "id": "2"}]
        assert not any(m.get("event") in TOPICS for m in messages)

    def test_a_session_that_ended_ends_the_stream(self, db: Database, clock: ManualClock) -> None:
        alive = iter([True, False])
        messages = run(event_stream(db, clock, Ticker(), alive=lambda: next(alive), heartbeat_seconds=2.0))
        assert messages[-2] == {"comment": "ping", "id": "0"}
        assert messages[-1] == {"event": "end", "data": {"reason": "session_ended"}}

    def test_the_server_closes_after_the_stream_time(self, db: Database, clock: ManualClock) -> None:
        ticker = Ticker()
        messages = run(event_stream(db, clock, ticker, stream_seconds=30.0, heartbeat_seconds=15.0))
        assert ticker.now == 30.0 and [m.get("comment") for m in messages[2:]] == ["ping"]

    def test_a_client_that_falls_behind_is_reset(self, db: Database, clock: ManualClock) -> None:
        def burst() -> None:
            log = StreamLog(db, clock, keep=3)
            with db.session() as sess:
                log.append(sess, ENGINE_ID, [entry(str(i)) for i in range(10)])

        ticker = Ticker(lambda: append(db, clock, entry("a")), burst)
        messages = run(event_stream(db, clock, ticker, keep=3, page=1, stream_seconds=3.0))
        assert [(m.get("event"), m.get("id")) for m in messages[2:]] == [("positions", "1"), ("reset", "11")]

    def test_a_full_page_is_followed_without_waiting(self, db: Database, clock: ManualClock) -> None:
        append(db, clock, *(entry(str(i)) for i in range(5)))
        ticker = Ticker()
        messages = run(event_stream(db, clock, ticker, page=2, stream_seconds=1.0))
        assert [m["id"] for m in messages[2:]] == ["1", "2", "3", "4", "5"] and ticker.now == 1.0


def test_sse_messages_are_single_line_json() -> None:
    assert sse("positions", {"a": "x\ny"}, 7) == 'event: positions\nid: 7\ndata: {"a":"x\\ny"}\n\n'
    assert sse(None, {}) == "data: {}\n\n"
    with pytest.raises(ValueError, match="JSON"):
        sse("x", {"v": float("nan")})
