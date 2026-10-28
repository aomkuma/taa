from __future__ import annotations

# Pytest assertions intentionally use Python's assertion syntax.
# ruff: noqa: S101
import pandas as pd
from run_historical_holdout import source_stopped_before_1r


def bars(rows: list[tuple[float, float, float]]) -> pd.DataFrame:
    index = pd.date_range("2022-01-03T00:00:00Z", periods=len(rows), freq="1min")
    return pd.DataFrame(rows, columns=["high", "low", "spread"], index=index)


def test_stopped_before_one_r_requires_adverse_touch_first():
    frame = bars([(100.5, 99.0, 0.0), (100.8, 99.2, 0.0)])
    assert source_stopped_before_1r(
        frame, frame.index[0], frame.index[-1] + pd.Timedelta(minutes=1), 1, 100.0, 1.0
    )


def test_same_bar_first_touch_is_ambiguous_not_eligible():
    frame = bars([(101.0, 99.0, 0.0), (100.4, 99.5, 0.0)])
    assert not source_stopped_before_1r(
        frame, frame.index[0], frame.index[-1] + pd.Timedelta(minutes=1), 1, 100.0, 1.0
    )


def test_favorable_one_r_before_later_stop_is_not_eligible():
    frame = bars([(101.1, 99.5, 0.0), (100.5, 99.0, 0.0)])
    assert not source_stopped_before_1r(
        frame, frame.index[0], frame.index[-1] + pd.Timedelta(minutes=1), 1, 100.0, 1.0
    )
