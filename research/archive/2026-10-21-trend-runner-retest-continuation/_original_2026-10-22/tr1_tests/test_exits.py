# ruff: noqa: S101
from __future__ import annotations

import pandas as pd
import pytest
from tr1.exits import ExitFamily, ExitReason, StructureEvent, run_exit

START = pd.Timestamp("2025-10-20", tz="UTC")


def ticks(minutes: list[int], bid: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time_utc": [START + pd.Timedelta(minutes=value) for value in minutes],
            "bid": bid,
            "ask": [value + 0.2 for value in bid],
        }
    )


def event(minute: int, timeframe: str, stop: float) -> StructureEvent:
    available = START + pd.Timedelta(minutes=minute)
    return StructureEvent(available, timeframe, available - pd.Timedelta(minutes=5), stop + 0.2, stop)


def test_fast_books_declared_target_before_time_exit() -> None:
    result = run_exit(ExitFamily.FAST, ticks([0, 60], [100.0, 105.0]), 1, 100.0, 98.0, START, [])
    assert result.reason is ExitReason.TARGET
    assert result.exit_price == pytest.approx(104.0)
    assert result.r == pytest.approx(2.0)


def test_structure_stop_activates_only_when_confirmation_is_available() -> None:
    stream = ticks([0, 9, 10], [100.0, 98.5, 98.5])
    result = run_exit(ExitFamily.SWING, stream, 1, 100.0, 98.0, START, [event(10, "M5", 99.0)])
    assert result.reason is ExitReason.STOP
    assert result.exit_time == START + pd.Timedelta(minutes=10)
    assert result.exit_price == pytest.approx(98.5)


def test_split_weights_realized_partial_and_gap_stop() -> None:
    stream = ticks([0, 10, 20], [100.0, 102.0, 97.0])
    result = run_exit(ExitFamily.SPLIT, stream, 1, 100.0, 98.0, START, [])
    assert result.partial_taken
    assert result.reason is ExitReason.STOP
    assert result.r == pytest.approx(-2.0 / 3.0)


def test_state_without_gate_uses_fast_time_exit() -> None:
    result = run_exit(ExitFamily.STATE, ticks([0, 60], [100.0, 101.0]), 1, 100.0, 98.0, START, [])
    assert not result.runner_activated
    assert result.reason is ExitReason.TIME
    assert result.r == pytest.approx(0.5)


def test_state_gate_converts_and_cancels_fast_target() -> None:
    stream = ticks([0, 10, 15, 30, 480], [100.0, 102.0, 101.5, 104.0, 106.0])
    result = run_exit(
        ExitFamily.STATE,
        stream,
        1,
        100.0,
        98.0,
        START,
        [event(15, "M5", 99.0)],
    )
    assert result.runner_activated
    assert result.reason is ExitReason.TIME
    assert result.r == pytest.approx(3.0)


def test_state_target_has_priority_over_gate_on_same_quote() -> None:
    stream = ticks([0, 15], [100.0, 104.0])
    result = run_exit(
        ExitFamily.STATE,
        stream,
        1,
        100.0,
        98.0,
        START,
        [event(15, "M5", 99.0)],
    )
    assert not result.runner_activated
    assert result.reason is ExitReason.TARGET
    assert result.r == pytest.approx(2.0)


def test_graduation_ignores_later_m5_but_accepts_m15() -> None:
    stream = ticks([0, 10, 20, 30], [100.0, 106.0, 103.0, 102.0])
    result = run_exit(
        ExitFamily.SWING,
        stream,
        1,
        100.0,
        98.0,
        START,
        [event(20, "M5", 104.0), event(30, "M15", 103.0)],
    )
    assert result.graduated
    assert result.reason is ExitReason.STOP
    assert result.exit_time == START + pd.Timedelta(minutes=30)
    assert result.final_stop == pytest.approx(103.0)


def test_missing_deadline_quote_is_censored() -> None:
    result = run_exit(ExitFamily.SWING, ticks([0, 60], [100.0, 101.0]), 1, 100.0, 98.0, START, [])
    assert not result.complete
    assert result.reason is ExitReason.CENSORED


def test_structure_stop_never_widens() -> None:
    stream = ticks([0, 10, 20, 30], [100.0, 101.0, 100.0, 98.5])
    result = run_exit(
        ExitFamily.SWING,
        stream,
        1,
        100.0,
        98.0,
        START,
        [event(10, "M5", 99.0), event(20, "M5", 97.0)],
    )
    assert result.reason is ExitReason.STOP
    assert result.final_stop == pytest.approx(99.0)


def test_quotes_appended_after_exit_do_not_change_result() -> None:
    short = ticks([0, 60], [100.0, 101.0])
    long = ticks([0, 60, 120], [100.0, 101.0, 120.0])
    before = run_exit(ExitFamily.FAST, short, 1, 100.0, 98.0, START, [])
    after = run_exit(ExitFamily.FAST, long, 1, 100.0, 98.0, START, [])
    assert before == after


def test_runner_does_not_graduate_below_three_r() -> None:
    result = run_exit(
        ExitFamily.SWING,
        ticks([0, 10], [100.0, 105.0]),
        1,
        100.0,
        98.0,
        START,
        [],
    )
    assert not result.graduated


def test_split_partial_precedes_structure_confirmation_on_the_same_quote() -> None:
    result = run_exit(
        ExitFamily.SPLIT,
        ticks([0, 10], [100.0, 102.0]),
        1,
        100.0,
        98.0,
        START,
        [event(10, "M5", 103.0)],
    )
    assert result.partial_taken
    assert result.reason is ExitReason.STOP
    assert result.r == pytest.approx(1.0)
