"""Stored ticks for quote replays (app/market_data/tick_store.py): one Parquet file per symbol and UTC day."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.market_data.tick_store import TickStore


def write(root: Path, day: str, rows: list[tuple[str, float, float]]) -> None:
    (root / "XAUUSD").mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=["time_utc", "bid", "ask"])
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    df.to_parquet(root / "XAUUSD" / f"{day}.parquet")


def test_ticks_across_days_in_time_order_and_never_past_the_end(tmp_path: Path) -> None:
    # day 1 written out of order; day 2 has a tick at / after the end
    write(tmp_path, "2026-01-05", [("2026-01-05 23:59:59", 2.0, 2.1), ("2026-01-05 23:59:58", 1.0, 1.1)])
    write(tmp_path, "2026-01-06", [("2026-01-06 00:00:01", 3.0, 3.1), ("2026-01-06 00:10:00", 9.0, 9.1)])
    store = TickStore(tmp_path, end=datetime(2026, 1, 6, 0, 5, tzinfo=UTC))
    t, bid, ask = store.between(
        "XAUUSD", datetime(2026, 1, 5, 23, 59, tzinfo=UTC), datetime(2026, 1, 6, 1, tzinfo=UTC)
    )
    assert list(bid) == [1.0, 2.0, 3.0] and list(ask) == [1.1, 2.1, 3.1]  # sorted; 00:10 is past the end
    assert t[0] == pd.Timestamp("2026-01-05 23:59:58", tz="UTC").value
    # [start, end): the start included, the end excluded
    t2, _, _ = store.between(
        "XAUUSD", datetime(2026, 1, 5, 23, 59, 58, tzinfo=UTC), datetime(2026, 1, 5, 23, 59, 59, tzinfo=UTC)
    )
    assert len(t2) == 1


def test_a_day_without_a_file_or_after_the_end_is_empty(tmp_path: Path) -> None:
    write(tmp_path, "2026-01-07", [("2026-01-07 10:00:00", 1.0, 1.1)])
    store = TickStore(tmp_path, end=datetime(2026, 1, 7, tzinfo=UTC))  # the 7th is at the end: never opened
    assert len(store.day("XAUUSD", datetime(2026, 1, 7, tzinfo=UTC))[0]) == 0
    assert len(store.day("XAUUSD", datetime(2026, 1, 8, tzinfo=UTC))[0]) == 0
    assert len(TickStore(tmp_path).day("XAUUSD", datetime(2026, 1, 7, 12, tzinfo=UTC))[0]) == 1
