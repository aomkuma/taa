"""Web Push subscriptions and the notification centre (PLAN §A14 "Web Push"; TAA-806).

Push (all for the session user; mutations need CSRF):

- ``GET /push/key``: ``{public_key}`` for ``PushManager.subscribe`` (404 ``push_not_configured`` when the web
  service has no ``VAPID_PUBLIC_KEY``)
- ``GET /push/subscriptions``: the user's devices (push service host, label, dates, active), never the
  endpoint or keys
- ``POST /push/subscribe`` ``{endpoint, keys: {p256dh, auth}, label?}``: 201 ``{subscription_id}``. Only https
  endpoints of known push services are accepted (400 ``push_endpoint_not_allowed``): the worker posts to
  them. Subscribing an endpoint again updates it (and moves it to this user: one browser, one user). At most
  ``MAX_SUBSCRIPTIONS`` active devices (409 ``push_subscription_limit``).
- ``POST /push/unsubscribe`` ``{endpoint}``: 204 (idempotent)
- ``POST /push/test``: 202, queues a TEST notification to the user's devices

Notification centre:

- ``GET /notifications[?unread=true]``: newest first, paginated like the read APIs
- ``POST /notifications/{id}/read`` (204) and ``POST /notifications/read-all`` (``{updated}``)
- ``GET|PUT /notifications/preferences``: ``{types, disabled}``; disabled types are not pushed (they stay in
  the centre)
"""

from __future__ import annotations

import base64
import binascii
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from starlette.concurrency import run_in_threadpool

from app.core.ids import new_id
from app.storage.models import NotificationPrefsRow, NotificationRow, PushSubscriptionRow
from app.sync.notifications import (
    MAX_ENDPOINT_LENGTH,
    NotificationType,
    Severity,
    notification_dict,
    notify,
    push_endpoint_allowed,
)
from app.sync.stream import StreamLog
from app.web.deps import Context, CsrfSession, CurrentSession, WebContext
from app.web.errors import ApiProblem
from app.web.readmodels import MAX_LIMIT, QueryError, paginate

router = APIRouter(tags=["notifications"])

MAX_SUBSCRIPTIONS = 10


def _b64url(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ApiProblem(400, "invalid_push_keys", "keys must be base64url") from exc


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=80, max_length=128, pattern=r"^[A-Za-z0-9_-]+=*$")
    auth: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+=*$")


class SubscribeBody(BaseModel):
    model_config = ConfigDict(extra="ignore")  # browsers add expirationTime

    endpoint: str = Field(min_length=10, max_length=MAX_ENDPOINT_LENGTH)
    keys: PushKeys
    label: str = Field(default="", max_length=64)


class EndpointBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(min_length=10, max_length=MAX_ENDPOINT_LENGTH)


class PrefsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disabled: list[NotificationType] = Field(max_length=50)


def subscription_dict(row: PushSubscriptionRow) -> dict[str, Any]:
    def iso(v: Any) -> str | None:
        return None if v is None else v.isoformat()

    return {
        "subscription_id": row.subscription_id,
        "service": urlsplit(row.endpoint).hostname,
        "label": row.label,
        "created_at": iso(row.created_at),
        "last_success_at": iso(row.last_success_at),
        "active": row.disabled_at is None,
    }


def _check_configured(ctx: WebContext) -> str:
    key = ctx.settings.VAPID_PUBLIC_KEY
    if key is None:
        raise ApiProblem(404, "push_not_configured", "Web Push is not configured on this server")
    return key


# --- push ---------------------------------------------------------------------------------------------------


@router.get("/push/key")
async def push_key(ctx: Context, session: CurrentSession) -> dict[str, str]:
    return {"public_key": _check_configured(ctx)}


@router.get("/push/subscriptions")
async def push_subscriptions(ctx: Context, session: CurrentSession) -> dict[str, Any]:
    def load() -> list[dict[str, Any]]:
        with ctx.db.session() as sess:
            rows = sess.scalars(
                select(PushSubscriptionRow)
                .where(PushSubscriptionRow.user_id == session.user_id)
                .order_by(PushSubscriptionRow.created_at)
            )
            return [subscription_dict(r) for r in rows]

    return {"items": await run_in_threadpool(load)}


@router.post("/push/subscribe", status_code=201)
async def subscribe(body: SubscribeBody, ctx: Context, session: CsrfSession) -> dict[str, str]:
    _check_configured(ctx)
    if not push_endpoint_allowed(body.endpoint):
        raise ApiProblem(400, "push_endpoint_not_allowed", "Not an endpoint of a known push service")
    p256dh, auth = _b64url(body.keys.p256dh), _b64url(body.keys.auth)
    if len(p256dh) != 65 or p256dh[0] != 4 or len(auth) != 16:
        raise ApiProblem(400, "invalid_push_keys", "p256dh must be a P-256 point and auth 16 bytes")
    now = ctx.clock.now_utc()

    def save() -> str:
        with ctx.db.session() as sess:
            row = sess.scalar(
                select(PushSubscriptionRow).where(PushSubscriptionRow.endpoint == body.endpoint)
            )
            active = sess.scalar(
                select(func.count())
                .select_from(PushSubscriptionRow)
                .where(
                    PushSubscriptionRow.user_id == session.user_id,
                    PushSubscriptionRow.disabled_at.is_(None),
                    PushSubscriptionRow.endpoint != body.endpoint,
                )
            )
            if int(active or 0) >= MAX_SUBSCRIPTIONS:
                raise ApiProblem(409, "push_subscription_limit", f"At most {MAX_SUBSCRIPTIONS} devices")
            if row is None:
                row = PushSubscriptionRow(subscription_id=new_id(), endpoint=body.endpoint, created_at=now)
                sess.add(row)
            row.user_id = session.user_id
            row.p256dh, row.auth = body.keys.p256dh.rstrip("="), body.keys.auth.rstrip("=")
            row.label = " ".join(body.label.split())[:64]
            row.failures, row.disabled_at = 0, None
            return row.subscription_id

    return {"subscription_id": await run_in_threadpool(save)}


