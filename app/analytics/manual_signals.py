"""Signals a manual trade may have followed, from a database (PLAN §A34; TAA-1006).

The engine's linker reads its own database; the cloud reads the replicas of one engine (``engine_id``) to
offer the owner other signals when correcting a link. Candidates are accepted EXECUTION decisions (what the
bot traded or would have traded) and ADVISORY opportunities (what alerts showed) on the symbol and side,
issued within :data:`LOOKBACK` before the fill.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.manual_match import SignalCandidate
from app.core.clock import ensure_utc
from app.core.enums import Side, Timeframe
from app.storage.models import DecisionRecordRow, OpportunityRow

LOOKBACK = timedelta(days=2)


def _bar_seconds(timeframe: str) -> int:
    try:
        return Timeframe(timeframe).seconds
    except ValueError:
        return 900


def _when(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value)
    if isinstance(value, str):
        try:
            return ensure_utc(datetime.fromisoformat(value))
        except ValueError:
            return None
    return None


def load_candidates(
    sess: Session, symbol: str, side: Side, opened_at: datetime, *, engine_id: str | None = None
) -> list[SignalCandidate]:
    """Candidates for a fill of *symbol*/*side* at *opened_at* (``engine_id``: one engine's replicas)."""
    opened_at = ensure_utc(opened_at)
    since = opened_at - LOOKBACK
    out: list[SignalCandidate] = []
    d_filters = [DecisionRecordRow.engine_id == engine_id] if engine_id else []
    decisions = sess.scalars(
        select(DecisionRecordRow).where(
            DecisionRecordRow.symbol == symbol,
            DecisionRecordRow.action == side.value,
            DecisionRecordRow.decision == "ACCEPT",
            DecisionRecordRow.profile == "EXECUTION",
            DecisionRecordRow.created_at >= since,
            DecisionRecordRow.created_at <= opened_at,
            *d_filters,
        )
    ).all()
    for d in decisions:
        signal = d.signal or {}
        issued = _when(signal.get("data_timestamp_utc")) or ensure_utc(d.created_at)
        expires = _when(signal.get("expires_at_utc"))
        if d.entry_price is None or d.stop_loss is None or expires is None:
            continue
        out.append(
            SignalCandidate(
                key=d.idempotency_key,
                symbol=symbol,
                side=side,
                entry=d.entry_price,
                stop=d.stop_loss,
                issued_at=issued,
                expires_at=expires,
                bar_seconds=_bar_seconds(d.timeframe),
                strategy=d.strategy,
                decision_id=d.decision_id,
            )
        )
    o_filters = [OpportunityRow.engine_id == engine_id] if engine_id else []
    opportunities = sess.scalars(
        select(OpportunityRow).where(
            OpportunityRow.symbol == symbol,
            OpportunityRow.side == side.value,
            OpportunityRow.bar_close_at >= since,
            OpportunityRow.bar_close_at <= opened_at,
            *o_filters,
        )
    ).all()
    for o in opportunities:
        expires = ensure_utc(o.signal_expires_at)
        if o.valid_until is not None:
            expires = max(expires, ensure_utc(o.valid_until))
        out.append(
            SignalCandidate(
                key=o.opportunity_id,
                symbol=symbol,
                side=side,
                entry=o.entry,
                stop=o.stop_loss,
                issued_at=ensure_utc(o.bar_close_at),
                expires_at=expires,
                bar_seconds=_bar_seconds(o.timeframe),
                strategy=o.strategy,
                decision_id=o.decision_id or None,
                opportunity_id=o.opportunity_id,
            )
        )
    return out
