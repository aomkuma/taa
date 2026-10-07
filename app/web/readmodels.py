"""Read models of the PWA API: queries over the replicated tables, always scoped to one engine (TAA-803).

Every function takes the ``engine_id`` that :func:`app.web.deps.owned_engine` resolved for the session user;
nothing here can reach another engine's rows. Results are plain JSON-ready dicts (aware datetimes as ISO 8601,
non-finite floats as null), so the routers stay thin and the PWA validates them with zod.

**Pagination** is keyset-based: newest first by a time column, then by the primary key. ``next_cursor`` is an
opaque token for the following page (``None`` on the last one). Pages hold at most ``MAX_LIMIT`` items.
"""

from __future__ import annotations

import base64
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import ColumnElement, String, and_, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.config import IndicatorParams
from app.core.clock import ensure_utc
from app.core.enums import Timeframe
from app.core.errors import TaaError
from app.indicators.momentum import rsi
from app.indicators.price_action import find_swings, sr_zones
from app.indicators.trend import adx, ema
from app.indicators.volatility import atr, bollinger
from app.market_data.history_store import SqlHistoryStore
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    AuditReplicaRow,
    BreakerEventRow,
    BreakerStateRow,
    BrokerTradeRow,
    ConfigSnapshot,
    DecisionCheckRow,
    DecisionRecordRow,
    EngineCommandRow,
    EngineHeartbeatRow,
    HistoryCandle,
    KillSwitchEvent,
    OrderIntentRow,
    PaperAccountRow,
    PaperIntentRow,
    PaperPositionRow,
    ReplicaVersionRow,
    RiskBaseline,
    RiskState,
    Run,
    SymbolCatalogRow,
)
from app.sync.command_queue import public
from app.sync.events import json_safe
from app.sync.heartbeat import BULKY

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_CANDLES = 2000
MAX_ZONES = 8
# the engine's trade lifecycle events on its audit chain (app.engine.trade_audit)
TRADE_EVENT_TYPES = ("POSITION_OPENED", "STOP_MOVED", "POSITION_CLOSED")
TRADE_EVENT_SLACK = timedelta(minutes=5)
ZONE_ATR_PERIOD = 14
SECRET_KEY = re.compile(r"secret|password|token|api_key|totp|hmac", re.I)


class QueryError(TaaError):
    """A request parameter is unusable (the router answers 400 ``invalid_query``)."""


# --- helpers ------------------------------------------------------------------------------------------------


def row_dict(row: Any, *, skip: Sequence[str] = ("engine_id",)) -> dict[str, Any]:
    """Every column of an ORM row, JSON-ready (the engine id is implied by the URL)."""
    return {c.key: json_safe(getattr(row, c.key)) for c in row.__table__.columns if c.key not in skip}


REASON_RE = re.compile(r"[A-Z][A-Z0-9_]{1,47}")


def reason_filter(column: Any, code: str) -> ColumnElement[bool]:
    """Rows whose JSON list of reason codes holds *code*, bare or parameterized (``CODE:detail``). Matched on
    the JSON text, which works on SQLite and PostgreSQL alike; ``_`` is escaped (a LIKE wildcard)."""
    if not REASON_RE.fullmatch(code):
        raise QueryError("reason: an upper-case reason code")
    text = func.cast(column, String)
    escaped = code.replace("_", r"\_")
    return or_(text.like(f'%"{escaped}"%', escape="\\"), text.like(f'%"{escaped}:%', escape="\\"))


def heartbeat_dict(row: EngineHeartbeatRow) -> dict[str, Any]:
    """The newest heartbeat as the stream sends it (``status``/``heartbeat``: the payload without quotes, plus
    ``received_at`` on the cloud clock) and the watchdog's verdict (TAA-705)."""
    return {
        **{k: v for k, v in row.payload.items() if k not in BULKY},
        "received_at": json_safe(ensure_utc(row.received_at)),
        "watch_status": row.watch_status,
        "offline_since": json_safe(None if row.offline_since is None else ensure_utc(row.offline_since)),
        "offline_reason": row.offline_reason,
    }


@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    next_cursor: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"items": self.items, "next_cursor": self.next_cursor}


