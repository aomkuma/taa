"""Opportunity alerts in the worker: personalized push with the entry plan, rate limits, quiet windows,
market sessions, the silent same-tag replacement, delivery through Web Push (TAA-810)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.advisory.preferences import (
    AdvisoryPreferences,
    AlertMetric,
    AlertPreferences,
    Watchlist,
    WatchlistKind,
)
from app.config import AppConfig
from app.core.clock import ManualClock
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import (
    DecisionCheckRow,
    DecisionRecordRow,
    NotificationRow,
    OpportunityAlertRow,
    OpportunityRow,
    PushSubscriptionRow,
)
from app.web.advisory import PreferenceStore
from app.web.auth import AuthKeys, AuthService
from app.web.engines import EngineRegistry
from app.worker.jobs import JobQueue
from app.worker.opportunities import OpportunityAlerter
from app.worker.push import PushDispatcher, SendResult
from app.worker.push import handlers as push_handlers
from app.worker.service import Worker
from tests.sync_data import sample_rows
from tests.unit.test_personalize import NOW, opportunity

ENGINE = "eng-a"
PLAN = [
    {"order_type": "MARKET", "entry": "1.1", "volume": "0.15", "taps": 15, "take_profit": "1.104", "risk_money": "30"},
    {"order_type": "LIMIT", "entry": "1.0995", "volume": "0.1", "taps": 10, "take_profit": None, "risk_money": "15"},
]  # fmt: skip
CONFIG = AppConfig()


def prefs(**alerts: Any) -> AdvisoryPreferences:
    return AdvisoryPreferences(
        watchlists=[Watchlist(name="Favourites", kind=WatchlistKind.FAVOURITES, symbols=["EURUSD"])],
        alerts=AlertPreferences(metric=AlertMetric.SETUP_STRENGTH, threshold=10, **alerts),
    )


class Cloud:
    def __init__(self, db: Database) -> None:
        self.db, self.clock = db, ManualClock(NOW)
        audit = AuditLog(db, "web", self.clock)
        auth = AuthService(db, self.clock, audit, AuthKeys("s" * 40))
        self.owner = auth.create_user(
            "alice", "correct horse battery staple", "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        )
        EngineRegistry(db, self.clock, audit, "s" * 40).import_env(
            self.owner, ENGINE, "e" * 40, None, actor="t"
        )
        self.alerter = OpportunityAlerter(db, self.clock, config=lambda: CONFIG)
        self.set_prefs(prefs())

    def set_prefs(self, p: AdvisoryPreferences) -> None:
        PreferenceStore(self.db).save(self.owner.id, p, self.clock.now_utc())

    def add(self, oid: str = "o1", heat: float = 1.25, **over: Any) -> None:
        opp = opportunity()
        samples = {type(r): r for r in sample_rows()}
        row, decision = samples[OpportunityRow], samples[DecisionRecordRow]
        assert isinstance(row, OpportunityRow) and isinstance(decision, DecisionRecordRow)
        for name in ("strategy", "symbol", "asset_class", "side", "entry", "stop_loss", "take_profit", "rr",
                     "created_at", "valid_until", "valid_reason", "lot", "risk_money", "currency"):  # fmt: skip
            setattr(row, name, getattr(opp, name))
        row.engine_id, row.opportunity_id, row.decision_id = ENGINE, oid, f"d-{oid}"
        row.signal, row.features, row.status = opp.signal.to_dict(), dict(opp.features), "CANDIDATE"
        for name, value in over.items():
            setattr(row, name, value)
        decision.engine_id, decision.decision_id, decision.plan = ENGINE, f"d-{oid}", PLAN
        with self.db.session() as sess:
            sess.add_all([row, decision])
            sess.add(
                DecisionCheckRow(
                    engine_id=ENGINE, decision_id=f"d-{oid}", seq=0, name="max_total_open_risk",
                    reason="MAX_TOTAL_OPEN_RISK", passed=heat <= 1.5, kind="ACCOUNT", value=heat, threshold=1.5,
                )
            )  # fmt: skip

    def notes(self, type_: str | None = None) -> list[NotificationRow]:
        with self.db.session() as sess:
            query = select(NotificationRow).order_by(
                NotificationRow.created_at, NotificationRow.notification_id
            )
            if type_:
                query = query.where(NotificationRow.type == type_)
            return list(sess.scalars(query))

    def status(self, oid: str, value: str, reason: str = "") -> None:
        with self.db.session() as sess:
            row = sess.get(OpportunityRow, (ENGINE, oid))
            assert row is not None
            row.status, row.status_reason = value, reason


@pytest.fixture
def cloud(db: Database) -> Cloud:
    return Cloud(db)


class TestAlerts:
    def test_an_alert_carries_the_entry_plan_once(self, cloud: Cloud) -> None:
        cloud.add()
        assert cloud.alerter.run() == "1 alerts, 0 updates"
        [note] = cloud.notes("OPPORTUNITY")
        push = note.payload["push"]
        assert push["tag"] == "o1" and push["badge"] == 1 and push["silent"] is False
        assert "1) ราคาตลาด 0.15 ล็อต (15 ครั้ง) @ 1.1 · TP 1.104" in push["body"]
        assert "ความเสี่ยงรวม 45.00 USD · heat หลังเข้า 1.25%" in push["body"]
        assert note.payload["plan"][1]["order_type"] == "LIMIT" and note.payload["heat_after"] == 1.25
        assert note.user_id == cloud.owner.id and note.engine_id == ENGINE
        assert cloud.alerter.run() is None  # never twice
        with cloud.db.session() as sess:
            [alert] = sess.scalars(select(OpportunityAlertRow)).all()
            assert alert.status == "SENT" and alert.notification_id == note.notification_id

    def test_the_badge_counts_open_alerts_and_the_cooldown_holds(self, cloud: Cloud) -> None:
        cloud.set_prefs(prefs(rate_limits={"symbol_cooldown_minutes": 0, "max_alerts_per_hour": 10}))
        cloud.add("o1")
        cloud.add("o2")
        cloud.alerter.run()
        assert [n.payload["push"]["badge"] for n in cloud.notes("OPPORTUNITY")] == [1, 2]
        cloud.set_prefs(prefs())  # default cooldown: a third one on EURUSD waits
        cloud.add("o3")
        assert cloud.alerter.run() is None

    @pytest.mark.parametrize(
        ("change", "why"),
        [
            ({"watchlists": []}, "not watched"),
            ({"alerts": {"metric": "SETUP_STRENGTH", "threshold": 99}}, "below the threshold"),
            (
                {
                    "alerts": {
                        "metric": "SETUP_STRENGTH",
                        "threshold": 10,
                        "windows": [{"days": [5], "start": "08:00", "end": "09:00"}],
                    }
                },
                "quiet: outside the window",
            ),
        ],
    )
    def test_no_alert(self, cloud: Cloud, change: dict[str, Any], why: str) -> None:
        cloud.set_prefs(AdvisoryPreferences.model_validate(prefs().model_dump(mode="json") | change))
        cloud.add()
        assert cloud.alerter.run() is None, why
        assert cloud.notes("OPPORTUNITY") == []

    def test_closed_markets_wait_for_the_users_sessions(self, cloud: Cloud) -> None:
        saturday = NOW + timedelta(days=3)
        cloud.clock.set(saturday)
        cloud.add(created_at=saturday, valid_until=saturday + timedelta(minutes=30))
        assert cloud.alerter.run() is None
        cloud.set_prefs(prefs(respect_market_sessions=False))
        assert cloud.alerter.run() == "1 alerts, 0 updates"


class TestReplacement:
    def test_a_silent_same_tag_update_when_it_ends(self, cloud: Cloud) -> None:
        cloud.add()
        cloud.alerter.run()
        cloud.status("o1", "INVALIDATED", "PRICE_DRIFT")
        assert cloud.alerter.run() == "0 alerts, 1 updates"
        [update] = cloud.notes("OPPORTUNITY_UPDATE")
        push = update.payload["push"]
        assert push["tag"] == "o1" and push["silent"] is True and push["badge"] == 0
        assert push["body"] == "เงื่อนไขไม่เป็นจริงแล้ว: ราคาวิ่งห่างจากจุดเข้า"
        assert cloud.alerter.run() is None  # once

    def test_the_window_passing_counts_as_the_end(self, cloud: Cloud) -> None:
        cloud.add()
        cloud.alerter.run()
        cloud.clock.advance(31 * 60)
        cloud.alerter.run()
        [update] = cloud.notes("OPPORTUNITY_UPDATE")
        assert update.payload["status"] == "EXPIRED"

    def test_updates_can_be_switched_off(self, cloud: Cloud) -> None:
        cloud.add()
        cloud.alerter.run()
        cloud.set_prefs(prefs(expiry_updates=False))
        cloud.status("o1", "EXPIRED", "SIGNAL_LIFETIME")
        assert cloud.alerter.run() is None and cloud.notes("OPPORTUNITY_UPDATE") == []
        with cloud.db.session() as sess:
            assert sess.scalars(select(OpportunityAlertRow.status)).all() == ["REPLACED"]


def test_alerts_and_updates_reach_the_device(cloud: Cloud) -> None:
    sent: list[dict[str, Any]] = []
    with cloud.db.session() as sess:
        sess.add(
            PushSubscriptionRow(
                subscription_id="s1", user_id=cloud.owner.id, endpoint="https://fcm.googleapis.com/fcm/send/x",
                p256dh="B" * 87, auth="a" * 22, created_at=NOW,
            )
        )  # fmt: skip
    push = PushDispatcher(cloud.db, cloud.clock, JobQueue(cloud.db, cloud.clock), lambda s, d, t: sent.append(json.loads(d)) or SendResult(201))  # fmt: skip
    worker = Worker(cloud.db, cloud.clock, handlers=push_handlers(push), tasks=[], worker_id="w1")

    def deliver() -> None:
        push.dispatch()
        while worker.step():
            pass

    cloud.add()
    cloud.alerter.run()
    deliver()
    cloud.status("o1", "FOLLOWED")
    cloud.alerter.run()
    deliver()
    assert [(m["type"], m["tag"], m["silent"]) for m in sent] == [
        ("OPPORTUNITY", "o1", False),
        ("OPPORTUNITY_UPDATE", "o1", True),
    ]
    assert sent[0]["url"] == "/opportunities/o1" and sent[1]["body"] == "คุณเปิดออเดอร์แล้ว"


class TestRiskBudget:
    def test_a_full_budget_pauses_alerts_until_one_fits_again(self, cloud: Cloud) -> None:
        cloud.add("o1", heat=2.4)  # positions already use the budget: heat after would be 2.4% > 1.5%
        assert cloud.alerter.run() is None and cloud.notes("OPPORTUNITY") == []
        cloud.set_prefs(prefs(rate_limits={"symbol_cooldown_minutes": 0, "max_alerts_per_hour": 10}))
        cloud.add("o2", heat=1.2)  # positions were closed meanwhile: this one fits
        assert cloud.alerter.run() == "1 alerts, 0 updates"
        assert [n.payload["opportunity_id"] for n in cloud.notes("OPPORTUNITY")] == ["o2"]

    def test_warn_sends_it_with_the_warning(self, cloud: Cloud) -> None:
        cloud.set_prefs(prefs(when_risk_full="WARN"))
        cloud.add("o1", heat=2.4)
        cloud.alerter.run()
        [note] = cloud.notes("OPPORTUNITY")
        assert note.payload["risk_warnings"] == ["HEAT_LIMIT"]
        assert note.payload["push"]["body"].startswith("⚠ เกินงบความเสี่ยง: heat 2.40% > 1.50%")


def test_the_plan_limits_alerts(cloud: Cloud) -> None:
    """TAA-8A2: the personalizer gets the user's entitlements (here an asset-class allow-list)."""
    from app.storage.models import EntitlementOverrideRow
    from app.web.entitlements import seed_plans

    seed_plans(cloud.db, NOW)
    with cloud.db.session() as sess:
        sess.add(
            EntitlementOverrideRow(
                user_id=cloud.owner.id, key="ASSET_CLASSES", value=["METAL"], created_at=NOW
            )
        )
    cloud.add()
    assert cloud.alerter.run() is None and cloud.notes("OPPORTUNITY") == []
