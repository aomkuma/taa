"""Link the owner's manual MT5 positions to the signals they followed (PLAN §A34; TAA-1006).

A position is matched once, when the engine first sees it (:func:`app.analytics.manual_match.match`), and
the result is stored in ``manual_trade_links`` (replicated to the cloud). Later snapshots read the stored
link, so a match never changes after the fact; the owner corrects it in the PWA (a cloud-side override).

When a linked position is no longer open, :meth:`ManualTradeLinker.settle` books its close from the MT5 deals
(price, net profit, R against the stop it had when first seen), so "signal vs bot vs me" can be compared.

Candidates come from the engine's own database (:func:`app.analytics.manual_signals.load_candidates`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.analytics.manual_match import RULE_VERSION, ManualFill, SignalCandidate, match
from app.analytics.manual_signals import load_candidates
from app.broker import mt5_constants as c
from app.broker.models import BrokerPosition, Deal
from app.core.clock import Clock, ensure_utc
from app.core.enums import Side
from app.storage.database import Database
from app.storage.models import ManualTradeLinkRow

log = logging.getLogger(__name__)

SETTLE_SECONDS = 30.0  # how often closed positions are looked up in the deal history
EXIT_ENTRIES = frozenset({c.DEAL_ENTRY_OUT, c.DEAL_ENTRY_OUT_BY, c.DEAL_ENTRY_INOUT})


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
        self._next_settle = 0.0

    def observe(self, positions: Sequence[BrokerPosition]) -> dict[int, ManualTradeLinkRow]:
        """The link of every given (manual) position, matching the ones seen for the first time."""
        out: dict[int, ManualTradeLinkRow] = {}
        for p in positions:
            pid = p.identifier or p.ticket
            row = self._links.get(pid) or self._load(pid) or self._match(p, pid)
            if row.sl_initial is None and p.sl > 0:  # linked before the stop was kept (TAA-1006 part 1)
                row = self._keep_stop(pid, p.sl) or row
            self._links[pid] = row
            out[pid] = row
        return out

    def _load(self, pid: int) -> ManualTradeLinkRow | None:
        with self.db.session() as sess:
            row = sess.scalar(select(ManualTradeLinkRow).where(ManualTradeLinkRow.position_id == pid))
            if row is not None:
                sess.expunge(row)
            return row

    def _keep_stop(self, pid: int, sl: float) -> ManualTradeLinkRow | None:
        with self.db.session() as sess:
            row = sess.scalar(select(ManualTradeLinkRow).where(ManualTradeLinkRow.position_id == pid))
            if row is None:
                return None
            row.sl_initial = sl
            sess.flush()
            sess.expunge(row)
            return row

    def candidates(self, symbol: str, side: Side, opened_at: datetime) -> list[SignalCandidate]:
        with self.db.session() as sess:
            return load_candidates(sess, symbol, side, opened_at)

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
            sl_initial=p.sl if p.sl > 0 else None,
            status="OPEN",
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

    # closing -----------------------------------------------------------------------------------------------

    def settle(self, open_ids: Iterable[int], deals: Callable[[datetime, datetime], list[Deal]]) -> int:
        """Book the close of every OPEN link whose position is gone (at most every :data:`SETTLE_SECONDS`).
        A position whose exit deal is not in the history yet stays OPEN and is tried again. Returns the
        number of trades closed."""
        now = self.clock.monotonic()
        if now < self._next_settle:
            return 0
        self._next_settle = now + SETTLE_SECONDS
        still_open = set(open_ids)
        with self.db.session() as sess:
            gone = [
                r
                for r in sess.scalars(select(ManualTradeLinkRow).where(ManualTradeLinkRow.status == "OPEN"))
                if r.position_id not in still_open
            ]
            if not gone:
                return 0
            since = min(ensure_utc(r.opened_at) for r in gone) - timedelta(minutes=1)
            history = deals(since, self.clock.now_utc())
            closed = 0
            for row in gone:
                if self._close(row, [d for d in history if d.position_id == row.position_id]):
                    self._links.pop(row.position_id, None)
                    closed += 1
            return closed

    @staticmethod
    def _close(row: ManualTradeLinkRow, deals: Sequence[Deal]) -> bool:
        exits = [d for d in deals if d.entry in EXIT_ENTRIES and not d.is_cash_flow]
        volume = sum(d.volume for d in exits)
        if not exits or volume <= 0:
            return False
        price = sum(d.price * d.volume for d in exits) / volume
        row.status = "CLOSED"
        row.closed_at = max(d.time_utc for d in exits)
        row.close_price = round(price, 8)
        row.net_profit = round(sum(d.net for d in deals if not d.is_cash_flow), 2)
        risk = None if row.sl_initial is None else abs(row.price_open - row.sl_initial)
        direction = 1 if row.side == Side.BUY.value else -1
        row.r_multiple = None if not risk else round(direction * (price - row.price_open) / risk, 3)
        log.info("manual position %s closed at %s (%s R)", row.position_id, row.close_price, row.r_multiple)
        return True
