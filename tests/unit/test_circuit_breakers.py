from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config import BreakerConfig, RiskConfig
from app.core.clock import ManualClock
from app.core.enums import Severity, TradingMode
from app.core.errors import SafetyViolation
from app.risk.breaker_monitor import BreakerMonitor
from app.risk.circuit_breaker import BreakerBoard, BreakerEvent, BreakerName, State, default_specs
from app.storage.audit import AuditLog, verify_chain
from app.storage.database import Database
from tests.unit.test_loss_tracker import status

T0 = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
N = BreakerName


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(T0)


def board(
    db: Database,
    clock: ManualClock,
    mode: TradingMode = TradingMode.PAPER,
    events: list[BreakerEvent] | None = None,
) -> BreakerBoard:
    return BreakerBoard(
        db,
        default_specs(BreakerConfig(), consecutive_pause_hours=24),
        clock,
        mode=mode,
        tz_name="Europe/Athens",
        audit=AuditLog(db, "engine", clock),
        notify=None if events is None else events.append,
    )


def state(b: BreakerBoard, name: BreakerName, key: str = "") -> State | None:
    for s in b.statuses():
        if s.name is name and s.scope_key == key:
            return s.state
    return None


class TestBoard:
    def test_trip_blocks_entries_in_scope(self, db: Database, clock: ManualClock) -> None:
        b = board(db, clock)
        assert b.trip(N.DAILY_LOSS, "day P/L -2.1%")
        assert b.trip(N.SPREAD, "wide", "XAUUSD")
        assert {s.name for s in b.blocking("EURUSD")} == {N.DAILY_LOSS}
        assert {s.name for s in b.blocking("XAUUSD")} == {N.DAILY_LOSS, N.SPREAD}
        codes = [c.reason_code for c in b.checks("XAUUSD")]
        assert sorted(codes) == ["BREAKER_OPEN:DAILY_LOSS", "BREAKER_OPEN:SPREAD"]
        assert all(not c.passed for c in b.checks("XAUUSD"))

    def test_no_breakers_one_passing_check(self, db: Database, clock: ManualClock) -> None:
        checks = board(db, clock).checks("EURUSD")
        assert len(checks) == 1 and checks[0].passed

    def test_trip_is_idempotent(self, db: Database, clock: ManualClock) -> None:
        events: list[BreakerEvent] = []
        b = board(db, clock, events=events)
        assert b.trip(N.CLOCK, "offset mismatch")
        assert not b.trip(N.CLOCK, "offset mismatch")
        assert [e.action for e in events] == ["TRIP"]

    def test_half_open_then_closed_after_n_healthy(self, db: Database, clock: ManualClock) -> None:
        events: list[BreakerEvent] = []
        b = board(db, clock, events=events)
        b.trip(N.CONNECTION, "disconnected")
        b.report_healthy(N.CONNECTION)
        assert state(b, N.CONNECTION) is State.HALF_OPEN
        assert b.blocking()  # half-open still blocks entries
        b.report_healthy(N.CONNECTION)
        b.report_healthy(N.CONNECTION)
        assert state(b, N.CONNECTION) is State.CLOSED
        assert [e.action for e in events] == ["TRIP", "HALF_OPEN", "RESET"]

    def test_unhealthy_in_half_open_reopens(self, db: Database, clock: ManualClock) -> None:
        b = board(db, clock)
        b.trip(N.CONNECTION, "down")
        b.report_healthy(N.CONNECTION)
        assert b.trip(N.CONNECTION, "down again")
        b.report_healthy(N.CONNECTION)
        b.report_healthy(N.CONNECTION)
        assert state(b, N.CONNECTION) is State.HALF_OPEN  # the count started over

    def test_recovery_needs_continuous_health(self, db: Database, clock: ManualClock) -> None:
        b = board(db, clock)
        b.trip(N.INVALID_PRICE, "ask < bid", "EURUSD")
        b.report_healthy(N.INVALID_PRICE, "EURUSD")
        clock.advance(29)
        b.report_healthy(N.INVALID_PRICE, "EURUSD")
        assert state(b, N.INVALID_PRICE, "EURUSD") is State.HALF_OPEN
        clock.advance(1)
        b.report_healthy(N.INVALID_PRICE, "EURUSD")
        assert state(b, N.INVALID_PRICE, "EURUSD") is State.CLOSED

    def test_cooldown_and_latch_after_repeated_trips(self, db: Database, clock: ManualClock) -> None:
        b = board(db, clock)
        for _ in range(2):
            b.trip(N.UNHANDLED_EXCEPTION, "boom")
            clock.advance(600)
            b.tick()
            assert state(b, N.UNHANDLED_EXCEPTION) is State.CLOSED
        b.trip(N.UNHANDLED_EXCEPTION, "boom")  # third trip today: latched
        clock.advance(3600)
        b.tick()
        assert state(b, N.UNHANDLED_EXCEPTION) is State.OPEN
        b.reset(N.UNHANDLED_EXCEPTION, actor="cli:operator", reason="fixed the bug")
        assert state(b, N.UNHANDLED_EXCEPTION) is State.CLOSED

    def test_healthy_reports_do_not_reset_time_based_breakers(self, db: Database, clock: ManualClock) -> None:
        b = board(db, clock)
        b.trip(N.DAILY_LOSS, "-2%")
        b.report_healthy(N.DAILY_LOSS)
        assert state(b, N.DAILY_LOSS) is State.OPEN

    def test_daily_and_weekly_resets_follow_broker_time(self, db: Database, clock: ManualClock) -> None:
        b = board(db, clock)
        b.trip(N.DAILY_LOSS, "-2%")
        b.trip(N.WEEKLY_LOSS, "-4%")
        clock.set(datetime(2026, 9, 30, 20, 59, tzinfo=UTC))  # 23:59 in Athens
        b.tick()
        assert state(b, N.DAILY_LOSS) is State.OPEN
        clock.set(datetime(2026, 9, 30, 21, 0, tzinfo=UTC))  # broker midnight
        b.tick()
        assert state(b, N.DAILY_LOSS) is State.CLOSED
        assert state(b, N.WEEKLY_LOSS) is State.OPEN
        clock.set(datetime(2026, 10, 4, 21, 0, tzinfo=UTC))  # Monday 00:00 broker time
        b.tick()
        assert state(b, N.WEEKLY_LOSS) is State.CLOSED

    def test_manual_only_breakers(self, db: Database, clock: ManualClock) -> None:
        b = board(db, clock)
        b.trip(N.ACCOUNT_CHANGE, "login changed")
        b.trip(N.MAX_DRAWDOWN, "drawdown 10.2%")
        clock.advance(7 * 86_400)
        b.tick()
        b.report_healthy(N.ACCOUNT_CHANGE)
        assert state(b, N.ACCOUNT_CHANGE) is State.OPEN
        with pytest.raises(SafetyViolation):
            b.reset(N.ACCOUNT_CHANGE, actor="", reason="x")
        with pytest.raises(SafetyViolation, match="acknowledgement"):
            b.reset(N.MAX_DRAWDOWN, actor="cli:operator", reason="reviewed")
        b.reset(N.MAX_DRAWDOWN, actor="cli:operator", reason="reviewed", acknowledge=True)
        assert state(b, N.MAX_DRAWDOWN) is State.CLOSED

    def test_order_path_breakers_inactive_in_milestone_1(self, db: Database, clock: ManualClock) -> None:
        paper = board(db, clock, TradingMode.PAPER)
        assert not paper.trip(N.ORDER_FAILURES, "3 failures")
        assert not paper.blocking()
        demo = board(db, clock, TradingMode.DEMO)
        assert demo.trip(N.DUPLICATE_EXECUTION, "unknown order state")
        assert demo.blocking()

    def test_state_survives_restart(self, db: Database, clock: ManualClock) -> None:
        board(db, clock).trip(N.MAX_DRAWDOWN, "10%")
        assert [s.name for s in board(db, clock).blocking()] == [N.MAX_DRAWDOWN]

    def test_events_are_audited_and_notified(self, db: Database, clock: ManualClock) -> None:
        events: list[BreakerEvent] = []
        b = board(db, clock, events=events)
        b.trip(N.STORAGE, "disk 0.5 GB", metrics={"free_gb": 0.5})
        b.report_healthy(N.STORAGE)
        assert [(e.action, e.severity) for e in events] == [
            ("TRIP", Severity.CRITICAL),
            ("HALF_OPEN", Severity.CRITICAL),
            ("RESET", Severity.CRITICAL),
        ]
        assert events[0].metrics == {"free_gb": 0.5}
        report = verify_chain(db, "engine")
        assert report.ok
        assert report.events_checked == 3


