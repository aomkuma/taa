"""Cloud side of the ingest API: validate a batch and apply it idempotently (PLAN §A13; TAA-703).

One ``POST /api/v1/ingest/batch`` after HMAC verification (``app/web/routers/ingest.py``):

1. :func:`decode_body` gunzips with an output cap, so a small body cannot expand without bound, and parses
   strict JSON (no NaN/Infinity).
2. The envelope (:class:`app.sync.events.WireBatch`) must be valid and name the engine that signed the
   request. Otherwise the whole batch is refused (:class:`BatchError`, HTTP 422) and the engine counts an
   attempt against every event in it.
3. Each event is validated on its own. An invalid event is listed in ``rejected`` with a code; the engine
   parks it as DEAD, and the rest of the batch proceeds.
4. The valid events are applied in one transaction. A database error fails the request (5xx) and the engine
   resends the batch, which is harmless:
   - row events: upsert by key, skipped when :class:`ReplicaVersionRow` holds the same or a newer event id
     for that row (UUIDv7 ids are time-ordered, so a late resend never rolls a row back)
   - ``audit_event``: stored by ``(chain, seq)``, see below
   - ``command_result``: :meth:`CommandQueue.record_result`, once per command; appended to the ``web`` audit
     chain (``COMMAND_RESULT``) after the commit, so the cloud audits remote commands end to end (TAA-805)
   - ``candles``: upserted into the engine's own ``history_candles`` by open time (TAA-706)
   - ``heartbeat``: the engine's newest heartbeat in ``engine_heartbeats`` (an older one is a duplicate),
     streamed as ``status``/``heartbeat`` plus its quotes as ``quotes``; the worker's watchdog reads it
     (TAA-705)

   Applied rows of streamed types also go to the engine's change feed in the same transaction
   (:class:`app.sync.stream.StreamLog`, TAA-804), so the live stream never shows a change that rolled back.

**Audit continuity.** Only the signing engine's own chain (``engine:<id>``) is accepted. Each event's hash is
recomputed on arrival; a mismatch, or a different event at a ``seq`` already held, is rejected and marks the
chain BROKEN. :class:`AuditReplicaRow` then advances over the gap-free prefix, checking that each
``prev_hash`` is the previous event's hash: status OK (all verified), GAP (a later event arrived first; it
fills on resend or RESYNC) or BROKEN (sticky; logged at ERROR and appended to the ``web`` audit chain).
"""

from __future__ import annotations

import json
import logging
import zlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import ValidationError
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.clock import Clock, ensure_utc
from app.core.errors import TaaError
from app.storage.audit import GENESIS_HASH, AuditLog, compute_hash
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    AuditReplicaRow,
    EngineCommandRow,
    EngineHeartbeatRow,
    HistoryCandle,
    ReplicaVersionRow,
)
from app.sync.command_queue import CommandQueue, stream_entry
from app.sync.events import (
    AUDIT_EVENT,
    CANDLES,
    COMMAND_RESULT,
    SPECS_BY_TYPE,
    CandlesPayload,
    CommandResultPayload,
    ReplicaSpec,
    WireBatch,
    WireEvent,
)
from app.sync.heartbeat import HEARTBEAT, HeartbeatPayload
from app.sync.stream import StreamEntry, StreamLog, entry_for

log = logging.getLogger(__name__)

MAX_DECOMPRESSED_BYTES = 32 * 1024 * 1024
ADVANCE_CHUNK = 1000


class RejectCode(StrEnum):
    INVALID_EVENT = "INVALID_EVENT"
    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    WRONG_CHAIN = "WRONG_CHAIN"
    HASH_MISMATCH = "HASH_MISMATCH"
    AUDIT_CONFLICT = "AUDIT_CONFLICT"
    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"


class ChainStatus(StrEnum):
    OK = "OK"
    GAP = "GAP"
    BROKEN = "BROKEN"


class BatchError(TaaError):
    """The batch as a whole is unusable (encoding, envelope, engine mismatch)."""


def engine_chain(engine_id: str) -> str:
    return f"engine:{engine_id}"


def _no_constants(token: str) -> Any:
    raise ValueError(f"{token} is not valid JSON")


