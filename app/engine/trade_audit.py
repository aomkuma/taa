"""Trade lifecycle on the engine's audit chain (TAA-907).

Openings, stop moves (break-even, trailing, re-attached stops) and closings were events on the bus only, so
they lived in the local event log. Appending them to the hash-chained audit log makes every change of a
position auditable, and the audit replica carries them to the cloud, where the PWA's trade timeline reads
them (``GET /engines/{id}/trades/{ticket}``).
"""

from __future__ import annotations

from app.monitoring.alerts import EventType, NotificationEvent
from app.storage.audit import AuditLog

TRADE_EVENTS = frozenset({EventType.POSITION_OPENED, EventType.STOP_MOVED, EventType.POSITION_CLOSED})
ACTOR = "engine"


class TradeAuditSink:
    """An event-bus sink that appends trade lifecycle events to the audit chain (type = the event type)."""

    def __init__(self, audit: AuditLog) -> None:
        self.audit = audit

    def handle(self, event: NotificationEvent) -> None:
        if event.type not in TRADE_EVENTS:
            return
        payload = {**event.params, "symbol": event.symbol, "event_id": event.event_id}
        self.audit.append(event.type.value, ACTOR, payload)
