from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from shadow.journal import ShadowJournal
from shadow.report import build_report
from shadow.schema import FEATURE_COLUMNS, Opportunity, Outcome
from shadow.service import score_opportunity, score_pending


def opportunity_payload(key: str, entry_time: pd.Timestamp, *, side: int = 1) -> dict[str, object]:
    window = "ASIA" if entry_time.hour < 6 else "LONDON"
    features = {name: 0.1 for name in FEATURE_COLUMNS}
    features["side_feature"] = float(side)
    features["session_asia"] = float(window == "ASIA")
    features["session_london"] = float(window == "LONDON")
    entry = 2000.0
    risk = 5.0
    return {
        "trade_key": key,
        "entry_time": entry_time.isoformat(),
        "anchor": (entry_time - pd.Timedelta(minutes=30)).isoformat(),
        "window": window,
        "side": side,
        "entry": entry,
        "spread": 0.2,
        "stop": entry - side * risk,
        "risk": risk,
        "features": features,
    }


def outcome_payload(key: str, exit_time: pd.Timestamp, runner_r: float) -> dict[str, object]:
    return {
        "trade_key": key,
        "fast_exit_time": (exit_time - pd.Timedelta(minutes=30)).isoformat(),
        "runner_exit_time": exit_time.isoformat(),
        "fast_r": min(runner_r, 2.0),
        "runner_r": runner_r,
        "fast_usd_fixed_001": min(runner_r, 2.0) * 5.0,
        "runner_usd_fixed_001": runner_r * 5.0,
    }


def journal_at(path: Path) -> ShadowJournal:
    journal = ShadowJournal(path)
    journal.initialize()
    return journal


def test_schema_boundary_and_feature_integrity() -> None:
    before = opportunity_payload("OLD", pd.Timestamp("2026-10-20T12:00:00Z"))
    with pytest.raises(ValueError, match="predates"):
        Opportunity.from_dict(before)
    bad = opportunity_payload("BAD", pd.Timestamp("2026-10-22T12:00:00Z"))
    bad["features"]["side_feature"] = -1.0
    with pytest.raises(ValueError, match="side_feature"):
        Opportunity.from_dict(bad)


def test_append_only_idempotency_and_outcome_checks(tmp_path: Path) -> None:
    journal = journal_at(tmp_path / "journal.sqlite")
    raw = opportunity_payload("T1", pd.Timestamp("2026-10-22T12:00:00Z"))
    event = Opportunity.from_dict(raw)
    assert journal.record_opportunity(event)
    assert not journal.record_opportunity(event)
    changed = dict(raw)
    changed["entry"] = 2001.0
    with pytest.raises(ValueError, match="risk must equal"):
        Opportunity.from_dict(changed)
    outcome = Outcome.from_dict(outcome_payload("T1", pd.Timestamp("2026-10-22T13:00:00Z"), 1.0))
    with pytest.raises(ValueError, match="score the opportunity"):
        journal.record_outcome(outcome)
    score_opportunity(journal, "T1")
    assert journal.record_outcome(outcome)
    assert not journal.record_outcome(outcome)
    bad_outcome = Outcome.from_dict(outcome_payload("T1", pd.Timestamp("2026-10-22T14:00:00Z"), 2.0))
    with pytest.raises(ValueError, match="immutable"):
        journal.record_outcome(bad_outcome)


def test_cold_start_freezes_entire_month_as_warmup(tmp_path: Path) -> None:
    journal = journal_at(tmp_path / "warmup.sqlite")
    event = Opportunity.from_dict(opportunity_payload("W1", pd.Timestamp("2026-11-03T12:00:00Z")))
    journal.record_opportunity(event)
    assert score_opportunity(journal, "W1") == 3
    decisions = journal.decisions()
    assert set(decisions["status"]) == {"WARMUP"}
    assert decisions["action"].isna().all()
    assert len(journal.snapshots()) == 3


def ready_journal(path: Path) -> tuple[ShadowJournal, str]:
    journal = journal_at(path)
    start = pd.Timestamp("2026-11-02T00:30:00Z")
    for index in range(60):
        entry_time = start + pd.Timedelta(days=index)
        key = f"TRAIN-{index:03d}"
        side = 1 if index % 2 == 0 else -1
        journal.record_opportunity(Opportunity.from_dict(opportunity_payload(key, entry_time, side=side)))
        score_opportunity(journal, key)
        runner_r = ((index % 7) - 2) / 3
        journal.record_outcome(
            Outcome.from_dict(outcome_payload(key, entry_time + pd.Timedelta(hours=2), runner_r))
        )
    target_key = "TARGET"
    target_time = pd.Timestamp("2027-01-02T12:00:00Z")
    journal.record_opportunity(Opportunity.from_dict(opportunity_payload(target_key, target_time)))
    return journal, target_key


def test_ready_month_scores_all_policies_and_freezes_model(tmp_path: Path) -> None:
    journal, target = ready_journal(tmp_path / "ready.sqlite")
    assert score_opportunity(journal, target) == 3
    decisions = journal.decisions()
    target_decisions = decisions.loc[decisions["trade_key"] == target]
    assert set(target_decisions["status"]) == {"SCORED"}
    assert set(target_decisions["policy"]) == {
        "CHAMPION_R3",
        "CHALLENGER_T010",
        "CHALLENGER_BUY_ONLY",
    }
    assert set(target_decisions["action"]) <= {"RUNNER", "SKIP"}
    before = target_decisions[["policy", "decision_hash"]].sort_values("policy").reset_index(drop=True)
    journal.record_outcome(
        Outcome.from_dict(outcome_payload(target, pd.Timestamp("2027-01-02T14:00:00Z"), 99.0))
    )
    assert score_pending(journal) == 0
    after = journal.decisions().loc[lambda frame: frame["trade_key"] == target]
    after = after[["policy", "decision_hash"]].sort_values("policy").reset_index(drop=True)
    pd.testing.assert_frame_equal(before, after)


def test_report_is_observational_and_not_ready_early(tmp_path: Path) -> None:
    journal, target = ready_journal(tmp_path / "report.sqlite")
    score_opportunity(journal, target)
    journal.record_outcome(
        Outcome.from_dict(outcome_payload(target, pd.Timestamp("2027-01-02T14:00:00Z"), 1.0))
    )
    report = build_report(journal)
    assert report["mode"] == "SHADOW_ONLY_NO_ORDER_CAPABILITY"
    assert report["champion_scored_opportunities"] == 1
    assert not report["evaluation_ready"]
    assert report["robustness"]["status"] == "INSUFFICIENT"
    assert report["robustness"]["hypothetical_slippage_stress"] == "EXCLUDED_BY_USER"
    assert set(report["policy_comparison"]) == {
        "CHAMPION_R3",
        "CHALLENGER_T010",
        "CHALLENGER_BUY_ONLY",
    }
    assert report["drift"]["status"] in {"OK", "WATCH", "ALERT"}


def test_source_has_no_execution_imports() -> None:
    source = Path(__file__).resolve().parents[1] / "shadow"
    import_lines = [
        line.strip()
        for path in source.glob("*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(("from ", "import "))
    ]
    forbidden = ("app", "broker", "engine", "execution", "tr1", "r2", "r3")
    assert not [line for line in import_lines if any(token in line for token in forbidden)]
