"""Link the owner's manual MT5 positions to the signals they followed (PLAN §A34; TAA-1006).

A position is matched once, when the engine first sees it (:func:`app.analytics.manual_match.match`), and
the result is stored in ``manual_trade_links`` (replicated to the cloud). Later snapshots read the stored
link, so a match never changes after the fact; the owner corrects it in the PWA (a cloud-side override).

Candidates come from the engine's own database: accepted EXECUTION decisions (what the bot traded or would
have traded) and ADVISORY opportunities (what alerts showed) on the position's symbol and side, issued within
:data:`LOOKBACK` before the position opened.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.analytics.manual_match import RULE_VERSION, ManualFill, SignalCandidate, match
from app.broker.models import BrokerPosition
from app.core.clock import Clock, ensure_utc
from app.core.enums import Side, Timeframe
from app.storage.database import Database
from app.storage.models import DecisionRecordRow, ManualTradeLinkRow, OpportunityRow

log = logging.getLogger(__name__)

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


def link_dict(row: ManualTradeLinkRow) -> dict[str, Any]:
    """The heartbeat's view of a link (``ManualLink`` in app/sync/heartbeat.py)."""
    return {
        "confidence": row.confidence,
        "strategy": row.strategy,
        "decision_id": row.decision_id,
        "opportunity_id": row.opportunity_id,
        "distance_r": row.distance_r,
    }


class ManualTradeLinker:
    def __init__(self, db: Database, clock: Clock, *, tolerance_r: float = 0.5) -> None:
        self.db = db
        self.clock = clock
        self.tolerance_r = tolerance_r
        self._links: dict[int, ManualTradeLinkRow] = {}

    def observe(self, positions: Sequence[BrokerPosition]) -> dict[int, ManualTradeLinkRow]:
        """The link of every given (manual) position, matching the ones seen for the first time."""
        out: dict[int, ManualTradeLinkRow] = {}
        for p in positions:
            pid = p.identifier or p.ticket
            row = self._links.get(pid) or self._load(pid) or self._match(p, pid)
            self._links[pid] = row
            out[pid] = row
        return out

    def _load(self, pid: int) -> ManualTradeLinkRow | None:
        with self.db.session() as sess:
            row = sess.scalar(select(ManualTradeLinkRow).where(ManualTradeLinkRow.position_id == pid))
            if row is not None:
                sess.expunge(row)
            return row

    def candidates(self, symbol: str, side: Side, opened_at: datetime) -> list[SignalCandidate]:
        since = opened_at - LOOKBACK
        out: list[SignalCandidate] = []
        with self.db.session() as sess:
            decisions = sess.scalars(
                select(DecisionRecordRow).where(
                    DecisionRecordRow.symbol == symbol,
                    DecisionRecordRow.action == side.value,
                    DecisionRecordRow.decision == "ACCEPT",
                    DecisionRecordRow.profile == "EXECUTION",
                    DecisionRecordRow.created_at >= since,
                    DecisionRecordRow.created_at <= opened_at,
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
            opportunities = sess.scalars(
                select(OpportunityRow).where(
                    OpportunityRow.symbol == symbol,
                    OpportunityRow.side == side.value,
                    OpportunityRow.bar_close_at >= since,
                    OpportunityRow.bar_close_at <= opened_at,
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

    def _match(self, p: BrokerPosition, pid: int) -> ManualTradeLinkRow:
        opened = ensure_utc(p.time_utc)
        fill = ManualFill(pid, p.symbol, p.side, p.price_open, opened)
        m = match(fill, self.candidates(p.symbol, p.side, opened), tolerance_r=self.tolerance_r)
        c = m.candidate
        row = ManualTradeLinkRow(
            position_id=pid,
            ticket=p.ticket,
            symbol=p.symbol,
            side=p.side.value,
            volume=p.volume,
            price_open=p.price_open,
            opened_at=opened,
            confidence=m.confidence.value,
            signal_key=None if c is None else c.key,
            strategy=None if c is None else c.strategy,
            decision_id=None if c is None else c.decision_id,
            opportunity_id=None if c is None else c.opportunity_id,
            score=m.score,
            distance_r=m.distance_r,
            candidates=m.candidates,
            rule_version=RULE_VERSION,
            matched_at=self.clock.now_utc(),
        )
        with self.db.session() as sess:
            if sess.scalar(select(ManualTradeLinkRow).where(ManualTradeLinkRow.position_id == pid)) is None:
                sess.add(row)
                sess.flush()
                sess.expunge(row)
        log.info(
            "manual position %s %s %s: %s %s",
            pid,
            p.symbol,
            p.side.value,
            m.confidence.value,
            "" if c is None else f"{c.strategy} ({c.decision_id or c.opportunity_id})",
        )
        return row
