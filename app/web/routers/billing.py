"""Subscription and billing routes behind the compliance gate (PLAN §A30, R32; TAA-8A5).

Every route answers 404 ``not_found`` while ``SUBSCRIPTIONS_ENABLED`` is false (the default), exactly like a
route that does not exist, so nothing about billing is reachable before the legal review.

- ``GET /billing/plans``: the plans offered (active ones)
- ``POST /billing/checkout`` ``{plan}`` (CSRF): a hosted checkout; the stub provider answers 503
  ``billing_unavailable``
- ``POST /billing/webhook``: the provider's signed events (``Billing-Signature: t=..,v1=..``); 401
  ``signature_invalid``, 200 ``{"applied": bool}`` (False: a replay)
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.storage.models import PlanRow
from app.web.billing import BillingError, StubProvider, apply_event, verify_webhook
from app.web.deps import Context, CsrfSession, CurrentSession, WebContext
from app.web.errors import ApiProblem

SIGNATURE_HEADER = "Billing-Signature"


def subscriptions_enabled(ctx: Context) -> WebContext:
    if not ctx.settings.SUBSCRIPTIONS_ENABLED:
        raise ApiProblem(404, "not_found", "Not found")
    return ctx


Enabled = Annotated[WebContext, Depends(subscriptions_enabled)]
router = APIRouter(prefix="/billing", tags=["billing"], dependencies=[Depends(subscriptions_enabled)])
PROVIDER = StubProvider()


class CheckoutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str = Field(min_length=1, max_length=32)


@router.get("/plans")
async def plans(ctx: Enabled, session: CurrentSession) -> dict[str, Any]:
    def load() -> list[dict[str, Any]]:
        with ctx.db.session() as sess:
            rows = sess.scalars(select(PlanRow).where(PlanRow.active.is_(True), PlanRow.code != "OWNER"))
            return [
                {"code": p.code, "name_th": p.name_th, "name_en": p.name_en, "spec": dict(p.spec)}
                for p in rows
            ]

    return {"items": await run_in_threadpool(load)}


@router.post("/checkout")
async def checkout(body: CheckoutBody, ctx: Enabled, session: CsrfSession) -> dict[str, str]:
    origin = ctx.settings.WEB_PUBLIC_ORIGIN or ""
    try:
        result = PROVIDER.checkout(
            session.user_id,
            body.plan,
            success_url=f"{origin}/account",
            cancel_url=f"{origin}/account",
        )
    except BillingError as exc:
        raise ApiProblem(503, exc.code, str(exc)) from exc
    return {"url": result.url}


@router.post("/webhook")
async def webhook(request: Request, ctx: Enabled) -> dict[str, bool]:
    secret = ctx.settings.BILLING_WEBHOOK_SECRET
    if secret is None:
        raise ApiProblem(503, "billing_unavailable", "No webhook secret is configured")
    body = await request.body()
    try:
        verify_webhook(
            secret.get_secret_value().encode(),
            request.headers.get(SIGNATURE_HEADER),
            body,
            ctx.clock.now_utc(),
        )
        event = PROVIDER.parse(json.loads(body))
        applied = await run_in_threadpool(apply_event, ctx.db, event, PROVIDER.name, ctx.clock.now_utc())
    except BillingError as exc:
        status = 401 if exc.code == "signature_invalid" else 400
        raise ApiProblem(status, exc.code, str(exc)) from exc
    except ValueError as exc:
        raise ApiProblem(400, "invalid_event", "The body is not JSON") from exc
    if applied:
        ctx.audit.append(
            "billing.event", PROVIDER.name, {"event_id": event.event_id, "type": event.type.value}
        )
    return {"applied": applied}
