"""AI on advisory (TAA-1305, TAA-1304): opinions on opportunities and narratives, written on the engine."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.ai.advisory import Kind, NarrativeV1, OpinionV1, analytics_request, opinion_request
from app.ai.notes import AINotes
from app.ai.providers import Answer, NullProvider
from app.ai.schema import Status
from app.config import AIAdvisoryConfig
from app.core.clock import ManualClock
from app.storage.database import Database
from app.storage.models import (
    AINoteRow,
    OpportunityRow,
    ShadowTradeRow,
    SuitabilitySnapshotRow,
)
from tests.sync_data import T, sample_rows
from tests.unit.test_ai import Response, provider


def opinion(subject: str, **over: Any) -> OpinionV1:
    base: dict[str, Any] = {
        "schema_version": "1.0",
        "subject": subject,
        "verdict": "DISAGREE",
        "confidence": 70,
        "reasons": ["H1 trend evidence opposes the BUY"],
        "narrative_en": "The entry follows a pullback, but the higher-timeframe trend evidence points down.",
        "narrative_th": "จุดเข้าเกิดหลังการย่อตัว แต่หลักฐานแนวโน้มใน timeframe ใหญ่ชี้ลง",
    }
    return OpinionV1.model_validate(base | over)


def narrative(subject: str, **over: Any) -> NarrativeV1:
    base: dict[str, Any] = {
        "schema_version": "1.0",
        "subject": subject,
        "text_en": "EURUSD leads the ranking on its current score.",
        "text_th": "EURUSD อยู่อันดับต้นจากคะแนนปัจจุบัน",
    }
    return NarrativeV1.model_validate(base | over)


class FakeProvider:
    """Answers with *reply(subject, schema)*; records every call."""

    name = "fake"

    def __init__(
        self, clock: ManualClock, reply: Callable[[str, type[BaseModel]], Any] | None = None
    ) -> None:
        self.clock = clock
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.reply = reply or (
            lambda subject, schema: opinion(subject) if schema is OpinionV1 else narrative(subject)
        )

    def assess(self, request: Any) -> Any:  # pragma: no cover - not used by the notes
        raise AssertionError

    def ask(self, key: str, system: str, content: str, output_format: type[BaseModel]) -> Answer:
        payload = json.loads(content)
        self.calls.append((key, system, payload))
        parsed = self.reply(payload["subject"], output_format)
        if isinstance(parsed, Exception):
            raise parsed
        return Answer(
            Status.OK, parsed=parsed, model="claude-opus-5-5", input_tokens=900, output_tokens=250,
            cost_usd=0.0086, latency_ms=1200.0, created_at=self.clock.now_utc(),
        )  # fmt: skip


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(T + timedelta(minutes=2))


def seed(db: Database, *, kinds: tuple[type, ...] = (OpportunityRow,)) -> None:
    with db.session() as sess:
        sess.add_all([r for r in sample_rows() if isinstance(r, kinds)])


def notes(db: Database, clock: ManualClock, fake: Any, **cfg: Any) -> AINotes:
    config = AIAdvisoryConfig(enabled=True, **cfg)
    return AINotes(db, fake, config, clock, background=False)


def rows(db: Database) -> list[AINoteRow]:
    with db.session() as sess:
        return list(sess.scalars(select(AINoteRow).order_by(AINoteRow.created_at)))


class TestOpinions:
    def test_a_new_opportunity_gets_one_opinion(self, db: Database, clock: ManualClock) -> None:
        seed(db)
        fake = FakeProvider(clock)
        service = notes(db, clock, fake, ranking_narrative=False, analytics_narrative=False)
        assert service.tick() is True
        assert service.tick() is False  # asked once: nothing left to do
        (row,) = rows(db)
        assert (row.note_id, row.kind, row.status, row.verdict, row.confidence) == (
            "OPPORTUNITY:k1", "OPPORTUNITY", "OK", "DISAGREE", 70,
        )  # fmt: skip
        assert row.text_th.startswith("จุดเข้า") and row.cost_usd == pytest.approx(0.0086)
        _, system, payload = fake.calls[0]
        assert "never promise" in system and payload["subject"] == "k1"
        assert not {"lot", "risk_money", "reward_money", "equity", "currency"} & set(
            payload
        )  # no account data

    def test_an_answer_about_another_subject_is_refused_and_not_asked_again(
        self, db: Database, clock: ManualClock
    ) -> None:
        seed(db)
        fake = FakeProvider(clock, lambda subject, schema: opinion("some-other-opportunity"))
        service = notes(db, clock, fake, ranking_narrative=False, analytics_narrative=False)
        service.tick()
        service.tick()
        (row,) = rows(db)
        assert row.status == "INVALID" and "describes" in row.detail and row.verdict is None
        assert len(fake.calls) == 1

    @pytest.mark.parametrize(
        "text",
        ["This setup is a guaranteed winner.", "Risk-free entry here.", "เข้าได้เลย การันตีกำไร"],
    )
    def test_a_claim_of_profit_or_certainty_is_refused(
        self, db: Database, clock: ManualClock, text: str
    ) -> None:
        seed(db)
        fake = FakeProvider(
            clock, lambda subject, schema: opinion(subject, narrative_th=text, narrative_en=text)
        )
        notes(db, clock, fake, ranking_narrative=False, analytics_narrative=False).tick()
        (row,) = rows(db)
        assert row.status == "INVALID" and row.text_en == "" and "claims" in row.detail

    def test_stale_or_low_scoring_opportunities_get_none(self, db: Database, clock: ManualClock) -> None:
        seed(db)
        fake = FakeProvider(clock)
        clock.advance(11 * 60)  # older than max_age_minutes (10)
        assert notes(db, clock, fake, ranking_narrative=False, analytics_narrative=False).tick() is False
        fresh = ManualClock(T + timedelta(minutes=2))
        low = notes(db, fresh, fake, min_score=50, ranking_narrative=False, analytics_narrative=False)
        assert low.tick() is False and fake.calls == []

    def test_the_budget_stops_calls_without_recording(self, db: Database, clock: ManualClock) -> None:
        seed(db)
        fake = FakeProvider(clock)
        service = notes(db, clock, fake, max_calls_per_day=0)
        assert service.tick() is False and fake.calls == [] and rows(db) == []
        assert service.stats.budget_holds == 1

    def test_a_provider_crash_is_counted_never_raised(self, db: Database, clock: ManualClock) -> None:
        seed(db)
        fake = FakeProvider(clock, lambda subject, schema: RuntimeError("boom"))
        service = notes(db, clock, fake, ranking_narrative=False, analytics_narrative=False)
        assert service.tick() is True
        assert service.stats.failures == 1 and "boom" in service.stats.last_error

    def test_off_without_a_provider_or_the_switch(self, db: Database, clock: ManualClock) -> None:
        assert not AINotes(db, NullProvider(clock), AIAdvisoryConfig(enabled=True), clock).active
        assert not AINotes(db, FakeProvider(clock), AIAdvisoryConfig(enabled=False), clock).active

    def test_the_call_runs_on_a_worker_thread(self, db: Database, clock: ManualClock) -> None:
        seed(db)
        service = AINotes(
            db,
            FakeProvider(clock),
            AIAdvisoryConfig(enabled=True, ranking_narrative=False, analytics_narrative=False),
            clock,
        )
        try:
            assert service.tick() is True
            assert service.tick() is False  # still running or done: never a second call at once
            deadline = time.monotonic() + 5
            while not rows(db) and time.monotonic() < deadline:
                time.sleep(0.01)
            assert rows(db)[0].status == "OK"
        finally:
            service.close()


class TestNarratives:
    def test_ranking_then_analytics_each_once_per_period(self, db: Database, clock: ManualClock) -> None:
        seed(db, kinds=(SuitabilitySnapshotRow,))
        with db.session() as sess:
            trade = next(r for r in sample_rows() if isinstance(r, ShadowTradeRow))
            trade.status, trade.exit_at, trade.r_multiple, trade.win = "CLOSED", T, 1.5, True
            sess.add(trade)
        fake = FakeProvider(clock)
        service = notes(db, clock, fake, opinions=False)
        assert service.tick() and service.tick()
        assert service.tick() is False  # both done; the next ones are due in 24 h
        kinds = [r.kind for r in rows(db)]
        assert kinds == ["RANKING", "ANALYTICS"] and all(r.status == "OK" for r in rows(db))
        ranking = fake.calls[0][2]
        assert ranking["top"][0]["symbol"] == "EURUSD"
        analytics = fake.calls[1][2]
        assert analytics["simulated"] is True and analytics["trades"] == 1 and analytics["avg_r"] == 1.5
        clock.advance(25 * 3600)
        assert service.tick() is True  # a day later: the analytics period moved, the ranking snapshot did not
        assert [r.kind for r in rows(db)] == ["RANKING", "ANALYTICS", "ANALYTICS"]


def test_inputs_are_numeric_facts() -> None:
    row = next(r for r in sample_rows() if isinstance(r, OpportunityRow))
    request = opinion_request(row)
    assert request.kind is Kind.OPPORTUNITY and request.note_id == "OPPORTUNITY:k1"
    assert request.payload["evidence"] == {"trend.ema": 1.0}
    assert analytics_request([], T, T) is None


def test_through_the_anthropic_provider(db: Database, clock: ManualClock) -> None:
    seed(db)
    claude, fake = provider(Response(parsed_output=opinion("k1", verdict="AGREE", confidence=64)))
    service = AINotes(
        db,
        claude,
        AIAdvisoryConfig(enabled=True, ranking_narrative=False, analytics_narrative=False),
        clock,
        background=False,
    )
    assert service.tick()
    (call,) = fake.calls
    assert call["output_format"] is OpinionV1 and "second opinion" in call["system"]
    (row,) = rows(db)
    assert (row.status, row.verdict, row.confidence, row.input_tokens) == ("OK", "AGREE", 64, 1200)
