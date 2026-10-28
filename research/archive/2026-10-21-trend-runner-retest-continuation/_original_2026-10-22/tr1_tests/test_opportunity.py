# ruff: noqa: S101
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from tr1.bars import minute_bars
from tr1.opportunity import BarCandidate, Impulse, find_first_pullback, find_impulse, initial_stop, label_path
from tr1.simulation import Fill


def m1_from_closes(closes: list[float], start: str = "2025-10-20") -> pd.DataFrame:
    index = pd.date_range(start, periods=len(closes), freq="1min", tz="UTC")
    close = np.asarray(closes, float)
    return pd.DataFrame(
        {
            "open": np.r_[close[0], close[:-1]],
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "tick_volume": 1,
            "spread": 20,
        },
        index=index,
    )


def test_impulse_uses_the_first_qualifying_close_not_the_future_extreme() -> None:
    m1 = m1_from_closes([100.0, 100.2, 101.1, 99.0, 103.0])
    result = find_impulse(m1, pd.Timestamp("2025-10-20", tz="UTC"), 2.0, 0.5)
    assert result is not None
    assert result.side == 1
    assert result.decision == pd.Timestamp("2025-10-20 00:03", tz="UTC")


def test_impulse_requires_a_bar_near_the_anchor() -> None:
    m1 = m1_from_closes([100.0, 102.0])
    m1.index += pd.Timedelta(minutes=6)
    assert find_impulse(m1, pd.Timestamp("2025-10-20", tz="UTC"), 2.0, 0.5) is None


def test_first_pullback_is_confirmed_then_broken_by_a_later_close() -> None:
    # Impulse decision at 00:02. The 00:03 low is confirmed by 00:04, and 00:05 closes above the
    # three-bar continuation high. The entry cannot exist before 00:06.
    bars = minute_bars(
        m1_from_closes(
            [99.5] * 20 + [100.0, 101.0, 102.0, 101.4, 101.6, 102.5, 103.0],
            start="2025-10-19 23:40",
        )
    )
    impulse = Impulse(
        anchor=pd.Timestamp("2025-10-20", tz="UTC"),
        reference=100.0,
        h1_atr=4.0,
        threshold=0.5,
        side=1,
        decision=pd.Timestamp("2025-10-20 00:03", tz="UTC"),
        decision_bar=pd.Timestamp("2025-10-20 00:02", tz="UTC"),
    )
    candidate, reasons = find_first_pullback(
        bars,
        impulse,
        window="ASIA",
        timeframe="M1",
        deadline_minutes=120,
    )
    assert candidate is not None
    assert candidate.pivot_time == pd.Timestamp("2025-10-20 00:03", tz="UTC")
    assert candidate.pivot_available == pd.Timestamp("2025-10-20 00:05", tz="UTC")
    assert candidate.decision_time == pd.Timestamp("2025-10-20 00:06", tz="UTC")
    assert reasons["pivot_before_impulse"] == 0


def test_initial_stop_uses_the_larger_of_spread_and_atr_buffer() -> None:
    impulse = Impulse(
        anchor=pd.Timestamp("2025-10-20", tz="UTC"),
        reference=100.0,
        h1_atr=4.0,
        threshold=0.5,
        side=1,
        decision=pd.Timestamp("2025-10-20 00:03", tz="UTC"),
        decision_bar=pd.Timestamp("2025-10-20 00:02", tz="UTC"),
    )
    candidate = BarCandidate(
        "ASIA",
        "M1",
        impulse,
        3,
        pd.Timestamp("2025-10-20 00:03", tz="UTC"),
        101.0,
        pd.Timestamp("2025-10-20 00:05", tz="UTC"),
        2.0,
        1.0,
        0.5,
        102.0,
        5,
        pd.Timestamp("2025-10-20 00:06", tz="UTC"),
        1.0,
    )
    fill = Fill(0, candidate.decision_time, 102.2)
    stop, risk = initial_stop(candidate, fill, spread=0.3)
    assert stop == pytest.approx(100.7)
    assert risk == pytest.approx(1.5)


