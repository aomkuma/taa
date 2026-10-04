"""Server-sent events over an engine's change feed (PLAN §A14 "SSE"; TAA-804).

Wire format (``text/event-stream``), in order:

- ``retry: 3000``: the browser's reconnect delay
- the opening event, ``id`` = the cursor the stream continues from:
  - ``event: ready`` ``{"cursor", "resumed"}``: ``resumed`` is true when the client's cursor was usable, so
    nothing was missed; false on a fresh start (no cursor), so the client loads its pages through the REST API
  - ``event: reset`` ``{"cursor"}``: the cursor is older than the retained events (or ahead of them): the
    client refetches its pages, then continues from the new cursor
- one event per change, ``event: <topic>``, ``id: <seq>``, data ``{"seq", "type", "key", "at", "item"}``
  (``item`` is the row as the read APIs serialize it); a later ``reset`` can follow when the client falls
  behind the retained events
- every ``HEARTBEAT_SECONDS``, a comment ``: ping`` with ``id: <cursor>``: an ``id`` without data moves the
  browser's last event id without dispatching an event, so a stream filtered to quiet topics still resumes
  near the head
- ``event: end`` ``{"reason": "session_ended"}`` when the web session expired or was revoked (the client stops
  reconnecting and its next API call signs it out)

The server closes the stream after ``STREAM_SECONDS`` (Railway caps a request at about 15 minutes); the
browser's EventSource reconnects with ``Last-Event-ID`` and the stream resumes after it. A stream re-checks
the session at every heartbeat without refreshing its idle timer, so an unattended tab cannot keep a session
alive.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from itertools import count
from threading import Lock
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.sync.stream import StreamLog

RETRY_MS = 3000
POLL_SECONDS = 1.0
HEARTBEAT_SECONDS = 15.0
STREAM_SECONDS = 600.0
PAGE = 200
MAX_STREAMS_PER_USER = 4


def sse(event: str | None, data: Any, event_id: int | None = None) -> str:
    """One SSE message; ``json.dumps`` never emits a newline, so ``data`` stays on one line."""
    lines = [f"event: {event}"] if event else []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {json.dumps(data, separators=(',', ':'), allow_nan=False)}")
    return "\n".join(lines) + "\n\n"


@dataclass
class StreamTiming:
    poll_seconds: float = POLL_SECONDS
    heartbeat_seconds: float = HEARTBEAT_SECONDS
    stream_seconds: float = STREAM_SECONDS
    page: int = PAGE


@dataclass
class EventStream:
    """The messages of one stream connection. *alive* re-checks the web session (blocking: it runs in the
    thread pool); *monotonic* and *sleep* are injectable for tests."""

    log: StreamLog
    engine_id: str
    topics: Sequence[str]
    cursor: int | None
    alive: Callable[[], bool]
    timing: StreamTiming = field(default_factory=StreamTiming)
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

    async def messages(self) -> AsyncIterator[str]:
        yield f"retry: {RETRY_MS}\n\n"
        bounds = await run_in_threadpool(self.log.bounds, self.engine_id)
        cursor = self.cursor
        if cursor is None:
            cursor = bounds.head
            yield sse("ready", {"cursor": cursor, "resumed": False}, cursor)
        elif bounds.resumable(cursor):
            yield sse("ready", {"cursor": cursor, "resumed": True}, cursor)
        else:
            cursor = bounds.head
            yield sse("reset", {"cursor": cursor}, cursor)
        start = self.monotonic()
        next_beat = start + self.timing.heartbeat_seconds
        while True:
            events, nxt, bounds = await run_in_threadpool(
                self.log.read, self.engine_id, cursor, self.topics, self.timing.page
            )
            if bounds.resumable(cursor):
                for e in events:
                    yield sse(e.topic, e.to_dict(), e.seq)
                cursor = nxt
            else:  # pruned while this client lagged behind
                events, cursor = [], bounds.head
                yield sse("reset", {"cursor": cursor}, cursor)
            now = self.monotonic()
            if now - start >= self.timing.stream_seconds:
                return
            if now >= next_beat:
                if not await run_in_threadpool(self.alive):
                    yield sse("end", {"reason": "session_ended"})
                    return
                yield f": ping\nid: {cursor}\n\n"
                next_beat = now + self.timing.heartbeat_seconds
            if len(events) < self.timing.page:  # a full page means more is waiting
                await self.sleep(self.timing.poll_seconds)


class StreamSlots:
    """Caps the open streams per user in this process. A slot is a lease that lapses after the longest stream
    could have lasted, so a connection that ended without releasing its slot cannot lock the user out."""

    def __init__(
        self,
        limit: int = MAX_STREAMS_PER_USER,
        lease_seconds: float = STREAM_SECONDS + 60.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.lease_seconds = lease_seconds
        self.monotonic = monotonic
        self._held: dict[str, dict[int, float]] = {}
        self._ids = count(1)
        self._lock = Lock()

    def acquire(self, user_id: str) -> int | None:
        """A slot id, or None when the user already has ``limit`` open streams."""
        now = self.monotonic()
        with self._lock:
            held = {k: t for k, t in self._held.get(user_id, {}).items() if now - t < self.lease_seconds}
            if len(held) >= self.limit:
                self._held[user_id] = held
                return None
            slot = next(self._ids)
            held[slot] = now
            self._held[user_id] = held
            return slot

    def release(self, user_id: str, slot: int) -> None:
        with self._lock:
            held = self._held.get(user_id)
            if held is not None:
                held.pop(slot, None)
                if not held:
                    del self._held[user_id]


@dataclass
class StreamHub:
    """Per-process stream state: the slot caps and the timing (tests shorten it)."""

    slots: StreamSlots = field(default_factory=StreamSlots)
    timing: StreamTiming = field(default_factory=StreamTiming)