def _encode(when: datetime, key: Any) -> str:
    raw = json.dumps([ensure_utc(when).isoformat(), key], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        when, key = json.loads(raw)
        return ensure_utc(datetime.fromisoformat(when)), key
    except (ValueError, TypeError) as exc:
        raise QueryError("cursor: not a cursor of this API") from exc


def limit_of(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if not 1 <= limit <= MAX_LIMIT:
        raise QueryError(f"limit: 1-{MAX_LIMIT}")
    return limit


def paginate(
    sess: Session,
    model: Any,
    where: Sequence[ColumnElement[bool]],
    time_col: InstrumentedAttribute[Any],
    key_col: InstrumentedAttribute[Any],
    *,
    limit: int | None,
    cursor: str | None,
    serialize: Callable[[Any], dict[str, Any]] = row_dict,
) -> Page:
    """Newest first by ``time_col`` then ``key_col``; the cursor continues after the last item."""
    n = limit_of(limit)
    query = select(model).where(*where)
    if cursor:
        when, key = _decode(cursor)
        query = query.where(or_(time_col < when, and_(time_col == when, key_col < key)))
    rows = list(sess.execute(query.order_by(time_col.desc(), key_col.desc()).limit(n + 1)).scalars())
    more = len(rows) > n
    rows = rows[:n]
    nxt = _encode(getattr(rows[-1], time_col.key), getattr(rows[-1], key_col.key)) if more else None
    return Page([serialize(r) for r in rows], nxt)


def mask_config(value: Any) -> Any:
    """Defence in depth over the engine's own masking (``Settings.summary``): any key that names a secret is
    replaced, whatever its value."""
    if isinstance(value, Mapping):
        return {
            str(k): ("***" if SECRET_KEY.search(str(k)) and v not in (None, "") else mask_config(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [mask_config(v) for v in value]
    return value


# --- read models --------------------------------------------------------------------------------------------


class ReadModels:
    def __init__(self, db: Database) -> None:
        self.db = db

    def status(self, engine_id: str) -> dict[str, Any]:
        with self.db.session() as sess:
            run = sess.execute(
                select(Run).where(Run.engine_id == engine_id).order_by(Run.started_at.desc()).limit(1)
            ).scalar_one_or_none()
            last_received = sess.execute(
                select(func.max(ReplicaVersionRow.received_at)).where(
                    ReplicaVersionRow.engine_id == engine_id
                )
            ).scalar_one()
            kill = sess.execute(
                select(KillSwitchEvent)
                .where(KillSwitchEvent.engine_id == engine_id)
                .order_by(KillSwitchEvent.ts_utc.desc(), KillSwitchEvent.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            open_breakers = sess.execute(
                select(func.count())
                .select_from(BreakerStateRow)
                .where(BreakerStateRow.engine_id == engine_id, BreakerStateRow.state != "CLOSED")
            ).scalar_one()
            open_positions = sess.execute(
                select(func.count())
                .select_from(PaperPositionRow)
                .where(PaperPositionRow.engine_id == engine_id, PaperPositionRow.status == "OPEN")
            ).scalar_one()
            chain = sess.get(AuditReplicaRow, f"engine:{engine_id}")
            beat = sess.get(EngineHeartbeatRow, engine_id)
            heartbeat = None if beat is None else heartbeat_dict(beat)
        return {
            "run": None if run is None else row_dict(run, skip=("engine_id", "host")),
            "last_received_at": json_safe(None if last_received is None else ensure_utc(last_received)),
            "kill_switch": {
                "active": kill is not None and kill.action == "ACTIVATE",
                "last": None if kill is None else row_dict(kill, skip=("engine_id", "id")),
            },
            "open_breakers": int(open_breakers),
            "open_positions": int(open_positions),
            "audit": None if chain is None else row_dict(chain, skip=("engine_id",)),
            "heartbeat": heartbeat,
        }

    def quotes(self, engine_id: str) -> dict[str, Any]:
        """The newest quotes of the engine's traded symbols, from its newest heartbeat (TAA-906)."""
        with self.db.session() as sess:
            beat = sess.get(EngineHeartbeatRow, engine_id)
            if beat is None:
                return {"at": None, "received_at": None, "quotes": []}
            return {
                "at": beat.payload.get("at"),
                "received_at": json_safe(ensure_utc(beat.received_at)),
                "quotes": list(beat.payload.get("quotes", [])),
            }

    def account(self, engine_id: str) -> dict[str, Any]:
        with self.db.session() as sess:
            accounts = sess.execute(
                select(PaperAccountRow).where(PaperAccountRow.engine_id == engine_id)
            ).scalars()
            risk = sess.execute(select(RiskState).where(RiskState.engine_id == engine_id)).scalars()
            baselines = sess.execute(
                select(RiskBaseline)
                .where(RiskBaseline.engine_id == engine_id)
                .order_by(RiskBaseline.created_at.desc())
                .limit(14)
            ).scalars()
            closed = sess.execute(
                select(PaperPositionRow.account_key, PaperPositionRow.exit_time, PaperPositionRow.net)
                .where(
                    PaperPositionRow.engine_id == engine_id,
                    PaperPositionRow.status == "CLOSED",
                    PaperPositionRow.exit_time.is_not(None),
                )
                .order_by(PaperPositionRow.exit_time)
            ).all()
            paper = [row_dict(a) for a in accounts]
            out: dict[str, Any] = {
                "paper_accounts": paper,
                "risk_state": [row_dict(r) for r in risk],
                "baselines": [row_dict(b) for b in baselines],
            }
        initial = {a["account_key"]: float(a["initial_balance"]) for a in paper}
        curves: dict[str, list[dict[str, Any]]] = {}
        equity = dict(initial)
        for account_key, exit_time, net in closed:  # realized equity after each closed paper trade
            if account_key not in equity or net is None or exit_time is None:
                continue
            equity[account_key] += float(net)
            curves.setdefault(account_key, []).append(
                {"at": json_safe(ensure_utc(exit_time)), "equity": round(equity[account_key], 2)}
            )
        out["realized_equity"] = curves
        return out

    def positions(
        self, engine_id: str, *, status: str | None, symbol: str | None, limit: int | None, cursor: str | None
    ) -> Page:
        where = [PaperPositionRow.engine_id == engine_id]
        if status:
            if status not in ("OPEN", "CLOSED"):
                raise QueryError("status: OPEN or CLOSED")
            where.append(PaperPositionRow.status == status)
        if symbol:
            where.append(PaperPositionRow.symbol == symbol)
        time_col = PaperPositionRow.exit_time if status == "CLOSED" else PaperPositionRow.entry_time
        with self.db.session() as sess:
            return paginate(
                sess, PaperPositionRow, where, time_col, PaperPositionRow.ticket, limit=limit, cursor=cursor
            )

    def broker_trades(
        self, engine_id: str, *, symbol: str | None, limit: int | None, cursor: str | None
    ) -> Page:
        """Closed bot positions on the broker account (DEMO/LIVE; TAA-1208), newest exit first."""
        where = [BrokerTradeRow.engine_id == engine_id]
        if symbol:
            where.append(BrokerTradeRow.symbol == symbol)
        with self.db.session() as sess:
            return paginate(
                sess,
                BrokerTradeRow,
                where,
                BrokerTradeRow.exit_time,
                BrokerTradeRow.position_ticket,
                limit=limit,
                cursor=cursor,
            )

    def trade(self, engine_id: str, ticket: int) -> dict[str, Any] | None:
        """One paper position with what led to it and what happened to it (TAA-907): its intent, the
        decision (with its checks and signal summary) and the trade lifecycle events from the engine's
        audit chain (opened, stop moves, closed), oldest first."""
        with self.db.session() as sess:
            pos = sess.get(PaperPositionRow, (engine_id, ticket))
            if pos is None:
                return None
            intent = sess.get(PaperIntentRow, (engine_id, pos.intent_id))
            decision = (
                None if intent is None else sess.get(DecisionRecordRow, (engine_id, intent.decision_id))
            )
            checks: list[DecisionCheckRow] = (
                []
                if decision is None
                else list(
                    sess.execute(
                        select(DecisionCheckRow)
                        .where(
                            DecisionCheckRow.engine_id == engine_id,
                            DecisionCheckRow.decision_id == decision.decision_id,
                        )
                        .order_by(DecisionCheckRow.seq)
                    ).scalars()
                )
            )
            start = ensure_utc(pos.entry_time) - TRADE_EVENT_SLACK
            where = [
                AuditEvent.engine_id == engine_id,
                AuditEvent.event_type.in_(TRADE_EVENT_TYPES),
                AuditEvent.ts_utc >= start,
            ]
            if pos.exit_time is not None:
                where.append(AuditEvent.ts_utc <= ensure_utc(pos.exit_time) + TRADE_EVENT_SLACK)
            events = [
                {"type": e.event_type, "at": json_safe(ensure_utc(e.ts_utc)), "payload": dict(e.payload)}
                for e in sess.execute(
                    select(AuditEvent).where(*where).order_by(AuditEvent.ts_utc, AuditEvent.seq)
                ).scalars()
                if e.payload.get("ticket") == ticket and e.payload.get("paper") is True
            ]
            return {
                "position": row_dict(pos),
                "intent": None if intent is None else row_dict(intent),
                "decision": None
                if decision is None
                else row_dict(decision, skip=("engine_id", "market", "plan"))
                | {"checks": [row_dict(c, skip=("engine_id", "id")) for c in checks]},
                "events": events,
            }

    def intents(
        self,
        engine_id: str,
        *,
        kind: str,
        status: str | None,
        symbol: str | None,
        limit: int | None,
        cursor: str | None,
    ) -> Page:
        model: Any = {"paper": PaperIntentRow, "broker": OrderIntentRow}.get(kind)
        if model is None:
            raise QueryError("kind: paper or broker")
        status_col = model.status if model is PaperIntentRow else model.state
        where = [model.engine_id == engine_id]
        if status:
            where.append(status_col == status)
        if symbol:
            where.append(model.symbol == symbol)
        with self.db.session() as sess:
            return paginate(sess, model, where, model.created_at, model.intent_id, limit=limit, cursor=cursor)

    def decisions(
        self,
        engine_id: str,
        *,
        decision: str | None,
        symbol: str | None,
        strategy: str | None,
        profile: str | None,
        limit: int | None,
        cursor: str | None,
        reason: str | None = None,
    ) -> Page:
        m = DecisionRecordRow
        where = [m.engine_id == engine_id]
        if reason:
            where.append(reason_filter(m.reason_codes, reason))
        for col, value in (
            (m.decision, decision),
            (m.symbol, symbol),
            (m.strategy, strategy),
            (m.profile, profile),
        ):
            if value:
                where.append(col == value)

        def brief(row: DecisionRecordRow) -> dict[str, Any]:  # the list leaves out the large documents
            return row_dict(row, skip=("engine_id", "signal", "market", "plan"))

        with self.db.session() as sess:
            return paginate(
                sess, m, where, m.created_at, m.decision_id, limit=limit, cursor=cursor, serialize=brief
            )

    def decision(self, engine_id: str, decision_id: str) -> dict[str, Any] | None:
        with self.db.session() as sess:
            row = sess.get(DecisionRecordRow, (engine_id, decision_id))
            if row is None:
                return None
            checks = sess.execute(
                select(DecisionCheckRow)
                .where(DecisionCheckRow.engine_id == engine_id, DecisionCheckRow.decision_id == decision_id)
                .order_by(DecisionCheckRow.seq)
            ).scalars()
            return row_dict(row) | {"checks": [row_dict(c, skip=("engine_id", "id")) for c in checks]}

    def breakers(self, engine_id: str, *, limit: int | None, cursor: str | None) -> dict[str, Any]:
        with self.db.session() as sess:
            states = sess.execute(
                select(BreakerStateRow)
                .where(BreakerStateRow.engine_id == engine_id)
                .order_by(BreakerStateRow.name, BreakerStateRow.scope_key)
            ).scalars()
            events = paginate(
                sess,
                BreakerEventRow,
                [BreakerEventRow.engine_id == engine_id],
                BreakerEventRow.ts_utc,
                BreakerEventRow.id,
                limit=limit,
                cursor=cursor,
                serialize=lambda r: row_dict(r, skip=("engine_id", "id")),
            )
            return {"states": [row_dict(s) for s in states], "events": events.to_dict()}

    def kill_switch(self, engine_id: str, *, limit: int | None, cursor: str | None) -> Page:
        with self.db.session() as sess:
            return paginate(
                sess,
                KillSwitchEvent,
                [KillSwitchEvent.engine_id == engine_id],
                KillSwitchEvent.ts_utc,
                KillSwitchEvent.id,
                limit=limit,
                cursor=cursor,
                serialize=lambda r: row_dict(r, skip=("engine_id", "id")),
            )

    def symbols(
        self, engine_id: str, *, asset_class: str | None, enabled: bool | None
    ) -> list[dict[str, Any]]:
        where = [SymbolCatalogRow.engine_id == engine_id, SymbolCatalogRow.present.is_(True)]
        if asset_class:
            where.append(SymbolCatalogRow.asset_class == asset_class)
        if enabled is not None:
            where.append(SymbolCatalogRow.enabled.is_(enabled))
        with self.db.session() as sess:
            rows = sess.execute(
                select(SymbolCatalogRow).where(*where).order_by(SymbolCatalogRow.symbol)
            ).scalars()
            return [row_dict(r, skip=("engine_id", "spec")) for r in rows]

    def symbol(self, engine_id: str, symbol: str) -> dict[str, Any] | None:
        with self.db.session() as sess:
            row = sess.execute(
                select(SymbolCatalogRow)
                .where(SymbolCatalogRow.engine_id == engine_id, SymbolCatalogRow.symbol == symbol)
                .order_by(SymbolCatalogRow.refreshed_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            return None if row is None else row_dict(row)

    def commands(self, engine_id: str, *, status: str | None, limit: int | None, cursor: str | None) -> Page:
        """Remote commands queued for the engine (TAA-805), newest first; TOTP codes are never included."""
        m = EngineCommandRow
        where = [m.engine_id == engine_id]
        if status:
            where.append(m.status == status)
        with self.db.session() as sess:
            return paginate(
                sess, m, where, m.created_at, m.command_id, limit=limit, cursor=cursor, serialize=public
            )

    def config(self, engine_id: str) -> dict[str, Any] | None:
        with self.db.session() as sess:
            run = sess.execute(
                select(Run).where(Run.engine_id == engine_id).order_by(Run.started_at.desc()).limit(1)
            ).scalar_one_or_none()
            if run is None:
                return None
            snap = sess.get(ConfigSnapshot, (engine_id, run.config_hash))
            if snap is None:
                return None
            return {
                "config_hash": snap.config_hash,
                "created_at": json_safe(ensure_utc(snap.created_at)),
                "config": mask_config(snap.payload),
            }

    # --- candles ----------------------------------------------------------------------------------------

    def default_server(self, engine_id: str, symbol: str) -> str | None:
        """The trade server of the engine's newest bars for *symbol* (a user rarely has more than one)."""
        with self.db.session() as sess:
            row = sess.execute(
                select(HistoryCandle.server)
                .where(HistoryCandle.engine_id == engine_id, HistoryCandle.symbol == symbol)
                .order_by(HistoryCandle.open_time.desc())
                .limit(1)
            ).scalar_one_or_none()
        return row

    def candles(
        self,
        engine_id: str,
        *,
        server: str,
        symbol: str,
        timeframe: str,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        overlays: Sequence[str],
        zones: bool = False,
    ) -> dict[str, Any]:
        try:
            tf = Timeframe(timeframe)
        except ValueError as exc:
            raise QueryError("timeframe: one of " + ", ".join(t.value for t in Timeframe)) from exc
        if not 1 <= limit <= MAX_CANDLES:
            raise QueryError(f"limit: 1-{MAX_CANDLES}")
        specs = [parse_overlay(o) for o in overlays]
        warmup = max((w for _, _, w in specs), default=ZONE_ATR_PERIOD if zones else 0)
        stored = SqlHistoryStore(self.db, engine_id).load(server, symbol, tf, None, end)
        # shown: `limit` bars from `start` (else the newest); indicators warm up on up to `warmup` bars before
        if start is not None:
            i0 = int((stored["open_time"] < pd.Timestamp(ensure_utc(start))).sum())
        else:
            i0 = max(0, len(stored) - limit)
        i1 = min(len(stored), i0 + limit)
        w0 = max(0, i0 - warmup)
        df = stored.iloc[w0:i1].reset_index(drop=True)
        shown = df.iloc[i0 - w0 :]
        out: dict[str, Any] = {
            "server": server,
            "symbol": symbol,
            "timeframe": tf.value,
            "bars": [
                [json_safe(t.to_pydatetime()), o, h, lo, c, int(v)]
                for t, o, h, lo, c, v in zip(
                    shown["open_time"],
                    shown["open"],
                    shown["high"],
                    shown["low"],
                    shown["close"],
                    shown["tick_volume"],
                    strict=True,
                )
            ],
            "overlays": {
                name: [json_safe(x) for x in series.iloc[len(df) - len(shown) :]]
                for name, series in _overlays(df, specs)
            },
        }
        out["markers"] = self._markers(engine_id, symbol, shown) if not shown.empty else []
        if zones:
            out["zones"] = _zones(df)
        # the live view (no time window) gets the engine's forming bar from its newest heartbeat
        last_open = (
            None if shown.empty else ensure_utc(pd.Timestamp(shown["open_time"].iloc[-1]).to_pydatetime())
        )
        live = start is None and end is None
        out["forming"] = self._forming(engine_id, symbol, tf, last_open) if live else None
        return out

    def _forming(
        self, engine_id: str, symbol: str, tf: Timeframe, after: datetime | None
    ) -> list[Any] | None:
        """``[open_time, o, h, l, c, tick_volume]`` of the bar still forming, newer than the last closed one.
        Display only: it changes until it closes, then arrives as a closed bar."""
        with self.db.session() as sess:
            beat = sess.get(EngineHeartbeatRow, engine_id)
            bars = [] if beat is None else list(beat.payload.get("forming") or [])
        for bar in bars:
            if bar.get("symbol") != symbol or bar.get("timeframe") != tf.value:
                continue
            opened = datetime.fromisoformat(str(bar["open_time"]))
            if after is not None and opened <= after:
                return None
            return [
                json_safe(ensure_utc(opened)),
                bar["open"],
                bar["high"],
                bar["low"],
                bar["close"],
                bar["tick_volume"],
            ]
        return None

    def _markers(self, engine_id: str, symbol: str, shown: pd.DataFrame) -> list[dict[str, Any]]:
        first = ensure_utc(pd.Timestamp(shown["open_time"].iloc[0]).to_pydatetime())
        last = ensure_utc(pd.Timestamp(shown["close_time"].iloc[-1]).to_pydatetime())
        markers: list[dict[str, Any]] = []
        with self.db.session() as sess:
            decisions = sess.execute(
                select(DecisionRecordRow).where(
                    DecisionRecordRow.engine_id == engine_id,
                    DecisionRecordRow.symbol == symbol,
                    DecisionRecordRow.created_at >= first,
                    DecisionRecordRow.created_at < last,
                )
            ).scalars()
            for d in decisions:
                markers.append(
                    {
                        "kind": "decision",
                        "at": json_safe(ensure_utc(d.created_at)),
                        "decision": d.decision,
                        "action": d.action,
                        "strategy": d.strategy,
                        "decision_id": d.decision_id,
                        "price": d.entry_price,
                    }
                )
            positions = sess.execute(
                select(PaperPositionRow).where(
                    PaperPositionRow.engine_id == engine_id,
                    PaperPositionRow.symbol == symbol,
                    or_(
                        and_(PaperPositionRow.entry_time >= first, PaperPositionRow.entry_time < last),
                        and_(PaperPositionRow.exit_time >= first, PaperPositionRow.exit_time < last),
                    ),
                )
            ).scalars()
            for p in positions:
                entry = ensure_utc(p.entry_time)
                if first <= entry < last:
                    markers.append(
                        {
                            "kind": "entry",
                            "at": json_safe(entry),
                            "side": p.side,
                            "price": p.entry_price,
                            "ticket": p.ticket,
                            "sl": p.sl,
                            "tp": p.tp,
                        }
                    )
                if p.exit_time is not None and first <= ensure_utc(p.exit_time) < last:
                    markers.append(
                        {
                            "kind": "exit",
                            "at": json_safe(ensure_utc(p.exit_time)),
                            "side": p.side,
                            "price": p.exit_price,
                            "ticket": p.ticket,
                            "reason": p.exit_reason,
                            "net": p.net,
                        }
                    )
            # the bot's closed positions on the broker account (DEMO/LIVE, TAA-1208), marked like paper ones
            trades = sess.execute(
                select(BrokerTradeRow).where(
                    BrokerTradeRow.engine_id == engine_id,
                    BrokerTradeRow.symbol == symbol,
                    or_(
                        and_(BrokerTradeRow.entry_time >= first, BrokerTradeRow.entry_time < last),
                        and_(BrokerTradeRow.exit_time >= first, BrokerTradeRow.exit_time < last),
                    ),
                )
            ).scalars()
            for b in trades:
                entry = ensure_utc(b.entry_time)
                if first <= entry < last:
                    markers.append(
                        {
                            "kind": "entry",
                            "at": json_safe(entry),
                            "side": b.side,
                            "price": b.entry_price,
                            "ticket": b.position_ticket,
                            "sl": b.sl_initial,
                            "tp": b.tp,
                        }
                    )
                if first <= ensure_utc(b.exit_time) < last:
                    markers.append(
                        {
                            "kind": "exit",
                            "at": json_safe(ensure_utc(b.exit_time)),
                            "side": b.side,
                            "price": b.exit_price,
                            "ticket": b.position_ticket,
                            "reason": b.exit_reason,
                            "net": b.net,
                        }
                    )
        return sorted(markers, key=lambda m: str(m["at"]))


def _zones(df: pd.DataFrame) -> list[dict[str, Any]]:
    """S/R zones as the strategies see them at the last shown bar (app.indicators: confirmed swings clustered
    within ``sr_tolerance_atr`` × ATR, default indicator parameters), strongest first; the role is relative to
    the last close."""
    if len(df) <= ZONE_ATR_PERIOD:
        return []
    params = IndicatorParams()
    close, high, low = df["close"], df["high"], df["low"]
    atr_value = float(atr(high, low, close, ZONE_ATR_PERIOD).iloc[-1])
    if not (math.isfinite(atr_value) and atr_value > 0):  # no meaningful zone width
        return []
    swings = find_swings(high.reset_index(drop=True), low.reset_index(drop=True), params.swing_k)
    found = sr_zones(
        swings, as_of_pos=len(df) - 1, atr_value=atr_value, tolerance_atr=params.sr_tolerance_atr
    )
    last = float(close.iloc[-1])
    return [
        {"low": z.low, "high": z.high, "touches": z.touches, "role": z.role(last)} for z in found[:MAX_ZONES]
    ]


OVERLAY_RE = re.compile(r"^(ema|bb|rsi|atr|adx):(\d{1,3})$")


def parse_overlay(spec: str) -> tuple[str, int, int]:
    """``ema:20`` → (kind, period, warm-up bars); periods 2-500."""
    m = OVERLAY_RE.fullmatch(spec.strip().lower())
    if m is None or not 2 <= int(m.group(2)) <= 500:
        raise QueryError("overlays: ema:N, bb:N, rsi:N, atr:N or adx:N with N in 2-500")
    kind, n = m.group(1), int(m.group(2))
    return kind, n, 2 * n if kind == "adx" else n


def _overlays(df: pd.DataFrame, specs: Sequence[tuple[str, int, int]]) -> list[tuple[str, pd.Series]]:
    """The same indicator functions the strategies use (app.indicators), on the closed bars only."""
    if df.empty:
        return [(f"{k}:{n}", pd.Series(dtype=float)) for k, n, _ in specs]
    close, high, low = df["close"], df["high"], df["low"]
    out: list[tuple[str, pd.Series]] = []
    for kind, n, _ in specs:
        if kind == "ema":
            out.append((f"ema:{n}", ema(close, n)))
        elif kind == "rsi":
            out.append((f"rsi:{n}", rsi(close, n)))
        elif kind == "atr":
            out.append((f"atr:{n}", atr(high, low, close, n)))
        elif kind == "bb":
            bands = bollinger(close, n)
            out += [(f"bb:{n}:{col}", bands[col]) for col in ("upper", "mid", "lower")]
        else:
            out.append((f"adx:{n}", adx(high, low, close, n)["adx"]))
    return out
