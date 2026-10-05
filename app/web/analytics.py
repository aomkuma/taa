"""Analytics and recommendations in the cloud (PLAN §A15, §A16; TAA-1005).

Loads one scope's closed trades from the engine's replicas and turns them into :mod:`app.analytics` records:

- ``PAPER``: the engine's closed paper positions, with their intents (initial stop, planned risk, strategy)
  and the entry context of their decision records;
- ``SHADOW``: the closed shadow trades of the signals (variant ``PLAN`` by default, or ``MANAGED``);
- ``BACKTEST``: one cloud backtest run of the engine (its stored trades).

DEMO and LIVE are reserved for broker deals (not served yet). Every scope here is hypothetical and labelled.

For the "stop too tight" rule, the bars after a stop-loss exit come from the engine's uploaded history
(``history_candles``): did price reach the take-profit within :data:`AFTER_STOP_BARS` bars of the trade's
entry timeframe? Unknown when the bars are not there.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.recommendations import AccountFacts, Inputs, as_dict, recommend, request_fields
from app.analytics.report import build_report
from app.analytics.trade_builder import (
    AnalyticsError,
    EntryContext,
    Trade,
    TradeSet,
    context_from_decision,
    trades_from_backtest,
    trades_from_paper,
    trades_from_shadow,
)
from app.core.clock import Clock, ensure_utc
from app.core.enums import ExitReason, Side, Timeframe
from app.execution.simulated_broker import ClosedTrade
from app.storage.database import Database
from app.storage.models import (
    BacktestRunRow,
    DecisionRecordRow,
    EngineHeartbeatRow,
    HistoryCandle,
    PaperIntentRow,
    PaperPositionRow,
    ShadowTradeRow,
)
from app.web.readmodels import QueryError

SCOPES = ("PAPER", "SHADOW", "BACKTEST")
VARIANTS = ("PLAN", "MANAGED")
DEFAULT_DAYS = 90
MAX_DAYS = 366
AFTER_STOP_BARS = 20
MAX_STOP_CHECKS = 300  # stop-loss exits whose follow-up is measured (the most recent)


def _closed_trade(row: Mapping[str, Any]) -> ClosedTrade:
    return ClosedTrade(
        ticket=int(row["ticket"]),
        symbol=str(row["symbol"]),
        side=Side(row["side"]),
        volume=float(row["volume"]),
        entry_time=datetime.fromisoformat(row["entry_time"]),
        entry_price=float(row["entry_price"]),
        exit_time=datetime.fromisoformat(row["exit_time"]),
        exit_price=float(row["exit_price"]),
        exit_reason=ExitReason(row["exit_reason"]),
        sl_initial=None if row.get("sl_initial") is None else float(row["sl_initial"]),
        tp_initial=None if row.get("tp_initial") is None else float(row["tp_initial"]),
        profit=float(row["profit"]),
        commission=float(row.get("commission") or 0.0),
        swap=float(row.get("swap") or 0.0),
        mae=float(row.get("mae") or 0.0),
        mfe=float(row.get("mfe") or 0.0),
        risk_money=float(row.get("risk_money") or 0.0),
        strategy=str(row.get("strategy") or ""),
        signal_id=str(row.get("signal_id") or ""),
        magic=0,
    )


class Analytics:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    # loading ---------------------------------------------------------------------------------------------

    def trades(
        self,
        engine_id: str,
        *,
        scope: str,
        days: int = DEFAULT_DAYS,
        run_id: str | None = None,
        variant: str = "PLAN",
        strategy: str | None = None,
        symbol: str | None = None,
    ) -> TradeSet:
        if scope not in SCOPES:
            raise QueryError("scope: PAPER, SHADOW or BACKTEST")
        if not 1 <= days <= MAX_DAYS:
            raise QueryError(f"days: 1-{MAX_DAYS}")
        if variant not in VARIANTS:
            raise QueryError("variant: PLAN or MANAGED")
        since = self.clock.now_utc() - timedelta(days=days)
        with self.db.session() as sess:
            if scope == "PAPER":
                found = self._paper(sess, engine_id, since)
            elif scope == "SHADOW":
                found = self._shadow(sess, engine_id, since, variant)
            else:
                if not run_id:
                    raise QueryError("run: a backtest run of this engine")
                found = self._backtest(sess, engine_id, run_id)
        kept = tuple(
            t
            for t in found.trades
            if (strategy is None or t.strategy == strategy) and (symbol is None or t.symbol == symbol)
        )
        return TradeSet(kept, found.skipped)

    @staticmethod
    def _paper(sess: Session, engine_id: str, since: datetime) -> TradeSet:
        positions = list(
            sess.scalars(
                select(PaperPositionRow).where(
                    PaperPositionRow.engine_id == engine_id,
                    PaperPositionRow.status == "CLOSED",
                    PaperPositionRow.exit_time >= since,
                )
            )
        )
        intents = {
            i.intent_id: i
            for i in sess.scalars(
                select(PaperIntentRow).where(
                    PaperIntentRow.engine_id == engine_id,
                    PaperIntentRow.intent_id.in_({p.intent_id for p in positions}),
                )
            )
        }
        contexts: dict[str, EntryContext] = {}
        decisions = sess.scalars(
            select(DecisionRecordRow).where(
                DecisionRecordRow.engine_id == engine_id,
                DecisionRecordRow.decision_id.in_({i.decision_id for i in intents.values()}),
            )
        )
        for d in decisions:
            try:
                contexts[d.signal_id] = context_from_decision(d.signal or {}, d.market or {})
            except AnalyticsError:
                continue  # a record from an older schema: the trade keeps an empty context
        return trades_from_paper(positions, intents, contexts=contexts)

    @staticmethod
    def _shadow(sess: Session, engine_id: str, since: datetime, variant: str) -> TradeSet:
        rows = sess.scalars(
            select(ShadowTradeRow).where(
                ShadowTradeRow.engine_id == engine_id,
                ShadowTradeRow.status == "CLOSED",
                ShadowTradeRow.variant == variant,
                ShadowTradeRow.exit_at >= since,
            )
        )
        return trades_from_shadow(rows)

    @staticmethod
    def _backtest(sess: Session, engine_id: str, run_id: str) -> TradeSet:
        run = sess.get(BacktestRunRow, run_id)
        if run is None or run.engine_id != engine_id:
            raise LookupError(run_id)
        if run.status != "DONE":
            raise QueryError("run: the backtest has not finished")
        closed = []
        for row in run.trades or []:
            try:
                closed.append(_closed_trade(row))
            except (KeyError, TypeError, ValueError):
                continue
        return trades_from_backtest(closed, run_id=run_id)

    # results ---------------------------------------------------------------------------------------------

    def report(self, engine_id: str, **query: Any) -> dict[str, Any]:
        found = self.trades(engine_id, **query)
        return {
            "scope": query["scope"],
            "skipped": len(found.skipped),
            **build_report(found.trades),
        }

    def recommendations(self, engine_id: str, **query: Any) -> dict[str, Any]:
        found = self.trades(engine_id, **query)
        with self.db.session() as sess:
            after = self._target_after_stop(sess, engine_id, found.trades)
            account = self._account(sess, engine_id) if query["scope"] == "PAPER" else None
        symbols = sorted({t.symbol for t in found.trades})[:5]
        items = []
        for rec in recommend(Inputs(found.trades, after, AFTER_STOP_BARS, account)):
            doc = as_dict(rec)
            doc["backtest"] = (
                None if rec.change is None or not symbols else request_fields(rec.change, symbols)
            )
            items.append(doc)
        return {
            "scope": query["scope"],
            "trades": len(found.trades),
            "after_stop_bars": AFTER_STOP_BARS,
            "stops_checked": len(after),
            "hypothetical": any(t.hypothetical for t in found.trades),
            "items": items,
        }

    @staticmethod
    def _target_after_stop(sess: Session, engine_id: str, trades: Iterable[Trade]) -> dict[str, bool]:
        stops = sorted(
            (t for t in trades if t.exit_reason is ExitReason.STOP_LOSS and t.initial_tp is not None),
            key=lambda t: t.exit_time,
        )[-MAX_STOP_CHECKS:]
        out: dict[str, bool] = {}
        for t in stops:
            tf = t.context.timeframe or Timeframe.M15
            bars = list(
                sess.scalars(
                    select(HistoryCandle)
                    .where(
                        HistoryCandle.engine_id == engine_id,
                        HistoryCandle.symbol == t.symbol,
                        HistoryCandle.timeframe == tf.value,
                        HistoryCandle.open_time >= ensure_utc(t.exit_time),
                    )
                    .order_by(HistoryCandle.open_time)
                    .limit(AFTER_STOP_BARS)
                )
            )
            if len(bars) < AFTER_STOP_BARS:
                continue  # not enough bars after the exit: unknown, no claim
            tp = t.initial_tp or 0.0
            out[t.trade_id] = (
                any(b.high >= tp for b in bars) if t.side is Side.BUY else any(b.low <= tp for b in bars)
            )
        return out

    @staticmethod
    def _account(sess: Session, engine_id: str) -> AccountFacts | None:
        beat = sess.get(EngineHeartbeatRow, engine_id)
        account = (beat.payload or {}).get("account") if beat is not None else None
        if not isinstance(account, dict):
            return None
        drawdown = account.get("drawdown_percent")
        limit = (account.get("limits") or {}).get("drawdown_percent")
        effective = ((account.get("risk_limits") or {}).get("effective") or {}).get("risk_per_trade_percent")
        if not (
            isinstance(drawdown, int | float)
            and isinstance(limit, int | float)
            and isinstance(effective, int | float)
        ):
            return None
        return AccountFacts(float(drawdown), float(limit), float(effective))