def decode_body(body: bytes, max_bytes: int = MAX_DECOMPRESSED_BYTES) -> Any:
    """Gunzip (at most *max_bytes* of output) and parse strict JSON; raises :class:`BatchError`."""
    inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    try:
        raw = inflater.decompress(body, max_bytes + 1)
    except zlib.error as exc:
        raise BatchError("the body is not valid gzip") from exc
    if len(raw) > max_bytes or inflater.unconsumed_tail:
        raise BatchError(f"the decompressed body exceeds {max_bytes} bytes")
    if not inflater.eof or inflater.unused_data:
        raise BatchError("the gzip stream is truncated or followed by extra data")
    try:
        return json.loads(raw, parse_constant=_no_constants)
    except ValueError as exc:  # also UnicodeDecodeError
        raise BatchError("the body is not valid JSON") from exc


def _summary(exc: ValidationError) -> str:
    """Field locations and error types only: submitted values are never echoed."""
    parts = [f"{'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['type']}" for e in exc.errors()[:5]]
    more = exc.error_count() - len(parts)
    return "; ".join(parts) + (f"; +{more} more" if more > 0 else "")


@dataclass(frozen=True, slots=True)
class Rejection:
    event_id: str
    code: RejectCode
    detail: str = ""


@dataclass
class IngestResult:
    accepted: int = 0
    duplicates: int = 0
    rejected: list[Rejection] = field(default_factory=list)

    def reject(self, event_id: str, code: RejectCode, detail: str = "") -> None:
        self.rejected.append(Rejection(event_id, code, detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "duplicates": self.duplicates,
            "rejected": [
                {"event_id": r.event_id, "code": r.code.value, "detail": r.detail} for r in self.rejected
            ],
        }


@dataclass(frozen=True, slots=True)
class _RowEvent:
    event: WireEvent
    spec: ReplicaSpec
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _CommandEvent:
    event: WireEvent
    payload: CommandResultPayload


@dataclass(frozen=True, slots=True)
class _CandlesEvent:
    event: WireEvent
    payload: CandlesPayload


@dataclass(frozen=True, slots=True)
class _HeartbeatEvent:
    event: WireEvent
    payload: HeartbeatPayload


@dataclass(frozen=True, slots=True)
class _Broken:
    chain: str
    seq: int | None
    detail: str


class IngestService:
    def __init__(
        self, db: Database, clock: Clock, commands: CommandQueue, *, audit: AuditLog | None = None
    ) -> None:
        self.db = db
        self.clock = clock
        self.commands = commands
        self.audit = audit  # the web chain, for BROKEN alerts
        self.stream = StreamLog(db, clock)

    def ingest(self, engine_id: str, doc: Any) -> IngestResult:
        batch = self._envelope(engine_id, doc)
        result = IngestResult()
        prepared = [
            p for p in (self._prepare(raw, engine_id, result) for raw in batch.events) if p is not None
        ]
        broken: list[_Broken] = []
        with self.db.session() as sess:
            chains: set[str] = set()
            streamed: list[StreamEntry] = []
            for item in prepared:
                if isinstance(item, _CommandEvent):
                    row = self._apply_command(sess, engine_id, item, result)
                    if row is not None:
                        streamed.append(stream_entry(row))
                elif isinstance(item, _CandlesEvent):
                    self._apply_candles(sess, engine_id, item, result)
                elif isinstance(item, _HeartbeatEvent):
                    streamed += self._apply_heartbeat(sess, engine_id, item, result)
                elif item.spec.event_type == AUDIT_EVENT:
                    if self._apply_audit(sess, engine_id, item, result, broken):
                        chains.add(item.values["chain"])
                else:
                    entry = self._apply_row(sess, engine_id, item, result)
                    if entry is not None:
                        streamed.append(entry)
            for chain in sorted(chains):
                self._advance(sess, engine_id, chain, broken)
            self.stream.append(sess, engine_id, streamed)
        for entry in streamed:
            if entry.type == "command" and self.audit is not None:
                c = entry.item
                self.audit.append(
                    "COMMAND_RESULT",
                    engine_id,
                    {"engine_id": engine_id, "command_id": c["id"], "type": c["type"], "result": c["result"]},
                )
        for b in broken:
            log.error("replicated audit chain %s is BROKEN at seq %s: %s", b.chain, b.seq, b.detail)
            if self.audit is not None:
                self.audit.append(
                    "AUDIT_REPLICA_BROKEN", "ingest", {"chain": b.chain, "seq": b.seq, "detail": b.detail}
                )
        if result.rejected:
            log.warning(
                "ingest from %s: %d events rejected (%s)",
                engine_id,
                len(result.rejected),
                ", ".join(sorted({r.code.value for r in result.rejected})),
            )
        return result

    # --- validation -----------------------------------------------------------------------------------------

    @staticmethod
    def _envelope(engine_id: str, doc: Any) -> WireBatch:
        if not isinstance(doc, dict):
            raise BatchError("the batch must be a JSON object")
        try:
            batch = WireBatch.model_validate(doc)
        except ValidationError as exc:
            raise BatchError(f"invalid batch envelope: {_summary(exc)}") from exc
        if batch.engine_id != engine_id:
            raise BatchError("the batch names a different engine than the one that signed it")
        return batch

    @staticmethod
    def _prepare(
        raw: dict[str, Any], engine_id: str, result: IngestResult
    ) -> _RowEvent | _CommandEvent | _CandlesEvent | _HeartbeatEvent | None:
        raw_id = raw.get("event_id")
        try:
            event = WireEvent.model_validate(raw)
        except ValidationError as exc:
            result.reject(raw_id if isinstance(raw_id, str) else "", RejectCode.INVALID_EVENT, _summary(exc))
            return None
        try:
            if event.type == COMMAND_RESULT:
                return _CommandEvent(event, CommandResultPayload.model_validate(event.payload))
            if event.type == CANDLES:
                return _CandlesEvent(event, CandlesPayload.model_validate(event.payload))
            if event.type == HEARTBEAT:
                return _HeartbeatEvent(event, HeartbeatPayload.model_validate(event.payload))
            spec = SPECS_BY_TYPE.get(event.type)
            if spec is None:
                result.reject(event.event_id, RejectCode.UNKNOWN_TYPE, event.type)
                return None
            values = spec.values(event.payload) | {"engine_id": engine_id}  # the signer, never the payload
        except ValidationError as exc:
            result.reject(event.event_id, RejectCode.INVALID_PAYLOAD, _summary(exc))
            return None
        if spec.source_id and values["source_id"] is None:
            result.reject(event.event_id, RejectCode.INVALID_PAYLOAD, "source_id: missing")
            return None
        if spec.event_type == AUDIT_EVENT and values["seq"] < 1:
            result.reject(event.event_id, RejectCode.INVALID_PAYLOAD, "seq: must be at least 1")
            return None
        return _RowEvent(event, spec, values)

    # --- applying -------------------------------------------------------------------------------------------

    @staticmethod
    def _version(sess: Session, engine_id: str, event_type: str, key: str) -> ReplicaVersionRow | None:
        return sess.get(ReplicaVersionRow, (engine_id, event_type, key))

    @staticmethod
    def _stale(version: ReplicaVersionRow | None, event: WireEvent) -> bool:
        """The same or a newer event was already applied to this entity."""
        return version is not None and version.event_id >= event.event_id

    def _record_version(
        self,
        sess: Session,
        engine_id: str,
        event_type: str,
        key: str,
        event: WireEvent,
        version: ReplicaVersionRow | None,
    ) -> None:
        now = self.clock.now_utc()
        if version is None:
            sess.add(
                ReplicaVersionRow(
                    engine_id=engine_id,
                    type=event_type,
                    entity_key=key,
                    event_id=event.event_id,
                    occurred_at=event.occurred_at_utc,
                    received_at=now,
                )
            )
        else:
            version.event_id = event.event_id
            version.occurred_at = event.occurred_at_utc
            version.received_at = now
        sess.flush()

    def _apply_row(
        self, sess: Session, engine_id: str, item: _RowEvent, result: IngestResult
    ) -> StreamEntry | None:
        """Upsert one row; returns its stream entry when it was applied and its type is streamed."""
        key = item.spec.entity_key(item.values)
        version = self._version(sess, engine_id, item.spec.event_type, key)
        if self._stale(version, item.event):
            result.duplicates += 1
            return None
        row = item.spec.find(sess, item.values)
        if row is None:
            sess.add(item.spec.model(**item.values))
        else:
            for name, value in item.values.items():
                setattr(row, name, value)
        self._record_version(sess, engine_id, item.spec.event_type, key, item.event, version)
        result.accepted += 1
        return entry_for(item.spec.event_type, key, item.values)

    @staticmethod
    def _apply_candles(sess: Session, engine_id: str, item: _CandlesEvent, result: IngestResult) -> None:
        """Upsert closed bars into the engine's own history by open time (a resend rewrites the same bars)."""
        p = item.payload
        bars = {ensure_utc(b[0]): b for b in p.bars}  # the last copy of a repeated open time wins
        sess.execute(
            delete(HistoryCandle).where(
                HistoryCandle.engine_id == engine_id,
                HistoryCandle.server == p.server,
                HistoryCandle.symbol == p.symbol,
                HistoryCandle.timeframe == p.timeframe,
                HistoryCandle.open_time.in_(list(bars)),
            )
        )
        sess.add_all(
            HistoryCandle(
                engine_id=engine_id,
                server=p.server,
                symbol=p.symbol,
                timeframe=p.timeframe,
                open_time=t,
                time_server=ts,
                open=o,
                high=h,
                low=lo,
                close=c,
                tick_volume=v,
                spread=sp,
            )
            for t, (_, ts, o, h, lo, c, v, sp) in bars.items()
        )
        sess.flush()
        result.accepted += 1

    def _apply_heartbeat(
        self, sess: Session, engine_id: str, item: _HeartbeatEvent, result: IngestResult
    ) -> list[StreamEntry]:
        """Keep the newest heartbeat; the watchdog's columns are left alone."""
        p = item.payload
        row = sess.get(EngineHeartbeatRow, engine_id)
        if row is not None and ensure_utc(row.sent_at) >= p.at:
            result.duplicates += 1
            return []
        now = self.clock.now_utc()
        doc = p.model_dump(mode="json")
        brief: dict[str, Any] = {k: v for k, v in doc.items() if k != "quotes"}
        values: dict[str, Any] = {
            "received_at": now,
            "sent_at": p.at,
            "run_id": p.run_id,
            "mode": p.mode,
            "state": p.state,
            "connected": p.connected,
            "market_open": p.market_open,
            "market_change_at": p.market_change_at,
            # the quotes are kept for GET /quotes; the status view and its stream event leave them out
            "payload": {**brief, "quotes": doc["quotes"]},
        }
        if row is None:
            sess.add(
                EngineHeartbeatRow(engine_id=engine_id, watch_status="ONLINE", offline_reason="", **values)
            )
        else:
            for name, value in values.items():
                setattr(row, name, value)
        sess.flush()
        result.accepted += 1
        status = {**brief, "received_at": now.isoformat()}
        entries = [StreamEntry("status", "heartbeat", "engine", status)]
        if doc["quotes"]:
            entries.append(
                StreamEntry("quotes", "quotes", "latest", {"at": doc["at"], "quotes": doc["quotes"]})
            )
        return entries

    def _apply_command(
        self, sess: Session, engine_id: str, item: _CommandEvent, result: IngestResult
    ) -> EngineCommandRow | None:
        """Record a command's result; returns the command when this event changed it."""
        key = item.payload.command_id
        version = self._version(sess, engine_id, COMMAND_RESULT, key)
        if self._stale(version, item.event):
            result.duplicates += 1
            return None
        row = self.commands.record_result(engine_id, item.payload.model_dump(mode="json"), sess)
        if row is None:
            result.reject(item.event.event_id, RejectCode.UNKNOWN_COMMAND, key)
            return None
        self._record_version(sess, engine_id, COMMAND_RESULT, key, item.event, version)
        result.accepted += 1
        return row

    def _apply_audit(
        self,
        sess: Session,
        engine_id: str,
        item: _RowEvent,
        result: IngestResult,
        broken: list[_Broken],
    ) -> bool:
        """Store one audit event; True when stored (the chain then needs advancing)."""
        v, event_id = item.values, item.event.event_id
        chain, seq = v["chain"], v["seq"]
        if chain != engine_chain(engine_id):
            result.reject(event_id, RejectCode.WRONG_CHAIN, chain)
            return False
        digest = compute_hash(
            v["prev_hash"],
            chain=chain,
            seq=seq,
            event_id=v["event_id"],
            ts_utc=v["ts_utc"],
            actor=v["actor"],
            event_type=v["event_type"],
            payload=v["payload"],
        )
        if digest != v["hash"]:
            self._mark_broken(sess, engine_id, chain, seq, "event content does not match its hash", broken)
            result.reject(event_id, RejectCode.HASH_MISMATCH, f"seq {seq}")
            return False
        clash = list(
            sess.execute(
                select(AuditEvent).where(
                    or_(
                        and_(AuditEvent.chain == chain, AuditEvent.seq == seq),
                        AuditEvent.event_id == v["event_id"],
                        AuditEvent.hash == v["hash"],
                    )
                )
            ).scalars()
        )
        if clash:
            if len(clash) == 1 and clash[0].seq == seq and clash[0].hash == v["hash"]:
                result.duplicates += 1
                return False
            self._mark_broken(
                sess, engine_id, chain, seq, f"a different event already holds seq {seq} or this id", broken
            )
            result.reject(event_id, RejectCode.AUDIT_CONFLICT, f"seq {seq}")
            return False
        sess.add(AuditEvent(**v))
        sess.flush()
        result.accepted += 1
        return True

    def _status(self, sess: Session, engine_id: str, chain: str) -> AuditReplicaRow:
        status = sess.get(AuditReplicaRow, chain)
        if status is None:
            status = AuditReplicaRow(
                chain=chain,
                engine_id=engine_id,
                status=ChainStatus.OK.value,
                verified_seq=0,
                verified_hash=GENESIS_HASH,
                max_seq=0,
                first_bad_seq=None,
                detail="",
                updated_at=self.clock.now_utc(),
            )
            sess.add(status)
            sess.flush()
        return status

    def _mark_broken(
        self,
        sess: Session,
        engine_id: str,
        chain: str,
        seq: int | None,
        detail: str,
        broken: list[_Broken],
    ) -> None:
        status = self._status(sess, engine_id, chain)
        if status.status == ChainStatus.BROKEN.value:
            return  # keep the first finding
        status.status = ChainStatus.BROKEN.value
        status.first_bad_seq = seq
        status.detail = detail
        status.updated_at = self.clock.now_utc()
        broken.append(_Broken(chain, seq, detail))

    def _advance(self, sess: Session, engine_id: str, chain: str, broken: list[_Broken]) -> None:
        status = self._status(sess, engine_id, chain)
        while status.status != ChainStatus.BROKEN.value:
            rows = list(
                sess.execute(
                    select(AuditEvent)
                    .where(AuditEvent.chain == chain, AuditEvent.seq > status.verified_seq)
                    .order_by(AuditEvent.seq)
                    .limit(ADVANCE_CHUNK)
                ).scalars()
            )
            advanced = 0
            for row in rows:
                if row.seq != status.verified_seq + 1:
                    break
                if row.prev_hash != status.verified_hash:
                    self._mark_broken(
                        sess, engine_id, chain, row.seq, "prev_hash does not match the previous event", broken
                    )
                    break
                status.verified_seq = row.seq
                status.verified_hash = row.hash
                advanced += 1
            if advanced < ADVANCE_CHUNK:
                break
        status.max_seq = int(
            sess.execute(select(func.max(AuditEvent.seq)).where(AuditEvent.chain == chain)).scalar_one() or 0
        )
        if status.status != ChainStatus.BROKEN.value:
            gap = status.max_seq > status.verified_seq
            status.status = (ChainStatus.GAP if gap else ChainStatus.OK).value
            status.detail = f"missing seq {status.verified_seq + 1}" if gap else ""
        status.updated_at = self.clock.now_utc()
