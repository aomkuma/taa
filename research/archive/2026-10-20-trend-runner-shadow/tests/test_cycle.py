# ruff: noqa: S101
from __future__ import annotations

from pathlib import Path

import pandas as pd
from shadow.journal import ShadowJournal
from shadow.pipeline import run_cycle


def test_cycle_keeps_unavailable_forward_data_pending_and_is_idempotent(tmp_path: Path) -> None:
    m1_path = tmp_path / "M1.parquet"
    pd.DataFrame(
        {
            "open_time": [pd.Timestamp("2026-10-20T23:59:00Z")],
            "open": [100.0],
            "high": [100.0],
            "low": [100.0],
            "close": [100.0],
            "tick_volume": [1],
            "spread": [0],
        }
    ).to_parquet(m1_path, index=False)
    tick_root = tmp_path / "ticks"
    tick_root.mkdir()
    journal = ShadowJournal(tmp_path / "journal.sqlite")
    arguments = {
        "m1_path": m1_path,
        "tick_root": tick_root,
        "start_day": "2026-10-21",
        "end_day": "2026-10-22",
        "report_output": tmp_path / "status",
    }

    first = run_cycle(journal, **arguments)
    second = run_cycle(journal, **arguments)

    for result in (first, second):
        assert result["scan"] == {"PENDING_M1": 3}
        assert result["decisions_added"] == 0
        assert result["settlement"] == {"ALREADY_SETTLED_OR_EMPTY": 0}
        assert result["report"]["opportunities"] == 0
        assert result["report"]["outcomes"] == 0
        assert result["report"]["robustness"]["status"] == "INSUFFICIENT"
    assert journal.opportunities().empty
    assert journal.outcomes().empty
    assert journal.adapter_anchors().empty
