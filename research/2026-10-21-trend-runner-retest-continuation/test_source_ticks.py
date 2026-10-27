# ruff: noqa: S101, PT018, E501
"""Hand-worked tests: V1 source eligibility from TR1's tick SPLIT exit, and the exam / tick guards (2026-10-22).

Common trade: BUY entry 100.00 at 10:00:00, initial stop 99.00 (1R = 1.00), +1R = 101.00, marks are bids.
"""

from __future__ import annotations

import pandas as pd
import pytest
from source_ticks import source_trades, stopped_before_plus1, tick_root_for
from ticks import DEFAULT_ROOTS, ExamLockedError, TickSource, refuse_exam
from tr1.exits import StructureEvent, run_exit

T = pd.Timestamp("2025-11-05 10:00", tz="UTC")


def quotes(*rows: tuple[float, float]) -> pd.DataFrame:
    """rows of (minutes after T, bid); ask = bid + 0.03."""
    return pd.DataFrame(
        {
            "time_utc": [T + pd.Timedelta(minutes=mi) for mi, _ in rows],
            "bid": [b for _, b in rows],
            "ask": [b + 0.03 for _, b in rows],
        }
    )


def split(ticks: pd.DataFrame, events: list[StructureEvent] | None = None):
    result = run_exit("SPLIT", ticks, 1, 100.00, 99.00, T, events or [])
    return result, stopped_before_plus1(result.complete, result.reason.value, result.partial_taken)


def test_initial_stop_before_plus_one_is_eligible():
    # bids 100.50 (+0.5R), 98.90 (through 99.00) -> STOP, no partial -> eligible
    result, ok = split(quotes((0, 99.97), (5, 100.50), (9, 98.90)))
    assert result.reason.value == "STOP" and not result.partial_taken and ok


def test_stop_after_plus_one_is_not_eligible():
    # 101.00 = +1R books the 1/3 partial first; the later stop at 98.90 is after the first +1R touch
    result, ok = split(quotes((0, 99.97), (5, 101.00), (9, 98.90)))
    assert result.partial_taken and not ok


def test_trailed_stop_before_plus_one_is_eligible_without_a_minus_one_touch():
    # Bug B8: the old holdout test demanded a -1R touch. An M5 trail at 99.60 (available 10:05) stops the RUNNER at
    # 99.55 (= -0.45R) before +1R: the rule ("stopped before its first +1R touch") makes it eligible.
    event = StructureEvent(T + pd.Timedelta(minutes=5), "M5", T + pd.Timedelta(minutes=1), 99.70, 99.60)
    result, ok = split(quotes((0, 99.97), (3, 100.40), (6, 99.55)), [event])
    assert result.reason.value == "STOP" and result.exit_price == pytest.approx(99.55) and ok


def test_time_exit_and_censored_paths_are_not_eligible():
    result, ok = split(quotes((0, 99.97), (480, 99.50)))  # first quote at entry + 8 h, above the stop
    assert result.reason.value == "TIME" and not ok
    result, ok = split(quotes((0, 99.97), (60, 99.50)))  # data ends before stop or deadline
    assert result.reason.value == "CENSORED" and not ok


def test_refuse_exam_spans():
    refuse_exam(pd.Timestamp("2026-04-17 23:59", tz="UTC"))  # the instant before the exam: allowed
    refuse_exam(pd.Timestamp("2026-10-18", tz="UTC"))  # first instant after the exam: allowed
    refuse_exam(
        pd.Timestamp("2026-04-10", tz="UTC"), pd.Timestamp("2026-04-18", tz="UTC")
    )  # half-open: allowed
    with pytest.raises(ExamLockedError):
        refuse_exam(pd.Timestamp("2026-04-18", tz="UTC"))
    with pytest.raises(ExamLockedError):
        refuse_exam(pd.Timestamp("2026-04-10", tz="UTC"), pd.Timestamp("2026-04-18 00:00:01", tz="UTC"))
    with pytest.raises(ExamLockedError):
        refuse_exam(pd.Timestamp("2026-10-17 23:59", tz="UTC"))


def test_tick_source_refuses_an_exam_day_before_touching_the_disk(tmp_path):
    # The roots point to an empty folder: a read attempt would return None; the guard must raise first.
    source = TickSource(roots=(tmp_path,))
    assert source.day(pd.Timestamp("2025-11-05", tz="UTC")) is None
    with pytest.raises(ExamLockedError):
        source.day(pd.Timestamp("2026-06-01", tz="UTC"))
    with pytest.raises(ExamLockedError):
        source.span(pd.Timestamp("2026-04-17 22:00", tz="UTC"), pd.Timestamp("2026-04-18 01:00", tz="UTC"))
    assert source.opened == []


def test_tick_source_reads_one_day_in_file_order(tmp_path):
    day = pd.Timestamp("2025-11-05", tz="UTC")
    frame = pd.DataFrame(
        {
            "time_utc": [day + pd.Timedelta(seconds=s) for s in (5, 1, 1)],
            "bid": [3.0, 1.0, 2.0],
            "ask": [3.1, 1.1, 2.1],
        }
    )
    frame.to_parquet(tmp_path / "2025-11-05.parquet")
    got = TickSource(roots=(tmp_path,)).day(day)
    # sorted by time with the two equal-time quotes kept in file order (1.0 then 2.0)
    assert list(got["bid"]) == [1.0, 2.0, 3.0]


def test_source_slice_refuses_the_exam_and_long_spans():
    with pytest.raises(ExamLockedError):
        source_trades(pd.Timestamp("2026-04-13", tz="UTC"), pd.Timestamp("2026-04-20", tz="UTC"))
    with pytest.raises(ExamLockedError):  # the 3-day settle after 2026-04-16 reaches the exam
        source_trades(pd.Timestamp("2026-04-09", tz="UTC"), pd.Timestamp("2026-04-16", tz="UTC"))
    with pytest.raises(ValueError, match="21 days"):
        source_trades(pd.Timestamp("2025-11-01", tz="UTC"), pd.Timestamp("2025-12-01", tz="UTC"))


def test_tick_root_by_date():
    assert (
        tick_root_for(pd.Timestamp("2025-11-01", tz="UTC"), pd.Timestamp("2025-11-08", tz="UTC"))
        == DEFAULT_ROOTS[0]
    )
    assert (
        tick_root_for(pd.Timestamp("2022-03-01", tz="UTC"), pd.Timestamp("2022-03-08", tz="UTC"))
        == DEFAULT_ROOTS[1]
    )
    with pytest.raises(ValueError, match="straddle"):
        tick_root_for(pd.Timestamp("2025-09-28", tz="UTC"), pd.Timestamp("2025-10-03", tz="UTC"))
