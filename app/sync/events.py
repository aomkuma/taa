"""Replicated event schemas, shared by the engine (producer) and the cloud ingest API (PLAN §A13; TAA-703).

**Row events.** Most event types carry one full row of a replicated table (:data:`REPLICAS`). The table's
columns *are* the wire schema: :meth:`ReplicaSpec.schema` builds a strict pydantic model from them (every
column required, no extra keys, string lengths and integer ranges of the column type, finite floats,
timezone-aware datetimes). Engine and cloud run the same code, so a schema change is a migration on both
sides; deploy the cloud first, or the engine's new rows are rejected (and parked as DEAD) until it catches up.

**Keys.** ``ReplicaSpec.key`` identifies a row on both sides. It is the primary key, except for tables whose
local surrogate id would collide with cloud rows: ``audit_events`` (the cloud keeps its own ``web`` chain in
the same table) is keyed by ``(chain, seq)`` and ``decision_checks`` by ``(decision_id, seq)``; those ids are
not sent. ``breaker_events`` and ``kill_switch_events`` have no natural key and keep the engine's id: only the
engine writes them, and there is one engine per deployment.

**Volume controls** (TAA-707). ``quiet`` columns change without an event of their own (the shadow tracker's
M1 ``cursor`` moves every poll); their values travel with the row's next real change. ``throttle_seconds``
emits an update of the same row at most that often (the ranking rewrites every snapshot row each minute);
inserts always go out, and the cloud copy lags at most that long behind.

**Other events.** ``command_result`` (:class:`CommandResultPayload`) answers a queued command.

Deletes are not replicated: the cloud applies its own retention.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Annotated, Any, Literal, cast

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    create_model,
)
from sqlalchemy import JSON, BigInteger, Boolean, Column, Float, Integer, String, Text, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import ColumnProperty, Session

from app.core.clock import ensure_utc
from app.storage.models import (
    AuditEvent,
    Base,
    BreakerEventRow,
    BreakerStateRow,
    CalibrationTableRow,
    ConfigSnapshot,
    DecisionCheckRow,
    DecisionRecordRow,
    EvidenceModelVersionRow,
    KillSwitchEvent,
    OpportunityRow,
    OrderIntentRow,
    PaperAccountRow,
    PaperIntentRow,
    PaperPositionRow,
    RiskBaseline,
    RiskDeal,
    RiskState,
    Run,
    ShadowTradeRow,
    SuitabilitySnapshotRow,
    SymbolCatalogRow,
)
from app.storage.types import UTCDateTime
from app.sync.outbox import Priority

MAX_BATCH_EVENTS = 1000
SNAPSHOT_THROTTLE_SECONDS = 300.0
MAX_TEXT_LENGTH = 100_000
EVENT_ID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
INT32 = 2**31
INT64 = 2**63

AUDIT_EVENT = "audit_event"
COMMAND_RESULT = "command_result"


def json_safe(value: Any) -> Any:
    """A JSON-ready copy: aware datetimes as ISO 8601, non-finite floats as None, other scalars as text."""
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat()
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [json_safe(v) for v in value]
    return str(value)  # Decimal, enums and the like


def _field_type(column: Column[Any]) -> Any:
    """The pydantic type of one column (subclasses first: Text is a String, BigInteger an Integer)."""
    ctype = column.type
    base: Any
    if isinstance(ctype, UTCDateTime):
        base = AwareDatetime
    elif isinstance(ctype, Boolean):
        base = StrictBool
    elif isinstance(ctype, BigInteger):
        base = Annotated[StrictInt, Field(ge=-INT64, lt=INT64)]
    elif isinstance(ctype, Integer):
        base = Annotated[StrictInt, Field(ge=-INT32, lt=INT32)]
    elif isinstance(ctype, Float):
        base = Annotated[float, Field(strict=True, allow_inf_nan=False)]  # ints pass, numeric strings do not
    elif isinstance(ctype, Text):
        base = Annotated[StrictStr, Field(max_length=MAX_TEXT_LENGTH)]
    elif isinstance(ctype, String):
        base = Annotated[StrictStr, Field(max_length=ctype.length or MAX_TEXT_LENGTH)]
    elif isinstance(ctype, JSON):
        base = Any
    else:  # a new column type must be mapped here before its table can be replicated
        raise TypeError(f"no wire type for column {column.table.name}.{column.name} ({ctype!r})")
    return base | None if column.nullable else base


@dataclass(frozen=True)
class ReplicaSpec:
    """One replicated table: event type, key columns, local-only columns and outbox priority."""

    event_type: str
    model: type[Base]
    key: tuple[str, ...] = ()  # default: the primary key
    exclude: tuple[str, ...] = ()  # local surrogate ids, never sent
    priority: Priority = Priority.CRITICAL
    quiet: tuple[str, ...] = ()  # columns whose changes alone emit nothing
    throttle_seconds: float = 0.0  # minimum time between update events of one row

    def __post_init__(self) -> None:
        if not self.key:
            object.__setattr__(self, "key", self.primary_key)
        if not set(self.key) <= set(self.column_names):
            raise TypeError(f"{self.event_type}: key {self.key} must be replicated columns")
        if not set(self.quiet) <= set(self.column_names) - set(self.key):
            raise TypeError(
                f"{self.event_type}: quiet columns {self.quiet} must be replicated non-key columns"
            )

    @cached_property
    def primary_key(self) -> tuple[str, ...]:
        return tuple(str(c.key) for c in sa_inspect(self.model).primary_key)

    @cached_property
    def columns(self) -> tuple[tuple[str, Column[Any]], ...]:
        attrs: list[ColumnProperty[Any]] = list(sa_inspect(self.model).column_attrs)
        return tuple((a.key, cast("Column[Any]", a.columns[0])) for a in attrs if a.key not in self.exclude)

    @cached_property
    def column_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.columns)

    @cached_property
    def schema(self) -> type[BaseModel]:
        fields: dict[str, Any] = {name: (_field_type(col), ...) for name, col in self.columns}
        model: type[BaseModel] = create_model(
            f"{self.event_type}_payload", __config__=ConfigDict(extra="forbid"), **fields
        )
        return model

    def changed_loudly(self, row: Any) -> bool:
        """Whether a pending change of *row* touches a column outside ``quiet``."""
        state = sa_inspect(row)
        return any(
            state.attrs[name].history.has_changes() for name in self.column_names if name not in self.quiet
        )

    def payload(self, row: Any) -> dict[str, Any]:
        """The wire payload of an ORM row."""
        return {name: json_safe(getattr(row, name)) for name in self.column_names}

    def values(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Validated column values from a wire payload; raises pydantic's ValidationError."""
        validated = self.schema.model_validate(dict(payload))
        values = {name: getattr(validated, name) for name in self.column_names}
        for name, col in self.columns:
            if isinstance(col.type, UTCDateTime) and values[name] is not None:
                values[name] = ensure_utc(values[name])
        return values

    def entity_key(self, values: Mapping[str, Any]) -> str:
        return "|".join(str(json_safe(values[k])) for k in self.key)

    def find(self, sess: Session, values: Mapping[str, Any]) -> Any:
        """The stored row with the same key, or None."""
        if self.key == self.primary_key:
            return sess.get(self.model, tuple(values[k] for k in self.key))
        where = [getattr(self.model, k) == values[k] for k in self.key]
        return sess.execute(select(self.model).where(*where)).scalar_one_or_none()


