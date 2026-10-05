"""The strategies page's read model (PLAN §A15 "TAA-909 decisions"): state, parameters and performance.

- **Configured strategies** come from the config snapshot of the engine's latest run (``strategies.items``).
  Parameters are resolved with this release's strategy catalog (``Params`` defaults + the configured
  overrides), the way the engine's registry builds them. A strategy this release does not know, or whose
  overrides it cannot validate, is shown with its configured overrides only (``known: false``).
- **State:** ``DISABLED_CONFIG`` (``enabled: false`` in ``config.yaml``), ``DISABLED_REMOTE`` (named in the
  newest heartbeat's ``disabled_strategies``: a STRATEGY_DISABLE command, re-enabled only locally),
  ``ENABLED``, or ``UNKNOWN`` while no heartbeat has reported the remote list (none yet, or an engine older
  than TAA-909). A disable command the engine executed after the newest heartbeat was received counts as
  ``DISABLED_REMOTE`` already (the next heartbeat lists it; one received later is authoritative again, so a
  local re-enable shows).
- **Performance** over a window of days: the bot's EXECUTION decisions by result with the most frequent
  rejection reasons, and the PAPER positions closed in the window (net P/L, wins, profit factor, R).
  Results are hypothetical (paper); DEMO broker positions are not replicated as position rows yet.
- ``last_command``: the newest STRATEGY_DISABLE command for the strategy, with its queue state and result.
- Page level: the configured timeframes every context has (a strategy's own ``timeframes`` lists only
  extra ones it reads) and the settings shared by all strategies (cooldown, signal expiry).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.clock import ensure_utc
from app.storage.database import Database
from app.storage.models import (
    ConfigSnapshot,
    DecisionRecordRow,
    EngineCommandRow,
    EngineHeartbeatRow,
    PaperIntentRow,
    PaperPositionRow,
    Run,
)
from app.strategy.catalog import default_registry
from app.sync.command_queue import public
from app.sync.commands import CommandType
from app.sync.events import json_safe

DEFAULT_DAYS = 30
MAX_DAYS = 365
TOP_REASONS = 3
DEFAULT_EXPIRY_BARS = 1  # StrategiesConfig.signal_expiry_bars


class StrategyState(StrEnum):
    """A configured strategy's state; ``frontend/src/i18n/codes.ts`` mirrors it (``codes:strategyState``)."""

    ENABLED = "ENABLED"
    DISABLED_REMOTE = "DISABLED_REMOTE"
    DISABLED_CONFIG = "DISABLED_CONFIG"
    UNKNOWN = "UNKNOWN"


SHARED = ("cooldown_bars", "signal_expiry_bars", "allow_single_indicator_signals")


def _bare(code: str) -> str:
    return code.split(":", 1)[0]


def _describe(item: dict[str, Any], expiry_bars: int) -> dict[str, Any]:
    """Catalog facts and effective parameters of one configured entry (never raises)."""
    name = str(item.get("name", ""))
    raw = item.get("params") or {}
    overrides = dict(raw) if isinstance(raw, dict) else {}
    out: dict[str, Any] = {
        "name": name,
        "configured_enabled": bool(item.get("enabled", True)),
        "overrides": sorted(overrides),
        "known": False,
        "version": None,
        "description": None,
        "demo_only": True,
        "timeframes": [],
        "warmup_bars": None,
        "params": json_safe(overrides),
    }
    registry = default_registry()
    if name not in registry.names:
        return out
    cls = registry.get(name)
    out |= {"version": cls.version, "description": cls.description, "demo_only": cls.demo_only}
    try:
        params = cls.Params.model_validate({"expiry_bars": expiry_bars, **overrides})
        strategy = cls(params)
    except (ValidationError, TypeError, ValueError):
        return out
    return out | {
        "known": True,
        "timeframes": [tf.value for tf in strategy.required_timeframes()],
        "warmup_bars": strategy.warmup_bars(),
        "params": json_safe(params.model_dump(mode="json")),
    }


def _state(
    configured_enabled: bool, name: str, remote: set[str] | None, disabled_after_beat: bool
) -> StrategyState:
    if not configured_enabled:
        return StrategyState.DISABLED_CONFIG
    if disabled_after_beat:  # executed after the newest heartbeat, which cannot list it yet
        return StrategyState.DISABLED_REMOTE
    if remote is None:
        return StrategyState.UNKNOWN
    return StrategyState.DISABLED_REMOTE if name in remote else StrategyState.ENABLED


def _performance(
    net: list[float], r: list[float], open_count: int, last_exit: datetime | None
) -> dict[str, Any]:
    wins = [n for n in net if n > 0]
    losses = [n for n in net if n < 0]
    gross_win, gross_loss = sum(wins), -sum(losses)
    return {
        "trades": len(net),
        "open": open_count,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(net) if net else None,
        "net": round(sum(net), 2) if net else None,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
        "avg_r": sum(r) / len(r) if r else None,
        "r_trades": len(r),
        "last_exit_at": json_safe(None if last_exit is None else ensure_utc(last_exit)),
    }


