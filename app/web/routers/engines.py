"""``/api/v1/engines``: the user's engine registrations (PLAN §A32; TAA-811).

- ``GET /engines`` (``CurrentSession``): the user's engines. ``?scope=all`` (OWNER role only): every engine,
  with its owner.
- ``POST /engines`` ``{label}`` (``StepUpSession``): 201 ``{engine_id, secret, cloud_base_url}``.
- ``POST /engines/{id}/rotate`` (``StepUpSession``): ``{engine_id, secret}``.
- ``POST /engines/{id}/revoke`` ``{confirm: id}`` (``StepUpSession``): 204.

A secret is in exactly one response, marked ``Cache-Control: no-store``; it is never listed, logged or
audited. A lost secret means rotating it. Rotation is for the engine's owner. Revocation is for the owner or
the deployment's OWNER role (§A32: the OWNER administers engines but commands only its own). Anyone else gets
404 ``engine_not_found``. New secrets (registrations plus rotations) are rate-limited per user
(``EngineRegistry.check_issue_rate``).

Errors are :class:`app.web.engines.EngineErrorCode` values with the statuses in :data:`STATUS`.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.web.auth import AuthSession
from app.web.deps import Context, CurrentSession, OwnedEngine, StepUpSession, no_admin_controls
from app.web.engines import ENGINE_ID_RE, OWNER_ROLE, EngineError, EngineErrorCode, EngineInfo
from app.web.errors import ApiProblem

router = APIRouter(prefix="/engines", tags=["engines"])

STATUS: dict[EngineErrorCode, int] = {
    EngineErrorCode.INVALID_LABEL: 400,
    EngineErrorCode.INVALID_ENGINE_ID: 400,
    EngineErrorCode.CONFIRMATION_MISMATCH: 400,
    EngineErrorCode.NOTHING_TO_IMPORT: 400,
    EngineErrorCode.ENGINE_LINKING_DISABLED: 403,
    EngineErrorCode.OWNER_ONLY: 403,
    EngineErrorCode.OWNER_NOT_FOUND: 404,
    EngineErrorCode.ENGINE_NOT_FOUND: 404,
    EngineErrorCode.ENGINE_EXISTS: 409,
    EngineErrorCode.ENGINE_LIMIT_REACHED: 409,
    EngineErrorCode.ENGINE_REVOKED: 409,
    EngineErrorCode.ENGINE_RATE_LIMITED: 429,
}
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def problem(exc: EngineError) -> ApiProblem:
    if exc.retry_after is None:
        return ApiProblem(STATUS[exc.code], exc.code.value, str(exc))
    return ApiProblem(
        STATUS[exc.code],
        exc.code.value,
        str(exc),
        headers={"Retry-After": str(exc.retry_after)},
        extra={"retry_after": exc.retry_after},
    )


async def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except EngineError as exc:
        raise problem(exc) from exc


def managed_engine(engine_id: str, ctx: Context, session: CurrentSession) -> EngineInfo:
    """An engine the session user owns, or any engine for the OWNER role (revocation only)."""
    info = ctx.engine.registry.get(engine_id) if ENGINE_ID_RE.fullmatch(engine_id) else None
    if info is None or (info.owner_user_id != session.user_id and session.role != OWNER_ROLE):
        raise ApiProblem(404, EngineErrorCode.ENGINE_NOT_FOUND.value, "No such engine")
    return info


ManagedEngine = Annotated[EngineInfo, Depends(managed_engine)]


class LabelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)  # the registry normalizes it and allows 1-64 characters


class RevokeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: str = Field(min_length=1, max_length=64)


def cloud_base_url(request: Request, ctx: Context) -> str:
    return ctx.settings.WEB_PUBLIC_ORIGIN or str(request.base_url).rstrip("/")


@router.get("")
async def list_engines(
    ctx: Context, session: CurrentSession, scope: Literal["mine", "all"] = "mine"
) -> dict[str, Any]:
    if scope == "all" and session.role != OWNER_ROLE:
        raise ApiProblem(403, EngineErrorCode.OWNER_ONLY.value, "Only the owner lists every engine")
    owner = None if scope == "all" else session.user_id
    infos: list[EngineInfo] = await run_in_threadpool(ctx.engine.registry.list_engines, owner)
    return {"items": [i.public(with_owner=scope == "all") for i in infos]}


async def _issue_check(ctx: Context, session: AuthSession) -> None:
    await _call(ctx.engine.registry.check_issue_rate, session.username)


@router.post("", response_model=None)
async def register_engine(
    body: LabelBody, request: Request, ctx: Context, session: StepUpSession
) -> JSONResponse:
    registry = ctx.engine.registry
    no_admin_controls(session)  # a support account links no trading account
    await _issue_check(ctx, session)
    owner = await _call(registry.user, session.username)
    issued = await _call(registry.register, owner, body.label, actor=session.username)
    return JSONResponse(
        {
            "engine_id": issued.engine_id,
            "secret": issued.secret,
            "cloud_base_url": cloud_base_url(request, ctx),
        },
        status_code=201,
        headers=NO_STORE,
    )


@router.post("/{engine_id}/rotate", response_model=None)
async def rotate_engine(engine: OwnedEngine, ctx: Context, session: StepUpSession) -> JSONResponse:
    if engine.status != "ACTIVE":
        raise ApiProblem(409, EngineErrorCode.ENGINE_REVOKED.value, "This engine was revoked")
    await _issue_check(ctx, session)
    issued = await _call(ctx.engine.registry.rotate, engine.engine_id, actor=session.username)
    return JSONResponse({"engine_id": issued.engine_id, "secret": issued.secret}, headers=NO_STORE)


@router.post("/{engine_id}/revoke", status_code=204, response_model=None)
async def revoke_engine(
    engine: ManagedEngine,
    body: RevokeBody,
    ctx: Context,
    session: StepUpSession,
) -> Response:
    if body.confirm != engine.engine_id:
        raise ApiProblem(
            400, EngineErrorCode.CONFIRMATION_MISMATCH.value, "Type the engine id to confirm the revocation"
        )
    await _call(
        ctx.engine.registry.revoke, engine.engine_id, actor=session.username, commands=ctx.engine.commands
    )
    return Response(status_code=204)
