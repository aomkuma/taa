"""Billing-ready scaffolding, disabled (PLAN §A30 "Entitlements & plans", R32, R33; TAA-8A5).

Nothing here charges anyone. It fixes the shape billing will have, so turning it on later is configuration
plus a provider adapter:

- :class:`BillingProvider`: the interface a provider implements (Stripe is the first candidate: recurring card
  payments; PromptPay only for prepaid periods, R33). :class:`StubProvider` is the only implementation and
  refuses every checkout.
- **Signed webhooks** (:func:`verify_webhook`): the provider signs ``<timestamp>.<raw body>`` with HMAC-SHA256
  under ``BILLING_WEBHOOK_SECRET`` and sends ``t=<unix seconds>,v1=<hex>`` (the Stripe scheme). Refused:
  a missing or malformed header, a timestamp more than 5 minutes off, a signature that does not match
  (compared in constant time). Each event id is applied once (``billing_events``), so a replay changes
  nothing.
- :func:`apply_event`: ACTIVATED/RENEWED → an ACTIVE subscription with its period end; CANCELED/EXPIRED and
  PAYMENT_FAILED (PAST_DUE) → no longer ACTIVE, so the user falls back to FREE (``EntitlementService``).

The routes (``app/web/routers/billing.py``) are unreachable (404) while ``SUBSCRIPTIONS_ENABLED`` is false,
and that flag needs a recorded legal review (``docs/COMPLIANCE.md``).
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy import select

from app.core.errors import TaaError
from app.core.ids import new_id
from app.storage.database import Database
from app.storage.models import BillingEventRow, PlanRow, SubscriptionRow, UserRow

TOLERANCE = timedelta(minutes=5)


class BillingError(TaaError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EventType(StrEnum):
    ACTIVATED = "ACTIVATED"
    RENEWED = "RENEWED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    PAYMENT_FAILED = "PAYMENT_FAILED"


@dataclass(frozen=True)
class BillingEvent:
    event_id: str
    type: EventType
    user_id: str
    plan_code: str
    provider_ref: str
    period_end: datetime | None


@dataclass(frozen=True)
class Checkout:
    url: str
    provider_ref: str


class BillingProvider(Protocol):
    name: str

    def checkout(self, user_id: str, plan_code: str, *, success_url: str, cancel_url: str) -> Checkout:
        """A hosted payment page for *plan_code* (the provider collects card details, never this service)."""

    def cancel(self, provider_ref: str) -> None:
        """Stop renewing at the end of the current period."""

    def parse(self, payload: Mapping[str, Any]) -> BillingEvent:
        """A verified webhook payload as a :class:`BillingEvent`."""


class StubProvider:
    """No provider is integrated in Milestone 1: every checkout is refused."""

    name = "stub"

    def checkout(self, user_id: str, plan_code: str, *, success_url: str, cancel_url: str) -> Checkout:
        raise BillingError("billing_unavailable", "No billing provider is configured")

    def cancel(self, provider_ref: str) -> None:
        raise BillingError("billing_unavailable", "No billing provider is configured")

    def parse(self, payload: Mapping[str, Any]) -> BillingEvent:
        """The neutral event format the stub accepts (tests; a real adapter maps its own payloads)."""
        try:
            end = payload.get("period_end")
            return BillingEvent(
                event_id=str(payload["id"]),
                type=EventType(str(payload["type"])),
                user_id=str(payload["user_id"]),
                plan_code=str(payload["plan"]),
                provider_ref=str(payload.get("ref", "")),
                period_end=None if end is None else datetime.fromisoformat(str(end)),
            )
        except (KeyError, ValueError) as exc:
            raise BillingError("invalid_event", "The event payload is not usable") from exc


def sign(secret: bytes, timestamp: int, body: bytes) -> str:
    return hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def verify_webhook(secret: bytes, header: str | None, body: bytes, now: datetime) -> None:
    """Raise :class:`BillingError` ``signature_invalid`` unless *header* signs *body* within the tolerance."""
    if not header:
        raise BillingError("signature_invalid", "Missing signature")
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    try:
        timestamp = int(parts["t"])
        given = parts["v1"]
    except (KeyError, ValueError) as exc:
        raise BillingError("signature_invalid", "Malformed signature") from exc
    if abs(now.timestamp() - timestamp) > TOLERANCE.total_seconds():
        raise BillingError("signature_invalid", "Stale signature")
    if not hmac.compare_digest(sign(secret, timestamp, body), given):
        raise BillingError("signature_invalid", "Signature mismatch")


def apply_event(db: Database, event: BillingEvent, provider: str, now: datetime) -> bool:
    """Apply a verified event once; False when its id was already applied (a replay)."""
    with db.session() as sess:
        if sess.get(BillingEventRow, event.event_id) is not None:
            return False
        if sess.get(UserRow, event.user_id) is None or sess.get(PlanRow, event.plan_code) is None:
            raise BillingError("invalid_event", "Unknown user or plan")
        sub = sess.scalar(
            select(SubscriptionRow).where(
                SubscriptionRow.user_id == event.user_id,
                SubscriptionRow.provider == provider,
                SubscriptionRow.provider_ref == event.provider_ref,
            )
        )
        if sub is None:
            sub = SubscriptionRow(
                subscription_id=new_id(),
                user_id=event.user_id,
                plan_code=event.plan_code,
                status="ACTIVE",
                provider=provider,
                provider_ref=event.provider_ref,
                created_at=now,
                created_by=f"billing:{provider}",
            )
            sess.add(sub)
        sub.plan_code = event.plan_code
        sub.period_end = event.period_end
        sub.status = {
            EventType.ACTIVATED: "ACTIVE",
            EventType.RENEWED: "ACTIVE",
            EventType.CANCELED: "CANCELED",
            EventType.EXPIRED: "EXPIRED",
            EventType.PAYMENT_FAILED: "PAST_DUE",
        }[event.type]
        sess.add(
            BillingEventRow(
                event_id=event.event_id,
                provider=provider,
                type=event.type.value,
                user_id=event.user_id,
                received_at=now,
            )
        )
    return True
