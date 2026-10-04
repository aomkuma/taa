"""Billing scaffolding behind the compliance gate: routes unreachable while disabled, the legal-review
requirement, signed webhooks (forged, stale, replayed), events mapped onto subscriptions (TAA-8A5)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import load_web_settings
from app.core.clock import ManualClock
from app.core.errors import ConfigError
from app.storage.database import Database
from app.web.billing import BillingError, StubProvider, sign, verify_webhook
from app.web.entitlements import EntitlementService
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, login, make_app, mutation_headers

SECRET = "whsec-0123456789abcdef0123456789"
ENABLED = DEV_ENV | {
    "SUBSCRIPTIONS_ENABLED": "true",
    "SUBSCRIPTIONS_LEGAL_REVIEW": "2027-01-15 counsel memo #12",
    "BILLING_WEBHOOK_SECRET": SECRET,
}


def make(
    db: Database, clock: ManualClock, static_dir: Path, env: dict[str, str]
) -> Iterator[tuple[FastAPI, TestClient]]:
    app = make_app(db, clock, static_dir, env)
    app.state.ctx.auth.create_user("alice", PASSWORD, TOTP_SECRET)
    app.state.ctx.auth.create_user("bob", PASSWORD, TOTP_SECRET, role="SUBSCRIBER")
    with TestClient(app, base_url="https://testserver") as client:
        assert login(client, clock, username="bob").status_code == 200
        yield app, client


def post_event(
    client: TestClient, clock: ManualClock, event: dict[str, Any], *, secret: str = SECRET, offset: int = 0
) -> Any:
    body = json.dumps(event).encode()
    t = int(clock.now_utc().timestamp()) + offset
    header = f"t={t},v1={sign(secret.encode(), t, body)}"
    return client.post("/api/v1/billing/webhook", content=body, headers={"Billing-Signature": header})


@pytest.fixture
def disabled(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[tuple[FastAPI, TestClient]]:
    yield from make(db, clock, static_dir, DEV_ENV)


class TestGate:
    def test_disabled_by_default_every_route_is_404(self, disabled: tuple[FastAPI, TestClient]) -> None:
        _, client = disabled
        for method, path in (
            ("get", "/billing/plans"),
            ("post", "/billing/checkout"),
            ("post", "/billing/webhook"),
        ):
            resp = getattr(client, method)(f"/api/v1{path}", headers=mutation_headers(client))
            assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found", path

    def test_enabling_needs_the_legal_review(self) -> None:
        env = {"WEB_ENV": "development", "WEB_SESSION_SECRET": "s" * 40, "SUBSCRIPTIONS_ENABLED": "true"}
        with pytest.raises(ConfigError, match="legal review"):
            load_web_settings(environ=env)
        assert load_web_settings(
            environ=env | {"SUBSCRIPTIONS_LEGAL_REVIEW": "memo 2027-01"}
        ).SUBSCRIPTIONS_ENABLED


@pytest.fixture
def enabled(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[tuple[FastAPI, TestClient]]:
    yield from make(db, clock, static_dir, ENABLED)


class TestEnabled:
    def test_plans_and_checkout(self, enabled: tuple[FastAPI, TestClient]) -> None:
        _, client = enabled
        assert client.get("/api/v1/billing/plans").json()["items"] == []  # FREE/PRO are inactive templates
        resp = client.post("/api/v1/billing/checkout", json={"plan": "PRO"}, headers=mutation_headers(client))
        assert resp.status_code == 503 and resp.json()["error"]["code"] == "billing_unavailable"

    def test_signed_events_drive_the_subscription(
        self, enabled: tuple[FastAPI, TestClient], clock: ManualClock
    ) -> None:
        app, client = enabled
        bob = next(u.id for u in app.state.ctx.auth.list_users() if u.username == "bob")
        end = (clock.now_utc() + timedelta(days=30)).isoformat()
        event = {
            "id": "evt_1",
            "type": "ACTIVATED",
            "user_id": bob,
            "plan": "PRO",
            "ref": "sub_9",
            "period_end": end,
        }
        assert post_event(client, clock, event).json() == {"applied": True}
        plans = EntitlementService(app.state.ctx.db, clock)
        assert plans.resolve(bob).plan == "PRO"
        assert post_event(client, clock, event).json() == {"applied": False}  # a replay changes nothing
        failed = event | {"id": "evt_2", "type": "PAYMENT_FAILED"}
        assert post_event(client, clock, failed).json() == {"applied": True}
        assert plans.resolve(bob).plan == "FREE"  # PAST_DUE is not ACTIVE

    @pytest.mark.parametrize(
        ("secret", "offset"), [("wrong-secret-0123456789", 0), (SECRET, 301), (SECRET, -301)]
    )
    def test_forged_or_stale_events_are_refused(
        self, enabled: tuple[FastAPI, TestClient], clock: ManualClock, secret: str, offset: int
    ) -> None:
        _, client = enabled
        resp = post_event(client, clock, {"id": "evt_x"}, secret=secret, offset=offset)
        assert resp.status_code == 401 and resp.json()["error"]["code"] == "signature_invalid"
        unsigned = client.post("/api/v1/billing/webhook", content=b"{}")
        assert unsigned.status_code == 401

    def test_unusable_events(self, enabled: tuple[FastAPI, TestClient], clock: ManualClock) -> None:
        _, client = enabled
        bad = post_event(client, clock, {"id": "e", "type": "NOPE", "user_id": "u", "plan": "PRO"})
        assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_event"
        unknown = post_event(
            client, clock, {"id": "e", "type": "ACTIVATED", "user_id": "nobody", "plan": "PRO"}
        )
        assert unknown.status_code == 400


def test_verify_webhook_header_shapes(clock: ManualClock) -> None:
    now = clock.now_utc()
    for header in (None, "", "v1=abc", "t=abc,v1=x", "t=1"):
        with pytest.raises(BillingError, match="ignature"):
            verify_webhook(b"k", header, b"{}", now)
    t = int(now.timestamp())
    verify_webhook(b"k", f"t={t},v1={sign(b'k', t, b'{}')}", b"{}", now)
    with pytest.raises(BillingError):
        StubProvider().checkout("u", "PRO", success_url="", cancel_url="")
