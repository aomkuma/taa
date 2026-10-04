"""Plans and entitlements: resolution, usage counters, enforcement in the API, the personalizer and the
engine compute union, plan administration (TAA-8A2)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.clock import ManualClock
from app.evidence.framework import Family
from app.security.hmac_auth import Signer
from app.storage.database import Database
from app.storage.models import EntitlementOverrideRow, PlanRow, SubscriptionRow
from app.sync.advisory_config import ADVISORY_CONFIG_PATH
from app.web.advisory import catalogs
from app.web.entitlements import EntitlementError, EntitlementService, Feature, Limit, seed_plans
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, current_code, login, make_app, mutation_headers
from tests.web.test_auth import next_step

SECRET = "engine-hmac-secret-0123456789abcdef-xyz"


class Rig:
    def __init__(self, app: FastAPI, client: TestClient, clock: ManualClock) -> None:
        self.app, self.client, self.clock = app, client, clock
        self.ctx = app.state.ctx
        self.ids = {u.username: u.id for u in self.ctx.auth.list_users()}
        self.plans = EntitlementService(self.ctx.db, clock)

    def login(self, name: str, *, step_up: bool = False) -> None:
        self.client.cookies.clear()
        next_step(self.clock)
        assert login(self.client, self.clock, username=name).status_code == 200
        if step_up:
            next_step(self.clock)
            assert self.post("/auth/step-up", {"code": current_code(self.clock)}).status_code == 200

    def post(self, path: str, body: Any = None) -> Any:
        return self.client.post(f"/api/v1{path}", json=body, headers=mutation_headers(self.client))

    def put(self, path: str, body: Any) -> Any:
        return self.client.put(f"/api/v1{path}", json=body, headers=mutation_headers(self.client))

    def subscribe(self, name: str, plan: str, *, ends_in: timedelta | None = None) -> None:
        with self.ctx.db.session() as sess:
            sess.add(
                SubscriptionRow(
                    subscription_id=f"s-{name}-{plan}",
                    user_id=self.ids[name],
                    plan_code=plan,
                    status="ACTIVE",
                    period_end=None if ends_in is None else self.clock.now_utc() + ends_in,
                    created_at=self.clock.now_utc(),
                )
            )


@pytest.fixture
def rig(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[Rig]:
    app = make_app(db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"})
    for name, role in (("alice", "OWNER"), ("ada", "ADMIN"), ("bob", "SUBSCRIBER")):
        app.state.ctx.auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
    with TestClient(app, base_url="https://testserver") as client:
        yield Rig(app, client, clock)


class TestResolution:
    def test_seeded_plans(self, rig: Rig) -> None:
        seed_plans(rig.ctx.db, rig.clock.now_utc())  # idempotent
        with rig.ctx.db.session() as sess:
            plans = {p.code: p.active for p in sess.scalars(select(PlanRow))}
        assert plans == {"OWNER": True, "FREE": False, "PRO": False}

    def test_owner_free_and_subscriptions(self, rig: Rig) -> None:
        owner = rig.plans.resolve(rig.ids["alice"])
        assert (
            owner.plan == "OWNER"
            and owner.has(Feature.BACKTESTS)
            and owner.limit(Limit.ALERTS_PER_DAY) is None
        )
        assert owner.families is None and owner.asset_classes is None
        free = rig.plans.resolve(rig.ids["bob"])
        assert free.plan == "FREE" and not free.has(Feature.BACKTESTS) and free.limit(Limit.WATCHLISTS) == 2
        assert free.personalizer().alerts_per_day == 5 and Family.ELLIOTT not in (free.families or ())
        rig.subscribe("bob", "PRO", ends_in=timedelta(days=30))
        assert rig.plans.resolve(rig.ids["bob"]).plan == "PRO"
        rig.clock.advance(31 * 86400)
        assert rig.plans.resolve(rig.ids["bob"]).plan == "FREE"  # the period ended

    def test_overrides_apply_last(self, rig: Rig) -> None:
        with rig.ctx.db.session() as sess:
            for key, value in (
                ("BACKTESTS", True),
                ("BACKTESTS_PER_MONTH", 1),
                ("FAMILIES", ["ELLIOTT"]),
                ("NOPE", 1),
            ):
                sess.add(
                    EntitlementOverrideRow(
                        user_id=rig.ids["bob"], key=key, value=value, created_at=rig.clock.now_utc()
                    )
                )
        ent = rig.plans.resolve(rig.ids["bob"])
        assert ent.has(Feature.BACKTESTS) and ent.limit(Limit.BACKTESTS_PER_MONTH) == 1
        assert ent.families == frozenset({Family.ELLIOTT})
        assert set(ent.overrides) == {
            "BACKTESTS",
            "BACKTESTS_PER_MONTH",
            "FAMILIES",
        }  # unknown keys change nothing

    def test_usage_counts_per_period(self, rig: Rig) -> None:
        rig.subscribe("bob", "PRO")
        for _ in range(20):
            rig.plans.consume(rig.ids["bob"], Limit.BACKTESTS_PER_MONTH)
        with pytest.raises(EntitlementError):
            rig.plans.consume(rig.ids["bob"], Limit.BACKTESTS_PER_MONTH)
        rig.clock.advance(31 * 86400)  # next month
        assert rig.plans.usage(rig.ids["bob"], Limit.BACKTESTS_PER_MONTH) == 0


class TestEnforcement:
    def test_watchlists_follow_the_plan(self, rig: Rig) -> None:
        rig.login("bob")
        resp = rig.post("/advisory/watchlists", {"name": "Third", "symbols": ["EURUSD"]})
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "plan_limit"
        assert resp.json()["error"]["key"] == "WATCHLISTS"
        prefs = rig.client.get("/api/v1/advisory/preferences").json()
        prefs["watchlists"][0]["symbols"] = [f"SYM{i}" for i in range(11)]
        big = rig.put("/advisory/preferences", prefs)
        assert big.status_code == 403 and big.json()["error"]["key"] == "WATCHLIST_SYMBOLS"
        assert rig.post("/advisory/favourites/EURUSD").status_code == 200  # within the plan
        rig.login("alice")
        assert rig.post("/advisory/watchlists", {"name": "Third", "symbols": ["EURUSD"]}).status_code == 201

    def test_backtests_follow_the_plan(self, rig: Rig) -> None:
        rig.login("bob")
        engine = rig.ctx.engine.registry.register(
            rig.ctx.engine.registry.user("bob"), "pc", actor="t"
        ).engine_id
        body = {"symbols": ["EURUSD"], "start": "2026-01-01T00:00:00Z", "end": "2026-02-01T00:00:00Z"}
        resp = rig.post(f"/engines/{engine}/backtests", body)
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "plan_limit"
        rig.subscribe("bob", "PRO")
        assert rig.post(f"/engines/{engine}/backtests", body).status_code == 202
        mine = rig.client.get("/api/v1/me/entitlements").json()
        assert mine["plan"] == "PRO" and mine["usage"]["BACKTESTS_PER_MONTH"] == 1

    def test_the_engine_computes_only_entitled_theories(self, rig: Rig) -> None:
        bob = rig.ctx.engine.registry.user("bob")
        rig.ctx.engine.registry.import_env(bob, "eng-b", SECRET, None, actor="t")
        headers = Signer("eng-b", SECRET.encode(), rig.clock).headers("GET", ADVISORY_CONFIG_PATH)
        detectors = set(rig.client.get(ADVISORY_CONFIG_PATH, headers=headers).json()["detectors"])
        evidence, _ = catalogs()
        allowed = evidence.ids_in_families(
            [Family.TREND, Family.LEVELS, Family.FIBONACCI, Family.CANDLESTICK]
        )
        assert detectors and detectors <= allowed
        assert not any(evidence.get(d).family is Family.ELLIOTT for d in detectors)


class TestAdministration:
    def test_the_owner_assigns_plans_and_overrides(self, rig: Rig) -> None:
        rig.login("alice", step_up=True)
        bob = rig.ids["bob"]
        assert rig.post(f"/admin/users/{bob}/plan", {"plan": "PRO"}).json()["plan"] == "PRO"
        assert (
            rig.post(f"/admin/users/{bob}/plan", {"plan": "NOPE"}).json()["error"]["code"] == "plan_not_found"
        )
        with rig.ctx.db.session() as sess:
            statuses = sorted(
                sess.scalars(select(SubscriptionRow.status).where(SubscriptionRow.user_id == bob))
            )
        assert statuses == ["ACTIVE"]
        changed = rig.put(
            f"/admin/users/{bob}/overrides/ALERTS_PER_DAY", {"value": 99, "reason": "beta tester"}
        )
        assert changed.json()["limits"]["ALERTS_PER_DAY"] == 99
        assert rig.put(f"/admin/users/{bob}/overrides/MADE_UP", {"value": 1}).status_code == 400
        bad = rig.put(f"/admin/users/{bob}/overrides/FAMILIES", {"value": ["NOT_A_FAMILY"]})
        assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_override"
        assert (
            rig.client.delete(
                f"/api/v1/admin/users/{bob}/overrides/ALERTS_PER_DAY", headers=mutation_headers(rig.client)
            ).status_code
            == 204
        )
        with rig.ctx.db.session() as sess:
            assert sess.scalar(select(func.count()).select_from(EntitlementOverrideRow)) == 0
        assert {p["code"] for p in rig.client.get("/api/v1/admin/plans").json()["items"]} == {
            "OWNER",
            "FREE",
            "PRO",
        }

    def test_admin_reads_plans_but_assigns_nothing(self, rig: Rig) -> None:
        rig.login("ada", step_up=True)
        assert rig.client.get("/api/v1/admin/plans").status_code == 200
        resp = rig.post(f"/admin/users/{rig.ids['bob']}/plan", {"plan": "PRO"})
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "role_forbidden"


def test_an_unseeded_database_still_resolves_each_plan_by_its_seed(db: Database, clock: ManualClock) -> None:
    from app.storage.audit import AuditLog
    from app.web.auth import AuthKeys, AuthService

    auth = AuthService(db, clock, AuditLog(db, "web", clock), AuthKeys("s" * 40))
    owner = auth.create_user("alice", PASSWORD, TOTP_SECRET)
    assert EntitlementService(db, clock).resolve(owner.id).asset_classes is None  # OWNER, not FREE
