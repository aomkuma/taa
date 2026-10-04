"""Cloud-side command queue (PLAN §A13 "Commands"; TAA-704). Used by the web service; no broker access.

- :meth:`CommandQueue.enqueue` refuses what the engine would refuse anyway: unknown or risk-increasing types,
  lifetimes over 120 s, and TOTP-protected commands without a code.
- :meth:`CommandQueue.pending` serves the engine's long poll: unanswered, unexpired commands after the cursor
  (UUIDv7 ids are time-ordered), marked DELIVERED. Redelivery after a lost response is harmless because the
  engine executes each id once.
- :meth:`CommandQueue.record_result` applies the engine's ``command_result`` event (from the ingest API).
- :meth:`CommandQueue.expire` closes commands nobody answered; a TOTP code is cleared as soon as the command
  is answered or expires.

The long-poll HTTP route (``GET /api/v1/engine/commands``, HMAC-verified) is a thin loop over :meth:`pending`.
The PWA's control API (``app/web/routers/control.py``, TAA-805) enqueues and lists through :func:`public`,
which never shows a TOTP code. Queuing and results also go to the engine's live stream (topic ``status``, type
``command``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import Clock, ensure_utc
from app.core.errors import TaaError
from app.core.ids import new_id
from app.storage.database import Database
from app.storage.models import EngineCommandRow
from app.sync.commands import MAX_LIFETIME, RISK_INCREASING, TOTP_REQUIRED, CommandType
from app.sync.stream import StreamEntry, StreamLog


class QueueStatus(StrEnum):
    QUEUED = "QUEUED"
    DELIVERED = "DELIVERED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


OPEN = (QueueStatus.QUEUED.value, QueueStatus.DELIVERED.value)


class CommandRefused(TaaError):
    pass


def wire(row: EngineCommandRow) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": row.command_id,
        "type": row.type,
        "params": dict(row.params),
        "created_by": row.created_by,
        "created_at": ensure_utc(row.created_at).isoformat(),
        "expires_at": ensure_utc(row.expires_at).isoformat(),
    }
    if row.totp:
        out["totp"] = row.totp
    return out


def public(row: EngineCommandRow) -> dict[str, Any]:
    """A command as users see it: its state and result, never the TOTP code."""
    out = {k: v for k, v in wire(row).items() if k != "totp"}
    return out | {
        "status": row.status,
        "delivered_at": None if row.delivered_at is None else ensure_utc(row.delivered_at).isoformat(),
        "completed_at": None if row.completed_at is None else ensure_utc(row.completed_at).isoformat(),
        "result": dict(row.result),
    }


def stream_entry(row: EngineCommandRow) -> StreamEntry:
    return StreamEntry("status", "command", row.command_id, public(row))


class CommandQueue:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock
        self.stream = StreamLog(db, clock)

    def enqueue(
        self,
        engine_id: str,
        command_type: str,
        params: Mapping[str, Any] | None = None,
        *,
        created_by: str,
        totp: str | None = None,
        lifetime: timedelta = MAX_LIFETIME,
    ) -> dict[str, Any]:
        if command_type in RISK_INCREASING:
            raise CommandRefused(f"{command_type} increases risk: only the local CLI or config may do it")
        try:
            ctype = CommandType(command_type)
        except ValueError as exc:
            raise CommandRefused(f"{command_type} is not an allowed command") from exc
        if not timedelta(0) < lifetime <= MAX_LIFETIME:
            raise CommandRefused("a command lives at most 120 s")
        if ctype in TOTP_REQUIRED and not (totp and totp.strip().isdigit()):
            raise CommandRefused(f"{command_type} needs a TOTP code")
        now = self.clock.now_utc()
        row = EngineCommandRow(
            command_id=new_id(),
            engine_id=engine_id,
            type=ctype.value,
            params=dict(params or {}),
            created_by=created_by[:128],
            created_at=now,
            expires_at=now + lifetime,
            totp=totp.strip() if ctype in TOTP_REQUIRED and totp else None,
            status=QueueStatus.QUEUED.value,
            result={},
        )
        with self.db.session() as sess:
            sess.add(row)
            self.stream.append(sess, engine_id, [stream_entry(row)])
        return wire(row)

    def pending(self, engine_id: str, cursor: str | None = None) -> list[dict[str, Any]]:
        self.expire()
        now = self.clock.now_utc()
        with self.db.session() as sess:
            query = select(EngineCommandRow).where(
                EngineCommandRow.engine_id == engine_id,
                EngineCommandRow.status.in_(OPEN),
                EngineCommandRow.expires_at > now,
            )
            if cursor:
                query = query.where(EngineCommandRow.command_id > cursor)
            rows = list(sess.execute(query.order_by(EngineCommandRow.command_id)).scalars())
            for row in rows:
                if row.status == QueueStatus.QUEUED.value:
                    row.status = QueueStatus.DELIVERED.value
                    row.delivered_at = now
            return [wire(r) for r in rows]

    def record_result(
        self, engine_id: str, payload: Mapping[str, Any], sess: Session | None = None
    ) -> EngineCommandRow | None:
        """Apply a ``command_result`` event; the updated command, or None when it is unknown for this engine.

        The ingest API passes its own *sess*, so the result commits with the rest of the batch (and streams
        with it); on its own, this method streams the result itself."""
        if sess is None:
            with self.db.session() as own:
                row = self._record(own, engine_id, payload)
                if row is not None:
                    self.stream.append(own, engine_id, [stream_entry(row)])
                return row
        return self._record(sess, engine_id, payload)

    def _record(self, sess: Session, engine_id: str, payload: Mapping[str, Any]) -> EngineCommandRow | None:
        outcome = str(payload.get("outcome", ""))
        if outcome not in (QueueStatus.EXECUTED, QueueStatus.REJECTED, QueueStatus.FAILED):
            return None
        row = sess.get(EngineCommandRow, str(payload.get("command_id", "")))
        if row is None or row.engine_id != engine_id:
            return None
        row.status = outcome
        row.completed_at = self.clock.now_utc()
        row.result = {k: payload.get(k) for k in ("outcome", "reason", "detail", "at")}
        row.totp = None
        return row

    def expire(self, now: datetime | None = None) -> int:
        now = ensure_utc(now or self.clock.now_utc())
        with self.db.session() as sess:
            result = sess.execute(
                update(EngineCommandRow)
                .where(EngineCommandRow.status.in_(OPEN), EngineCommandRow.expires_at <= now)
                .values(status=QueueStatus.EXPIRED.value, totp=None, completed_at=now)
            )
        return int(getattr(result, "rowcount", 0) or 0)

    def expire_engine(self, engine_id: str) -> int:
        """Close every open command of a revoked engine (TOTP codes are cleared)."""
        now = self.clock.now_utc()
        with self.db.session() as sess:
            result = sess.execute(
                update(EngineCommandRow)
                .where(EngineCommandRow.engine_id == engine_id, EngineCommandRow.status.in_(OPEN))
                .values(status=QueueStatus.EXPIRED.value, totp=None, completed_at=now)
            )
        return int(getattr(result, "rowcount", 0) or 0)

    def get(self, command_id: str) -> EngineCommandRow | None:
        with self.db.session() as sess:
            return sess.get(EngineCommandRow, command_id)
