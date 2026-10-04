"""Opportunity alerts in the cloud worker (PLAN §A26, §A30, §A31; TAA-810).

A scheduled task (``opportunity_alerts``, every 15 s) runs the pure personalizer
(:func:`app.advisory.personalize.personalize`) for every open opportunity of every ACTIVE engine and that
engine's users (its owner until tenancy, 8A), and turns its decisions into notifications:

- **Alert:** the personalizer's TH/EN push (tag = opportunity id, top-3 theory contributions, the owner's
  entry plan with lots, MT5 taps, prices, TPs, risk per order and in total and the portfolio heat after it,
  "valid until" in the user's timezone, the app-badge count) becomes an OPPORTUNITY notification, delivered
  by Web Push (TAA-806). An ``opportunity_alerts`` row records it: the personalizer's duplicate check,
  symbol cooldown, hourly and daily limits and the badge count read these rows. The user's quiet windows
  and market-session preference are applied by the personalizer.
- **Replacement:** once an alerted opportunity is EXPIRED, INVALIDATED or FOLLOWED (or its window passed),
  a silent same-tag OPPORTUNITY_UPDATE replaces the alert on the device (unless the user turned expiry
  updates off), once.

Inputs per opportunity: its calibration version (win probability and contributions; without one the
probability reads "insufficient data"), the decision's entry plan and heat, the latest ranking (AUTO_TOP_N
lists) and the symbol's market session from the replicated symbol catalog. Opportunities older than
``LOOKBACK`` are not considered. A failure on one opportunity is logged and never stops the others.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisory.asset_classes import AssetClass
from app.advisory.calibration import load_version
from app.advisory.confidence import BucketModel, WinProbability
from app.advisory.market_sessions import session_state, sessions_for
from app.advisory.personalize import MarketOpportunity, SentAlert, UserContext, personalize, replacement
from app.advisory.requirements import pattern_setups
from app.advisory.statuses import OPEN
from app.config import AppConfig, load_app_config
from app.core.clock import Clock, ensure_utc
from app.core.errors import TaaError
from app.storage.database import Database
from app.storage.models import (
    DecisionCheckRow,
    DecisionRecordRow,
    EngineRow,
    OpportunityAlertRow,
    OpportunityRow,
    SuitabilitySnapshotRow,
    SymbolCatalogRow,
)
from app.sync.notifications import NotificationType, Severity, notify
from app.sync.stream import StreamLog
from app.web.advisory import PreferenceStore, catalogs

log = logging.getLogger(__name__)

LOOKBACK = timedelta(hours=24)
MAX_PER_PASS = 200
SENT, REPLACED = "SENT", "REPLACED"


class OpportunityAlerter:
    def __init__(self, db: Database, clock: Clock, *, config: Callable[[], AppConfig] | None = None) -> None:
        self.db = db
        self.clock = clock
        self._config = config
        self.stream = StreamLog(db, clock)
        self.failures = 0

    def config(self) -> AppConfig:
        return self._config() if self._config is not None else load_app_config()

    def run(self) -> str | None:
        """One pass over every ACTIVE engine; returns a summary for the log, or None when nothing happened."""
        now = self.clock.now_utc()
        config = self.config()
        with self.db.session() as sess:
            engines = [
                (e.engine_id, e.owner_user_id)
                for e in sess.scalars(select(EngineRow).where(EngineRow.status == "ACTIVE"))
            ]
        alerts = updates = 0
        for engine_id, owner in engines:
            a, u = self._engine(engine_id, [owner], config, now)
            alerts, updates = alerts + a, updates + u
        if alerts or updates:
            return f"{alerts} alerts, {updates} updates"
        return None

    # --- one engine ---------------------------------------------------------------------------------------

    def _engine(self, engine_id: str, users: list[str], config: AppConfig, now: datetime) -> tuple[int, int]:
        with self.db.session() as sess:
            rows = list(
                sess.scalars(
                    select(OpportunityRow)
                    .where(OpportunityRow.engine_id == engine_id, OpportunityRow.created_at >= now - LOOKBACK)
                    .order_by(OpportunityRow.created_at)
                    .limit(MAX_PER_PASS)
                )
            )
            ranked = list(
                sess.scalars(
                    select(SuitabilitySnapshotRow.symbol)
                    .where(
                        SuitabilitySnapshotRow.engine_id == engine_id,
                        SuitabilitySnapshotRow.computed_at
                        == select(SuitabilitySnapshotRow.computed_at)
                        .where(SuitabilitySnapshotRow.engine_id == engine_id)
                        .order_by(SuitabilitySnapshotRow.computed_at.desc())
                        .limit(1)
                        .scalar_subquery(),
                    )
                    .order_by(SuitabilitySnapshotRow.rank)
                )
            )
        models: dict[str | None, WinProbability] = {}
        alerts = updates = 0
        for user_id in users:
            prefs = PreferenceStore(self.db).get(user_id)
            for row in rows:
                try:
                    if self._replace(engine_id, user_id, row, prefs, now):
                        updates += 1
                    elif row.status in OPEN and self._alert(
                        engine_id, user_id, row, prefs, ranked, models, config, now
                    ):
                        alerts += 1
                except Exception:  # one broken opportunity never stops the others
                    self.failures += 1
                    log.exception("opportunity %s for user %s failed", row.opportunity_id, user_id)
        return alerts, updates

    def _model(
        self, engine_id: str, version: str | None, cache: dict[str | None, WinProbability]
    ) -> WinProbability:
        if version not in cache:
            try:
                cache[version] = (
                    load_version(self.db, version, engine_id).model
                    if version
                    else WinProbability(BucketModel())
                )
            except TaaError:  # the version was pruned: no probability rather than a wrong one
                cache[version] = WinProbability(BucketModel())
        return cache[version]

    def _user(
        self, sess: Session, engine_id: str, user_id: str, prefs: Any, ranked: list[str], now: datetime
    ) -> UserContext:
        sent = sess.scalars(
            select(OpportunityAlertRow).where(
                OpportunityAlertRow.user_id == user_id, OpportunityAlertRow.sent_at >= now - timedelta(days=1)
            )
        ).all()
        active = sum(1 for s in sent if s.status == SENT)
        _, strategies = catalogs()
        return UserContext(
            preferences=prefs,
            sent=tuple(SentAlert(s.opportunity_id, s.symbol, ensure_utc(s.sent_at)) for s in sent),
            active_alerts=active,
            ranked_top=tuple(ranked),
            is_owner=True,  # the engine's owner: its exact MT5 sizing (other users need account profiles, 8A)
            pattern_strategies=tuple(pattern_setups(strategies)),
        )

    def _alert(
        self,
        engine_id: str,
        user_id: str,
        row: OpportunityRow,
        prefs: Any,
        ranked: list[str],
        models: dict[str | None, WinProbability],
        config: AppConfig,
        now: datetime,
    ) -> bool:
        with self.db.session() as sess:
            if sess.get(OpportunityAlertRow, (user_id, engine_id, row.opportunity_id)) is not None:
                return False
            user = self._user(sess, engine_id, user_id, prefs, ranked, now)
            _, strategies = catalogs()
            if row.strategy in strategies.names:
                user = dataclasses.replace(
                    user, core_families=tuple(strategies.get(row.strategy).core_families)
                )
            opportunity = self._opportunity(sess, engine_id, row)
            market_open = self._market_open(sess, engine_id, row, config, now)
            result = personalize(
                opportunity,
                user,
                self._model(engine_id, row.calibration_version, models),
                config.evidence.confluence,
                now=now,
                market_open=market_open,
            )
            if not result.alert or result.payload is None:
                return False
            note = notify(
                sess,
                self.stream,
                user_id=user_id,
                engine_id=engine_id,
                type_=NotificationType.OPPORTUNITY,
                severity=Severity.INFO,
                payload={
                    "push": result.payload,
                    "opportunity_id": row.opportunity_id,
                    "symbol": row.symbol,
                    "side": row.side,
                    "probability": None
                    if result.explanation.estimate.insufficient
                    else result.explanation.estimate.p,
                    "setup_strength": result.setup_strength,
                    "contributions": [
                        {"family": c.family, "detector": c.detector, "points": c.points}
                        for c in result.explanation.top(3)
                    ],
                    "plan": [dict(p) for p in opportunity.plan],
                    "heat_after": opportunity.heat_after,
                    "risk_warnings": [w.value for w in result.risk_warnings],
                    "valid_until": result.valid_until,
                    "watchlist": result.watchlist,
                },
                now=now,
            )
            sess.add(
                OpportunityAlertRow(
                    user_id=user_id,
                    engine_id=engine_id,
                    opportunity_id=row.opportunity_id,
                    symbol=row.symbol,
                    sent_at=now,
                    valid_until=result.valid_until,
                    notification_id=note.notification_id,
                    status=SENT,
                    final_status="",
                )
            )
        log.info("opportunity %s alerted to %s", row.opportunity_id, user_id)
        return True

    def _replace(self, engine_id: str, user_id: str, row: OpportunityRow, prefs: Any, now: datetime) -> bool:
        """The silent same-tag update once an alerted opportunity has ended (sent once)."""
        with self.db.session() as sess:
            alert = sess.get(OpportunityAlertRow, (user_id, engine_id, row.opportunity_id))
            if alert is None or alert.status != SENT:
                return False
            window_over = alert.valid_until is not None and now >= ensure_utc(alert.valid_until)
            if row.status in OPEN and not window_over:
                return False
            status = row.status if row.status not in OPEN else "EXPIRED"
            reason = row.status_reason or alert_reason(row, window_over)
            active = sess.scalars(
                select(OpportunityAlertRow).where(
                    OpportunityAlertRow.user_id == user_id, OpportunityAlertRow.status == SENT
                )
            ).all()
            user = UserContext(preferences=prefs, active_alerts=len(active))
            payload = replacement(MarketOpportunity.from_row(row), user, status=status, reason=reason)
            alert.status, alert.final_status, alert.replaced_at = REPLACED, status, now
            if payload is None:  # the user turned expiry updates off
                return False
            notify(
                sess,
                self.stream,
                user_id=user_id,
                engine_id=engine_id,
                type_=NotificationType.OPPORTUNITY_UPDATE,
                severity=Severity.INFO,
                payload={
                    "push": payload,
                    "opportunity_id": row.opportunity_id,
                    "status": status,
                    "reason": reason,
                },
                now=now,
            )
        return True

    # --- inputs -------------------------------------------------------------------------------------------

    @staticmethod
    def _opportunity(sess: Session, engine_id: str, row: OpportunityRow) -> MarketOpportunity:
        """The replicated opportunity plus its decision's entry plan and the account's risk budget then:
        heat and open positions after the trade and the engine's limits for both."""
        base = MarketOpportunity.from_row(row)
        decision = sess.get(DecisionRecordRow, (engine_id, row.decision_id))
        checks = {
            c.name: c
            for c in sess.scalars(
                select(DecisionCheckRow).where(
                    DecisionCheckRow.engine_id == engine_id,
                    DecisionCheckRow.decision_id == row.decision_id,
                    DecisionCheckRow.name.in_(("max_total_open_risk", "max_open_positions")),
                )
            )
        }

        def number(name: str, attr: str) -> float | None:
            check = checks.get(name)
            value = None if check is None else getattr(check, attr)
            return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None

        positions_after, positions_limit = (
            number("max_open_positions", "value"),
            number("max_open_positions", "threshold"),
        )
        plan = tuple(dict(p) for p in (decision.plan if decision is not None and decision.plan else []))
        return dataclasses.replace(
            base,
            plan=plan,
            heat_after=number("max_total_open_risk", "value"),
            heat_limit=number("max_total_open_risk", "threshold"),
            positions_after=None if positions_after is None else int(positions_after),
            positions_limit=None if positions_limit is None else int(positions_limit),
        )

    @staticmethod
    def _market_open(
        sess: Session, engine_id: str, row: OpportunityRow, config: AppConfig, now: datetime
    ) -> bool:
        """The symbol's own market sessions (exchange-local tables); unknown asset class or spec: open, so
        the user's preference never blocks on missing data alone."""
        catalog = sess.get(SymbolCatalogRow, (engine_id, row.server, row.symbol))
        try:
            asset = AssetClass(row.asset_class)
        except ValueError:
            return True
        quote = str((catalog.spec or {}).get("currency_profit", "USD")) if catalog is not None else "USD"
        names = sessions_for(row.symbol, asset, quote, config.advisory.sessions.overrides)
        return session_state(names, now).open


def alert_reason(row: OpportunityRow, window_over: bool) -> str:
    if window_over and row.status in OPEN:
        return "USER_WINDOW"
    return row.valid_reason or "SIGNAL_LIFETIME"
