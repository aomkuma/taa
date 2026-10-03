"""Tamper-evident audit log.

Each chain (``engine:<id>``, ``web``) is an append-only sequence where::

    hash_n = sha256(hash_{n-1} || canonical_json(chain, seq, event_id, ts, actor, type, payload))

Modifying, deleting or reordering any past event breaks every later hash, which
:meth:`AuditLog.verify` detects. Replicas (the cloud copy of the engine chain) can be verified
independently because the hash inputs are self-contained.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.clock import Clock, SystemClock
from app.core.errors import StorageError
from app.core.ids import new_id
from app.storage.database import Database
from app.storage.models import AuditChainHead, AuditEvent

log = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
_MAX_RETRIES = 5


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_hash(
    prev_hash: str,
    *,
    chain: str,
    seq: int,
    event_id: str,
    ts_utc: datetime,
    actor: str,
    event_type: str,
    payload: dict[str, Any],
) -> str:
    body = canonical_json(
        {
            "chain": chain,
            "seq": seq,
            "event_id": event_id,
            "ts": ts_utc.isoformat(),
            "actor": actor,
            "type": event_type,
            "payload": payload,
        }
    )
    return hashlib.sha256((prev_hash + body).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerificationReport:
    chain: str
    events_checked: int
    ok: bool
    first_bad_seq: int | None = None
    detail: str = ""


class AuditLog:
    def __init__(self, db: Database, chain: str, clock: Clock | None = None) -> None:
        self.db = db
        self.chain = chain
        self.clock = clock or SystemClock()
        self._lock = threading.Lock()

    def append(self, event_type: str, actor: str, payload: dict[str, Any] | None = None) -> AuditEvent:
        """Append an event. Retries on concurrent-append conflicts (unique chain/seq)."""
        payload = json.loads(canonical_json(payload or {}))  # normalize to JSON-safe types
        with self._lock:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    return self._append_once(event_type, actor, payload)
                except IntegrityError:
                    if attempt == _MAX_RETRIES:
                        raise StorageError(f"audit append failed after {attempt} attempts") from None
                    log.warning("audit append conflict on chain %s, retrying", self.chain)
        raise StorageError("unreachable")  # pragma: no cover

    def _append_once(self, event_type: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
        with self.db.session() as sess:
            head = sess.execute(
                select(AuditChainHead).where(AuditChainHead.chain == self.chain).with_for_update()
            ).scalar_one_or_none()
            if head is None:
                head = AuditChainHead(chain=self.chain, last_seq=0, last_hash=GENESIS_HASH)
                sess.add(head)
                sess.flush()
            seq = head.last_seq + 1
            event_id = new_id()
            now = self.clock.now_utc()
            ts = now.replace(microsecond=(now.microsecond // 1000) * 1000)  # ms precision survives all DBs
            digest = compute_hash(
                head.last_hash,
                chain=self.chain,
                seq=seq,
                event_id=event_id,
                ts_utc=ts,
                actor=actor,
                event_type=event_type,
                payload=payload,
            )
            event = AuditEvent(
                event_id=event_id,
                chain=self.chain,
                seq=seq,
                ts_utc=ts,
                actor=actor,
                event_type=event_type,
                payload=payload,
                prev_hash=head.last_hash,
                hash=digest,
            )
            sess.add(event)
            head.last_seq = seq
            head.last_hash = digest
            sess.flush()
            return event

    def verify(self, batch_size: int = 1000) -> VerificationReport:
        return verify_chain(self.db, self.chain, batch_size=batch_size)


def verify_chain(db: Database, chain: str, batch_size: int = 1000) -> VerificationReport:
    prev_hash = GENESIS_HASH
    expected_seq = 1
    checked = 0
    last_seq = 0
    while True:
        with db.session() as sess:
            rows = list(
                sess.execute(
                    select(AuditEvent)
                    .where(AuditEvent.chain == chain, AuditEvent.seq > last_seq)
                    .order_by(AuditEvent.seq)
                    .limit(batch_size)
                ).scalars()
            )
        if not rows:
            break
        for ev in rows:
            if ev.seq != expected_seq:
                return VerificationReport(chain, checked, False, expected_seq, f"missing seq {expected_seq}")
            if ev.prev_hash != prev_hash:
                return VerificationReport(
                    chain, checked, False, ev.seq, "prev_hash does not match previous event"
                )
            recomputed = compute_hash(
                prev_hash,
                chain=chain,
                seq=ev.seq,
                event_id=ev.event_id,
                ts_utc=ev.ts_utc,
                actor=ev.actor,
                event_type=ev.event_type,
                payload=ev.payload,
            )
            if recomputed != ev.hash:
                return VerificationReport(
                    chain, checked, False, ev.seq, "event content does not match its hash"
                )
            prev_hash = ev.hash
            expected_seq += 1
            checked += 1
            last_seq = ev.seq
    with db.session() as sess:
        head = sess.get(AuditChainHead, chain)
    if head is not None and (head.last_seq != checked or head.last_hash != prev_hash):
        return VerificationReport(
            chain, checked, False, checked + 1, "chain head does not match the last event"
        )
    return VerificationReport(chain, checked, True, None, f"{checked} events verified")
