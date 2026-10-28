from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from shadow.adapter import load_m1, load_ticks, process_anchor, scan
from shadow.clocks import anchor
from shadow.detector import detect, fill_and_risk
from shadow.journal import ShadowJournal
from shadow.live_features import build_features
from shadow.schema import FEATURE_COLUMNS

REPO = Path(__file__).resolve().parents[3]


def test_dst_aware_session_anchors() -> None:
    assert anchor("2026-01-15", "ASIA") == pd.Timestamp("2026-01-15T00:00:00Z")
    assert anchor("2026-01-15", "LONDON") == pd.Timestamp("2026-01-15T06:00:00Z")
    assert anchor("2026-01-15", "NY0830") == pd.Timestamp("2026-01-15T13:30:00Z")
    assert anchor("2026-07-15", "NY0830") == pd.Timestamp("2026-07-15T12:30:00Z")


def test_real_safe_entry_matches_frozen_and_ignores_later_m1(tmp_path: Path) -> None:
    m1_path = REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet"
    m1 = load_m1(
        m1_path,
        pd.Timestamp("2025-09-01T00:00:00Z"),
        pd.Timestamp("2025-10-22T00:00:00Z"),
    )
    at = pd.Timestamp("2025-10-20T00:00:00Z")
    detection = detect(m1, at, "ASIA")
    truncated = detect(m1.loc[m1.index < at + pd.Timedelta(hours=2)], at, "ASIA")
    assert detection == truncated
    assert detection is not None
    ticks = load_ticks(
        REPO / "data/ticks/XAUUSD",
        detection.decision_time,
        detection.decision_time + pd.Timedelta(minutes=5),
    )
    assert ticks is not None
    fill = fill_and_risk(detection, ticks)
    assert fill is not None
    frozen = pd.read_parquet(
        REPO / "research/2026-10-20-trend-runner/frozen_entries_p1.parquet"
    ).iloc[0]
    assert fill["entry_time"] == frozen["entry_time"]
    assert fill["entry"] == frozen["entry"]
    assert fill["stop"] == frozen["stop"]
    assert fill["risk"] == frozen["risk"]

    journal = ShadowJournal(tmp_path / "empty.sqlite")
    journal.initialize()
    features = build_features(m1, detection, fill, journal)
    expected = pd.read_parquet(
        REPO / "research/2026-10-20-trend-runner-r2/feature_panel.parquet"
    ).loc[lambda frame: frame["trade_key"] == "P1-000"].iloc[0]
    for name in FEATURE_COLUMNS:
        assert features[name] == expected[name]

    no_entry_anchor = pd.Timestamp("2025-10-20T06:00:00Z")
    assert (
        process_anchor(
            journal,
            m1,
            REPO / "data/ticks/XAUUSD",
            no_entry_anchor,
            "LONDON",
            operational=False,
        )
        == "NO_ENTRY"
    )
    assert (
        process_anchor(
            journal,
            m1,
            REPO / "data/ticks/XAUUSD",
            no_entry_anchor,
            "LONDON",
            operational=False,
        )
        == "ALREADY_PROCESSED"
    )


def test_operational_scan_rejects_historical_start(tmp_path: Path) -> None:
    journal = ShadowJournal(tmp_path / "boundary.sqlite")
    journal.initialize()
    with pytest.raises(ValueError, match="collection boundary"):
        scan(
            journal,
            m1_path=REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet",
            tick_root=REPO / "data/ticks/XAUUSD",
            start_day="2026-10-20",
            end_day="2026-10-21",
        )
