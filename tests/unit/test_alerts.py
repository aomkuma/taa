from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.config import BreakerConfig
from app.core.clock import ManualClock
from app.core.enums import Severity, TradingMode
from app.monitoring.alerts import (
    DEFAULT_SEVERITY,
    EventBus,
    EventType,
    LocalLogSink,
    MemorySink,
    from_breaker,
    make_event,
)
from app.risk.circuit_breaker import BreakerBoard, BreakerEvent, BreakerName, default_specs
from app.storage.database import Database

T = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)


def test_every_type_has_a_severity_and_translation_keys() -> None:
    assert set(DEFAULT_SEVERITY) == set(EventType)
    e = make_event(EventType.POSITION_OPENED, T, symbol="EURUSD", volume=0.24)
    assert e.title_key == "event.position_opened.title"
    assert e.body_key == "event.position_opened.body"
    assert e.params == {"volume": 0.24}
    assert not e.push
    assert make_event(EventType.KILL_SWITCH_ACTIVATED, T).push


def test_breaker_events_keep_their_severity() -> None:
    trip = BreakerEvent(BreakerName.MAX_DRAWDOWN, "", "TRIP", Severity.CRITICAL, "engine", "dd 10%", T)
    e = from_breaker(trip)
    assert e.type is EventType.BREAKER_TRIPPED and e.severity is Severity.CRITICAL and e.push
    reset = from_breaker(
        BreakerEvent(BreakerName.SPREAD, "XAUUSD", "RESET", Severity.WARNING, "engine", "ok", T)
    )
    assert (
        reset.type is EventType.BREAKER_RESET and reset.severity is Severity.INFO and reset.symbol == "XAUUSD"
    )


class TestBus:
    def test_dedupe_window(self) -> None:
        clock = ManualClock(T)
        sink = MemorySink()
        bus = EventBus(clock, [sink], dedupe_seconds=300)
        assert bus.emit(EventType.CONNECTION_LOST, dedupe_key="conn")
        clock.advance(299)
        assert not bus.emit(EventType.CONNECTION_LOST, dedupe_key="conn")
        clock.advance(1)
        assert bus.emit(EventType.CONNECTION_LOST, dedupe_key="conn")
        assert bus.emit(EventType.CONNECTION_RESTORED)  # no key: never suppressed
        assert [e.type for e in sink.events] == [
            EventType.CONNECTION_LOST,
            EventType.CONNECTION_LOST,
            EventType.CONNECTION_RESTORED,
        ]

    def test_a_failing_sink_does_not_stop_the_others(self, caplog: pytest.LogCaptureFixture) -> None:
        class Broken:
            def handle(self, event: object) -> None:
                raise RuntimeError("disk full")

        sink = MemorySink()
        bus = EventBus(ManualClock(T), [Broken(), sink])
        assert bus.emit(EventType.ENGINE_STARTED)
        assert len(sink.events) == 1
        assert any("Broken" in r.getMessage() for r in caplog.records)

    def test_local_log_sink_writes_json_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "logs" / "events.jsonl"
        bus = EventBus(ManualClock(T), [LocalLogSink(path)])
        bus.emit(EventType.POSITION_CLOSED, symbol="EURUSD", net=12.5)
        bus.emit(EventType.ENGINE_STOPPED)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert [r["type"] for r in rows] == ["POSITION_CLOSED", "ENGINE_STOPPED"]
        assert rows[0]["params"] == {"net": 12.5} and rows[0]["symbol"] == "EURUSD"

    def test_breaker_board_notifies_the_bus(self, db: Database) -> None:
        clock = ManualClock(T)
        sink = MemorySink()
        bus = EventBus(clock, [sink])
        board = BreakerBoard(
            db,
            default_specs(BreakerConfig(), consecutive_pause_hours=24),
            clock,
            mode=TradingMode.PAPER,
            tz_name="Europe/Athens",
            notify=bus.breaker_notifier(),
        )
        board.trip(BreakerName.DAILY_LOSS, "-2%")
        assert [(e.type, e.severity) for e in sink.events] == [(EventType.BREAKER_TRIPPED, Severity.HIGH)]
