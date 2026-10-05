"""Engine heartbeats: market schedule, emitter, ingest, and the worker's offline/back watchdog (TAA-705)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.advisory.market_sessions import SESSIONS, next_start
from app.config import SyncConfig
from app.core.clock import ManualClock
from app.core.ids import new_id
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import EngineHeartbeatRow, NotificationRow, OutboxEventRow
from app.sync.command_queue import CommandQueue
from app.sync.heartbeat import HeartbeatEmitter, HeartbeatPayload, market_open_at, market_state
from app.sync.ingest import IngestService
from app.sync.outbox import Outbox
from app.sync.stream import TOPICS, StreamLog
from app.web.engines import EngineRegistry
from app.worker.watchdog import EngineWatchdog
from tests.strategy_data import EURUSD_SPEC

WEDNESDAY = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)  # FX open (London and New York later)
SATURDAY = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)  # FX closed, crypto open
BTCUSD = dataclasses.replace(EURUSD_SPEC, name="BTCUSD", currency_base="BTC", currency_profit="USD")


class TestMarketState:
    def test_fx_stays_open_through_the_session_handovers_until_friday(self) -> None:
        is_open, change = market_state([EURUSD_SPEC], WEDNESDAY)
        assert is_open and change == datetime(2026, 10, 2, 21, 0, tzinfo=UTC)  # Friday 17:00 New York (EDT)

    def test_a_single_session_market_closes_with_its_session(self) -> None:
        dax = dataclasses.replace(
            EURUSD_SPEC, name="DE40", currency_base="EUR", currency_profit="EUR", path="Indices/DE40"
        )
        is_open, change = market_state([dax], WEDNESDAY)
        assert is_open and change == datetime(2026, 9, 30, 15, 30, tzinfo=UTC)  # 17:30 CEST

    def test_fx_at_the_weekend_reopens_with_sydney(self) -> None:
        is_open, change = market_state([EURUSD_SPEC], SATURDAY)
        assert not is_open and change == next_start(SESSIONS["SYDNEY"], SATURDAY)

    def test_crypto_never_closes(self) -> None:
        assert market_state([EURUSD_SPEC, BTCUSD], SATURDAY) == (True, None)
        assert market_state([], SATURDAY) == (False, None)

    @pytest.mark.parametrize(
        ("is_open", "change", "at", "expected"),
        [
            (True, None, SATURDAY, True),
            (True, WEDNESDAY, WEDNESDAY - timedelta(seconds=1), True),
            (True, WEDNESDAY, WEDNESDAY, False),
            (False, WEDNESDAY, WEDNESDAY - timedelta(seconds=1), False),
            (False, WEDNESDAY, WEDNESDAY, True),
            (False, None, SATURDAY, False),
        ],
    )
    def test_the_schedule_at_a_later_time(
        self, is_open: bool, change: datetime | None, at: datetime, expected: bool
    ) -> None:
        assert market_open_at(is_open, change, at) is expected


def beat(at: datetime, **overrides: Any) -> dict[str, Any]:
    return {
        "at": at,
        "run_id": "r1",
        "mode": "PAPER",
        "state": "running",
        "connected": True,
        "clock_verified": True,
        "kill_switch": False,
        "open_positions": 1,
        "cycles": 10,
        "market_open": True,
        "market_change_at": at + timedelta(hours=8),
        "outbox_pending": 0,
        "quotes": [{"symbol": "EURUSD", "bid": 1.1, "ask": 1.1002, "spread_points": 2.0, "time": at}],
    } | overrides


class TestEmitter:
    def test_heartbeats_coalesce_and_follow_the_interval(self, db: Database) -> None:
        clock = ManualClock(WEDNESDAY)
        emitter = HeartbeatEmitter(Outbox(db, clock, SyncConfig()), every=10.0)
        assert emitter.maybe_emit(0.0, lambda: beat(clock.now_utc()))
        assert not emitter.maybe_emit(9.9, lambda: beat(clock.now_utc()))
        assert emitter.maybe_emit(10.0, lambda: beat(clock.now_utc(), cycles=11))
        with db.session() as sess:
            [row] = sess.scalars(select(OutboxEventRow)).all()  # only the newest is waiting
            assert row.type == "heartbeat" and row.priority == 2 and row.payload["cycles"] == 11

    def test_the_payload_is_strict(self) -> None:
        for bad in (
            {"state": "sleeping"},
            {"extra": 1},
            {"open_positions": -1},
            {"at": "2026-09-30T10:00:00"},
            {"disabled_strategies": ["s"] * 65},
            {"disabled_strategies": "s"},
        ):
            with pytest.raises(ValidationError):
                HeartbeatPayload.model_validate(beat(WEDNESDAY) | bad)
        assert HeartbeatPayload.model_validate(beat(WEDNESDAY)).disabled_strategies is None  # before TAA-909
        assert HeartbeatPayload.model_validate(
            beat(WEDNESDAY) | {"disabled_strategies": ["a"]}
        ).disabled_strategies


ENGINE = "eng-1"


class Cloud:
    """A cloud database with one registered engine, the ingest service and the watchdog."""

    def __init__(self, db: Database, clock: ManualClock) -> None:
        self.db, self.clock = db, clock
        audit = AuditLog(db, "web", clock)
        self.registry = EngineRegistry(db, clock, audit, "s" * 40)
        from app.web.auth import AuthKeys, AuthService

        auth = AuthService(db, clock, audit, AuthKeys("s" * 40))
        self.owner = auth.create_user(
            "alice", "correct horse battery staple", "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        )
        self.registry.import_env(self.owner, ENGINE, "e" * 40, None, actor="test")
        self.ingest = IngestService(db, clock, CommandQueue(db, clock), audit=audit)
        self.watchdog = EngineWatchdog(db, clock)

    def send(self, payload: dict[str, Any]) -> Any:
        event = {
            "event_id": new_id(),
            "type": "heartbeat",
            "occurred_at_utc": self.clock.now_utc().isoformat(),
            "payload": HeartbeatPayload.model_validate(payload).model_dump(mode="json"),
        }
        doc = {
            "schema": 1,
            "engine_id": ENGINE,
            "sent_at_utc": self.clock.now_utc().isoformat(),
            "events": [event],
        }
        return self.ingest.ingest(ENGINE, doc)

    def row(self) -> EngineHeartbeatRow:
        with self.db.session() as sess:
            row = sess.get(EngineHeartbeatRow, ENGINE)
            assert row is not None
            return row

    def notes(self) -> list[tuple[str, dict[str, Any]]]:
        with self.db.session() as sess:
            rows = sess.scalars(select(NotificationRow).order_by(NotificationRow.notification_id)).all()
            return [(r.type, dict(r.payload)) for r in rows]


@pytest.fixture
def cloud(db: Database) -> Cloud:
    return Cloud(db, ManualClock(WEDNESDAY))


class TestIngest:
    def test_the_newest_heartbeat_is_kept_and_streamed(self, cloud: Cloud) -> None:
        assert cloud.send(beat(WEDNESDAY)).accepted == 1
        row = cloud.row()
        assert row.state == "running" and row.connected and row.market_open and row.watch_status == "ONLINE"
        assert row.payload["cycles"] == 10 and row.payload["quotes"][0]["symbol"] == "EURUSD"
        older = cloud.send(beat(WEDNESDAY - timedelta(seconds=10), cycles=9))
        assert older.duplicates == 1 and cloud.row().payload["cycles"] == 10
        events = StreamLog(cloud.db, cloud.clock).read(ENGINE, 0, TOPICS, 10)[0]
        assert [(e.topic, e.type) for e in events] == [("status", "heartbeat"), ("quotes", "quotes")]
        assert events[1].item["quotes"][0]["symbol"] == "EURUSD"
        assert "quotes" not in events[0].item  # the status event stays small

    def test_forming_bars_are_kept_but_not_streamed(self, cloud: Cloud) -> None:
        bar = {
            "symbol": "EURUSD",
            "timeframe": "M15",
            "open_time": WEDNESDAY,
            "open": 1.1,
            "high": 1.102,
            "low": 1.099,
            "close": 1.101,
            "tick_volume": 42,
        }
        assert cloud.send(beat(WEDNESDAY, forming=[bar])).accepted == 1
        assert cloud.row().payload["forming"][0]["close"] == 1.101
        events = StreamLog(cloud.db, cloud.clock).read(ENGINE, 0, TOPICS, 10)[0]
        assert "forming" not in events[0].item
        with pytest.raises(ValidationError):
            HeartbeatPayload.model_validate(beat(WEDNESDAY, forming=[bar | {"timeframe": "M2"}]))

    def test_the_account_snapshot_is_kept_with_the_heartbeat(self, cloud: Cloud) -> None:
        account = {
            "as_of": WEDNESDAY,
            "backend": "paper",
            "currency": "USD",
            "balance": 10_000.0,
            "equity": 9_950.0,
            "margin": 100.0,
            "margin_free": 9_850.0,
            "day_pnl": -50.0,
            "day_pnl_percent": -0.5,
            "week_pnl": None,
            "week_pnl_percent": None,
            "drawdown_percent": 0.5,
            "open_risk": 25.0,
            "heat_percent": 0.2513,
            "unknown_risk_positions": 0,
            "consecutive_losses": 1,
            "limits": {
                "daily_loss_percent": 2.0,
                "weekly_loss_percent": 4.0,
                "drawdown_percent": 10.0,
                "heat_percent": 1.5,
                "consecutive_losses": 4,
            },
        }
        assert cloud.send(beat(WEDNESDAY, account=account)).accepted == 1
        stored = cloud.row().payload["account"]
        assert stored["equity"] == 9_950.0 and stored["week_pnl"] is None
        assert stored["limits"]["heat_percent"] == 1.5
        with pytest.raises(ValueError, match=r"allow_inf_nan|finite"):
            HeartbeatPayload.model_validate(beat(WEDNESDAY, account=account | {"equity": float("nan")}))
        with pytest.raises(ValueError, match="extra"):
            HeartbeatPayload.model_validate(beat(WEDNESDAY, account=account | {"password": "x"}))

    def test_an_invalid_heartbeat_is_rejected(self, cloud: Cloud) -> None:
        event = {
            "event_id": new_id(),
            "type": "heartbeat",
            "occurred_at_utc": WEDNESDAY.isoformat(),
            "payload": {"at": WEDNESDAY.isoformat(), "state": "running"},
        }
        doc = {"schema": 1, "engine_id": ENGINE, "sent_at_utc": WEDNESDAY.isoformat(), "events": [event]}
        result = cloud.ingest.ingest(ENGINE, doc)
        assert [r.code.value for r in result.rejected] == ["INVALID_PAYLOAD"]


class TestWatchdog:
    def test_silence_while_the_market_is_open_alerts_once_then_back(self, cloud: Cloud) -> None:
        cloud.send(beat(WEDNESDAY))
        cloud.clock.advance(60)
        assert cloud.watchdog.check() == []  # 60 s is not yet silence
        cloud.clock.advance(1)
        assert cloud.watchdog.check() == [f"{ENGINE}:OFFLINE"]
        assert cloud.watchdog.check() == []  # one alert per episode
        row = cloud.row()
        assert row.watch_status == "OFFLINE" and row.offline_reason == "SILENT"
        cloud.clock.advance(300)
        cloud.send(beat(cloud.clock.now_utc()))
        assert cloud.watchdog.check() == [f"{ENGINE}:ONLINE"]
        [(t1, offline), (t2, back)] = cloud.notes()
        assert (t1, t2) == ("ENGINE_OFFLINE", "ENGINE_BACK")
        assert offline == {"label": "imported", "reason": "SILENT", "last_seen_at": WEDNESDAY.isoformat()}
        assert back["downtime_seconds"] == 361 and "balance" not in str(back)
        streamed = StreamLog(cloud.db, cloud.clock).read(ENGINE, 0, ("notifications",), 10)[0]
        assert [e.item["type"] for e in streamed] == ["ENGINE_OFFLINE", "ENGINE_BACK"]

    def test_a_closed_market_waits_for_its_opening(self, cloud: Cloud) -> None:
        opens = WEDNESDAY + timedelta(hours=2)
        cloud.send(beat(WEDNESDAY, market_open=False, market_change_at=opens))
        cloud.clock.advance(3600)
        assert cloud.watchdog.check() == []
        cloud.clock.advance(3600)  # the market opened and the engine is still silent
        assert cloud.watchdog.check() == [f"{ENGINE}:OFFLINE"]

    def test_a_deliberate_stop_alerts_at_once(self, cloud: Cloud) -> None:
        cloud.send(beat(WEDNESDAY, state="stopped"))
        assert cloud.watchdog.check() == [f"{ENGINE}:OFFLINE"]
        assert cloud.notes()[0][1]["reason"] == "STOPPED"

    def test_never_seen_and_revoked_engines_are_quiet(self, cloud: Cloud) -> None:
        cloud.clock.advance(3600)
        assert cloud.watchdog.check() == []  # waiting for first contact
        cloud.send(beat(cloud.clock.now_utc()))
        cloud.registry.revoke(ENGINE, actor="test")
        cloud.clock.advance(3600)
        assert cloud.watchdog.check() == [] and cloud.notes() == []


def test_an_offline_alert_is_pushed_to_the_owners_device(cloud: Cloud) -> None:
    """TAA-705 item 3: the watchdog's notification goes out through the Web Push dispatch (TAA-806)."""
    from app.storage.models import PushSubscriptionRow
    from app.worker.jobs import JobQueue
    from app.worker.push import PushDispatcher, SendResult
    from app.worker.push import handlers as push_handlers
    from app.worker.service import Worker

    sent: list[str] = []
    with cloud.db.session() as sess:
        sess.add(
            PushSubscriptionRow(
                subscription_id="s1",
                user_id=cloud.owner.id,
                endpoint="https://fcm.googleapis.com/fcm/send/x",
                p256dh="B" * 87,
                auth="a" * 22,
                created_at=WEDNESDAY,
            )
        )
    push = PushDispatcher(
        cloud.db,
        cloud.clock,
        JobQueue(cloud.db, cloud.clock),
        lambda s, d, t: sent.append(d) or SendResult(201),
    )
    worker = Worker(cloud.db, cloud.clock, handlers=push_handlers(push), tasks=[], worker_id="w1")
    cloud.send(beat(WEDNESDAY))
    cloud.clock.advance(61)
    cloud.watchdog.check()
    push.dispatch()
    while worker.step():
        pass
    assert len(sent) == 1 and "Engine ออฟไลน์" in sent[0]
