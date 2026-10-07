"""Per-engine change feed behind the PWA's live stream (PLAN §A14 "SSE"; TAA-804).

The ingest transaction appends one :class:`StreamEventRow` for every applied row event of a streamed type
(:data:`TOPIC_OF_TYPE`); ``GET /api/v1/engines/{id}/stream`` (``app/web/routers/stream.py``) reads them after
a client's cursor. An event carries the changed row as the read APIs serialize it, so the PWA can update a
list in place; it is a notification of the newest state, not a history (several changes of one row in a batch
collapse into the last one).

**Sequence numbers.** ``seq`` counts per engine from 1. :meth:`StreamLog.append` raises the engine's
``stream_heads`` row with one UPDATE inside the ingest transaction. That locks the row until commit, so two
concurrent batches of one engine take turns and their events become visible in ``seq`` order: a reader that
has seen ``n`` never sees a smaller number appear later, which is what makes a cursor safe to resume from. (An
autoincrement id would not give that guarantee on PostgreSQL.) The very first batches of a new engine may race
on inserting the head row; the loser fails with an integrity error and the engine resends the batch.

**Retention.** Only the newest :data:`KEEP_EVENTS` events per engine are kept. A cursor older than that (or
ahead of the head, after a database reset) cannot be resumed: the stream tells the client to refetch.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.storage.database import Database
from app.storage.models import StreamEventRow, StreamHeadRow
from app.sync.events import json_safe

TOPICS: tuple[str, ...] = ("status", "quotes", "positions", "notifications", "decisions")

# Replica event type → topic. The other producers append their own entries: heartbeats (``status``/
# ``heartbeat``, ``quotes``; app.sync.ingest), notifications (app.sync.notifications) and commands
# (``status``/``command``; app.sync.command_queue).
TOPIC_OF_TYPE: Mapping[str, str] = {
    "run": "status",
    "kill_switch": "status",
    "breaker": "status",
    "breaker_event": "status",
    "paper_account": "status",
    "risk_state": "status",
    "risk_baseline": "status",
    "paper_position": "positions",
    "paper_intent": "positions",
    "order_intent": "positions",
    "broker_trade": "positions",
    "deal": "positions",
    "decision": "decisions",
}

# Columns left out of a streamed row, like the read API's list views (the detail routes have them).
OMIT: Mapping[str, tuple[str, ...]] = {"decision": ("signal", "market", "plan")}

KEEP_EVENTS = 5000


@dataclass(frozen=True, slots=True)
class StreamEntry:
    """One applied change, before it has a sequence number."""

    topic: str
    type: str
    key: str
    item: dict[str, Any]


def entry_for(event_type: str, key: str, values: Mapping[str, Any]) -> StreamEntry | None:
    """The stream entry of an applied row event, or None when the type is not streamed."""
    topic = TOPIC_OF_TYPE.get(event_type)
    if topic is None:
        return None
    skip = {"engine_id", *OMIT.get(event_type, ())}
    item = {k: json_safe(v) for k, v in values.items() if k not in skip}
    return StreamEntry(topic, event_type, key, item)


@dataclass(frozen=True, slots=True)
class StreamEvent:
    seq: int
    topic: str
    type: str
    key: str
    item: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"seq": self.seq, "type": self.type, "key": self.key, "at": self.created_at, "item": self.item}


@dataclass(frozen=True, slots=True)
class Bounds:
    """The resumable range of an engine's stream: cursors from ``floor - 1`` to ``head`` are usable."""

    floor: int
    head: int

    def resumable(self, cursor: int) -> bool:
        return self.floor - 1 <= cursor <= self.head


class StreamLog:
    def __init__(self, db: Database, clock: Clock, *, keep: int = KEEP_EVENTS) -> None:
        self.db = db
        self.clock = clock
        self.keep = keep

    def append(self, sess: Session, engine_id: str, entries: Iterable[StreamEntry]) -> int | None:
        """Add *entries* in the caller's transaction; returns the new head, or None when there was nothing."""
        latest: dict[tuple[str, str], StreamEntry] = {}
        for entry in entries:  # the newest change of a row wins and keeps its place in the order
            latest.pop((entry.type, entry.key), None)
            latest[(entry.type, entry.key)] = entry
        if not latest:
            return None
        n = len(latest)
        head = sess.execute(
            update(StreamHeadRow)
            .where(StreamHeadRow.engine_id == engine_id)
            .values(seq=StreamHeadRow.seq + n)
            .returning(StreamHeadRow.seq)
            .execution_options(synchronize_session=False)
        ).scalar_one_or_none()
        if head is None:
            sess.add(StreamHeadRow(engine_id=engine_id, seq=n))
            sess.flush()
            head = n
        now = self.clock.now_utc()
        sess.add_all(
            StreamEventRow(
                engine_id=engine_id,
                seq=head - n + 1 + i,
                topic=e.topic,
                type=e.type,
                entity_key=e.key,
                item=e.item,
                created_at=now,
            )
            for i, e in enumerate(latest.values())
        )
        sess.execute(
            delete(StreamEventRow).where(
                StreamEventRow.engine_id == engine_id, StreamEventRow.seq <= head - self.keep
            )
        )
        sess.flush()
        return int(head)

    def bounds(self, engine_id: str) -> Bounds:
        with self.db.session() as sess:
            head = self._head(sess, engine_id)
            return Bounds(self._floor(sess, engine_id, head), head)

    @staticmethod
    def _head(sess: Session, engine_id: str) -> int:
        row = sess.get(StreamHeadRow, engine_id)
        return 0 if row is None else int(row.seq)

    @staticmethod
    def _floor(sess: Session, engine_id: str, head: int) -> int:
        low = sess.execute(
            select(func.min(StreamEventRow.seq)).where(StreamEventRow.engine_id == engine_id)
        ).scalar_one()
        return head + 1 if low is None else int(low)

    def read(
        self, engine_id: str, after: int, topics: Sequence[str], limit: int
    ) -> tuple[list[StreamEvent], int, Bounds]:
        """Events of *topics* after *after* (at most *limit*), the cursor to continue from, and the bounds.

        Only use the events when ``bounds.resumable(after)``. The head is read before the events and the floor
        after them, so an event committed meanwhile is never skipped and one pruned meanwhile shows up as a
        lost cursor. The cursor moves to the head when the page is not full, so events of other topics are not
        scanned again."""
        with self.db.session() as sess:
            head = self._head(sess, engine_id)
            rows = list(
                sess.execute(
                    select(StreamEventRow)
                    .where(
                        StreamEventRow.engine_id == engine_id,
                        StreamEventRow.seq > after,
                        StreamEventRow.topic.in_(topics),
                    )
                    .order_by(StreamEventRow.seq)
                    .limit(limit)
                ).scalars()
            )
            bounds = Bounds(self._floor(sess, engine_id, head), head)
        events = [
            StreamEvent(r.seq, r.topic, r.type, r.entity_key, r.item, str(json_safe(r.created_at)))
            for r in rows
        ]
        if len(events) == limit:
            return events, events[-1].seq, bounds
        return events, max([after, head, *(e.seq for e in events)]), bounds
