# ruff: noqa: S101
from __future__ import annotations

import pandas as pd
import pytest
from build_weekly_journal import add_review_fields, build_summary, render_markdown, weekly_summary


def _row(key: str, entry_time: str, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "trade_key": key,
        "entry_time_utc": entry_time,
        "window": "LONDON",
        "side": "BUY",
        "action": "RUNNER",
        "action_reason": "selected",
        "runner_r": -1.0,
        "fast_r": -1.0,
        "runner_exit_reason": "STOP_INTRABAR",
        "fast_exit_reason": "STOP_INTRABAR",
        "runner_hold_minutes": 12.0,
        "path_class": "STOP_BEFORE_1R",
        "h1_atr": 8.0,
        "risk_h1_atr": 0.3,
        "pullback_ratio": 0.4,
        "open_space_atr": 1.5,
        "post_exit_favorable_from_exit_r": 2.0,
        "mfe_before_exit_r_including_exit_bar": 0.2,
        "mae_before_exit_r_including_exit_bar": -1.1,
    }
    row.update(updates)
    return row


def test_weekly_journal_preserves_each_trade_and_marks_review_flags():
    source = pd.DataFrame(
        [
            _row("b", "2024-01-08T06:00:00Z"),
            _row("a", "2024-01-07T06:00:00Z", action="SKIP", runner_r=0.5),
        ]
    )
    journal = add_review_fields(source)
    assert journal["trade_key"].tolist() == ["a", "b"]
    assert journal["week_start_utc"].tolist() == ["2024-01-01", "2024-01-08"]
    assert "SKIPPED_COUNTERFACTUAL_WIN" in journal.iloc[0]["review_flags"]
    assert "STOPPED_BEFORE_1R" in journal.iloc[0]["review_flags"]
    assert "SELECTED_RUNNER_LOSS" in journal.iloc[1]["review_flags"]


def test_weekly_summary_counts_wins_losses_and_flags_by_entry_week():
    source = pd.DataFrame(
        [
            _row("win", "2024-01-08T06:00:00Z", runner_r=1.5, path_class="STOP_AFTER_1R_PARTIAL"),
            _row("loss", "2024-01-09T06:00:00Z"),
            _row("skip", "2024-01-10T06:00:00Z", action="SKIP", runner_r=0.8),
        ]
    )
    summary = weekly_summary(add_review_fields(source))
    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["week_start_utc"] == "2024-01-08"
    assert row["opportunities"] == 3
    assert row["selected_runner"] == 2
    assert row["selected_wins"] == 1
    assert row["selected_losses"] == 1
    assert row["selected_total_r"] == pytest.approx(0.5)
    assert row["skipped_counterfactual_wins"] == 1


def test_weekly_journal_rejects_duplicate_trade_keys():
    source = pd.DataFrame([_row("same", "2024-01-08T06:00:00Z")] * 2)
    with pytest.raises(ValueError, match="duplicate trade keys"):
        add_review_fields(source)


def test_report_does_not_render_nan_for_weeks_with_no_selected_trade():
    source = pd.DataFrame([_row("skip", "2024-01-08T06:00:00Z", action="SKIP", runner_r=-1.0)])
    journal = add_review_fields(source)
    weeks = weekly_summary(journal)
    report = render_markdown(build_summary(journal, weeks), weeks)
    assert "| - | - |" in report
    assert "nan" not in report.lower()
