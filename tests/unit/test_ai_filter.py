"""The AI opinions' accuracy and the opt-in AI alert filter (TAA-1305)."""

from __future__ import annotations

from typing import Any

import pytest

from app.storage.database import Database
from app.storage.models import AINoteRow, ShadowTradeRow
from app.web.ai import filter_evaluation, implied_win, opinion_stats
from tests.unit.test_opportunity_alerts import ENGINE, Cloud, prefs


def note(subject: str, verdict: str, confidence: int = 70) -> AINoteRow:
    return AINoteRow(
        note_id=f"OPPORTUNITY:{subject}", kind="OPPORTUNITY", subject=subject, created_at=None, status="OK",
        verdict=verdict, confidence=confidence, reasons=[], text_en="x", text_th="x", facts={},
    )  # fmt: skip


def shadow(r: float) -> ShadowTradeRow:
    return ShadowTradeRow(win=r > 0, r_multiple=r)


def pairs(spec: list[tuple[str, float]]) -> list[tuple[AINoteRow, ShadowTradeRow]]:
    return [(note(f"o{i}", v), shadow(r)) for i, (v, r) in enumerate(spec)]


class TestAccuracy:
    def test_right_rate_brier_and_calibration(self) -> None:
        stats = opinion_stats(pairs([("AGREE", 2.0), ("AGREE", -1.0), ("DISAGREE", -1.0), ("UNSURE", 2.0)]))
        assert stats["judged"] == 4 and stats["right_rate"] == pytest.approx(2 / 3, abs=1e-4)
        assert stats["verdicts"]["AGREE"] == {"n": 2, "win_rate": 0.5, "avg_r": 0.5}
        assert stats["base_win_rate"] == 0.5 and stats["brier_baseline"] == 0.25
        assert sum(b["n"] for b in stats["calibration"]) == 4 and stats["simulated"] is True

    def test_implied_win(self) -> None:
        assert (implied_win("AGREE", 70), implied_win("DISAGREE", 70), implied_win("UNSURE", 90)) == (
            0.7, pytest.approx(0.3), 0.5,
        )  # fmt: skip


class TestFilterEvaluation:
    def test_offered_only_when_the_kept_trades_beat_all_with_enough_samples(self) -> None:
        good = pairs([("AGREE", 1.5)] * 30 + [("AGREE", -1.0)] * 10 + [("DISAGREE", -1.0)] * 30)
        result = filter_evaluation(good)
        assert result["offered"] is True and result["ci_low"] > 0 and result["n_kept"] == 40

    def test_not_offered_when_it_does_not_help_or_samples_are_few(self) -> None:
        useless = pairs([("AGREE", 1.0), ("AGREE", -1.0), ("DISAGREE", 1.0), ("DISAGREE", -1.0)] * 20)
        assert filter_evaluation(useless)["offered"] is False
        few = pairs([("AGREE", 1.5)] * 10 + [("DISAGREE", -1.0)] * 10)
        assert filter_evaluation(few)["offered"] is False
        assert filter_evaluation([])["offered"] is False


class TestAlertFilter:
    """Through the worker: the owner turns the filter on; it acts only while offered."""

    @pytest.fixture
    def cloud(self, db: Database, monkeypatch: pytest.MonkeyPatch) -> Cloud:
        monkeypatch.setattr("app.web.ai.AINotesReadModel.filter_offered", lambda self, engine_id: True)
        c = Cloud(db)
        c.set_prefs(prefs(ai_filter=True))
        return c

    def opinion(self, cloud: Cloud, verdict: str, *, oid: str = "o1", **over: Any) -> None:
        row = note(oid, verdict)
        row.engine_id, row.created_at = ENGINE, cloud.clock.now_utc()
        for k, v in over.items():
            setattr(row, k, v)
        with cloud.db.session() as sess:
            sess.add(row)

    def test_disagree_and_unsure_are_not_alerted(self, cloud: Cloud) -> None:
        cloud.add("o1")
        self.opinion(cloud, "DISAGREE", oid="o1")
        cloud.add("o2", symbol="EURUSD")
        self.opinion(cloud, "UNSURE", oid="o2")
        assert cloud.alerter.run() is None and cloud.notes("OPPORTUNITY") == []

    def test_agree_is_alerted(self, cloud: Cloud) -> None:
        cloud.add("o1")
        self.opinion(cloud, "AGREE")
        assert cloud.alerter.run() == "1 alerts, 0 updates"

    def test_a_missing_opinion_waits_briefly_then_alerts(self, cloud: Cloud) -> None:
        self.opinion(cloud, "AGREE", oid="earlier")  # the engine writes opinions: wait for this one's
        cloud.add("o1", created_at=cloud.clock.now_utc())
        assert cloud.alerter.run() is None
        cloud.clock.advance(91)
        cloud.alerter._ai.clear()
        assert cloud.alerter.run() == "1 alerts, 0 updates"

    def test_not_offered_means_no_filtering(self, cloud: Cloud, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.web.ai.AINotesReadModel.filter_offered", lambda self, engine_id: False)
        cloud.add("o1")
        self.opinion(cloud, "DISAGREE")
        assert cloud.alerter.run() == "1 alerts, 0 updates"
