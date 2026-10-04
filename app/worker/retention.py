"""Retention of the cloud database (PLAN §A14 "Worker", §A18; TAA-808).

Only housekeeping tables are pruned. The audit chains, the replicated trading records (decisions, intents,
positions, deals, breaker and kill-switch events) and uploaded history are kept forever: they are the record
of what happened. The live-stream feed caps itself on ingest, and ingest nonces are purged as they are used.

| Table | Removed |
|---|---|
| ``sessions`` | 30 days after they expired or were revoked |
| ``login_throttle`` | counters untouched for 24 h and not locked |
| ``ingest_nonces`` | expired |
| ``engine_commands`` | answered or expired commands older than 90 days |
| ``worker_jobs`` | DONE or FAILED jobs finished more than 30 days ago |
| ``worker_heartbeats`` | workers silent for 7 days |

Rules for new data (quotes 7 days, downsampled snapshots after 90 days) are added with the tables that hold
them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, and_, delete, or_

from app.core.clock import Clock
from app.storage.database import Database
from app.storage.models import EngineCommandRow, IngestNonceRow, LoginThrottleRow, SessionRow
from app.storage.models.worker import WorkerHeartbeatRow, WorkerJobRow
from app.sync.command_queue import OPEN as OPEN_COMMANDS
from app.worker.jobs import CLOSED as CLOSED_JOBS

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rule:
    table: str
    model: type
    where: Callable[[datetime], ColumnElement[bool]]


RULES: tuple[Rule, ...] = (
    Rule(
        "sessions",
        SessionRow,
        lambda now: or_(
            SessionRow.expires_at < now - timedelta(days=30),
            and_(SessionRow.revoked_at.is_not(None), SessionRow.revoked_at < now - timedelta(days=30)),
        ),
    ),
    Rule(
        "login_throttle",
        LoginThrottleRow,
        lambda now: and_(
            LoginThrottleRow.updated_at < now - timedelta(hours=24),
            or_(LoginThrottleRow.locked_until.is_(None), LoginThrottleRow.locked_until < now),
        ),
    ),
    Rule("ingest_nonces", IngestNonceRow, lambda now: IngestNonceRow.expires_at <= now),
    Rule(
        "engine_commands",
        EngineCommandRow,
        lambda now: and_(
            EngineCommandRow.status.not_in(OPEN_COMMANDS),
            EngineCommandRow.created_at < now - timedelta(days=90),
        ),
    ),
    Rule(
        "worker_jobs",
        WorkerJobRow,
        lambda now: and_(
            WorkerJobRow.status.in_(CLOSED_JOBS), WorkerJobRow.finished_at < now - timedelta(days=30)
        ),
    ),
    Rule(
        "worker_heartbeats",
        WorkerHeartbeatRow,
        lambda now: WorkerHeartbeatRow.beat_at < now - timedelta(days=7),
    ),
)


def run_retention(db: Database, clock: Clock, rules: tuple[Rule, ...] = RULES) -> dict[str, int]:
    """Apply every rule in its own transaction; returns the rows removed per table."""
    now = clock.now_utc()
    removed: dict[str, int] = {}
    for rule in rules:
        with db.session() as sess:
            result = sess.execute(delete(rule.model).where(rule.where(now)))
            removed[rule.table] = int(getattr(result, "rowcount", 0) or 0)
    if any(removed.values()):
        log.info("retention removed %s", ", ".join(f"{t}={n}" for t, n in removed.items() if n))
    return removed
