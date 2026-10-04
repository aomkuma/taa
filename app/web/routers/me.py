"""The user's own data and the minimal user administration (PLAN §A30; TAA-8A1).

- ``GET /me/export``: everything stored about the session user as a JSON download (:mod:`app.web.privacy`)
- ``POST /me/erase`` ``{confirm: <username>}`` (step-up): erase the session user's personal data; 409
  ``owner_cannot_be_erased`` / ``engines_active``, 400 ``confirmation_mismatch``
- ``GET /admin/users`` (OWNER or ADMIN): username, role, state and creation date of every user, nothing else
- ``POST /admin/users/{user_id}/erase`` ``{confirm: <username>}`` (OWNER, step-up): erase another user on
  their request
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.storage.models import UserRow
from app.sync.events import json_safe
from app.web.auth import AuthSession, Role
from app.web.deps import AdminSession, Context, CurrentSession, StepUpSession, WebContext, require_roles
from app.web.errors import ApiProblem
from app.web.privacy import PrivacyError, erase_user, export_user

router = APIRouter(tags=["me"])

STATUS = {"user_not_found": 404, "owner_cannot_be_erased": 409, "engines_active": 409}


class ConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: str = Field(min_length=1, max_length=64)


async def _erase(ctx: WebContext, user_id: str, confirm: str, actor: str) -> None:
    def run() -> None:
        with ctx.db.session() as sess:
            user = sess.get(UserRow, user_id)
            if user is None:
                raise PrivacyError("user_not_found", "No such user")
            if confirm != user.username:
                raise ApiProblem(400, "confirmation_mismatch", "Type the username to confirm")
        erase_user(ctx.db, ctx.clock, ctx.audit, user_id, actor=actor)

    try:
        await run_in_threadpool(run)
    except PrivacyError as exc:
        raise ApiProblem(STATUS.get(exc.code, 400), exc.code, str(exc)) from exc


@router.get("/me/export", response_model=None)
async def export(ctx: Context, session: CurrentSession) -> Response:
    data = await run_in_threadpool(
        export_user, ctx.db, ctx.engine.registry, session.user_id, ctx.clock.now_utc()
    )
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="taa-{session.username}.json"'},
    )


@router.post("/me/erase", status_code=204, response_model=None)
async def erase_me(body: ConfirmBody, ctx: Context, session: StepUpSession) -> Response:
    await _erase(ctx, session.user_id, body.confirm, session.username)
    return Response(status_code=204)


@router.get("/admin/users")
async def users(ctx: Context, session: AdminSession) -> dict[str, Any]:
    def load() -> list[dict[str, Any]]:
        with ctx.db.session() as sess:
            rows = sess.scalars(select(UserRow).order_by(UserRow.created_at)).all()
            return [
                {
                    "id": u.id,
                    "username": u.username,
                    "role": u.role,
                    "disabled": u.disabled,
                    "created_at": json_safe(u.created_at),
                }
                for u in rows
            ]

    return {"items": await run_in_threadpool(load)}


OwnerSession = Annotated[AuthSession, Depends(require_roles(Role.OWNER))]


@router.post("/admin/users/{user_id}/erase", status_code=204, response_model=None)
async def erase_other(
    user_id: str, body: ConfirmBody, ctx: Context, owner: OwnerSession, session: StepUpSession
) -> Response:
    await _erase(ctx, user_id[:36], body.confirm, session.username)
    return Response(status_code=204)