REPLICAS: tuple[ReplicaSpec, ...] = (
    ReplicaSpec(AUDIT_EVENT, AuditEvent, key=("chain", "seq"), exclude=("id",)),
    ReplicaSpec("decision", DecisionRecordRow),
    ReplicaSpec("decision_check", DecisionCheckRow, key=("decision_id", "seq"), exclude=("id",)),
    ReplicaSpec("order_intent", OrderIntentRow),
    ReplicaSpec("paper_intent", PaperIntentRow),
    ReplicaSpec("paper_position", PaperPositionRow),
    ReplicaSpec("paper_account", PaperAccountRow, priority=Priority.STATE),
    ReplicaSpec("breaker", BreakerStateRow),
    ReplicaSpec("breaker_event", BreakerEventRow),
    ReplicaSpec("kill_switch", KillSwitchEvent),
    ReplicaSpec("deal", RiskDeal),
    ReplicaSpec("risk_state", RiskState, priority=Priority.STATE),
    ReplicaSpec("risk_baseline", RiskBaseline, priority=Priority.STATE),
    ReplicaSpec("run", Run, priority=Priority.STATE),
    ReplicaSpec("config_snapshot", ConfigSnapshot, priority=Priority.STATE),
    # advisory (TAA-707): opportunities drive alerts, so they travel with the critical events
    ReplicaSpec("symbol_catalog", SymbolCatalogRow, priority=Priority.STATE),
    ReplicaSpec(
        "suitability_snapshot",
        SuitabilitySnapshotRow,
        key=("server", "symbol", "hour"),
        exclude=("id",),
        priority=Priority.TELEMETRY,
        throttle_seconds=SNAPSHOT_THROTTLE_SECONDS,
    ),
    ReplicaSpec("opportunity", OpportunityRow),
    ReplicaSpec("shadow_trade", ShadowTradeRow, priority=Priority.STATE, quiet=("cursor", "updated_at")),
    ReplicaSpec("calibration_version", CalibrationTableRow, priority=Priority.STATE),
    ReplicaSpec("evidence_model_version", EvidenceModelVersionRow, priority=Priority.STATE),
)
SPECS_BY_TYPE: dict[str, ReplicaSpec] = {s.event_type: s for s in REPLICAS}
SPECS_BY_MODEL: dict[type[Base], ReplicaSpec] = {s.model: s for s in REPLICAS}


# --- envelopes and non-row payloads -------------------------------------------------------------------------


class WireEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(pattern=EVENT_ID_PATTERN)
    type: str = Field(min_length=1, max_length=48)
    occurred_at_utc: AwareDatetime
    payload: dict[str, Any]


class WireBatch(BaseModel):
    """The body of ``POST /api/v1/ingest/batch`` (:func:`app.sync.outbox.encode_batch`).

    Events stay raw here, so one malformed event is rejected on its own instead of failing the batch."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schema")  # app.sync.outbox.SCHEMA_VERSION
    engine_id: str = Field(min_length=1, max_length=64)
    sent_at_utc: AwareDatetime
    events: list[dict[str, Any]] = Field(max_length=MAX_BATCH_EVENTS)


class CommandResultPayload(BaseModel):
    """``command_result``: the engine's answer to a queued command (:meth:`CommandResult.to_payload`)."""

    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=48)
    outcome: Literal["EXECUTED", "REJECTED", "FAILED"]
    reason: str = Field(max_length=32)
    detail: str = Field(max_length=4000)
    at: AwareDatetime
