from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from shadow.journal import ShadowJournal
from shadow.outcome_adapter import calculate_outcome, load_outcome_ticks, settle
from shadow.outcomes import StructureContext, StructureEvent, run_exit
from shadow.schema import FEATURE_COLUMNS, Opportunity
from shadow.service import score_opportunity


def empty_context() -> StructureContext:
    columns = ["kind", "pivot_time", "price", "confirm", "avail"]
    return StructureContext(
        {"M5": pd.DataFrame(), "M15": pd.DataFrame()},
        {"M5": np.array([]), "M15": np.array([])},
        {"M5": pd.DataFrame(columns=columns), "M15": pd.DataFrame(columns=columns)},
    )


def raw_opportunity(key: str, entry_time: pd.Timestamp) -> dict[str, object]:
    features = {name: 0.1 for name in FEATURE_COLUMNS}
    features.update({"side_feature": 1.0, "session_asia": 1.0, "session_london": 0.0})
    return {
        "trade_key": key,
        "entry_time": entry_time.isoformat(),
        "anchor": (entry_time - pd.Timedelta(minutes=1)).isoformat(),
        "window": "ASIA",
        "side": 1,
        "entry": 100.0,
        "spread": 0.1,
        "stop": 99.0,
        "risk": 1.0,
        "features": features,
    }


def test_dual_outcome_partial_accounting() -> None:
    entry_time = pd.Timestamp("2026-11-02T00:01:00Z")
    ticks = pd.DataFrame(
        {
            "time_utc": [
                entry_time,
                entry_time + pd.Timedelta(minutes=1),
                entry_time + pd.Timedelta(minutes=2),
                entry_time + pd.Timedelta(hours=8),
            ],
            "bid": [99.9, 101.1, 102.1, 101.5],
            "ask": [100.0, 101.2, 102.2, 101.6],
        }
    )
    outcome = calculate_outcome(raw_opportunity("DUAL", entry_time), ticks, empty_context())
    assert outcome.fast_r == 2.0
    assert outcome.fast_exit_time == entry_time + pd.Timedelta(minutes=2)
    assert np.isclose(outcome.runner_r, 4.0 / 3.0)
    assert outcome.runner_exit_time == entry_time + pd.Timedelta(hours=8)


def test_exact_time_structure_confirmation_applies_after_price_action() -> None:
    entry_time = pd.Timestamp("2026-11-02T00:01:00Z")
    tick_time = entry_time + pd.Timedelta(minutes=5)
    ticks = pd.DataFrame({"time_utc": [tick_time], "bid": [98.0], "ask": [98.1]})
    event = StructureEvent(tick_time, "M5", entry_time, 99.1, 99.0)
    result = run_exit("RUNNER", ticks, 1, 100.0, 90.0, entry_time, [event])
    assert result.reason.value == "STOP"
    assert result.exit_time == tick_time
    assert result.exit_price == 98.0
    assert result.final_stop == 99.0


def test_tick_loader_waits_for_next_market_quote(tmp_path: Path) -> None:
    root = tmp_path / "ticks"
    root.mkdir()
    start = pd.Timestamp("2026-11-06T20:00:00Z")
    deadline = start + pd.Timedelta(hours=8)
    pd.DataFrame(
        {"time_utc": [start], "bid": [100.0], "ask": [100.1]}
    ).to_parquet(root / "2026-11-06.parquet", index=False)
    next_quote = pd.Timestamp("2026-11-09T00:00:00Z")
    pd.DataFrame(
        {"time_utc": [next_quote], "bid": [101.0], "ask": [101.1]}
    ).to_parquet(root / "2026-11-09.parquet", index=False)
    ticks = load_outcome_ticks(root, start, deadline)
    assert ticks is not None
    assert list(ticks["time_utc"]) == [start, next_quote]


def test_settle_writes_once_after_full_data_is_available(tmp_path: Path) -> None:
    entry_time = pd.Timestamp("2026-11-02T00:01:00Z")
    journal = ShadowJournal(tmp_path / "journal.sqlite")
    journal.initialize()
    journal.record_opportunity(Opportunity.from_dict(raw_opportunity("SETTLE", entry_time)))
    score_opportunity(journal, "SETTLE")

    m1_start = entry_time - pd.Timedelta(days=30)
    m1_index = pd.date_range(m1_start, entry_time + pd.Timedelta(hours=8), freq="1min")
    m1 = pd.DataFrame(
        {
            "open_time": m1_index,
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "tick_volume": 1,
            "spread": 0,
        }
    )
    m1_path = tmp_path / "M1.parquet"
    m1.to_parquet(m1_path, index=False)
    tick_root = tmp_path / "ticks"
    tick_root.mkdir()
    pd.DataFrame(
        {
            "time_utc": [entry_time, entry_time + pd.Timedelta(hours=8)],
            "bid": [99.9, 100.5],
            "ask": [100.0, 100.6],
        }
    ).to_parquet(tick_root / "2026-11-02.parquet", index=False)

    assert settle(journal, m1_path=m1_path, tick_root=tick_root) == {"SETTLED": 1}
    assert len(journal.outcomes()) == 1
    assert settle(journal, m1_path=m1_path, tick_root=tick_root) == {
        "ALREADY_SETTLED_OR_EMPTY": 0
    }
    assert len(journal.outcomes()) == 1
