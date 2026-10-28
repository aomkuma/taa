"""Tests of exam43.py's guard and summaries. No exam data is read: every reader here is a fake that records its calls."""

import numpy as np
import pandas as pd
import pytest

import exam43 as X


def fake_m1(rows_until: str):
    calls = []

    def reader(path, filters):
        calls.append(filters)
        t = pd.date_range("2026-04-15", rows_until, freq="1D", tz="UTC", inclusive="left")
        return pd.DataFrame({"open_time": t, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "tick_volume": 1.0,
                             "spread": 1.0})
    return reader, calls


def test_default_is_learning_and_abbreviation_refused():
    assert X.parser().parse_args([]).exam is False
    with pytest.raises(SystemExit):
        X.parser().parse_args(["--ex"])  # allow_abbrev=False
    assert X.parser().parse_args(["--exam"]).exam is True


def test_learning_m1_filter_stops_before_the_exam():
    reader, calls = fake_m1("2026-04-18")
    X.load_m1(False, reader)
    (f,) = calls
    assert ("open_time", "<", X.EXAM_START) in f
    assert f[0] == ("open_time", ">=", X.PERIODS["P1"][0] - X.WARMUP)


def test_learning_m1_refuses_exam_rows_from_a_reader():
    reader, _ = fake_m1("2026-04-20")  # returns 04-18 and 04-19: exam rows
    with pytest.raises(X.ExamPeriodError):
        X.load_m1(False, reader)


def test_exam_m1_reads_only_the_exam_window():
    reader, calls = fake_m1("2026-04-20")
    X.load_m1(True, reader)
    (f,) = calls
    assert ("open_time", "<", X.EXAM_END) in f and f[0] == ("open_time", ">=", X.EXAM_START - X.WARMUP)


def test_ticks_refused_before_the_reader_is_called():
    calls = []

    def reader(d):
        calls.append(d)
        return np.array([1]), np.array([1.0]), np.array([1.1])
    with pytest.raises(X.ExamPeriodError):
        X.day_ticks(pd.Timestamp("2026-04-18"), False, reader)
    assert calls == []
    # the last learning day is not joined to the exam's first day
    X.span(pd.Timestamp("2026-04-17 20:00", tz="UTC").value, False, reader)
    assert calls == [pd.Timestamp("2026-04-17", tz="UTC")]
    # with the switch, nothing at / after the exam's end
    assert X.day_ticks(pd.Timestamp("2026-10-18"), True, reader) is None
    assert pd.Timestamp("2026-10-18", tz="UTC") not in calls


def test_parts_and_labels():
    assert X.parts_for(False) == ["P1", "P2"] and X.parts_for(True) == ["exam"]
    assert X.window(False) == (X.PERIODS["P1"][0], X.EXAM_START)
    assert X.label(pd.Timestamp("2026-04-17 23:59", tz="UTC").value) == "P2"
    assert X.label(pd.Timestamp("2026-04-18", tz="UTC").value) == "exam"


def test_summary_by_hand():
    T = pd.DataFrame({"t_exit": [1, 2, 3, 4, 5], "pnl": [10.0, -4.0, -6.0, 0.0, 8.0], "R": [1.0, -1.0, -1.0, 0.0, 0.8]})
    s = X.summary(T)
    # equity 0, 10, 6, 0, 0, 8 -> max drawdown 10 (from 10 to 0); losing streak: -4, -6, 0 (pnl <= 0) = 3
    assert s["n"] == 5 and s["dd"] == pytest.approx(10.0) and s["streak"] == 3
    assert s["win"] == pytest.approx(0.4) and s["worst"] == -6.0 and s["usd"] == pytest.approx(8.0)
    assert s["R"] == pytest.approx(-0.04)


def test_summary_uses_exit_order_and_counts_dd_from_zero():
    T = pd.DataFrame({"t_exit": [2, 1], "pnl": [5.0, -3.0], "R": [0.5, -1.0]})
    # in exit order: -3 then +5 -> equity 0, -3, 2 -> drawdown 3 from the start (0)
    assert X.summary(T)["dd"] == pytest.approx(3.0)


def test_thai_week():
    # Sunday 2026-03-01 18:00 UTC = Monday 01:00 Thai -> the week of Monday 2026-03-02
    t = pd.Series([pd.Timestamp("2026-03-01 18:00", tz="UTC").value, pd.Timestamp("2026-03-01 16:00", tz="UTC").value])
    assert X.thai_week(t).tolist() == ["2026-03-02", "2026-02-23"]


def test_summary_sorts_by_exit():
    T = pd.DataFrame({"t_exit": [3, 1, 2], "pnl": [-5.0, 4.0, -2.0], "R": [-1.0, 1.0, -0.5]})
    # exit order 4, -2, -5 -> equity 0, 4, 2, -3 -> drawdown 7 (the file order would give 5)
    assert X.summary(T)["dd"] == pytest.approx(7.0)
