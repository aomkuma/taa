"""Notification events (PLAN §A10 step 4, §A15 Web Push, §A19; TAA-606).

Every alert the engine raises is a :class:`NotificationEvent` with a type, a severity and translation keys for
its title and body (the PWA renders TH/EN; parameters fill the placeholders). Events go through an
:class:`EventBus` to its sinks: a local JSON-lines log now, the cloud outbox (Phase 7) and Web Push (Phase 8,
HIGH and CRITICAL only) later.

The bus suppresses repeats of the same ``dedupe_key`` inside ``dedupe_seconds``, so a flapping condition
produces one notification, not one per loop cycle. A failing sink is logged and never stops the others or the
engine.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from app.core.clock import Clock, ensure_utc
from app.core.enums import Severity
from app.core.ids import new_id
from app.risk.circuit_breaker import BreakerEvent

log = logging.getLogger(__name__)


class EventType(StrEnum):
    ENGINE_STARTED = "ENGINE_STARTED"
    ENGINE_STOPPED = "ENGINE_STOPPED"
    ENGINE_ERROR = "ENGINE_ERROR"
    CONNECTION_LOST = "CONNECTION_LOST"
    CONNECTION_RESTORED = "CONNECTION_RESTORED"
    CLOCK_UNVERIFIED = "CLOCK_UNVERIFIED"
    BREAKER_TRIPPED = "BREAKER_TRIPPED"
    BREAKER_RESET = "BREAKER_RESET"
    KILL_SWITCH_ACTIVATED = "KILL_SWITCH_ACTIVATED"
    KILL_SWITCH_RELEASED = "KILL_SWITCH_RELEASED"
    SIGNAL_ACCEPTED = "SIGNAL_ACCEPTED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    STOP_MOVED = "STOP_MOVED"
    ORDER_REJECTED = "ORDER_REJECTED"
    UNKNOWN_POSITION = "UNKNOWN_POSITION"  # a position with the bot's magic that the engine did not open
    DAILY_SUMMARY = "DAILY_SUMMARY"


DEFAULT_SEVERITY: dict[EventType, Severity] = {
    EventType.ENGINE_STARTED: Severity.INFO,
    EventType.ENGINE_STOPPED: Severity.WARNING,
    EventType.ENGINE_ERROR: Severity.HIGH,
    EventType.CONNECTION_LOST: Severity.HIGH,
    EventType.CONNECTION_RESTORED: Severity.INFO,
    EventType.CLOCK_UNVERIFIED: Severity.HIGH,
    EventType.BREAKER_TRIPPED: Severity.HIGH,  # replaced by the breaker's own severity
    EventType.BREAKER_RESET: Severity.INFO,
    EventType.KILL_SWITCH_ACTIVATED: Severity.CRITICAL,
    EventType.KILL_SWITCH_RELEASED: Severity.WARNING,
    EventType.SIGNAL_ACCEPTED: Severity.INFO,
    EventType.POSITION_OPENED: Severity.INFO,
    EventType.POSITION_CLOSED: Severity.INFO,
    EventType.STOP_MOVED: Severity.INFO,
    EventType.ORDER_REJECTED: Severity.WARNING,
    EventType.UNKNOWN_POSITION: Severity.CRITICAL,
    EventType.DAILY_SUMMARY: Severity.INFO,
}
PUSH_SEVERITIES = frozenset({Severity.HIGH, Severity.CRITICAL})


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    event_id: str
    type: EventType
    severity: Severity
    created_at: datetime
    params: Mapping[str, Any] = field(default_factory=dict)  # values for the TH/EN templates
    symbol: str | None = None
    dedupe_key: str = ""

    @property
    def title_key(self) -> str:
        return f"event.{self.type.value.lower()}.title"

    @property
    def body_key(self) -> str:
        return f"event.{self.type.value.lower()}.body"

    @property
    def push(self) -> bool:
        return self.severity in PUSH_SEVERITIES

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type.value,
            "severity": self.severity.value,
            "created_at": self.created_at.isoformat(),
            "symbol": self.symbol,
            "params": dict(self.params),
            "title_key": self.title_key,
            "body_key": self.body_key,
            "push": self.push,
            "dedupe_key": self.dedupe_key,
        }


def make_event(
    type_: EventType,
    at: datetime,
    *,
    severity: Severity | None = None,
    symbol: str | None = None,
    dedupe_key: str = "",
    **params: Any,
) -> NotificationEvent:
    return NotificationEvent(
        event_id=new_id(),
        type=type_,
        severity=severity or DEFAULT_SEVERITY[type_],
        created_at=ensure_utc(at),
        params=params,
        symbol=symbol,
        dedupe_key=dedupe_key,
    )


def from_breaker(event: BreakerEvent) -> NotificationEvent:
    """A breaker trip keeps the breaker's severity; half-open probes and resets are informational."""
    if event.action == "TRIP":
        type_, severity = EventType.BREAKER_TRIPPED, event.severity
    else:
        type_, severity = EventType.BREAKER_RESET, Severity.INFO
    return make_event(
        type_,
        event.at,
        severity=severity,
        symbol=event.scope_key or None,
        dedupe_key=f"breaker:{event.name.value}:{event.scope_key}:{event.action}",
        breaker=event.name.value,
        action=event.action,
        reason=event.reason,
        actor=event.actor,
    )


class EventSink(Protocol):
    def handle(self, event: NotificationEvent) -> None: ...


class LocalLogSink:
    """Appends one JSON line per event (``logs/events.jsonl``) and mirrors it to the application log."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def handle(self, event: NotificationEvent) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), sort_keys=True, default=str) + "\n")
        level = logging.WARNING if event.severity in (Severity.WARNING, *PUSH_SEVERITIES) else logging.INFO
        log.log(
            level,
            "event %s %s %s %s",
            event.type.value,
            event.severity.value,
            event.symbol or "",
            dict(event.params),
        )


class MemorySink:
    """Keeps events in memory (tests and the health endpoint's recent-events view)."""

    def __init__(self, keep: int = 200) -> None:
        self.events: list[NotificationEvent] = []
        self.keep = keep

    def handle(self, event: NotificationEvent) -> None:
        self.events.append(event)
        del self.events[: -self.keep]


class EventBus:
    def __init__(
        self, clock: Clock, sinks: list[EventSink] | None = None, *, dedupe_seconds: float = 300.0
    ) -> None:
        self.clock = clock
        self.sinks: list[EventSink] = list(sinks or [])
        self.dedupe = timedelta(seconds=dedupe_seconds)
        self._last: dict[str, datetime] = {}

    def publish(self, event: NotificationEvent) -> bool:
        """Deliver to every sink; False when suppressed as a repeat."""
        if event.dedupe_key:
            last = self._last.get(event.dedupe_key)
            if last is not None and event.created_at - last < self.dedupe:
                return False
            self._last[event.dedupe_key] = event.created_at
        for sink in self.sinks:
            try:
                sink.handle(event)
            except Exception:  # a broken sink must never stop the engine or the other sinks
                log.exception("event sink %s failed for %s", type(sink).__name__, event.type)
        return True

    def emit(self, type_: EventType, **kw: Any) -> bool:
        return self.publish(make_event(type_, self.clock.now_utc(), **kw))

    def breaker_notifier(self) -> Callable[[BreakerEvent], None]:
        """The ``notify`` callback of a :class:`BreakerBoard`."""

        def notify(event: BreakerEvent) -> None:
            self.publish(from_breaker(event))

        return notify