class TestMonitor:
    def monitor(self, db: Database, clock: ManualClock) -> tuple[BreakerMonitor, BreakerBoard]:
        b = board(db, clock)
        return BreakerMonitor(b, BreakerConfig(), RiskConfig(), clock), b

    def test_connection_grace(self, db: Database, clock: ManualClock) -> None:
        m, b = self.monitor(db, clock)
        m.observe_connection(False)
        clock.advance(14)
        m.observe_connection(False)
        assert not b.blocking()
        clock.advance(1)
        m.observe_connection(False)
        assert state(b, N.CONNECTION) is State.OPEN
        for _ in range(3):
            m.observe_connection(True)
        assert state(b, N.CONNECTION) is State.CLOSED

    def test_short_blips_never_trip(self, db: Database, clock: ManualClock) -> None:
        m, b = self.monitor(db, clock)
        for _ in range(5):
            m.observe_connection(False)
            clock.advance(10)
            m.observe_connection(True)
        assert not b.blocking()

    def quote(self, m: BreakerMonitor, **kw: object) -> None:
        base: dict[str, object] = {
            "bid": 1.1,
            "ask": 1.10008,
            "spread_points": 8.0,
            "spread_limit": 30.0,
            "tick_age_seconds": 1.0,
            "in_session": True,
        }
        base.update(kw)
        m.observe_quote("EURUSD", **base)  # type: ignore[arg-type]

    def test_invalid_prices(self, db: Database, clock: ManualClock) -> None:
        m, b = self.monitor(db, clock)
        self.quote(m, ask=1.0999)
        assert state(b, N.INVALID_PRICE, "EURUSD") is State.OPEN
        m2, b2 = self.monitor(Database("sqlite://"), clock)
        b2.db.create_all()
        self.quote(m2, previous_mid=1.09, atr=0.001)  # a 10-ATR jump
        assert state(b2, N.INVALID_PRICE, "EURUSD") is State.OPEN

    def test_wide_spread_must_persist_but_a_spike_trips_at_once(
        self, db: Database, clock: ManualClock
    ) -> None:
        m, b = self.monitor(db, clock)
        self.quote(m, spread_points=35.0)
        clock.advance(29)
        self.quote(m, spread_points=35.0)
        assert state(b, N.SPREAD, "EURUSD") is None
        clock.advance(1)
        self.quote(m, spread_points=35.0)
        assert state(b, N.SPREAD, "EURUSD") is State.OPEN
        m2, b2 = self.monitor(Database("sqlite://"), clock)
        b2.db.create_all()
        self.quote(m2, spread_points=25.0, median_spread=8.0)  # under the limit, but 3x the median
        assert state(b2, N.SPREAD, "EURUSD") is State.OPEN

    def test_stale_only_in_session(self, db: Database, clock: ManualClock) -> None:
        m, b = self.monitor(db, clock)
        self.quote(m, tick_age_seconds=600.0, in_session=False)
        assert state(b, N.STALE_DATA, "EURUSD") is None
        self.quote(m, tick_age_seconds=600.0)
        assert state(b, N.STALE_DATA, "EURUSD") is State.OPEN
        self.quote(m)
        assert state(b, N.STALE_DATA, "EURUSD") is State.CLOSED

    def test_losses_trip_their_breakers(self, db: Database, clock: ManualClock) -> None:
        m, b = self.monitor(db, clock)
        m.observe_losses(status(equity=9_780.0, adjusted_equity=9_780.0, hwm=11_000.0))
        assert {s.name for s in b.blocking()} == {N.DAILY_LOSS, N.MAX_DRAWDOWN}
        m.observe_losses(status(consecutive_losses=4, last_loss_at=T0))
        assert state(b, N.CONSECUTIVE_LOSSES) is State.OPEN
        clock.advance(24 * 3600)
        b.tick()
        assert state(b, N.CONSECUTIVE_LOSSES) is State.CLOSED

    def test_slippage(self, db: Database, clock: ManualClock) -> None:
        m, b = self.monitor(db, clock)
        m.observe_fill("EURUSD", 6.0)
        m.observe_fill("EURUSD", 6.0)
        assert state(b, N.SLIPPAGE, "EURUSD") is None
        m.observe_fill("EURUSD", 6.0)
        assert state(b, N.SLIPPAGE, "EURUSD") is State.OPEN
        m.observe_fill("GBPUSD", 11.0)
        assert state(b, N.SLIPPAGE, "GBPUSD") is State.OPEN

    def test_exceptions_and_account_change(self, db: Database, clock: ManualClock) -> None:
        m, b = self.monitor(db, clock)
        m.record_exception("decision", RuntimeError("bad"))
        m.account_changed("server changed")
        assert {s.name for s in b.blocking()} == {N.UNHANDLED_EXCEPTION, N.ACCOUNT_CHANGE}
        assert any("RuntimeError" in s.reason for s in b.statuses())


def test_every_a10_breaker_has_a_spec() -> None:
    specs = default_specs(BreakerConfig(), consecutive_pause_hours=24)
    assert set(specs) == set(BreakerName)
    assert specs[N.CONNECTION].healthy_needed == 3
    assert specs[N.SLIPPAGE].cooldown_seconds == 3600
    assert specs[N.CONSECUTIVE_LOSSES].cooldown_seconds == timedelta(hours=24).total_seconds()
