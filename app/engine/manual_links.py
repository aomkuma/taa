"""Link the owner's manual MT5 positions to the signals they followed (PLAN §A34; TAA-1006).

A position is matched once, when the engine first sees it (:func:`app.analytics.manual_match.match`), and
the result is stored in ``manual_trade_links`` (replicated to the cloud). Later snapshots read the stored
link, so a match never changes after the fact; the owner corrects it in the PWA (a cloud-side override).

When a linked position is no longer open, :meth:`ManualTradeLinker.settle` books its close from the MT5 deals
(price, net profit, R against the stop it had when first seen), so "signal vs bot vs me" can be compared.

A manual position that opened and closed while the engine did not watch (stopped, or between two snapshots)
was never seen open: :meth:`ManualTradeLinker.backfill` finds it in the deal history of the last
:data:`BACKFILL_DAYS` and links it the same way, closed at once. Its stop is not known (MT5 keeps no stop in
the deals, and the owner sets it after the fill, so the opening order has none either), so it has no R.

Candidates come from the engine's own database (:func:`app.analytics.manual_signals.load_candidates`).
"""

from __future__ import annotations

import logging
from collections import defaultdict
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
from app.core.errors import TaaError
from app.storage.database import Database
from app.storage.models import ManualTradeLinkRow

log = logging.getLogger(__name__)

SETTLE_SECONDS = 30.0  # how often closed positions are looked up in the deal history
BACKFILL_SECONDS = 300.0  # how often the deal history is searched for manual trades never seen open
BACKFILL_DAYS = 30
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
        self._next_backfill = 0.0

    def observe(self, positions: Sequence[BrokerPosition]) -> dict[int, ManualTradeLinkRow]:
        """The link of every given (manual) position, matching the ones seen for the first time."""
        out: dict[int, ManualTradeLinkRow] = {}
        for p in positions:
            pid = p.identifier or p.ticket
            row = self._links.get(pid) or self._load(pid) or self._match(p, pid)
            if row.sl_initial is None and p.sl > 0:  # linked before the stop was kept (TAA-1006 part 1)
                row = self._keep_stop(pid, p.sl) or row
            elif row.stop_history is not None and row.sl_initial is not None:
                row = self._track_stop(row, p.sl) or row
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

    def _track_stop(self, row: ManualTradeLinkRow, sl: float) -> ManualTradeLinkRow | None:
        """Record a stop change of a manual position (TAA-L808: was the stop widened or removed?)."""
        history = list(row.stop_history or [])
        last = history[-1]["sl"] if history else row.sl_initial
        current = sl if sl > 0 else None
        if current == last:
            return None
        history.append({"at": self.clock.now_utc().isoformat(), "sl": current})
        with self.db.session() as sess:
            stored = sess.scalar(
                select(ManualTradeLinkRow).where(ManualTradeLinkRow.position_id == row.position_id)
            )
            if stored is None:
                return None
            stored.stop_history = history
            sess.flush()
            sess.expunge(stored)
            return stored

    def candidates(self, symbol: str, side: Side, opened_at: datetime) -> list[SignalCandidate]:
        with self.db.session() as sess:
            return load_candidates(sess, symbol, side, opened_at)

    def _link(self, fill: ManualFill, ticket: int, volume: float) -> ManualTradeLinkRow:
        """A new, unsaved link of *fill* to the signal it followed (or UNMATCHED)."""
        m = match(fill, self.candidates(fill.symbol, fill.side, fill.opened_at), tolerance_r=self.tolerance_r)
        c = m.candidate
        log.info(
            "manual position %s %s %s: %s %s",
            fill.position_id,
            fill.symbol,
            fill.side.value,
            m.confidence.value,
            "" if c is None else f"{c.strategy} ({c.decision_id or c.opportunity_id})",
        )
        return ManualTradeLinkRow(
            position_id=fill.position_id,
            ticket=ticket,
            symbol=fill.symbol,
            side=fill.side.value,
            volume=volume,
            price_open=fill.price_open,
            opened_at=fill.opened_at,
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
            status="OPEN",
        )

    def _store(self, row: ManualTradeLinkRow) -> bool:
        with self.db.session() as sess:
            if sess.scalar(
                select(ManualTradeLinkRow).where(ManualTradeLinkRow.position_id == row.position_id)
            ):
                return False
            sess.add(row)
            sess.flush()
            sess.expunge(row)
            return True

    def _match(self, p: BrokerPosition, pid: int) -> ManualTradeLinkRow:
        fill = ManualFill(pid, p.symbol, p.side, p.price_open, ensure_utc(p.time_utc))
        row = self._link(fill, p.ticket, p.volume)
        row.sl_initial = p.sl if p.sl > 0 else None
        row.stop_history = []
        self._store(row)
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

    def backfill(
        self,
        open_ids: Iterable[int],
        deals: Callable[[datetime, datetime], list[Deal]],
        is_bot: Callable[[int], bool],
    ) -> int:
        """Link, closed at once, every manual position of the last :data:`BACKFILL_DAYS` that opened and fully
        closed without ever being seen open (at most every :data:`BACKFILL_SECONDS`). Returns how many."""
        now = self.clock.monotonic()
        if now < self._next_backfill:
            return 0
        self._next_backfill = now + BACKFILL_SECONDS
        until = self.clock.now_utc()
        try:
            history = deals(until - timedelta(days=BACKFILL_DAYS), until + timedelta(minutes=1))
        except TaaError:
            log.warning("history_deals_get failed; manual trades are backfilled later")
            return 0
        by_position: dict[int, list[Deal]] = defaultdict(list)
        for d in history:
            if not d.is_cash_flow and d.position_id:
                by_position[d.position_id].append(d)
        still_open = set(open_ids)
        with self.db.session() as sess:
            known = set(
                sess.scalars(
                    select(ManualTradeLinkRow.position_id).where(
                        ManualTradeLinkRow.position_id.in_(list(by_position))
                    )
                )
            )
        added = 0
        for pid, own in by_position.items():
            if pid in known or pid in still_open:
                continue
            entries = [d for d in own if d.entry == c.DEAL_ENTRY_IN]
            exits = [d for d in own if d.entry in EXIT_ENTRIES]
            volume = sum(d.volume for d in entries)
            # opened before the window, still (partly) open, or the bot's own: not a missed manual trade
            if not entries or not exits or is_bot(entries[0].magic):
                continue
            if sum(d.volume for d in exits) < volume - 1e-9:
                continue
            side = Side.BUY if entries[0].type == c.DEAL_TYPE_BUY else Side.SELL
            price = sum(d.price * d.volume for d in entries) / volume
            fill = ManualFill(pid, entries[0].symbol, side, round(price, 8), min(d.time_utc for d in entries))
            row = self._link(fill, pid, round(volume, 8))
            if self._close(row, own) and self._store(row):
                added += 1
        if added:
            log.info("backfilled %d manual trade(s) closed while the engine did not watch", added)
        return added

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
