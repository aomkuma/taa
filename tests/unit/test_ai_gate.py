"""The AI review in the decision pipeline: modes, cache, budgets, never a larger trade (TAA-1303)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.ai.gate import AIGate
from app.ai.providers import NullProvider
from app.ai.schema import Assessment, AssessmentInput, Status, Verdict
from app.config import AIConfig
from app.core.clock import ManualClock
from app.engine.decision_engine import Decision, Profile
from app.risk.reasons import Reason
from app.storage.database import Database
from app.storage.models import AIAssessmentRow
from tests.unit.test_decision_engine import engine, request
from tests.unit.test_strategy_models import make_context, make_signal

CLOCK = ManualClock(datetime(2026, 9, 30, 10, 0, tzinfo=UTC))


class FakeProvider:
    name = "fake"

    def __init__(self, verdict: Verdict | None = Verdict.AGREE, confidence: int = 80, **kw: Any) -> None:
        self.verdict, self.confidence, self.kw = verdict, confidence, kw
        self.calls = 0

    def assess(self, req: AssessmentInput) -> Assessment:
        self.calls += 1
        status = self.kw.get("status", Status.OK)
        return Assessment(
            status,
            req.signal_key,
            verdict=self.verdict if status is Status.OK else None,
            confidence=self.confidence if status is Status.OK else None,
            reasons=("H1 trend against the entry",),
            model="claude-opus-5-5",
            cost_usd=self.kw.get("cost", 0.01),
            created_at=CLOCK.now_utc(),
        )


def gate(db: Database, provider: Any, mode: str = "veto", **cfg: Any) -> AIGate:
    return AIGate(db, provider, AIConfig(**cfg), mode, CLOCK)  # type: ignore[arg-type]


def review(g: AIGate, **signal: Any) -> Any:
    return g.review(make_signal(**signal), make_context())


class TestModes:
    def test_off_or_no_provider_adds_no_check(self, db: Database) -> None:
        assert review(gate(db, FakeProvider(), mode="off")) is None
        assert review(gate(db, NullProvider(CLOCK))) is None

    def test_veto_outcomes(self, db: Database) -> None:
        cases = [
            (FakeProvider(Verdict.AGREE, 80), True, Reason.AI_DISAGREES),
            (FakeProvider(Verdict.DISAGREE, 80), False, Reason.AI_DISAGREES),
            (FakeProvider(Verdict.AGREE, 40), False, Reason.AI_LOW_CONFIDENCE),
            (FakeProvider(Verdict.UNSURE, 90), False, Reason.AI_LOW_CONFIDENCE),
            (FakeProvider(status=Status.REFUSED), False, Reason.AI_UNAVAILABLE),
            (FakeProvider(status=Status.TIMEOUT), False, Reason.AI_UNAVAILABLE),
        ]
        for i, (provider, passed, reason) in enumerate(cases):
            check = review(gate(db, provider), signal_id=f"s{i}", strategy=f"strategy_{i}")
            assert (check.passed, check.reason) == (passed, reason), provider.kw or provider.verdict

    def test_advisory_records_but_never_blocks(self, db: Database) -> None:
        check = review(gate(db, FakeProvider(Verdict.DISAGREE, 95), mode="advisory"))
        assert check.passed and check.detail.startswith("advisory:")
        with db.session() as sess:
            assert sess.scalars(select(AIAssessmentRow.effect)).one() == "ADVISORY"


class TestCacheAndBudgets:
    def test_one_call_per_candle_also_after_a_restart(self, db: Database) -> None:
        provider = FakeProvider(Verdict.DISAGREE, 80)
        first = gate(db, provider)
        review(first)
        review(first)
        assert provider.calls == 1
        restarted = gate(db, provider)
        assert not review(restarted).passed and provider.calls == 1  # the stored answer counts

    def test_a_used_up_budget_holds_without_calling(self, db: Database) -> None:
        provider = FakeProvider()
        g = gate(db, provider, max_calls_per_day=1)
        assert review(g, strategy="a").passed
        held = review(g, strategy="b")
        assert (held.passed, held.reason) == (False, Reason.AI_UNAVAILABLE) and provider.calls == 1
        assert "budget" in held.detail
        costly = gate(db, FakeProvider(cost=5.0), max_cost_per_day_usd=1.0, max_calls_per_day=10)
        review(costly, strategy="c")
        assert not review(costly, strategy="d").passed


class TestInTheDecision:
    def test_the_ai_can_veto_but_never_changes_the_size(self, db: Database) -> None:
        plain = engine(db).decide(request())
        agreeing = engine(db)
        agreeing.reviewer = gate(db, FakeProvider(Verdict.AGREE, 90)).review
        accepted = agreeing.decide(
            request(signal=make_signal(evidence=(), signal_id="s-ok", strategy="agree"))
        )
        assert accepted.decision is Decision.ACCEPT and accepted.volume == plain.volume == Decimal("0.24")
        assert accepted.checks[-1].name == "ai_review"
        vetoing = engine(db)
        vetoing.reviewer = gate(db, FakeProvider(Verdict.DISAGREE, 90)).review
        vetoed = vetoing.decide(request(signal=make_signal(evidence=(), signal_id="s-no", strategy="veto")))
        assert vetoed.decision is Decision.REJECT and vetoed.reason_codes == ("AI_DISAGREES",)

    def test_no_call_when_another_check_already_failed_or_for_advisory_decisions(self, db: Database) -> None:
        provider = FakeProvider()
        e = engine(db)
        e.reviewer = gate(db, provider).review
        e.decide(request(quote=None))  # rejected before the AI is asked
        e.decide(request(), Profile.ADVISORY)
        assert provider.calls == 0
