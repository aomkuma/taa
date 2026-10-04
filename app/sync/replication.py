"""Engine side of row replication: committed changes become outbox events (PLAN §A13; TAA-703).

:class:`Replicator` listens to every flush of the engine database. Each inserted or changed row of a
replicated table (:data:`app.sync.events.REPLICAS`) is written to ``outbox_events`` through the flushing
session's own connection, so the event commits or rolls back with the change it describes. Producers need no
code of their own: anything that writes these tables through the ORM (the engine, the CLI) is replicated.

- Each event carries the full row, so only the newest unsent one per row matters: events coalesce on
  ``<type>:<entity key>``. A spec's ``quiet`` columns and ``throttle_seconds`` (``app/sync/events.py``) cut
  the volume of rows that change often.
- Bulk ``update()``/``delete()`` statements bypass the ORM and are not seen; replicated tables are written
  through the ORM only. Deletes are not replicated at all.
- The hook never raises into the write it observes: replication must not block trading. A failure is logged
  and counted, and the cloud copy catches up on the next change of that row or a RESYNC.
- :meth:`Replicator.snapshot` re-emits every replicated row (first start with sync, the RESYNC command), so
  rows written before sync was enabled reach the cloud too. Re-sending is harmless: the cloud upserts.
"""

from __future__ import annotations

import logging
import threading
import weakref
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Connection, delete, event, insert, select
from sqlalchemy.orm import Session, UOWTransaction

from app.core.clock import Clock
from app.core.ids import new_id
from app.storage.database import Database
from app.storage.models import AuditEvent, OutboxEventRow
from app.sync.events import REPLICAS, ReplicaSpec
from app.sync.outbox import Status

log = logging.getLogger(__name__)

SNAPSHOT_CHUNK = 500
THROTTLE_KEYS_MAX = 5000

_installed: weakref.WeakKeyDictionary[Database, Replicator] = weakref.WeakKeyDictionary()
_install_lock = threading.Lock()


def write_event(conn: Connection, clock: Clock, spec: ReplicaSpec, payload: dict[str, Any]) -> str:
    """Insert one row event on *conn*, replacing the row's unsent predecessor."""
    now = clock.now_utc()
    event_id = new_id()
    key = f"{spec.event_type}:{spec.entity_key(payload)}"[:96]
    conn.execute(
        delete(OutboxEventRow).where(
            OutboxEventRow.coalesce_key == key, OutboxEventRow.status == Status.PENDING.value
        )
    )
    conn.execute(
        insert(OutboxEventRow).values(
            event_id=event_id,
            type=spec.event_type,
            priority=int(spec.priority),
            occurred_at=now,
            created_at=now,
            payload=payload,
            coalesce_key=key,
            status=Status.PENDING.value,
            attempts=0,
            last_error="",
        )
    )
    return event_id


class Replicator:
    """*audit_chain* is the engine's own chain (``engine:<ENGINE_ID>``); other chains in the file (an older
    ``engine:local``) are not replicated, because the cloud accepts only the chain of the signing engine."""

    def __init__(self, clock: Clock, audit_chain: str, specs: Iterable[ReplicaSpec] = REPLICAS) -> None:
        self.clock = clock
        self.audit_chain = audit_chain
        self.specs = tuple(specs)
        self.by_model = {s.model: s for s in self.specs}
        self.emitted = 0
        self.errors = 0
        self._last_update: dict[str, float] = {}  # coalesce key → monotonic time of its last update event

    def _wanted(self, obj: object) -> bool:
        if type(obj) not in self.by_model:
            return False
        return not isinstance(obj, AuditEvent) or obj.chain == self.audit_chain

    def _due(self, spec: ReplicaSpec, payload: dict[str, Any], now: float, is_update: bool) -> bool:
        """Throttling: inserts always go out; an update only once the row's interval has passed."""
        key = f"{spec.event_type}:{spec.entity_key(payload)}"
        last = self._last_update.get(key)
        if is_update and last is not None and now - last < spec.throttle_seconds:
            return False
        self._last_update[key] = now
        if len(self._last_update) > THROTTLE_KEYS_MAX:  # rows of past hours never update again: forget them
            horizon = max(s.throttle_seconds for s in self.specs)
            self._last_update = {k: t for k, t in self._last_update.items() if now - t < horizon}
        return True

    def _after_flush(self, session: Session, _flush: UOWTransaction) -> None:
        try:
            inserted = [o for o in session.new if self._wanted(o)]
            updated = [
                o
                for o in session.dirty
                if self._wanted(o)
                and session.is_modified(o, include_collections=False)
                and self.by_model[type(o)].changed_loudly(o)
            ]
            if not inserted and not updated:
                return
            conn = session.connection()
            now = self.clock.monotonic()
            for obj, is_update in [(o, False) for o in inserted] + [(o, True) for o in updated]:
                spec = self.by_model[type(obj)]
                payload = spec.payload(obj)
                if spec.throttle_seconds and not self._due(spec, payload, now, is_update):
                    continue
                write_event(conn, self.clock, spec, payload)
                self.emitted += 1
        except Exception:  # the observed write must go through; the cloud copy catches up later
            self.errors += 1
            log.exception(
                "replication hook failed; the cloud copy lags until the row changes again or RESYNC"
            )

    def snapshot(self, db: Database, types: Iterable[str] | None = None) -> int:
        """Emit every row of the replicated tables (in key order, committed in chunks). Returns the count."""
        wanted = set(types) if types is not None else None
        total = 0
        for spec in self.specs:
            if wanted is not None and spec.event_type not in wanted:
                continue
            query = select(spec.model).order_by(*(getattr(spec.model, k) for k in spec.key))
            if spec.model is AuditEvent:
                query = query.where(AuditEvent.chain == self.audit_chain)
            offset = 0
            while True:
                with db.session() as sess:
                    rows = list(sess.execute(query.offset(offset).limit(SNAPSHOT_CHUNK)).scalars())
                    conn = sess.connection()
                    for row in rows:
                        write_event(conn, self.clock, spec, spec.payload(row))
                total += len(rows)
                offset += len(rows)
                if len(rows) < SNAPSHOT_CHUNK:
                    break
        log.info("replication snapshot: %d rows queued for the cloud", total)
        return total


def install_replication(db: Database, clock: Clock, audit_chain: str) -> Replicator:
    """Attach a :class:`Replicator` to *db* once (later calls return the installed one)."""
    with _install_lock:
        existing = _installed.get(db)
        if existing is not None:
            return existing
        replicator = Replicator(clock, audit_chain)
        event.listen(db.session_factory, "after_flush", replicator._after_flush)
        _installed[db] = replicator
        return replicator
