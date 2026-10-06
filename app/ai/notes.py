"""The engine's AI notes on advisory (TAA-1305, TAA-1304): one background call at a time, never blocking.

:meth:`AINotes.tick` runs in the engine cycle after the scanner. It collects a finished call, and when none
is running picks the next job, newest first:

1. an **opinion** on the newest OPEN opportunity without a note that is younger than
   ``ai.advisory.max_age_minutes`` and scores at least ``ai.advisory.min_score``;
2. a **ranking narrative** of the latest snapshot, at most every ``ranking_every_hours``;
3. an **analytics narrative** of the last ``analytics_days`` of closed PLAN shadow trades, at most every
   ``analytics_every_hours``.

The call itself runs on one worker thread (PLAN D6: "AI failures must never stop monitoring") and writes its
``ai_notes`` row from there. Every attempt is recorded, answered or not, so a subject is asked once. The
budget (``ai.advisory.max_calls_per_day`` / ``max_cost_per_day_usd`` per UTC day) is counted from
``ai_notes``; when it is used up no call is made and nothing is recorded.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.advisory.statuses import OPEN
from app.ai.advisory import (
    Kind,
    NoteRequest,
    analytics_request,
    check,
    opinion_request,
    ranking_request,
)
from app.ai.providers import AIProvider
from app.ai.schema import Status
from app.config import AIAdvisoryConfig
from app.core.clock import Clock, ensure_utc
from app.storage.database import Database
from app.storage.models import AINoteRow, OpportunityRow, ShadowTradeRow, SuitabilitySnapshotRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)

UNCOUNTED = (Status.BUDGET.value, Status.SKIPPED.value)


@dataclass
class NotesStats:
    calls: int = 0
    answered: int = 0
    failures: int = 0
    budget_holds: int = 0
    last_error: str = ""
    by_kind: dict[str, int] = field(default_factory=dict)


class AINotes:
    def __init__(
        self,
        db: Database,
        provider: AIProvider,
        config: AIAdvisoryConfig,
        clock: Clock,
        *,
        background: bool = True,
    ) -> None:
        self.db = db
        self.provider = provider
        self.config = config
        self.clock = clock
        self.stats = NotesStats()
        # one worker thread; without it (tests) the call runs inside tick()
        self._executor = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-notes") if background else None
        )
        self._running: Future[None] | None = None

    @property
    def active(self) -> bool:
        return self.config.enabled and self.provider.name != "none"

    def close(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    # cycle -------------------------------------------------------------------------------------------------

    def tick(self) -> bool:
        """Start the next call if none is running. Returns True when a call was started."""
        if not self.active:
            return False
        if self._running is not None:
            if not self._running.done():
                return False
            exc = self._running.exception()
            self._running = None
            if exc is not None:
                self._failed(exc)
        now = self.clock.now_utc()
        request = self.next_request(now)
        if request is None:
            return False
        calls, cost = self.spent_today(now)
        if calls >= self.config.max_calls_per_day or cost >= self.config.max_cost_per_day_usd:
            self.stats.budget_holds += 1
            return False
        if self._executor is None:
            try:
                self._call(request)
            except Exception as exc:  # advisory boundary, as on the worker thread
                self._failed(exc)
        else:
            self._running = self._executor.submit(self._call, request)
        return True

    def _failed(self, exc: BaseException) -> None:
        self.stats.failures += 1
        self.stats.last_error = f"{type(exc).__name__}: {exc}"
        log.error("AI note failed: %s", self.stats.last_error)

    def next_request(self, now: datetime) -> NoteRequest | None:
        with self.db.session() as sess:
            if self.config.opinions:
                since = now - timedelta(minutes=self.config.max_age_minutes)
                done = select(AINoteRow.subject).where(AINoteRow.kind == Kind.OPPORTUNITY.value)
                row = sess.scalar(
                    select(OpportunityRow)
                    .where(
                        OpportunityRow.created_at >= since,
                        OpportunityRow.status.in_(sorted(OPEN)),
                        OpportunityRow.score >= self.config.min_score,
                        OpportunityRow.opportunity_id.not_in(done),
                    )
                    .order_by(OpportunityRow.created_at.desc())
                    .limit(1)
                )
                if row is not None:
                    return opinion_request(row)
            if self.config.ranking_narrative and self._due(
                sess, Kind.RANKING, now, self.config.ranking_every_hours
            ):
                latest = sess.scalar(select(func.max(SuitabilitySnapshotRow.hour)))
                if latest is not None:
                    rows = list(
                        sess.scalars(
                            select(SuitabilitySnapshotRow).where(SuitabilitySnapshotRow.hour == latest)
                        )
                    )
                    request = ranking_request(rows)
                    if request is not None and sess.get(AINoteRow, (LOCAL_ENGINE, request.note_id)) is None:
                        return request
            if self.config.analytics_narrative and self._due(
                sess, Kind.ANALYTICS, now, self.config.analytics_every_hours
            ):
                since = now - timedelta(days=self.config.analytics_days)
                trades = list(
                    sess.scalars(
                        select(ShadowTradeRow).where(
                            ShadowTradeRow.variant == "PLAN",
                            ShadowTradeRow.source == "LIVE",
                            ShadowTradeRow.status == "CLOSED",
                            ShadowTradeRow.exit_at >= since,
                        )
                    )
                )
                request = analytics_request(trades, since, now)
                if request is not None and sess.get(AINoteRow, (LOCAL_ENGINE, request.note_id)) is None:
                    return request
        return None

    @staticmethod
    def _due(sess: Session, kind: Kind, now: datetime, every_hours: int) -> bool:
        last = sess.scalar(select(func.max(AINoteRow.created_at)).where(AINoteRow.kind == kind.value))
        return last is None or now - ensure_utc(last) >= timedelta(hours=every_hours)

    def spent_today(self, now: datetime) -> tuple[int, float]:
        start = datetime.combine(now.date(), time(0), tzinfo=now.tzinfo)
        with self.db.session() as sess:
            calls, cost = sess.execute(
                select(func.count(), func.coalesce(func.sum(AINoteRow.cost_usd), 0.0)).where(
                    AINoteRow.created_at >= start,
                    AINoteRow.created_at < start + timedelta(days=1),
                    AINoteRow.status.not_in(UNCOUNTED),
                )
            ).one()
        return int(calls), float(cost)

    # the call (worker thread) ------------------------------------------------------------------------------

    def _call(self, request: NoteRequest) -> None:
        answer = self.provider.ask(request.note_id, request.prompt, request.to_json(), request.schema)
        status, detail = answer.status, answer.detail
        verdict = confidence = None
        reasons: tuple[str, ...] = ()
        text_en = text_th = ""
        if status is Status.OK:
            try:
                checked = check(answer.parsed, request)
            except ValueError as exc:
                status, detail = Status.INVALID, str(exc)[:500]
            else:
                verdict, confidence, reasons = checked.verdict, checked.confidence, checked.reasons
                text_en, text_th = checked.text_en, checked.text_th
        with self.db.session() as sess:
            if sess.get(AINoteRow, (LOCAL_ENGINE, request.note_id)) is None:
                sess.add(
                    AINoteRow(
                        note_id=request.note_id,
                        kind=request.kind.value,
                        subject=request.subject,
                        created_at=answer.created_at or self.clock.now_utc(),
                        status=status.value,
                        verdict=None if verdict is None else verdict.value,
                        confidence=confidence,
                        reasons=list(reasons),
                        text_en=text_en,
                        text_th=text_th,
                        facts=request.payload,
                        model=answer.model,
                        input_tokens=answer.input_tokens,
                        output_tokens=answer.output_tokens,
                        cost_usd=answer.cost_usd,
                        latency_ms=answer.latency_ms,
                        detail=detail,
                    )
                )
        self.stats.calls += 1
        self.stats.by_kind[request.kind.value] = self.stats.by_kind.get(request.kind.value, 0) + 1
        if status is Status.OK:
            self.stats.answered += 1
        log.info(
            "AI note %s: %s %s", request.note_id[:60], status.value, "" if verdict is None else verdict.value
        )
