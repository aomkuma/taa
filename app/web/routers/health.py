"""``GET /api/v1/health``: liveness plus a database check (Railway healthcheck, PLAN §A21).

Public and minimal: it reveals no configuration, account or engine data.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app import __version__
from app.web.deps import WebContext, get_context

router = APIRouter(tags=["system"])


@router.get("/health")
def health(ctx: Annotated[WebContext, Depends(get_context)]) -> JSONResponse:
    database = ctx.db.healthcheck()
    body = {
        "status": "ok" if database else "unavailable",
        "checks": {"database": database},
        "version": __version__,
        "time": ctx.clock.now_utc().isoformat(),
    }
    return JSONResponse(body, status_code=200 if database else 503)
