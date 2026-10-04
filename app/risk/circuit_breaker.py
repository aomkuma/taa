"""Circuit breakers (PLAN §A10; TAA-404).

A tripped breaker blocks **new entries** in its scope (global, or one symbol). It never closes positions:
monitoring, position management and health checks keep running.

- **States:** CLOSED → OPEN on a trip. Auto-resetting breakers go OPEN → HALF_OPEN on the first healthy
  observation and back to CLOSED once healthy long enough (``healthy_needed`` reports, or ``recover_seconds``
  of continuous health). An unhealthy report in HALF_OPEN re-opens it. HALF_OPEN still blocks entries.
- **Reset policies:** ``HEALTHY`` (as above), ``COOLDOWN`` (time since the trip), ``NEXT_DAY`` / ``NEXT_WEEK``
  (the broker day or week changed), ``MANUAL``. A breaker that trips ``manual_after`` times in one broker day
  **latches**: only a manual reset clears it.
- **Manual reset** needs an actor and a reason, and ``MAX_DRAWDOWN`` also an explicit acknowledgement. Every
  trip, half-open and reset is persisted (``breaker_states`` / ``breaker_events``), appended to the audit
  chain, and passed to the notifier (Web Push for HIGH and CRITICAL, TAA-606).
- **Milestone 1 subset:** the order-path breakers (ORDER_FAILURES, DUPLICATE_EXECUTION, UNPROTECTED_POSITION)
  are defined but inactive unless the mode may send broker orders.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BreakerConfig
from app.core.clock import Clock
from app.core.enums import Severity, TradingMode
from app.core.errors import SafetyViolation
from app.risk.checks import Check, CheckKind
from app.risk.loss_tracker import period_keys
from app.risk.reasons import Reason, with_detail
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import BreakerEventRow, BreakerStateRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)


class BreakerName(StrEnum):
    CONNECTION = "CONNECTION"
    ACCOUNT_CHANGE = "ACCOUNT_CHANGE"
    CLOCK = "CLOCK"
    STORAGE = "STORAGE"
    INVALID_PRICE = "INVALID_PRICE"
    SPREAD = "SPREAD"
    STALE_DATA = "STALE_DATA"
    SLIPPAGE = "SLIPPAGE"
    DAILY_LOSS = "DAILY_LOSS"
    WEEKLY_LOSS = "WEEKLY_LOSS"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    UNHANDLED_EXCEPTION = "UNHANDLED_EXCEPTION"
    ORDER_FAILURES = "ORDER_FAILURES"
    DUPLICATE_EXECUTION = "DUPLICATE_EXECUTION"
    UNPROTECTED_POSITION = "UNPROTECTED_POSITION"
    SYMBOL_RESTRICTED = "SYMBOL_RESTRICTED"  # server: trade disabled / market closed / long or short only


class Scope(StrEnum):
    GLOBAL = "GLOBAL"
    SYMBOL = "SYMBOL"


class ResetPolicy(StrEnum):
    HEALTHY = "HEALTHY"
    COOLDOWN = "COOLDOWN"
    NEXT_DAY = "NEXT_DAY"
    NEXT_WEEK = "NEXT_WEEK"
    MANUAL = "MANUAL"


class State(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass(frozen=True, slots=True)
class BreakerSpec:
    name: BreakerName
    scope: Scope
    severity: Severity
    policy: ResetPolicy
    healthy_needed: int = 1  # HEALTHY: consecutive healthy reports
    recover_seconds: float = 0.0  # HEALTHY: continuous health required (0: count reports only)
    cooldown_seconds: float = 0.0  # COOLDOWN
    manual_after: int | None = None  # latch after this many trips in one broker day
    requires_ack: bool = False  # manual reset needs an explicit acknowledgement
    order_path: bool = False  # Milestone 2 only


def default_specs(
    cfg: BreakerConfig, *, consecutive_pause_hours: float, symbol_pause_minutes: float = 60.0
) -> dict[BreakerName, BreakerSpec]:
    """The A10 table with the thresholds from ``config.yaml`` → ``breakers:``."""
    n, g, s = BreakerName, Scope.GLOBAL, Scope.SYMBOL
    hi, crit, warn = Severity.HIGH, Severity.CRITICAL, Severity.WARNING
    specs = [
        BreakerSpec(n.CONNECTION, g, hi, ResetPolicy.HEALTHY, healthy_needed=cfg.healthy_checks_to_recover),
        BreakerSpec(n.ACCOUNT_CHANGE, g, crit, ResetPolicy.MANUAL),
        BreakerSpec(n.CLOCK, g, hi, ResetPolicy.HEALTHY),
        BreakerSpec(n.STORAGE, g, crit, ResetPolicy.HEALTHY),
        BreakerSpec(
            n.INVALID_PRICE, s, warn, ResetPolicy.HEALTHY, recover_seconds=cfg.invalid_price_recovery_seconds
        ),
        BreakerSpec(n.SPREAD, s, warn, ResetPolicy.HEALTHY, recover_seconds=cfg.spread_recovery_seconds),
        BreakerSpec(n.STALE_DATA, s, warn, ResetPolicy.HEALTHY),
        BreakerSpec(
            n.SLIPPAGE,
            s,
            hi,
            ResetPolicy.COOLDOWN,
            cooldown_seconds=cfg.slippage_cooldown_minutes * 60,
            manual_after=3,
        ),
        BreakerSpec(n.DAILY_LOSS, g, hi, ResetPolicy.NEXT_DAY),
        BreakerSpec(n.WEEKLY_LOSS, g, hi, ResetPolicy.NEXT_WEEK),
        BreakerSpec(n.MAX_DRAWDOWN, g, crit, ResetPolicy.MANUAL, requires_ack=True),
        BreakerSpec(
            n.CONSECUTIVE_LOSSES, g, hi, ResetPolicy.COOLDOWN, cooldown_seconds=consecutive_pause_hours * 3600
        ),
        BreakerSpec(
            n.UNHANDLED_EXCEPTION,
            g,
            hi,
            ResetPolicy.COOLDOWN,
            cooldown_seconds=cfg.exception_cooldown_minutes * 60,
            manual_after=cfg.exception_max_trips_per_day,
        ),
        BreakerSpec(
            n.ORDER_FAILURES,
            g,
            hi,
            ResetPolicy.COOLDOWN,
            cooldown_seconds=cfg.order_failures_cooldown_minutes * 60,
            manual_after=3,
            order_path=True,
        ),
        BreakerSpec(n.DUPLICATE_EXECUTION, g, crit, ResetPolicy.MANUAL, order_path=True),
        BreakerSpec(n.UNPROTECTED_POSITION, g, crit, ResetPolicy.MANUAL, order_path=True),
        BreakerSpec(
            n.SYMBOL_RESTRICTED,
            s,
            warn,
            ResetPolicy.COOLDOWN,
            cooldown_seconds=symbol_pause_minutes * 60,
            order_path=True,
        ),
    ]
    return {spec.name: spec for spec in specs}


@dataclass(frozen=True, slots=True)
class BreakerEvent:
    name: BreakerName
    scope_key: str
    action: str  # TRIP | HALF_OPEN | RESET
    severity: Severity
    actor: str
    reason: str
    at: datetime
    metrics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BreakerStatus:
    name: BreakerName
    scope_key: str
    state: State
    latched: bool
    reason: str
    opened_at: datetime | None

    @property
    def blocks_entries(self) -> bool:
        return self.state is not State.CLOSED


Notifier = Callable[[BreakerEvent], None]


class BreakerBoard:
    """Persisted breaker states for one engine. All methods are safe to call every loop cycle."""

    def __init__(
        self,
        db: Database,
        specs: Mapping[BreakerName, BreakerSpec],
        clock: Clock,
        *,
        mode: TradingMode,
        tz_name: str,
        audit: AuditLog | None = None,
        notify: Notifier | None = None,
    ) -> None:
        self.db = db
        self.specs = dict(specs)
        self.clock = clock
        self.mode = mode
        self.tz = ZoneInfo(tz_name)
        self.audit = audit
        self.notify = notify

    def active(self, name: BreakerName) -> bool:
        return not self.specs[name].order_path or self.mode.may_send_broker_orders

    # transitions -------------------------------------------------------------------------------------------

    def trip(
        self, name: BreakerName, reason: str, scope_key: str = "", metrics: Mapping[str, Any] | None = None
    ) -> bool:
        """Open the breaker. Returns True when this call changed its state (a new trip)."""
        if not self.active(name):
            log.debug("breaker %s is inactive in %s mode; trip ignored: %s", name, self.mode, reason)
            return False
        spec = self.specs[name]
        now = self.clock.now_utc()
        day, week = period_keys(now, self.tz)
        with self.db.session() as sess:
            row = self._row(sess, name, scope_key)
            row.healthy_count = 0
            row.healthy_since = None
            if row.state == State.OPEN:
                row.metrics = dict(metrics or {})
                row.updated_at = now
                return False
            if row.trips_day_key != day:
                row.trips_day_key, row.trips_today = day, 0
            row.trips_today += 1
            row.state = State.OPEN.value
            row.reason = reason
            row.opened_at = now
            row.opened_day_key, row.opened_week_key = day, week
            row.latched = spec.policy is ResetPolicy.MANUAL or (
                spec.manual_after is not None and row.trips_today >= spec.manual_after
            )
            row.metrics = dict(metrics or {})
            row.updated_at = now
            event = self._event(sess, spec, scope_key, "TRIP", "engine", reason, now, row.metrics)
        self._publish(event)
        return True

    def report_healthy(self, name: BreakerName, scope_key: str = "") -> None:
        """A healthy observation; moves an auto-resetting breaker toward CLOSED."""
        spec = self.specs[name]
        if spec.policy is not ResetPolicy.HEALTHY:
            return
        now = self.clock.now_utc()
        events = []
        with self.db.session() as sess:
            row = sess.get(BreakerStateRow, (LOCAL_ENGINE, name.value, scope_key))
            if row is None or row.state == State.CLOSED or row.latched:
                return
            if row.state == State.OPEN:
                row.state = State.HALF_OPEN.value
                row.healthy_count, row.healthy_since = 0, now
                events.append(
                    self._event(sess, spec, scope_key, "HALF_OPEN", "engine", "healthy again", now, {})
                )
            row.healthy_count += 1
            since = row.healthy_since or now
            if (
                row.healthy_count >= spec.healthy_needed
                and (now - since).total_seconds() >= spec.recover_seconds
            ):
                self._close(row, now)
                events.append(self._event(sess, spec, scope_key, "RESET", "engine", "recovered", now, {}))
            row.updated_at = now
        for event in events:
            self._publish(event)

    def tick(self) -> None:
        """Time-based resets: cooldowns, a new broker day or week."""
        now = self.clock.now_utc()
        day, week = period_keys(now, self.tz)
        events = []
        with self.db.session() as sess:
            rows = sess.execute(
                select(BreakerStateRow).where(BreakerStateRow.state != State.CLOSED.value)
            ).scalars()
            for row in rows:
                spec = self.specs.get(BreakerName(row.name))
                if spec is None or row.latched or row.opened_at is None:
                    continue
                due = (
                    (
                        spec.policy is ResetPolicy.COOLDOWN
                        and now - row.opened_at >= timedelta(seconds=spec.cooldown_seconds)
                    )
                    or (spec.policy is ResetPolicy.NEXT_DAY and day != row.opened_day_key)
                    or (spec.policy is ResetPolicy.NEXT_WEEK and week != row.opened_week_key)
                )
                if due:
                    self._close(row, now)
                    events.append(
                        self._event(
                            sess,
                            spec,
                            row.scope_key,
                            "RESET",
                            "engine",
                            f"{spec.policy.value} reset",
                            now,
                            {},
                        )
                    )
        for event in events:
            self._publish(event)

    def reset(
        self, name: BreakerName, *, actor: str, reason: str, scope_key: str = "", acknowledge: bool = False
    ) -> None:
        """Manual reset (local CLI only, PLAN §A20): always audited."""
        if not actor.strip() or not reason.strip():
            raise SafetyViolation("a manual breaker reset needs an actor and a reason")
        spec = self.specs[name]
        if spec.requires_ack and not acknowledge:
            raise SafetyViolation(f"resetting {name} requires an explicit acknowledgement")
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = sess.get(BreakerStateRow, (LOCAL_ENGINE, name.value, scope_key))
            if row is None or row.state == State.CLOSED:
                return
            self._close(row, now)
            event = self._event(sess, spec, scope_key, "RESET", actor, reason, now, {"manual": True})
        self._publish(event)

    # queries -----------------------------------------------------------------------------------------------

    def statuses(self) -> list[BreakerStatus]:
        with self.db.session() as sess:
            rows = sess.execute(
                select(BreakerStateRow).order_by(BreakerStateRow.name, BreakerStateRow.scope_key)
            )
            return [
                BreakerStatus(
                    BreakerName(r.name), r.scope_key, State(r.state), r.latched, r.reason, r.opened_at
                )
                for r in rows.scalars()
            ]

    def blocking(self, symbol: str | None = None) -> list[BreakerStatus]:
        """Breakers that block a new entry: every non-closed global one, plus *symbol*'s own."""
        return [
            s
            for s in self.statuses()
            if s.blocks_entries
            and self.active(s.name)
            and (self.specs[s.name].scope is Scope.GLOBAL or s.scope_key == symbol)
        ]

    def checks(self, symbol: str | None = None) -> list[Check]:
        """One failing ``BREAKER_OPEN:<name>`` check per blocking breaker (or one passing check)."""
        blocking = self.blocking(symbol)
        if not blocking:
            return [Check("breakers", Reason.BREAKER_OPEN, True, CheckKind.ACCOUNT, 0, 0)]
        return [
            Check(
                f"breaker_{s.name.value.lower()}",
                Reason.BREAKER_OPEN,
                False,
                CheckKind.ACCOUNT,
                s.state.value,
                State.CLOSED.value,
                s.reason,
                code=with_detail(Reason.BREAKER_OPEN, s.name.value),
            )
            for s in blocking
        ]

    # internals ---------------------------------------------------------------------------------------------

    @staticmethod
    def _row(sess: Session, name: BreakerName, scope_key: str) -> BreakerStateRow:
        row = sess.get(BreakerStateRow, (LOCAL_ENGINE, name.value, scope_key))
        if row is None:
            row = BreakerStateRow(name=name.value, scope_key=scope_key, state=State.CLOSED.value, metrics={})
            sess.add(row)
        return row

    @staticmethod
    def _close(row: BreakerStateRow, now: datetime) -> None:
        row.state = State.CLOSED.value
        row.latched = False
        row.healthy_count, row.healthy_since = 0, None
        row.updated_at = now

    @staticmethod
    def _event(
        sess: Session,
        spec: BreakerSpec,
        scope_key: str,
        action: str,
        actor: str,
        reason: str,
        now: datetime,
        metrics: Mapping[str, Any],
    ) -> BreakerEvent:
        sess.add(
            BreakerEventRow(
                ts_utc=now,
                name=spec.name.value,
                scope_key=scope_key,
                action=action,
                severity=spec.severity.value,
                actor=actor,
                reason=reason,
                metrics=dict(metrics),
            )
        )
        return BreakerEvent(spec.name, scope_key, action, spec.severity, actor, reason, now, dict(metrics))

    def _publish(self, event: BreakerEvent) -> None:
        level = logging.WARNING if event.action == "TRIP" else logging.INFO
        log.log(
            level, "breaker %s %s scope=%r reason=%s", event.name, event.action, event.scope_key, event.reason
        )
        if self.audit is not None:
            self.audit.append(
                f"BREAKER_{event.action}",
                event.actor,
                {
                    "breaker": event.name.value,
                    "scope": event.scope_key,
                    "severity": event.severity.value,
                    "reason": event.reason,
                    "metrics": dict(event.metrics),
                },
            )
        if self.notify is not None:
            self.notify(event)
