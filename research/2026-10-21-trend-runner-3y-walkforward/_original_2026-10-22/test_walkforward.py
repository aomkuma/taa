from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walkforward import simulate_m1_exit  # noqa: E402


def setup_trade(*, time: str = "2024-01-01T00:00:00Z") -> pd.Series:
    return pd.Series({
        "side": 1,
        "entry": 100.0,
        "stop": 99.0,
        "risk": 1.0,
        "entry_time": pd.Timestamp(time),
        "spread": 0.1,
    })


def bars(rows: list[tuple[int, float, float, float, float]]) -> pd.DataFrame:
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    index = [start + pd.Timedelta(minutes=x[0]) for x in rows]
    return pd.DataFrame(
        [{"open": x[1], "high": x[2], "low": x[3], "close": x[4], "spread": 10} for x in rows],
        index=pd.DatetimeIndex(index, name="open_time"),
    )


def test_stop_wins_when_same_m1_bar_touches_stop_and_target() -> None:
    result = simulate_m1_exit(
        bars([(0, 100.0, 102.5, 98.5, 101.0)]), setup_trade(), "FAST", []
    )
    assert result.complete
    assert result.reason == "STOP_INTRABAR"
    assert result.r == -1.0


def test_gap_through_stop_fills_at_worse_open() -> None:
    result = simulate_m1_exit(
        bars([(0, 98.0, 100.0, 97.5, 99.0)]), setup_trade(), "SPLIT", []
    )
    assert result.complete
    assert result.reason == "STOP_GAP"
    assert result.r == -2.0


def test_fast_target_fills_at_declared_two_r() -> None:
    result = simulate_m1_exit(
        bars([(0, 100.0, 102.0, 99.5, 101.5)]), setup_trade(), "FAST", []
    )
    assert result.complete
    assert result.reason == "TARGET_2R"
    assert result.r == 2.0


def test_split_partial_is_applied_before_later_stop() -> None:
    result = simulate_m1_exit(
        bars([(0, 100.0, 101.2, 99.5, 100.8), (1, 100.8, 101.0, 98.8, 99.2)]),
        setup_trade(), "SPLIT", [],
    )
    assert result.complete
    assert result.partial_taken
    assert result.reason == "STOP_INTRABAR"
    assert abs(result.r - (-1.0 / 3.0)) < 1e-12
