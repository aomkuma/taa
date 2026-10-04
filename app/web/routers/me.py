"""The user's own data and the minimal user administration (PLAN §A30; TAA-8A1).

- ``GET /me/export``: everything stored about the session user as a JSON download (:mod:`app.web.privacy`)
- ``POST /me/erase`` ``{confirm: <username>}`` (step-up): erase the session user's personal data; 409
  ``owner_cannot_be_erased`` / ``engines_active``, 400 ``confirmation_mismatch``
- ``GET /admin/users`` (OWNER or ADMIN): username, role, state and creation date of every user, nothing else
- ``POST /admin/users/{user_id}/erase`` ``{confirm: <username>}`` (OWNER, step-up): erase another user on
  their request
- ``GET /me/entitlements``: the session user's plan, features, limits and this period's usage (TAA-8A2)
- ``GET /admin/plans`` (OWNER/ADMIN)
- ``POST /admin/users/{user_id}/plan`` ``{plan}`` (OWNER, step-up): assign a plan by hand
  (``provider = "manual"``; billing stays disabled)
- ``PUT|DELETE /admin/users/{user_id}/overrides/{key}`` (OWNER, step-up): one feature, limit or allow-list
  exception
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.advisory.personalize import badge
from app.core.clock import ensure_utc
from app.core.ids import new_id
from app.storage.models import (
    EntitlementOverrideRow,
    OpportunityAlertRow,
    OpportunityRow,
    PlanRow,
    SubscriptionRow,
    UserRow,
)
from app.sync.events import json_safe
from app.web.account_profiles import ProfileBody, ProfileError, load_profile, profile_dict, save_profile
from app.web.auth import AuthSession, Role
from app.web.deps import (
    AdminSession,
    Context,
    CsrfSession,
    CurrentSession,
    StepUpSession,
    WebContext,
    require_roles,
)
from app.web.entitlements import ASSET_CLASSES_KEY, FAMILIES_KEY, EntitlementService, Feature, Limit
from app.web.errors import ApiProblem
from app.web.feed import feed_engine, own_engine
from app.web.privacy import PrivacyError, erase_user, export_user
from app.web.readmodels import MAX_LIMIT, QueryError, paginate

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


@router.get("/me/entitlements")
async def my_entitlements(ctx: Context, session: CurrentSession) -> dict[str, Any]:
    service = EntitlementService(ctx.db, ctx.clock)
    ent = await run_in_threadpool(service.resolve, session.user_id)
    usage = {k.value: await run_in_threadpool(service.usage, session.user_id, k) for k in Limit}
    return ent.to_dict() | {"usage": usage}


@router.get("/admin/plans")
async def plans(ctx: Context, session: AdminSession) -> dict[str, Any]:
    def load() -> list[dict[str, Any]]:
        with ctx.db.session() as sess:
            return [
                {
                    "code": p.code,
                    "name_th": p.name_th,
                    "name_en": p.name_en,
                    "active": p.active,
                    "spec": dict(p.spec),
                }
                for p in sess.scalars(select(PlanRow).order_by(PlanRow.code))
            ]

    return {"items": await run_in_threadpool(load)}


class PlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str = Field(min_length=1, max_length=32)


@router.post("/admin/users/{user_id}/plan")
async def assign_plan(
    user_id: str, body: PlanBody, ctx: Context, owner: OwnerSession, session: StepUpSession
) -> dict[str, Any]:
    def assign() -> None:
        now = ctx.clock.now_utc()
        with ctx.db.session() as sess:
            if sess.get(UserRow, user_id[:36]) is None:
                raise ApiProblem(404, "user_not_found", "No such user")
            if sess.get(PlanRow, body.plan) is None:
                raise ApiProblem(404, "plan_not_found", "No such plan")
            for sub in sess.scalars(
                select(SubscriptionRow).where(
                    SubscriptionRow.user_id == user_id, SubscriptionRow.status == "ACTIVE"
                )
            ):
                sub.status = "CANCELED"
            sess.add(
                SubscriptionRow(
                    subscription_id=new_id(),
                    user_id=user_id,
                    plan_code=body.plan,
                    status="ACTIVE",
                    provider="manual",
                    created_at=now,
                    created_by=session.username,
                )
            )
        ctx.audit.append("plan.assigned", session.username, {"user_id": user_id, "plan": body.plan})

    await run_in_threadpool(assign)
    ent = await run_in_threadpool(EntitlementService(ctx.db, ctx.clock).resolve, user_id)
    return ent.to_dict()


OVERRIDE_KEYS = frozenset({*Feature.__members__, *Limit.__members__, ASSET_CLASSES_KEY, FAMILIES_KEY})


class OverrideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: bool | int | list[str] | None
    reason: str = Field(default="", max_length=200)


async def _override(ctx: WebContext, user_id: str, key: str, body: OverrideBody | None, actor: str) -> None:
    if key not in OVERRIDE_KEYS:
        raise ApiProblem(400, "invalid_override", "Unknown entitlement key")

    def save() -> None:
        with ctx.db.session() as sess:
            if sess.get(UserRow, user_id) is None:
                raise ApiProblem(404, "user_not_found", "No such user")
            row = sess.get(EntitlementOverrideRow, (user_id, key))
            if body is None:
                if row is not None:
                    sess.delete(row)
                return
            if row is None:
                row = EntitlementOverrideRow(user_id=user_id, key=key, created_at=ctx.clock.now_utc())
                sess.add(row)
            row.value, row.reason, row.created_by = body.value, body.reason, actor

    await run_in_threadpool(save)
    ctx.audit.append(
        "entitlement.override",
        actor,
        {"user_id": user_id, "key": key, "value": None if body is None else body.value},
    )


@router.put("/admin/users/{user_id}/overrides/{key}")
async def put_override(
    user_id: str, key: str, body: OverrideBody, ctx: Context, owner: OwnerSession, session: StepUpSession
) -> dict[str, Any]:
    await _override(ctx, user_id[:36], key, body, session.username)
    try:
        ent = await run_in_threadpool(EntitlementService(ctx.db, ctx.clock).resolve, user_id[:36])
    except ValueError as exc:  # e.g. an unknown family in an allow-list
        await _override(ctx, user_id[:36], key, None, session.username)
        raise ApiProblem(400, "invalid_override", str(exc)) from exc
    return ent.to_dict()


@router.delete("/admin/users/{user_id}/overrides/{key}", status_code=204, response_model=None)
async def delete_override(
    user_id: str, key: str, ctx: Context, owner: OwnerSession, session: StepUpSession
) -> Response:
    await _override(ctx, user_id[:36], key, None, session.username)
    return Response(status_code=204)


@router.get("/me/account-profile")
async def get_account_profile(ctx: Context, session: CurrentSession) -> dict[str, Any]:
    """The account the user's alerts are sized for (TAA-8A3); none set yet: ``{"source": null}``."""
    row = await run_in_threadpool(load_profile, ctx.db, session.user_id)
    return {"source": None} if row is None else profile_dict(row)


