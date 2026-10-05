"""Engine routes: the command long poll (PLAN §A13; TAA-704) and the advisory config (TAA-809).

``GET /api/v1/engine/advisory-config``: the compute requirements of the engine's users
(:func:`app.web.advisory.engine_advisory_config`), with ``ETag: "<version>"``; a matching ``If-None-Match``
gets 304. The engine client (``app/sync/advisory_config.py``) keeps its fallback on anything else.

``GET /api/v1/engine/risk-profile``: the engine owner's trading-profile limits (PLAN §A33, TAA-710) as a
:class:`app.risk.limits.RiskProfileDoc`, with ``ETag`` / 304 like the advisory config; 404 ``no_profile`` when
the owner has not saved one. The engine (``app/sync/risk_profile.py``) can only lower its local limits.

``GET /api/v1/engine/commands?cursor=``:

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

from app.advisory.requirements import AdvisoryConfig
from app.risk.limits import RiskProfileDoc
from app.web.advisory import engine_advisory_config, engine_risk_profile
from app.web.deps import SignedEngine, WebContext
from app.web.entitlements import EntitlementService
from app.web.feed import engine_users

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


def _requirements(ctx: WebContext, engine_id: str) -> AdvisoryConfig:
    """Every user the engine serves (owner, and the subscribers of the market feed), with their plans."""
    plans = EntitlementService(ctx.db, ctx.clock)
    users = [(u, plans.resolve(u).families) for u in engine_users(ctx.db, engine_id)]
    return engine_advisory_config(ctx.db, users)


@router.get("/advisory-config", response_model=None)
async def advisory_config(request: Request, engine: SignedEngine) -> Response:
    ctx = request.app.state.ctx
    config = await run_in_threadpool(_requirements, ctx, engine.engine_id)
    etag = f'"{config.version}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(config.model_dump(mode="json"), headers={"ETag": etag})


def _risk_profile(ctx: WebContext, engine_id: str) -> RiskProfileDoc | None:
    users = engine_users(ctx.db, engine_id)
    return engine_risk_profile(ctx.db, users[0]) if users else None


@router.get("/risk-profile", response_model=None)
async def risk_profile(request: Request, engine: SignedEngine) -> Response:
    ctx = request.app.state.ctx
    doc = await run_in_threadpool(_risk_profile, ctx, engine.engine_id)
    if doc is None:
        return JSONResponse({"code": "no_profile"}, status_code=404)
    etag = f'"{doc.version}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(doc.model_dump(mode="json"), headers={"ETag": etag})
