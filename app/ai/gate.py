"""The AI review of entries in the decision pipeline (PLAN §A8 "AI", R21; TAA-1303).

:meth:`AIGate.review` is called by the decision engine **after every other check passed** on an
EXECUTION decision. It returns one more check, so the AI can only block an entry: it never sizes, never adds
an order and never touches an open position. Nothing is ever executed from its text.

Modes (``AI_MODE``):

- ``off`` (or no provider): no check, no call.
- ``advisory``: the answer is recorded and shown, and the check always passes.
- ``veto``: AGREE at ``ai.min_confidence`` or more passes. DISAGREE at that confidence fails
  ``AI_DISAGREES``; UNSURE or a lower confidence fails ``AI_LOW_CONFIDENCE``. No usable answer fails
  ``AI_UNAVAILABLE``: that covers a refusal, a ``max_tokens`` stop, an invalid answer, a timeout, an error and
  a used-up budget. All three mean HOLD.

**Per-candle cache:** one call per signal (strategy, symbol, bar, side), kept in memory and in
``ai_assessments``, so a restart does not ask again. **Budgets:** ``ai.max_calls_per_day`` and
``ai.max_cost_per_day_usd`` per UTC day, counted from ``ai_assessments``. When one is used up no call is made
(status BUDGET). An AI failure never trips a trading breaker; it only holds.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Literal

from sqlalchemy import func, select

from app.ai.providers import AIProvider
from app.ai.schema import Assessment, AssessmentInput, Status, Verdict, build_input
from app.config import AIConfig
from app.core.clock import Clock
from app.core.ids import new_id
from app.risk.checks import Check, CheckKind
from app.risk.reasons import Reason
from app.storage.database import Database
from app.storage.models import AIAssessmentRow
from app.strategy.signal_models import MarketContext, Signal

log = logging.getLogger(__name__)

Mode = Literal["off", "advisory", "veto"]
CHECK_NAME = "ai_review"
UNCOUNTED = (Status.BUDGET.value, Status.SKIPPED.value)


class AIGate:
    def __init__(
        self, db: Database, provider: AIProvider, config: AIConfig, mode: Mode, clock: Clock
    ) -> None:
        self.db = db
        self.provider = provider
        self.config = config
        self.mode = mode
        self.clock = clock
        self._cache: dict[str, Assessment] = {}

    @property
    def active(self) -> bool:
        return self.mode != "off" and self.provider.name != "none"

    # budget ------------------------------------------------------------------------------------------------

    def spent_today(self, now: datetime) -> tuple[int, float]:
        start = datetime.combine(now.date(), time(0), tzinfo=now.tzinfo)
        with self.db.session() as sess:
            calls, cost = sess.execute(
                select(func.count(), func.coalesce(func.sum(AIAssessmentRow.cost_usd), 0.0)).where(
                    AIAssessmentRow.created_at >= start,
                    AIAssessmentRow.created_at < start + timedelta(days=1),
                    AIAssessmentRow.status.not_in(UNCOUNTED),
                )
            ).one()
        return int(calls), float(cost)

    # review ------------------------------------------------------------------------------------------------

    def review(self, signal: Signal, market: MarketContext) -> Check | None:
        if not self.active:
            return None
        request = build_input(signal, market)
        assessment = self._assessment(request, signal)
        return self._check(assessment)

    def _assessment(self, request: AssessmentInput, signal: Signal) -> Assessment:
        cached = self._cache.get(request.signal_key) or self._load(request.signal_key)
        if cached is not None:
            self._cache[request.signal_key] = cached
            return cached
        now = self.clock.now_utc()
        calls, cost = self.spent_today(now)
        if calls >= self.config.max_calls_per_day or cost >= self.config.max_cost_per_day_usd:
            result = Assessment(
                Status.BUDGET,
                request.signal_key,
                created_at=now,
                detail=f"daily AI budget used: {calls} calls, ${cost:.2f}",
            )
        else:
            result = self.provider.assess(request)
        self._cache[request.signal_key] = result
        self._store(result, request, signal)
        return result

    def _check(self, a: Assessment) -> Check:
        confidence = a.confidence if a.confidence is not None else 0
        sure = confidence >= self.config.min_confidence
        if not a.answered:
            reason, passed = Reason.AI_UNAVAILABLE, False
        elif a.verdict is Verdict.AGREE and sure:
            reason, passed = Reason.AI_DISAGREES, True
        elif a.verdict is Verdict.DISAGREE and sure:
            reason, passed = Reason.AI_DISAGREES, False
        else:
            reason, passed = Reason.AI_LOW_CONFIDENCE, False
        detail = "; ".join(a.reasons) if a.answered else f"{a.status.value}: {a.detail}"
        if self.mode == "advisory":
            passed = True
            detail = f"advisory: {detail}"
        return Check(
            CHECK_NAME,
            reason,
            passed,
            CheckKind.HARD,
            f"{a.verdict.value} {confidence}" if a.answered and a.verdict else a.status.value,
            self.config.min_confidence,
            detail[:500],
        )

    # records -----------------------------------------------------------------------------------------------

    def _load(self, signal_key: str) -> Assessment | None:
        with self.db.session() as sess:
            row = sess.scalar(
                select(AIAssessmentRow)
                .where(AIAssessmentRow.signal_key == signal_key, AIAssessmentRow.status.not_in(UNCOUNTED))
                .order_by(AIAssessmentRow.created_at.desc())
                .limit(1)
            )
            if row is None:
                return None
            return Assessment(
                Status(row.status),
                row.signal_key,
                verdict=Verdict(row.verdict) if row.verdict else None,
                confidence=row.confidence,
                reasons=tuple(row.reasons or ()),
                model=row.model,
                created_at=row.created_at,
                detail=row.detail,
            )

    def _store(self, a: Assessment, request: AssessmentInput, signal: Signal) -> None:
        check = self._check(a)
        effect = "ADVISORY" if self.mode == "advisory" else ("PASSED" if check.passed else "VETOED")
        with self.db.session() as sess:
            sess.add(
                AIAssessmentRow(
                    assessment_id=new_id(),
                    created_at=a.created_at or self.clock.now_utc(),
                    signal_key=request.signal_key,
                    symbol=signal.symbol,
                    strategy=signal.strategy,
                    side=signal.side.value if signal.side is not None else "",
                    bar_close_utc=request.bar_close_utc,
                    mode=self.mode,
                    status=a.status.value,
                    verdict=a.verdict.value if a.verdict else None,
                    confidence=a.confidence,
                    reasons=list(a.reasons),
                    model=a.model,
                    input_tokens=a.input_tokens,
                    output_tokens=a.output_tokens,
                    cost_usd=a.cost_usd,
                    latency_ms=a.latency_ms,
                    effect=effect,
                    detail=a.detail,
                )
            )
        log.info("AI review %s %s: %s (%s)", signal.symbol, signal.strategy, effect, a.status.value)