@router.put("/me/account-profile")
async def put_account_profile(body: ProfileBody, ctx: Context, session: CsrfSession) -> dict[str, Any]:
    try:
        saved: dict[str, Any] = await run_in_threadpool(
            save_profile, ctx.db, session.user_id, body, ctx.clock.now_utc()
        )
    except ProfileError as exc:
        raise ApiProblem(404, "engine_not_found", "Link an engine you own") from exc
    return saved


@router.get("/me/feed")
async def my_feed(ctx: Context, session: CurrentSession) -> dict[str, Any]:
    """Which engine's market facts the user reads: their own, or the market feed (TAA-8A4)."""
    own = await run_in_threadpool(own_engine, ctx.db, session.user_id)
    feed = own or await run_in_threadpool(feed_engine, ctx.db, session.user_id, session.role)
    return {"engine_id": feed, "own": own is not None}


@router.get("/me/alerts")
async def my_alerts(
    ctx: Context,
    session: CurrentSession,
    limit: Annotated[int | None, Query(ge=1, le=MAX_LIMIT)] = None,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> dict[str, Any]:
    """The opportunities this user was alerted to, newest first, with the user's own sizing and the badge
    now (ACTIVE / EXPIRING / EXPIRED / INVALIDATED / FOLLOWED; the user's window counts, TAA-8A4)."""
    now = ctx.clock.now_utc()

    def load() -> dict[str, Any]:
        with ctx.db.session() as sess:

            def item(a: OpportunityAlertRow) -> dict[str, Any]:
                opp = sess.get(OpportunityRow, (a.engine_id, a.opportunity_id))
                status = a.final_status or (opp.status if opp is not None else "EXPIRED")
                return {
                    "engine_id": a.engine_id,
                    "opportunity_id": a.opportunity_id,
                    "symbol": a.symbol,
                    "side": None if opp is None else opp.side,
                    "sent_at": json_safe(a.sent_at),
                    "valid_until": json_safe(a.valid_until),
                    "lot": a.lot,
                    "risk_money": a.risk_money,
                    "currency": a.currency or None,
                    "badge": json_safe(
                        badge(status, ensure_utc(a.sent_at), a.valid_until and ensure_utc(a.valid_until), now)
                    ),
                }

            return paginate(
                sess,
                OpportunityAlertRow,
                [OpportunityAlertRow.user_id == session.user_id],
                OpportunityAlertRow.sent_at,
                OpportunityAlertRow.opportunity_id,
                limit=limit,
                cursor=cursor,
                serialize=item,
            ).to_dict()

    try:
        result: dict[str, Any] = await run_in_threadpool(load)
    except QueryError as exc:
        raise ApiProblem(400, "invalid_query", str(exc)) from exc
    return result