@router.post("/push/unsubscribe", status_code=204, response_model=None)
async def unsubscribe(body: EndpointBody, ctx: Context, session: CsrfSession) -> Response:
    def remove() -> None:
        with ctx.db.session() as sess:
            row = sess.scalar(
                select(PushSubscriptionRow).where(PushSubscriptionRow.endpoint == body.endpoint)
            )
            if row is not None and row.user_id == session.user_id:
                sess.delete(row)

    await run_in_threadpool(remove)
    return Response(status_code=204)


@router.post("/push/test", status_code=202)
async def push_test(ctx: Context, session: CsrfSession) -> dict[str, str]:
    _check_configured(ctx)

    def create() -> str:
        with ctx.db.session() as sess:
            row = notify(
                sess,
                StreamLog(ctx.db, ctx.clock),
                user_id=session.user_id,
                engine_id=None,
                type_=NotificationType.TEST,
                severity=Severity.INFO,
                payload={},
                now=ctx.clock.now_utc(),
            )
            return row.notification_id

    return {"notification_id": await run_in_threadpool(create)}


# --- notification centre ----------------------------------------------------------------------------------


def _notification(row: NotificationRow) -> dict[str, Any]:
    return notification_dict(row) | {"push_status": row.push_status}


@router.get("/notifications")
async def notifications(
    ctx: Context,
    session: CurrentSession,
    unread: bool = False,
    limit: Annotated[int | None, Query(ge=1, le=MAX_LIMIT)] = None,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        where = [NotificationRow.user_id == session.user_id]
        if unread:
            where.append(NotificationRow.read_at.is_(None))
        with ctx.db.session() as sess:
            page = paginate(
                sess,
                NotificationRow,
                where,
                NotificationRow.created_at,
                NotificationRow.notification_id,
                limit=limit,
                cursor=cursor,
                serialize=_notification,
            )
            return page.to_dict()

    try:
        result: dict[str, Any] = await run_in_threadpool(load)
    except QueryError as exc:
        raise ApiProblem(400, "invalid_query", str(exc)) from exc
    return result


@router.post("/notifications/read-all")
async def read_all(ctx: Context, session: CsrfSession) -> dict[str, int]:
    def mark() -> int:
        with ctx.db.session() as sess:
            result = sess.execute(
                update(NotificationRow)
                .where(NotificationRow.user_id == session.user_id, NotificationRow.read_at.is_(None))
                .values(read_at=ctx.clock.now_utc())
                .execution_options(synchronize_session=False)
            )
            return int(getattr(result, "rowcount", 0) or 0)

    return {"updated": await run_in_threadpool(mark)}


@router.post("/notifications/{notification_id}/read", status_code=204, response_model=None)
async def read_one(notification_id: str, ctx: Context, session: CsrfSession) -> Response:
    def mark() -> bool:
        with ctx.db.session() as sess:
            row = sess.get(NotificationRow, notification_id[:36])
            if row is None or row.user_id != session.user_id:
                return False
            row.read_at = row.read_at or ctx.clock.now_utc()
            return True

    if not await run_in_threadpool(mark):
        raise ApiProblem(404, "notification_not_found", "No such notification")
    return Response(status_code=204)


@router.get("/notifications/preferences")
async def get_preferences(ctx: Context, session: CurrentSession) -> dict[str, list[str]]:
    def load() -> list[str]:
        with ctx.db.session() as sess:
            row = sess.get(NotificationPrefsRow, session.user_id)
            return list(row.disabled_types) if row is not None else []

    return {"types": [t.value for t in NotificationType], "disabled": await run_in_threadpool(load)}


@router.put("/notifications/preferences")
async def put_preferences(body: PrefsBody, ctx: Context, session: CsrfSession) -> dict[str, list[str]]:
    disabled = sorted({t.value for t in body.disabled})

    def save() -> None:
        with ctx.db.session() as sess:
            row = sess.get(NotificationPrefsRow, session.user_id)
            if row is None:
                row = NotificationPrefsRow(user_id=session.user_id, disabled_types=disabled)
                sess.add(row)
            row.disabled_types = disabled
            row.updated_at = ctx.clock.now_utc()

    await run_in_threadpool(save)
    return {"types": [t.value for t in NotificationType], "disabled": disabled}
