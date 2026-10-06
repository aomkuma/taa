"""DEMO soak report (TAA-1206): what the engine did on the demo account, from the local database only.

It answers the soak questions of ``docs/RUNBOOK_DEMO.md``: did every order end in a known state, how often
did the server refuse, how much slippage, which breakers tripped, what did the closed bot trades return.
Nothing here forecasts anything; a two-week demo says little about profitability.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.clock import ensure_utc
from app.storage.database import Database
from app.storage.models import BreakerEventRow, DecisionRecordRow, OrderIntentRow, RiskDeal

UNRESOLVED = ("NEW", "PRECHECKED", "SENDING", "UNKNOWN", "UNPROTECTED")
OVERDUE_GRACE = timedelta(minutes=10)  # a resting limit part this long past its cancel time is overdue


@dataclass
class DemoReport:
    since: datetime
    until: datetime
    intents_by_state: Counter[str] = field(default_factory=Counter)
    retcodes: Counter[str] = field(default_factory=Counter)
    slippage_points: list[float] = field(default_factory=list)
    breaker_trips: Counter[str] = field(default_factory=Counter)
    decisions: Counter[str] = field(default_factory=Counter)
    rejection_reasons: Counter[str] = field(default_factory=Counter)
    closed_trades: int = 0
    winning_trades: int = 0
    net_result: float = 0.0
    overdue_limits: int = 0  # PLACED limit parts past their cancel time (TAA-1207)

    @property
    def unresolved(self) -> int:
        return sum(self.intents_by_state[s] for s in UNRESOLVED)

    @property
    def checks(self) -> dict[str, bool]:
        """Soak acceptance checks (docs/RUNBOOK_DEMO.md §4)."""
        sent = sum(self.intents_by_state.values())
        return {
            "every order in a final state": self.unresolved == 0,
            "no limit part left past its lifetime": self.overdue_limits == 0,
            "no unprotected position": self.breaker_trips["UNPROTECTED_POSITION"] == 0
            and self.intents_by_state["EMERGENCY_CLOSED"] == 0,
            "no duplicate or unknown execution": self.breaker_trips["DUPLICATE_EXECUTION"] == 0,
            "orders were actually exercised": sent > 0,
        }

    def to_dict(self) -> dict[str, Any]:
        slip = self.slippage_points
        return {
            "period": {"since": self.since.isoformat(), "until": self.until.isoformat()},
            "intents_by_state": dict(self.intents_by_state),
            "overdue_limit_parts": self.overdue_limits,
            "retcodes": dict(self.retcodes),
            "slippage_points": {
                "fills": len(slip),
                "mean": round(statistics.fmean(slip), 2) if slip else None,
                "max": max(slip) if slip else None,
            },
            "breaker_trips": dict(self.breaker_trips),
            "decisions": dict(self.decisions),
            "top_rejection_reasons": dict(self.rejection_reasons.most_common(10)),
            "closed_bot_trades": {
                "count": self.closed_trades,
                "winners": self.winning_trades,
                "net": round(self.net_result, 2),
            },
            "checks": self.checks,
            "note": "a demo soak tests the machinery, not the strategy's profitability",
        }


def build_report(db: Database, until: datetime, days: float = 14.0) -> DemoReport:
    until = ensure_utc(until)
    since = until - timedelta(days=days)
    report = DemoReport(since, until)
    with db.session() as sess:
        for row in sess.execute(select(OrderIntentRow).where(OrderIntentRow.created_at >= since)).scalars():
            report.intents_by_state[row.state] += 1
            if (
                row.state == "PLACED"
                and row.cancel_after is not None
                and until - ensure_utc(row.cancel_after) > OVERDUE_GRACE
            ):
                report.overdue_limits += 1
            if row.retcode_desc:
                report.retcodes[row.retcode_desc] += 1
            if row.slippage_points is not None:
                report.slippage_points.append(float(row.slippage_points))
        for ev in sess.execute(
            select(BreakerEventRow).where(BreakerEventRow.ts_utc >= since, BreakerEventRow.action == "TRIP")
        ).scalars():
            report.breaker_trips[ev.name] += 1
        for rec in sess.execute(
            select(DecisionRecordRow).where(
                DecisionRecordRow.created_at >= since, DecisionRecordRow.profile == "EXECUTION"
            )
        ).scalars():
            report.decisions[rec.decision] += 1
            for code in rec.reason_codes or []:
                report.rejection_reasons[code] += 1
        for deal in sess.execute(
            select(RiskDeal).where(RiskDeal.kind == "CLOSE", RiskDeal.time_utc >= since)
        ).scalars():
            report.closed_trades += 1
            report.winning_trades += int(deal.amount > 0)
            report.net_result += deal.amount
    return report
