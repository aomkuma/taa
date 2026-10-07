"""The owner's manual MT5 trades and the signals they followed (PLAN §A34; TAA-1006), cloud side.

The engine links each manual position once (``manual_trade_links``, replicated) and books its close. Here the
owner reads them, sees the alternatives and corrects a link (``manual_trade_overrides``, cloud-only, audited):

- ``CONFIRMED``: the engine's link is right;
- ``OWN_IDEA``: the trade did not follow a signal;
- ``SIGNAL``: it followed this other signal (one of :meth:`ManualTrades.candidates`).

A closed trade compares three results in R for its effective signal: the owner's own (from the MT5 deals),
the signal's PLAN shadow trade and the bot's trade, so "signal vs bot vs me" can be read per trade. The bot's
trade is its position on the broker account when the decision was executed there (DEMO/LIVE, TAA-1208: the
first part of a split entry, as for PAPER), else its paper position; ``bot_source`` says which.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.manual_match import DEFAULT_TOLERANCE_R, ManualFill, rank
from app.analytics.manual_signals import load_candidates
from app.core.clock import Clock, ensure_utc
from app.core.enums import Side
from app.storage.database import Database
from app.storage.models import (
    BrokerTradeRow,
    ManualTradeLinkRow,
    ManualTradeOverrideRow,
    OrderIntentRow,
    PaperIntentRow,
    PaperPositionRow,
    Run,
    ShadowTradeRow,
)
from app.web.readmodels import QueryError

CHOICES = ("CONFIRMED", "OWN_IDEA", "SIGNAL")
STATUSES = ("OPEN", "CLOSED")
MAX_LIMIT = 200


def _iso(value: datetime | None) -> str | None:
    return None if value is None else ensure_utc(value).isoformat()


class ManualTrades:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    # reading -----------------------------------------------------------------------------------------------

    def list(self, engine_id: str, *, status: str | None = None, limit: int = 50) -> dict[str, Any]:
        if status is not None and status not in STATUSES:
            raise QueryError("status: OPEN or CLOSED")
        limit = max(1, min(limit, MAX_LIMIT))
        m = ManualTradeLinkRow
        with self.db.session() as sess:
            where = [m.engine_id == engine_id] + ([m.status == status] if status else [])
            rows = list(
                sess.scalars(select(m).where(*where).order_by(m.opened_at.desc(), m.position_id).limit(limit))
            )
            overrides = {
                o.position_id: o
                for o in sess.scalars(
                    select(ManualTradeOverrideRow).where(
                        ManualTradeOverrideRow.engine_id == engine_id,
                        ManualTradeOverrideRow.position_id.in_([r.position_id for r in rows]),
                    )
                )
            }
            return {"items": [self._item(sess, engine_id, r, overrides.get(r.position_id)) for r in rows]}

    def _row(self, sess: Session, engine_id: str, position_id: int) -> ManualTradeLinkRow:
        row = sess.get(ManualTradeLinkRow, (engine_id, position_id))
        if row is None:
            raise LookupError(position_id)
        return row

    @staticmethod
    def effective(row: ManualTradeLinkRow, override: ManualTradeOverrideRow | None) -> dict[str, Any]:
        """The link that counts: the owner's override, else the engine's match."""
        if override is None or override.choice == "CONFIRMED":
            followed = row.confidence != "UNMATCHED"
            return {
                "source": "AUTO" if override is None else "OWNER",
                "followed": followed,
                "confidence": row.confidence if override is None else "CONFIRMED",
                "signal_key": row.signal_key if followed else None,
                "strategy": row.strategy if followed else None,
                "decision_id": row.decision_id if followed else None,
                "opportunity_id": row.opportunity_id if followed else None,
            }
        followed = override.choice == "SIGNAL"
        return {
            "source": "OWNER",
            "followed": followed,
            "confidence": "OWNER" if followed else "OWN_IDEA",
            "signal_key": override.signal_key,
            "strategy": override.strategy,
            "decision_id": override.decision_id,
            "opportunity_id": override.opportunity_id,
        }

    def _item(
        self, sess: Session, engine_id: str, row: ManualTradeLinkRow, override: ManualTradeOverrideRow | None
    ) -> dict[str, Any]:
        effective = self.effective(row, override)
        return {
            "position_id": row.position_id,
            "ticket": row.ticket,
            "symbol": row.symbol,
            "side": row.side,
            "volume": row.volume,
            "price_open": row.price_open,
            "sl_initial": row.sl_initial,
            "opened_at": _iso(row.opened_at),
            "status": row.status,
            "closed_at": _iso(row.closed_at),
            "close_price": row.close_price,
            "net_profit": row.net_profit,
            "r_multiple": row.r_multiple,
            "auto": {
                "confidence": row.confidence,
                "strategy": row.strategy,
                "decision_id": row.decision_id,
                "opportunity_id": row.opportunity_id,
                "distance_r": row.distance_r,
                "candidates": row.candidates,
            },
            "effective": effective,
            "compare": self._compare(sess, engine_id, effective),
        }

    @staticmethod
    def _compare(sess: Session, engine_id: str, effective: dict[str, Any]) -> dict[str, Any]:
        """The signal's PLAN shadow trade and the bot's trade, in R (None when there is none)."""
        signal_r = signal_status = bot_r = bot_status = bot_source = None
        key = effective.get("opportunity_id") or effective.get("signal_key")
        if key:
            shadow = sess.scalar(
                select(ShadowTradeRow).where(
                    ShadowTradeRow.engine_id == engine_id,
                    ShadowTradeRow.opportunity_id == key,
                    ShadowTradeRow.variant == "PLAN",
                )
            )
            if shadow is not None:
                signal_r, signal_status = shadow.r_multiple, shadow.status
        decision_id = effective.get("decision_id")
        broker = None
        if decision_id:
            broker = ManualTrades._broker(sess, engine_id, decision_id)
        if broker is not None:
            bot_r, bot_status, bot_source = broker
        elif decision_id:
            position = sess.scalar(
                select(PaperPositionRow)
                .join(
                    PaperIntentRow,
                    (PaperIntentRow.intent_id == PaperPositionRow.intent_id)
                    & (PaperIntentRow.engine_id == PaperPositionRow.engine_id),
                )
                .where(
                    PaperPositionRow.engine_id == engine_id,
                    PaperIntentRow.decision_id == effective["decision_id"],
                )
                .order_by(PaperPositionRow.entry_time)
                .limit(1)
            )
            if position is not None:
                bot_r, bot_status, bot_source = position.r_multiple, position.status, "PAPER"
        return {
            "signal_r": signal_r,
            "signal_status": signal_status,
            "bot_r": bot_r,
            "bot_status": bot_status,
            "bot_source": bot_source,
        }

    @staticmethod
    def _broker(sess: Session, engine_id: str, decision_id: str) -> tuple[float | None, str, str] | None:
        """The bot's first broker position of the decision: (R, CLOSED/OPEN, DEMO/LIVE); None when the
        decision never filled on the broker account."""
        intent = sess.scalar(
            select(OrderIntentRow)
            .where(
                OrderIntentRow.engine_id == engine_id,
                OrderIntentRow.decision_id == decision_id,
                OrderIntentRow.position_ticket.is_not(None),
            )
            .order_by(OrderIntentRow.part_index, OrderIntentRow.created_at)
            .limit(1)
        )
        if intent is None or intent.position_ticket is None:
            return None
        trade = sess.get(BrokerTradeRow, (engine_id, intent.position_ticket))
        if trade is not None:
            return trade.r_multiple, "CLOSED", trade.mode
        run_mode = sess.scalar(  # the mode the engine ran in when it sent the order
            select(Run.mode)
            .where(Run.engine_id == engine_id, Run.started_at <= intent.created_at)
            .order_by(Run.started_at.desc())
            .limit(1)
        )
        return None, "OPEN", "LIVE" if run_mode == "LIVE" else "DEMO"

    def candidates(self, engine_id: str, position_id: int) -> dict[str, Any]:
        """Every signal on the trade's symbol and side the owner can pick, qualifying ones first."""
        with self.db.session() as sess:
            row = self._row(sess, engine_id, position_id)
            side = Side(row.side)
            fill = ManualFill(row.position_id, row.symbol, side, row.price_open, ensure_utc(row.opened_at))
            found = load_candidates(sess, row.symbol, side, fill.opened_at, engine_id=engine_id)
        ranked = rank(fill, found, tolerance_r=DEFAULT_TOLERANCE_R)
        return {
            "items": [
                {
                    "signal_key": r.candidate.key,
                    "strategy": r.candidate.strategy,
                    "decision_id": r.candidate.decision_id,
                    "opportunity_id": r.candidate.opportunity_id,
                    "entry": r.candidate.entry,
                    "stop": r.candidate.stop,
                    "issued_at": _iso(r.candidate.issued_at),
                    "expires_at": _iso(r.candidate.expires_at),
                    "qualifies": r.qualifies,
                    "score": r.score,
                    "distance_r": r.distance_r,
                }
                for r in ranked
            ]
        }

    # correcting --------------------------------------------------------------------------------------------

    def save_override(
        self, engine_id: str, position_id: int, *, choice: str, signal_key: str | None, user_id: str
    ) -> dict[str, Any]:
        """Store the owner's correction; ``SIGNAL`` must name one of :meth:`candidates`. Raises
        :class:`QueryError` for an invalid choice and :class:`LookupError` for an unknown trade."""
        if choice not in CHOICES:
            raise QueryError("choice: CONFIRMED, OWN_IDEA or SIGNAL")
        picked: dict[str, Any] | None = None
        if choice == "SIGNAL":
            options = {c["signal_key"]: c for c in self.candidates(engine_id, position_id)["items"]}
            if signal_key is None or signal_key not in options:
                raise QueryError("signal_key: one of the trade's candidate signals")
            picked = options[signal_key]
        with self.db.session() as sess:
            row = self._row(sess, engine_id, position_id)
            override = sess.get(ManualTradeOverrideRow, (engine_id, position_id))
            if override is None:
                override = ManualTradeOverrideRow(engine_id=engine_id, position_id=position_id)
                sess.add(override)
            override.choice = choice
            override.signal_key = None if picked is None else picked["signal_key"]
            override.strategy = None if picked is None else picked["strategy"]
            override.decision_id = None if picked is None else picked["decision_id"]
            override.opportunity_id = None if picked is None else picked["opportunity_id"]
            override.user_id = user_id
            override.updated_at = self.clock.now_utc()
            sess.flush()
            return self._item(sess, engine_id, row, override)

    def clear_override(self, engine_id: str, position_id: int) -> dict[str, Any]:
        """Back to the engine's own match."""
        with self.db.session() as sess:
            row = self._row(sess, engine_id, position_id)
            override = sess.get(ManualTradeOverrideRow, (engine_id, position_id))
            if override is not None:
                sess.delete(override)
                sess.flush()
            return self._item(sess, engine_id, row, None)
