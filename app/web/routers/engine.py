"""``GET /api/v1/engine/commands?cursor=``: the engine's command long poll (PLAN §A13; TAA-704).

Authenticated by the paired engine's HMAC signature (``SignedEngine``; the signature covers the query string,
so the cursor cannot be altered). A thin loop over :meth:`app.sync.command_queue.CommandQueue.pending`:

- 200 ``{"commands": [...], "cursor": "<last id>"}`` as soon as an open command after the cursor exists (the
  commands are marked DELIVERED; the engine executes each id once, so a redelivery is harmless)
- 204 when none arrived within ``LONG_POLL_SECONDS`` (or the engine hung up)
- 401 ``signature_invalid``; 422 for a malformed cursor; 503 ``sync_disabled`` when no engine is paired
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.web.deps import SignedEngine

router = APIRouter(prefix="/engine", tags=["sync"])

# The engine waits poll_seconds + 10 s (app.sync.commands.CommandPoller), so 25 s stays inside its timeout.
LONG_POLL_SECONDS = 25.0
POLL_INTERVAL_SECONDS = 1.0


@router.get("/commands", response_model=None)
async def poll_commands(
    request: Request,
    engine: SignedEngine,
    cursor: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
) -> Response:
    queue, engine_id = engine.link.commands, engine.verified.engine_id
    deadline = time.monotonic() + LONG_POLL_SECONDS
    while True:
        commands = await run_in_threadpool(queue.pending, engine_id, cursor)
        if commands:
            return JSONResponse({"commands": commands, "cursor": commands[-1]["id"]})
        remaining = deadline - time.monotonic()
        if remaining <= 0 or await request.is_disconnected():
            return Response(status_code=204)
        await asyncio.sleep(min(POLL_INTERVAL_SECONDS, remaining))