def strategy_overview(
    db: Database, engine_id: str, now: datetime, days: int = DEFAULT_DAYS
) -> dict[str, Any]:
    """Every configured strategy of the engine's latest run with its state and performance since
    ``now - days``."""
    since = now - timedelta(days=days)
    with db.session() as sess:
        run = sess.execute(
            select(Run).where(Run.engine_id == engine_id).order_by(Run.started_at.desc()).limit(1)
        ).scalar_one_or_none()
        snap = None if run is None else sess.get(ConfigSnapshot, (engine_id, run.config_hash))
        beat = sess.get(EngineHeartbeatRow, engine_id)
        decided = sess.execute(
            select(DecisionRecordRow.strategy, DecisionRecordRow.decision, func.count())
            .where(
                DecisionRecordRow.engine_id == engine_id,
                DecisionRecordRow.profile == "EXECUTION",
                DecisionRecordRow.created_at >= since,
            )
            .group_by(DecisionRecordRow.strategy, DecisionRecordRow.decision)
        ).all()
        rejected = sess.execute(
            select(DecisionRecordRow.strategy, DecisionRecordRow.reason_codes).where(
                DecisionRecordRow.engine_id == engine_id,
                DecisionRecordRow.profile == "EXECUTION",
                DecisionRecordRow.decision == "REJECT",
                DecisionRecordRow.created_at >= since,
            )
        ).all()
        positions = sess.execute(
            select(
                PaperIntentRow.strategy,
                PaperPositionRow.status,
                PaperPositionRow.net,
                PaperPositionRow.r_multiple,
                PaperPositionRow.exit_time,
            )
            .join(
                PaperIntentRow,
                (PaperIntentRow.engine_id == PaperPositionRow.engine_id)
                & (PaperIntentRow.intent_id == PaperPositionRow.intent_id),
            )
            .where(
                PaperPositionRow.engine_id == engine_id,
                (PaperPositionRow.status == "OPEN") | (PaperPositionRow.exit_time >= since),
            )
        ).all()
        commands = list(
            sess.execute(
                select(EngineCommandRow)
                .where(
                    EngineCommandRow.engine_id == engine_id,
                    EngineCommandRow.type == CommandType.STRATEGY_DISABLE.value,
                )
                .order_by(EngineCommandRow.created_at.desc())
                .limit(200)
            ).scalars()
        )
        last_command: dict[str, dict[str, Any]] = {}
        disabled_after_beat: set[str] = set()
        beat_received = None if beat is None else ensure_utc(beat.received_at)
        for row in commands:  # newest first: keep the first one per strategy
            name = str(row.params.get("strategy", ""))
            if name in last_command:
                continue
            last_command[name] = public(row)
            done = None if row.completed_at is None else ensure_utc(row.completed_at)
            if (
                row.status == "EXECUTED"
                and done is not None
                and (beat_received is None or done > beat_received)
            ):
                disabled_after_beat.add(name)

    config = (snap.payload.get("config") or {}) if snap is not None else {}
    section = config.get("strategies") or {}
    items = [i for i in section.get("items") or [] if isinstance(i, dict)]
    expiry = int(section.get("signal_expiry_bars") or DEFAULT_EXPIRY_BARS)
    payload = {} if beat is None else beat.payload
    listed = payload.get("disabled_strategies")
    remote = {str(n) for n in listed} if isinstance(listed, list) else None

    counts: dict[str, Counter[str]] = {}
    for strategy, decision, n in decided:
        counts.setdefault(strategy, Counter())[decision] += int(n)
    reasons: dict[str, Counter[str]] = {}
    for strategy, codes in rejected:
        reasons.setdefault(strategy, Counter()).update({_bare(str(c)) for c in codes or []})
    nets: dict[str, list[float]] = {}
    rs: dict[str, list[float]] = {}
    opens: Counter[str] = Counter()
    last_exit: dict[str, datetime] = {}
    for strategy, status, net, r, exit_time in positions:
        if status == "OPEN":
            opens[strategy] += 1
            continue
        if net is not None:
            nets.setdefault(strategy, []).append(float(net))
        if r is not None:
            rs.setdefault(strategy, []).append(float(r))
        if exit_time is not None and (strategy not in last_exit or exit_time > last_exit[strategy]):
            last_exit[strategy] = exit_time

    strategies = []
    for item in items:
        entry = _describe(item, expiry)
        name = entry["name"]
        per = counts.get(name, Counter())
        entry |= {
            "state": _state(entry["configured_enabled"], name, remote, name in disabled_after_beat).value,
            "decisions": {d: per.get(d, 0) for d in ("ACCEPT", "REJECT", "HOLD")},
            "top_reject_reasons": [
                {"code": code, "count": n}
                for code, n in reasons.get(name, Counter()).most_common(TOP_REASONS)
            ],
            "performance": _performance(
                nets.get(name, []), rs.get(name, []), opens[name], last_exit.get(name)
            ),
            "last_command": last_command.get(name),
        }
        strategies.append(entry)
    frames = config.get("timeframes") or {}
    return {
        "config_hash": None if snap is None else snap.config_hash,
        "run_id": None if run is None else run.run_id,
        "mode": None if run is None else run.mode,
        "heartbeat_at": payload.get("at"),
        "remote_known": remote is not None,
        "window": {"days": days, "since": json_safe(ensure_utc(since))},
        "timeframes": {k: frames.get(k) for k in ("higher", "entry", "refinement")},
        "shared": {k: section.get(k) for k in SHARED},
        "strategies": strategies,
    }