def test_path_processes_stop_before_later_quotes_with_the_same_timestamp() -> None:
    start = pd.Timestamp("2025-10-20", tz="UTC")
    ticks = pd.DataFrame(
        {
            "time_utc": [start, start, start + pd.Timedelta(minutes=60)],
            "bid": [100.0, 104.0, 104.0],
            "ask": [100.2, 104.2, 104.2],
        }
    )
    result = label_path(ticks, 1, 102.0, 100.0, start, start + pd.Timedelta(hours=8))
    assert result.stopped
    assert not result.reached_1r


def test_path_labels_milestones_horizons_and_giveback() -> None:
    start = pd.Timestamp("2025-10-20", tz="UTC")
    times = [start + pd.Timedelta(minutes=value) for value in (0, 10, 20, 60, 120, 240, 480)]
    ticks = pd.DataFrame(
        {
            "time_utc": times,
            "bid": [100.0, 102.0, 104.0, 103.0, 106.0, 105.0, 108.0],
            "ask": [100.2, 102.2, 104.2, 103.2, 106.2, 105.2, 108.2],
        }
    )
    result = label_path(ticks, 1, 100.0, 98.0, start, start + pd.Timedelta(hours=8))
    assert result.reached_1r
    assert result.reached_2r
    assert result.reached_3r
    assert not result.reached_5r
    assert result.time_1r_min == 10
    assert result.time_2r_min == 20
    assert result.mae_before_1r == pytest.approx(0.0)
    assert result.mae_before_2r == pytest.approx(0.0)
    assert result.mae_before_5r == pytest.approx(0.0)
    assert result.giveback_after_1r == pytest.approx(0.5)
    assert result.r_60 == pytest.approx(1.5)
    assert result.r_480 == pytest.approx(4.0)
    assert result.complete_8h


def test_ticks_after_the_intended_end_do_not_change_the_path() -> None:
    start = pd.Timestamp("2025-10-20", tz="UTC")
    ticks = pd.DataFrame(
        {
            "time_utc": [start, start + pd.Timedelta(hours=8), start + pd.Timedelta(hours=8, minutes=1)],
            "bid": [100.0, 102.0, 120.0],
            "ask": [100.2, 102.2, 120.2],
        }
    )
    result = label_path(ticks, 1, 100.0, 98.0, start, start + pd.Timedelta(hours=8))
    assert result.mfe_r == pytest.approx(1.0)
    assert not result.reached_2r


def test_stop_gap_is_included_in_mae_and_adverse_before_unreached_targets() -> None:
    start = pd.Timestamp("2025-10-20", tz="UTC")
    ticks = pd.DataFrame(
        {
            "time_utc": [start, start + pd.Timedelta(seconds=1)],
            "bid": [100.0, 96.0],
            "ask": [100.2, 96.2],
        }
    )
    result = label_path(ticks, 1, 100.0, 98.0, start, start + pd.Timedelta(hours=8))
    assert result.stopped
    assert result.mae_r == pytest.approx(-2.0)
    assert result.mae_before_1r == pytest.approx(-2.0)
    assert result.mae_before_5r == pytest.approx(-2.0)


def test_appending_future_bars_does_not_change_an_earlier_candidate() -> None:
    base = m1_from_closes(
        [99.5] * 20 + [100.0, 101.0, 102.0, 101.4, 101.6, 102.5] + [102.5] * 20,
        start="2025-10-19 23:40",
    )
    full = pd.concat(
        [
            base,
            m1_from_closes([50.0] * 20).set_axis(
                pd.date_range("2025-10-20 00:26", periods=20, freq="1min", tz="UTC")
            ),
        ]
    )
    impulse = Impulse(
        anchor=pd.Timestamp("2025-10-20", tz="UTC"),
        reference=100.0,
        h1_atr=4.0,
        threshold=0.5,
        side=1,
        decision=pd.Timestamp("2025-10-20 00:03", tz="UTC"),
        decision_bar=pd.Timestamp("2025-10-20 00:02", tz="UTC"),
    )
    short_result, _ = find_first_pullback(
        minute_bars(base), impulse, window="ASIA", timeframe="M1", deadline_minutes=120
    )
    full_result, _ = find_first_pullback(
        minute_bars(full), impulse, window="ASIA", timeframe="M1", deadline_minutes=120
    )
    assert short_result is not None
    assert full_result is not None
    assert short_result == full_result
