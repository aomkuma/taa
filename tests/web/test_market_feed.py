"""The market feed for several users (TAA-8A4): subscribers read the owner's market facts without the
owner's account, get alerts sized on their own profile, their own ranking and accuracy; the engine computes
the union of its users' theories."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.clock import ManualClock
from app.security.hmac_auth import Signer
from app.storage.database import Database
from app.storage.models import (
    AccountProfileRow,
    NotificationRow,
    OpportunityAlertRow,
    ShadowTradeRow,
    SuitabilitySnapshotRow,
)
from app.sync.advisory_config import ADVISORY_CONFIG_PATH
from app.web.advisory import PreferenceStore
from app.web.feed import OWNER_ONLY_FIELDS, engine_users
from app.worker.opportunities import OpportunityAlerter
from tests.unit.test_calibration import shadow
from tests.unit.test_cloud_sizing import store
from tests.unit.test_opportunity_alerts import CONFIG, add_opportunity, prefs
from tests.unit.test_personalize import NOW
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, login, make_app
from tests.web.test_auth import next_step

FEED, OWN = "eng-a", "eng-c"
SECRET = "engine-hmac-secret-0123456789abcdef-xyz"


class Rig:
    def __init__(self, app: FastAPI, client: TestClient) -> None:
        self.app, self.client = app, client
        self.ctx = app.state.ctx
        self.clock: ManualClock = self.ctx.clock
        self.ids = {u.username: u.id for u in self.ctx.auth.list_users()}

    def login(self, name: str) -> None:
        self.client.cookies.clear()
        next_step(self.clock)
        assert login(self.client, self.clock, username=name).status_code == 200

    def get(self, path: str) -> Any:
        return self.client.get(f"/api/v1{path}")

    def alerts(self, name: str) -> list[NotificationRow]:
        with self.ctx.db.session() as sess:
            return list(
                sess.scalars(
                    select(NotificationRow).where(
                        NotificationRow.user_id == self.ids[name], NotificationRow.type == "OPPORTUNITY"
                    )
                )
            )


@pytest.fixture
def rig(db: Database, static_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Rig]:
    monkeypatch.setattr("app.web.routers.advisory.load_app_config", lambda: CONFIG)
    clock = ManualClock(NOW)
    app = make_app(db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"})
    ctx = app.state.ctx
    users = {}
    for name, role in (("alice", "OWNER"), ("bob", "SUBSCRIBER"), ("carol", "SUBSCRIBER"), ("ada", "ADMIN")):
        users[name] = ctx.auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
    ctx.engine.registry.import_env(users["alice"], FEED, SECRET, None, actor="t")
    ctx.engine.registry.import_env(users["carol"], OWN, SECRET + "c", None, actor="t")
    for name in ("alice", "bob"):
        PreferenceStore(db).save(users[name].id, prefs(), NOW)
    with db.session() as sess:
        sess.add(
            AccountProfileRow(
                user_id=users["bob"].id, source="MANUAL", equity=5_000.0, balance=5_000.0, currency="USD",
                leverage=100.0, risk_percent=None, updated_at=NOW,
            )
        )  # fmt: skip
        for symbol, failed in (("EURUSD", []), ("XAUUSD", ["G2_MIN_LOT"])):
            sess.add(
                SuitabilitySnapshotRow(
                    engine_id=FEED, server="FBS-Demo", symbol=symbol, hour=NOW, computed_at=NOW,
                    asset_class="FOREX_MAJOR", rank=1 if symbol == "XAUUSD" else 2, eligible=not failed,
                    overall=80.0, now_score=60.0, failed_gates=failed,
                    payload={"metrics": {"min_lot": 0.01, "min_lot_risk": 2.0, "currency": "USD", "lot": 0.3,
                                         "risk_money": 9.9, "required_equity": 400.0}},
                )
            )  # fmt: skip
    store(db, "EURUSD", 1.10, NOW - timedelta(minutes=15))  # spec + a close: bob's sizing
    add_opportunity(db, "o1")
    with TestClient(app, base_url="https://testserver") as client:
        yield Rig(app, client)


class TestAccess:
    def test_who_reads_which_engine(self, rig: Rig) -> None:
        assert engine_users(rig.ctx.db, FEED) == [rig.ids["alice"], rig.ids["bob"]]  # carol runs her own
        assert engine_users(rig.ctx.db, OWN) == [rig.ids["carol"]]
        for name, expected in (
            ("alice", (FEED, True)),
            ("bob", (FEED, False)),
            ("carol", (OWN, True)),
            ("ada", (None, False)),
        ):
            rig.login(name)
            body = rig.get("/me/feed").json()
            assert (body["engine_id"], body["own"]) == expected, name
        rig.login("carol")  # a user with an engine of her own reads no one else's
        assert rig.get(f"/engines/{FEED}/ranking").json()["error"]["code"] == "engine_not_found"

    def test_a_subscriber_never_sees_the_owners_account(self, rig: Rig) -> None:
        rig.login("bob")
        [item] = rig.get(f"/engines/{FEED}/opportunities").json()["items"]
        detail = rig.get(f"/engines/{FEED}/opportunities/o1").json()
        for doc in (item, detail):
            assert not OWNER_ONLY_FIELDS & set(doc), set(doc) & OWNER_ONLY_FIELDS
        assert detail["my_sizing"]["available"] and detail["my_sizing"]["currency"] == "USD"
        assert detail["my_sizing"]["budget"] == 25.0  # 0.5% of bob's 5,000, not the owner's equity
        for route in (
            "status",
            "positions",
            "decisions",
            "account",
            "commands",
        ):  # trading data stays private
            assert rig.get(f"/engines/{FEED}/{route}").json()["error"]["code"] == "engine_not_found", route
        metrics = rig.get(f"/engines/{FEED}/ranking/EURUSD").json()["payload"]["metrics"]
        assert "lot" not in metrics and "risk_money" not in metrics and metrics["min_lot"] == 0.01

    def test_a_personal_ranking_on_the_users_equity(self, rig: Rig) -> None:
        rig.login("bob")
        body = rig.get(f"/engines/{FEED}/ranking").json()
        assert body["personal"] is True
        gold = next(i for i in body["items"] if i["symbol"] == "XAUUSD")
        assert (
            gold["failed_gates"] == [] and gold["personal"]["eligible"] is True
        )  # the owner's G2, not bob's
        assert gold["personal"]["risk_budget"] == 25.0 and gold["personal"]["lot"] == 0.12
        assert gold["personal"]["required_equity"] is None  # affordable: no hint
        assert gold["metrics"] == {} and gold["gates"] == []  # no owner sizing, no account gates
        assert body["account"] == {
            "source": "MANUAL",
            "equity": 5000.0,
            "balance": 5000.0,
            "leverage": 100.0,
            "currency": "USD",
            "risk_percent": 0.5,
        }
        rig.login("alice")
        owner = rig.get(f"/engines/{FEED}/ranking").json()
        assert "personal" not in owner and owner["items"][0]["symbol"] == "XAUUSD"
        assert owner["items"][0]["metrics"]["required_equity"] == 400.0


class TestAlerts:
    def test_each_user_gets_their_own_alert(self, rig: Rig) -> None:
        OpportunityAlerter(rig.ctx.db, rig.clock, config=lambda: CONFIG).run()
        [owner], [sub] = rig.alerts("alice"), rig.alerts("bob")
        assert "1) ราคาตลาด" in owner.payload["push"]["body"]  # the owner's MT5 entry plan
        assert sub.payload["plan"] == [] and sub.payload["heat_after"] is None
        assert "1)" not in sub.payload["push"]["body"] and "heat" not in sub.payload["push"]["body"]
        with rig.ctx.db.session() as sess:
            mine = sess.get(OpportunityAlertRow, (rig.ids["bob"], FEED, "o1"))
            assert mine is not None and mine.currency == "USD" and mine.risk_money is not None
            assert 0 < mine.risk_money <= 25.0 and mine.lot is not None
            assert f"ล็อต {mine.lot:g}" in sub.payload["push"]["body"]  # bob's lot, not the owner's 0.1
            assert mine.selection["preset"] == "ALL"  # the theory selection it was evaluated with
        rig.login("bob")
        [record] = rig.get("/me/alerts").json()["items"]
        assert record["opportunity_id"] == "o1" and record["badge"] == "ACTIVE" and record["lot"] == mine.lot

    def test_accuracy_counts_my_alerts_at_my_risk(self, rig: Rig) -> None:
        OpportunityAlerter(rig.ctx.db, rig.clock, config=lambda: CONFIG).run()
        shadow(rig.ctx.db, "o1")
        with rig.ctx.db.session() as sess:
            sess.execute(update(ShadowTradeRow).values(engine_id=FEED))
            r_net = sess.scalar(select(ShadowTradeRow.r_net))
            bob_risk = sess.get(OpportunityAlertRow, (rig.ids["bob"], FEED, "o1")).risk_money  # type: ignore[union-attr]
        rig.login("bob")
        acc = rig.get(f"/engines/{FEED}/accuracy").json()
        assert acc["scope"] == "my_alerts" and acc["live"]["summary"]["n"] == 1
        assert acc["live"]["summary"]["total_pnl"] == pytest.approx(r_net * bob_risk)
        rig.login("alice")
        assert (
            rig.get(f"/engines/{FEED}/accuracy").json().get("scope") is None
        )  # the owner sees the whole record


def test_the_engine_computes_the_union_of_its_users(rig: Rig) -> None:
    store_ = PreferenceStore(rig.ctx.db)

    def switch_off_fibonacci(name: str) -> None:
        p = store_.get(rig.ids[name])
        theories = p.theories.model_copy(update={"detectors": {"fib.retracement": False}})
        store_.save(rig.ids[name], p.model_copy(update={"theories": theories}), NOW)

    def detectors() -> set[str]:
        headers = Signer(FEED, SECRET.encode(), rig.clock).headers("GET", ADVISORY_CONFIG_PATH)
        return set(rig.client.get(ADVISORY_CONFIG_PATH, headers=headers).json()["detectors"])

    switch_off_fibonacci("alice")
    assert "fib.retracement" in detectors()  # bob still wants it, and his FREE plan allows Fibonacci
    switch_off_fibonacci("bob")
    assert "fib.retracement" not in detectors()  # nobody wants it: the engine stops computing it


def test_a_subscribers_entry_plan_is_sized_on_their_account(rig: Rig) -> None:
    """(rev. 3) The user's own split (here SAME_PRICE, two parts) on their own MANUAL account."""
    from app.advisory.preferences import EntryPlanPreferences, SplitMode

    store_ = PreferenceStore(rig.ctx.db)
    bob = rig.ids["bob"]
    plan = EntryPlanPreferences(mode=SplitMode.SAME_PRICE, parts=2)
    store_.save(bob, store_.get(bob).model_copy(update={"entry_plan": plan}), NOW)
    rig.login("bob")
    sizing = rig.get(f"/engines/{FEED}/opportunities/o1").json()["my_sizing"]
    assert sizing["available"] and len(sizing["plan"]) == 2
    assert sum(float(p["risk_money"]) for p in sizing["plan"]) == pytest.approx(sizing["risk_money"])
    OpportunityAlerter(rig.ctx.db, rig.clock, config=lambda: CONFIG).run()
    [sub] = rig.alerts("bob")
    body = sub.payload["push"]["body"]
    assert "1) ราคาตลาด" in body and "2) ราคาตลาด" in body and "heat" not in body  # bob's own heat is unknown
