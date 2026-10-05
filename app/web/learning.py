"""Learning reports in the cloud (PLAN_LEARNING §L19.2, §L20.0, §L20.7; TAA-L701, L801, L808).

Computed on request from the engine's replicas, like the analytics of TAA-1005 (no tables of their own yet):

- **timing**: the failure modes of losing trades, winners' MAE and time to target, and the random-walk
  baseline (:mod:`app.learning.timing`), over the same trade scopes as the analytics page;
- **expectancy**: E[R] = p·W − (1 − p)·L − c overall and per strategy × symbol, plus which lever moved
  against the previous period of the same length (:mod:`app.learning.expectancy`);
- **behavior**: patterns in the owner's closed manual trades (:mod:`app.learning.behavior`), from
  ``manual_trade_links`` (TAA-1006), the matched signal's plan and the owner's corrections.

Bars come from the engine's uploaded history (``history_candles``). Without bars a trade's follow-up is
unknown and no claim is made. Everything here is hypothetical and labelled so; nothing changes any setting.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisory.preferences import AdvisoryPreferences
from app.core.clock import Clock, ensure_utc
from app.core.enums import Side, Timeframe
from app.learning import behavior as lb
from app.learning import expectancy as le
from app.learning import timing as lt
from app.storage.database import Database
from app.storage.models import (
    DecisionRecordRow,
    HistoryCandle,
    ManualTradeLinkRow,
    ManualTradeOverrideRow,
    OpportunityRow,
    UserAdvisoryPrefsRow,
)
from app.web.analytics import DEFAULT_DAYS, MAX_DAYS, Analytics
from app.web.readmodels import QueryError

MAX_TIMING_TRADES = 200  # the most recent trades whose bars are loaded
LOOKAHEAD = timedelta(hours=24)  # after-exit follow-up in the cloud (bounded load per trade)
MATCHED = ("HIGH", "LIKELY")


def _num(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _share(s: lt.Share | None) -> dict[str, Any] | None:
    if s is None:
        return None
    return {"count": s.count, "n": s.n, "share": _num(s.share), "low": _num(s.low), "high": _num(s.high)}


def _quantiles(q: Any) -> dict[str, float] | None:
    return None if q is None else {str(k): round(float(v), 4) for k, v in q.items()}


def _key(value: Hashable) -> list[str]:
    return [str(v) for v in value] if isinstance(value, tuple) else [str(value)]


def _decomposition(d: le.Decomposition) -> dict[str, Any]:
    return {
        "key": _key(d.key),
        "n": d.n,
        "p": _num(d.p),
        "win_r": _num(d.win_r),
        "loss_r": _num(d.loss_r),
        "cost_r": _num(d.cost_r),
        "expectancy_r": _num(d.expectancy_r),
        "ci": {"mean": d.ci.mean, "low": d.ci.low, "high": d.ci.high},
        "per_week": _num(d.per_week, 2),
        "unknown_costs": d.unknown_costs,
    }


class LearningReports:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock
        self.analytics = Analytics(db, clock)

    # bars ------------------------------------------------------------------------------------------------

    @staticmethod
    def _bars(
        sess: Session, engine_id: str, symbol: str, tf: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        m = HistoryCandle
        rows = sess.execute(
            select(m.open_time, m.high, m.low, m.close)
            .where(
                m.engine_id == engine_id,
                m.symbol == symbol,
                m.timeframe == tf.value,
                m.open_time >= start,
                m.open_time < end,
            )
            .order_by(m.open_time)
        ).all()
        frame = pd.DataFrame(rows, columns=["open_time", "high", "low", "close"])
        if not frame.empty:
            frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
        return frame

    # timing ----------------------------------------------------------------------------------------------

    def timing(self, engine_id: str, **query: Any) -> dict[str, Any]:
        found = self.analytics.trades(engine_id, **query)
        recent = sorted(found.trades, key=lambda t: t.exit_time)[-MAX_TIMING_TRADES:]
        params = lt.TimingParams(lookahead=LOOKAHEAD)
        frames: dict[str, pd.DataFrame] = {}
        with self.db.session() as sess:
            for t in recent:
                tf = t.context.timeframe or Timeframe.M15
                start = ensure_utc(t.entry_time) - timedelta(seconds=tf.seconds * (params.pre_trend_bars + 1))
                end = ensure_utc(t.exit_time) + params.lookahead
                frames[t.trade_id] = self._bars(sess, engine_id, t.symbol, tf, start, end)
        groups = lt.report(
            recent, lambda t: frames.get(t.trade_id), key=lambda t: (t.strategy,), params=params
        )
        overall = lt.report(recent, lambda t: frames.get(t.trade_id), key=lambda t: ("all",), params=params)
        return {
            "scope": query["scope"],
            "trades": len(recent),
            "skipped": len(found.skipped),
            "lookahead_hours": int(params.lookahead.total_seconds() // 3600),
            "hypothetical": any(t.hypothetical for t in recent),
            "overall": [self._timing_doc(r) for r in overall],
            "groups": [self._timing_doc(r) for r in groups],
        }

    @staticmethod
    def _timing_doc(r: lt.TimingReport) -> dict[str, Any]:
        return {
            "key": _key(r.key),
            "trades": r.trades,
            "losers": r.losers,
            "modes": {mode.value: _share(share) for mode, share in r.modes.items()},
            "winner_mae_r": _quantiles(r.winner_mae_r),
            "winner_mae_atr": _quantiles(r.winner_mae_atr),
            "winner_bars_to_tp": _quantiles(r.winner_bars_to_tp),
            "hit_rate": _share(r.hit_rate),
            "baseline_hit_rate": _num(r.baseline_hit_rate),
            "vindicated": _share(r.vindicated),
            "baseline_vindicated": _num(r.baseline_vindicated),
        }

    # expectancy ------------------------------------------------------------------------------------------

    def expectancy(self, engine_id: str, *, days: int = DEFAULT_DAYS, **query: Any) -> dict[str, Any]:
        if not 1 <= days <= MAX_DAYS // 2:
            raise QueryError(f"days: 1-{MAX_DAYS // 2} (the previous period is compared too)")
        both = self.analytics.trades(engine_id, days=2 * days, **query)
        cut = self.clock.now_utc() - timedelta(days=days)
        current = [t for t in both.trades if ensure_utc(t.exit_time) >= cut]
        previous = [t for t in both.trades if ensure_utc(t.exit_time) < cut]
        now = le.decompose(current, "all")
        before = le.decompose(previous, "previous")
        change = None if now is None or before is None else le.lever_change(before, now)
        return {
            "scope": query["scope"],
            "days": days,
            "hypothetical": any(t.hypothetical for t in both.trades),
            "overall": None if now is None else _decomposition(now),
            "previous": None if before is None else _decomposition(before),
            "change": None
            if change is None
            else {**{k: _num(v) for k, v in asdict(change).items()}, "main": change.main},
            "groups": [_decomposition(d) for d in le.by_group(current, key=lambda t: (t.strategy, t.symbol))],
        }

    # behavior --------------------------------------------------------------------------------------------

    def behavior(self, engine_id: str, owner_id: str, *, days: int = DEFAULT_DAYS) -> dict[str, Any]:
        if not 1 <= days <= MAX_DAYS:
            raise QueryError(f"days: 1-{MAX_DAYS}")
        since = self.clock.now_utc() - timedelta(days=days)
        with self.db.session() as sess:
            links = list(
                sess.scalars(
                    select(ManualTradeLinkRow).where(
                        ManualTradeLinkRow.engine_id == engine_id,
                        ManualTradeLinkRow.status == "CLOSED",
                        ManualTradeLinkRow.closed_at >= since,
                    )
                )
            )
            trades = self._manual_trades(sess, engine_id, links)
            frames = {
                t.position_id: self._bars(
                    sess,
                    engine_id,
                    t.symbol,
                    Timeframe.M15,
                    ensure_utc(t.closed_at),
                    ensure_utc(t.closed_at) + LOOKAHEAD,
                )
                for t in trades
                if t.tp_plan is not None
            }
            opportunity_classes = list(
                sess.scalars(
                    select(OpportunityRow.asset_class).where(
                        OpportunityRow.engine_id == engine_id, OpportunityRow.created_at >= since
                    )
                )
            )
            max_per_day = self._max_per_day(sess, owner_id)
        rep = lb.report(
            trades,
            lambda t: frames.get(t.position_id),
            params=lb.BehaviorParams(max_trades_per_day=max_per_day, lookahead=LOOKAHEAD),
            opportunity_classes=opportunity_classes,
        )
        return {
            "days": days,
            "trades": rep.trades,
            "max_trades_per_day": max_per_day,
            "lookahead_hours": int(LOOKAHEAD.total_seconds() // 3600),
            "hypothetical": True,
            "patterns": [
                {
                    "pattern": s.pattern.value,
                    "count": s.count,
                    "considered": s.considered,
                    "share": _num(s.share),
                    "delta_r": _num(s.delta_r),
                }
                for s in rep.patterns.values()
            ],
            "class_mix": {k: _num(v) for k, v in rep.class_mix.items()},
            "opportunity_mix": {k: _num(v) for k, v in rep.opportunity_mix.items()},
            "comfort_distance": _num(rep.comfort_distance),
        }

    @staticmethod
    def _manual_trades(
        sess: Session, engine_id: str, links: Sequence[ManualTradeLinkRow]
    ) -> list[lb.ManualTrade]:
        ids = [link.position_id for link in links]
        overrides = {
            o.position_id: o
            for o in sess.scalars(
                select(ManualTradeOverrideRow).where(
                    ManualTradeOverrideRow.engine_id == engine_id, ManualTradeOverrideRow.position_id.in_(ids)
                )
            )
        }
        opp_ids, decision_ids = set(), set()
        for link in links:
            o = overrides.get(link.position_id)
            opp_ids.add(o.opportunity_id if o is not None and o.choice == "SIGNAL" else link.opportunity_id)
            decision_ids.add(o.decision_id if o is not None and o.choice == "SIGNAL" else link.decision_id)
        opportunities = {
            r.opportunity_id: r
            for r in sess.scalars(
                select(OpportunityRow).where(
                    OpportunityRow.engine_id == engine_id, OpportunityRow.opportunity_id.in_(opp_ids - {None})
                )
            )
        }
        decisions = {
            r.decision_id: r
            for r in sess.scalars(
                select(DecisionRecordRow).where(
                    DecisionRecordRow.engine_id == engine_id,
                    DecisionRecordRow.decision_id.in_(decision_ids - {None}),
                )
            )
        }
        classes = {r.symbol: r.asset_class for r in opportunities.values()}
        out = []
        for link in links:
            if link.closed_at is None or link.close_price is None:
                continue
            o = overrides.get(link.position_id)
            if o is not None and o.choice == "OWN_IDEA":
                matched, opp_id, dec_id = False, None, None
            elif o is not None and o.choice == "SIGNAL":
                matched, opp_id, dec_id = True, o.opportunity_id, o.decision_id
            else:
                matched = link.confidence in MATCHED or (o is not None and o.choice == "CONFIRMED")
                opp_id, dec_id = link.opportunity_id, link.decision_id
            tp = None
            if matched and opp_id in opportunities:
                tp = opportunities[opp_id].take_profit
            elif matched and dec_id in decisions:
                tp = decisions[dec_id].take_profit
            out.append(
                lb.ManualTrade(
                    position_id=link.position_id,
                    symbol=link.symbol,
                    side=Side(link.side),
                    opened_at=link.opened_at,
                    closed_at=link.closed_at,
                    price_open=link.price_open,
                    close_price=link.close_price,
                    r_multiple=link.r_multiple,
                    sl_initial=link.sl_initial,
                    tp_plan=tp,
                    matched=matched,
                    asset_class=classes.get(link.symbol),
                )
            )
        return out

    @staticmethod
    def _max_per_day(sess: Session, owner_id: str) -> int | None:
        row = sess.get(UserAdvisoryPrefsRow, owner_id)
        if row is None:
            return None
        try:
            prefs = AdvisoryPreferences.model_validate(dict(row.prefs))
        except ValueError:
            return None
        return prefs.trading_profile.max_signals_per_day
