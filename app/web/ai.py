"""The AI review in the cloud: assessments, agreement and cost (PLAN §A15 "AI"; TAA-1304).

Reads the engine's replicated ``ai_assessments``. Agreement is measured against what the signal did
afterwards: the PLAN shadow trade of the same signal (``opportunity_id`` = the signal key). "The AI was right"
means it agreed and the trade won, or it disagreed and the trade lost. These are simulated outcomes, labelled
as such. The cloud never calls the AI: it holds no AI key (PLAN §A20).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.clock import Clock, ensure_utc
from app.storage.database import Database
from app.storage.models import AIAssessmentRow, ShadowTradeRow
from app.web.readmodels import QueryError

MAX_DAYS = 366
MAX_ITEMS = 200
UNCOUNTED = ("BUDGET", "SKIPPED")


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


class AIReadModel:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def assessments(self, engine_id: str, *, days: int = 30, limit: int = 100) -> dict[str, Any]:
        if not 1 <= days <= MAX_DAYS:
            raise QueryError(f"days: 1-{MAX_DAYS}")
        limit = max(1, min(limit, MAX_ITEMS))
        now = self.clock.now_utc()
        since = now - timedelta(days=days)
        m = AIAssessmentRow
        with self.db.session() as sess:
            rows = list(
                sess.scalars(
                    select(m)
                    .where(m.engine_id == engine_id, m.created_at >= since)
                    .order_by(m.created_at.desc())
                )
            )
            keys = {r.signal_key for r in rows}
            shadows = {
                s.opportunity_id: s
                for s in sess.scalars(
                    select(ShadowTradeRow).where(
                        ShadowTradeRow.engine_id == engine_id,
                        ShadowTradeRow.opportunity_id.in_(keys),
                        ShadowTradeRow.variant == "PLAN",
                        ShadowTradeRow.status == "CLOSED",
                    )
                )
            }
        return {
            "days": days,
            "summary": self._summary(rows, shadows, now),
            "items": [self._item(r, shadows.get(r.signal_key)) for r in rows[:limit]],
        }

    @staticmethod
    def _item(r: AIAssessmentRow, shadow: ShadowTradeRow | None) -> dict[str, Any]:
        return {
            "assessment_id": r.assessment_id,
            "created_at": ensure_utc(r.created_at).isoformat(),
            "symbol": r.symbol,
            "strategy": r.strategy,
            "side": r.side,
            "mode": r.mode,
            "status": r.status,
            "verdict": r.verdict,
            "confidence": r.confidence,
            "reasons": list(r.reasons or []),
            "effect": r.effect,
            "model": r.model,
            "cost_usd": round(r.cost_usd, 6),
            "latency_ms": r.latency_ms,
            "outcome": None if shadow is None else {"win": shadow.win, "r": shadow.r_multiple},
        }

    @staticmethod
    def _summary(
        rows: list[AIAssessmentRow], shadows: dict[str, ShadowTradeRow], now: datetime
    ) -> dict[str, Any]:
        called = [r for r in rows if r.status not in UNCOUNTED]
        answered = [r for r in called if r.status == "OK" and r.verdict]
        verdicts = Counter(r.verdict for r in answered)
        effects = Counter(r.effect for r in rows)
        today = now.date()
        judged = [(r, shadows[r.signal_key]) for r in answered if r.signal_key in shadows]
        right = sum(
            1
            for r, s in judged
            if (r.verdict == "AGREE" and s.win is True) or (r.verdict == "DISAGREE" and s.win is False)
        )
        agree_outcomes = [s.win for r, s in judged if r.verdict == "AGREE" and s.win is not None]
        disagree_outcomes = [s.win for r, s in judged if r.verdict == "DISAGREE" and s.win is not None]
        latencies = [r.latency_ms for r in called if r.latency_ms is not None]
        return {
            "calls": len(called),
            "answered": len(answered),
            "unavailable": len(called) - len(answered),
            "budget_holds": sum(r.status == "BUDGET" for r in rows),
            "agree": verdicts.get("AGREE", 0),
            "disagree": verdicts.get("DISAGREE", 0),
            "unsure": verdicts.get("UNSURE", 0),
            "agreement_rate": _rate(verdicts.get("AGREE", 0), len(answered)),
            "vetoed": effects.get("VETOED", 0),
            "passed": effects.get("PASSED", 0),
            "advisory": effects.get("ADVISORY", 0),
            "with_outcome": len(judged),
            "right_rate": _rate(right, len(judged)),
            "win_rate_when_agree": _rate(sum(1 for w in agree_outcomes if w), len(agree_outcomes)),
            "win_rate_when_disagree": _rate(sum(1 for w in disagree_outcomes if w), len(disagree_outcomes)),
            "cost_usd": round(sum(r.cost_usd for r in called), 4),
            "cost_today_usd": round(
                sum(r.cost_usd for r in called if ensure_utc(r.created_at).date() == today), 4
            ),
            "tokens": sum(r.input_tokens + r.output_tokens for r in called),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "models": sorted({r.model for r in called if r.model}),
        }
