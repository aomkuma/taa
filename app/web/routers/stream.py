"""``GET /api/v1/engines/{engine_id}/stream``: the PWA's live stream (PLAN §A14 "SSE"; TAA-804).

Server-sent events over the engine's change feed; the message format is in :mod:`app.web.stream`.

- ``topics``: comma-separated subset of ``status, quotes, positions, notifications, decisions`` (default: all)
- cursor: the ``Last-Event-ID`` header (sent by the browser when it reconnects) wins over ``?cursor=`` (for a
  new EventSource that resumes a cursor it kept); both are the decimal ``seq`` of an earlier event

Errors before the stream starts: 401 ``unauthenticated``, 404 ``engine_not_found`` (not the user's engine),
400 ``invalid_query`` (unknown topic, malformed cursor), 429 ``too_many_streams`` (open streams per user).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.sync.stream import TOPICS, StreamLog
from app.web.deps import Context, CurrentSession, OwnedEngine
from app.web.errors import ApiProblem
from app.web.stream import EventStream

router = APIRouter(prefix="/engines/{engine_id}", tags=["stream"])

CURSOR_RE = re.compile(r"\d{1,18}")


def parse_topics(raw: str | None) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return TOPICS
    chosen = tuple(dict.fromkeys(t.strip() for t in raw.split(",") if t.strip()))
    unknown = [t for t in chosen if t not in TOPICS]
    if unknown or not chosen:
        raise ApiProblem(400, "invalid_query", "topics: any of " + ", ".join(TOPICS))
    return chosen


def parse_cursor(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    if not CURSOR_RE.fullmatch(raw):
        raise ApiProblem(400, "invalid_query", "cursor: the id of an earlier stream event")
    return int(raw)


@router.get("/stream", response_model=None)
async def stream(
    request: Request,
    engine: OwnedEngine,
    session: CurrentSession,
    ctx: Context,
    topics: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=32)] = None,
) -> StreamingResponse:
    chosen = parse_topics(topics)
    start = parse_cursor(request.headers.get("last-event-id") or cursor)
    slots = ctx.streams.slots
    slot = slots.acquire(session.user_id)
    if slot is None:
        raise ApiProblem(429, "too_many_streams", "Too many open live streams; close another tab")

    def release() -> None:
        slots.release(session.user_id, slot)

    events = EventStream(
        StreamLog(ctx.db, ctx.clock),
        engine.engine_id,
        chosen,
        start,
        alive=lambda: ctx.auth.is_live(session),
        timing=ctx.streams.timing,
    )

    async def body() -> AsyncIterator[str]:
        try:
            async for message in events.messages():
                yield message
        finally:
            release()

    # The background task also releases a slot whose body never started (a client that left at once).
    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},  # no proxy buffering of the event stream
        background=BackgroundTask(release),
    )
