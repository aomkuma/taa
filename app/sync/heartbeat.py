"""Engine heartbeats (PLAN §A13 "Heartbeats"; TAA-705): payload, the engine's market state, the emitter.

Every ``sync.heartbeat_seconds`` (10 s) the engine queues one ``heartbeat`` outbox event (telemetry priority,
coalesced, so a backlog never holds more than the newest). It says whether the engine runs and is connected,
a few counters, the latest quotes of its traded symbols, and **whether its markets are open**:
``market_open`` plus ``market_change_at``, the moment that flips (the session end while open, the next
session start while closed; ``None`` for markets that never close). The cloud watchdog cannot see the broker,
so this is how it knows whether a silent engine matters: it raises ENGINE_OFFLINE only while the engine's
markets are open by the last heartbeat's schedule. A deliberate stop sends a final heartbeat with
``state: "stopped"``.

Market hours come from :mod:`app.advisory.market_sessions` (exchange-local session tables): open when any
traded symbol's sessions are open.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.advisory.asset_classes import classify
from app.advisory.market_sessions import session_state, sessions_for
from app.core.clock import ensure_utc
from app.market_data.data_models import SymbolSpec
from app.sync.outbox import Outbox, Priority

HEARTBEAT = "heartbeat"
MAX_QUOTES = 100
MAX_SESSION_HOPS = 64  # about two weeks of handovers between sessions


class QuoteItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=32)
    bid: float = Field(allow_inf_nan=False)
    ask: float = Field(allow_inf_nan=False)
    spread_points: float | None = Field(default=None, allow_inf_nan=False)
    time: AwareDatetime


class AccountLimits(BaseModel):
    """The engine's local risk limits (``RiskConfig``, percent of equity) the dashboard gauges compare to."""

    model_config = ConfigDict(extra="forbid")

    daily_loss_percent: float = Field(gt=0, allow_inf_nan=False)
    weekly_loss_percent: float = Field(gt=0, allow_inf_nan=False)
    drawdown_percent: float = Field(gt=0, allow_inf_nan=False)
    heat_percent: float = Field(gt=0, allow_inf_nan=False)
    consecutive_losses: int = Field(ge=1)


class AccountSnapshot(BaseModel):
    """The traded account at the last health step (TAA-904): the paper book in PAPER, the broker account in
    DEMO. P/L figures follow the loss tracker (flow-adjusted, broker day and ISO week); open risk is the risk
    to stop of the counted positions (§A9). A figure that could not be measured is null, never 0."""

    model_config = ConfigDict(extra="forbid")

    as_of: AwareDatetime
    backend: str = Field(max_length=16)
    currency: str = Field(max_length=8)
    balance: float | None = Field(allow_inf_nan=False)
    equity: float | None = Field(allow_inf_nan=False)
    margin: float | None = Field(allow_inf_nan=False)
    margin_free: float | None = Field(allow_inf_nan=False)
    day_pnl: float | None = Field(allow_inf_nan=False)
    day_pnl_percent: float | None = Field(allow_inf_nan=False)
    week_pnl: float | None = Field(allow_inf_nan=False)
    week_pnl_percent: float | None = Field(allow_inf_nan=False)
    drawdown_percent: float | None = Field(allow_inf_nan=False)
    open_risk: float | None = Field(ge=0, allow_inf_nan=False)
    heat_percent: float | None = Field(ge=0, allow_inf_nan=False)
    unknown_risk_positions: int = Field(ge=0)
    consecutive_losses: int = Field(ge=0)
    limits: AccountLimits


class HeartbeatPayload(BaseModel):
    """The wire schema of a ``heartbeat`` event (strict: unknown keys are refused)."""

    model_config = ConfigDict(extra="forbid")

    at: AwareDatetime
    run_id: str = Field(max_length=64)
    mode: str = Field(max_length=16)
    state: Literal["running", "stopped"]
    connected: bool
    clock_verified: bool
    kill_switch: bool
    open_positions: int = Field(ge=0)
    cycles: int = Field(ge=0)
    market_open: bool
    market_change_at: AwareDatetime | None
    outbox_pending: int | None = Field(default=None, ge=0)
    account: AccountSnapshot | None = None  # TAA-904; None until the first health step or when unreadable
    quotes: list[QuoteItem] = Field(default_factory=list, max_length=MAX_QUOTES)


def market_state(
    specs: Iterable[SymbolSpec], now: datetime, overrides: Mapping[str, Sequence[str]] | None = None
) -> tuple[bool, datetime | None]:
    """Whether any of *specs*' markets is open at *now*, and when that changes (None: never, e.g. crypto).

    Open: the end of the continuous open stretch, following sessions that overlap or touch (London hands
    over to New York, New York to Sydney, so forex is open from Monday morning in Sydney to Friday evening in
    New York). Closed: the earliest next session start. No symbols: closed with no known change, so the
    watchdog never alerts for an engine that trades nothing."""
    names = [sessions_for(s.name, classify(s), s.currency_profit, overrides) for s in specs]
    states = [session_state(n, now) for n in names]
    if not any(s.open for s in states):
        starts = [ensure_utc(s.next_open) for s in states if s.next_open is not None]
        return False, min(starts) if starts else None
    change = ensure_utc(now)
    for _ in range(MAX_SESSION_HOPS):
        open_states = [s for s in states if s.open]
        if not open_states:
            return True, change
        if any(s.ends_at is None for s in open_states):  # an always-open market (crypto)
            return True, None
        later = max(ensure_utc(s.ends_at) for s in open_states if s.ends_at is not None)
        if later <= change:
            return True, change
        change = later
        states = [session_state(n, change) for n in names]
    return True, change


def market_open_at(market_open: bool, change_at: datetime | None, now: datetime) -> bool:
    """The market state at *now* by a heartbeat's schedule (the single next change it announced)."""
    if market_open:
        return change_at is None or now < ensure_utc(change_at)
    return change_at is not None and now >= ensure_utc(change_at)


class HeartbeatEmitter:
    """Queues a heartbeat every *every* seconds (monotonic), and once more on a deliberate stop."""

    def __init__(self, outbox: Outbox, every: float) -> None:
        self.outbox = outbox
        self.every = every
        self.sent = 0
        self._next = float("-inf")

    def maybe_emit(self, now_monotonic: float, payload: Callable[[], Mapping[str, Any]]) -> bool:
        if now_monotonic < self._next:
            return False
        self._next = now_monotonic + self.every
        self.emit(payload())
        return True

    def emit(self, payload: Mapping[str, Any]) -> None:
        body = HeartbeatPayload.model_validate(dict(payload)).model_dump(mode="json")
        self.outbox.emit(HEARTBEAT, body, coalesce_key=HEARTBEAT, priority=Priority.TELEMETRY)
        self.sent += 1
