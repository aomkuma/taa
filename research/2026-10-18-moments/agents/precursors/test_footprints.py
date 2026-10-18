"""footprints.py by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_footprints.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from footprints import USD_PAIRS, change, event_minutes, round_dist, usd, volume_rel  # noqa: E402


def frame(idx: pd.DatetimeIndex, close: np.ndarray, vol: np.ndarray | None = None) -> pd.DataFrame:
    c = np.asarray(close, float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "tick_volume": np.ones(len(c)) if vol is None else vol}, index=idx)


def test_volume_against_the_same_minutes_of_earlier_days_only():
    # 21 days of 08:00-08:09 UTC; 10 a minute on odd days, 20 on even days, 30 on the last day
    days = pd.date_range("2026-05-01 08:00", periods=21, freq="D", tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=k) for d in days for k in range(10)])
    day_no = np.repeat(np.arange(1, 22), 10)
    vol = np.where(day_no == 21, 30.0, np.where(day_no % 2 == 1, 10.0, 20.0))
    m = frame(idx, np.full(len(idx), 100.0), vol)
    t = pd.DatetimeIndex(["2026-05-21 08:05", "2026-05-20 08:05"], tz="UTC").as_unit("ns").asi8
    # at 08:05 the last 5 bars are 08:00-08:04: 150 on day 21 against days 1-20 (ten 50s, ten 100s: median 75) -> 2.0
    # (with day 21 itself in the window the median would be 100 -> 1.5); day 20: 100 against days 1-19 (median 50) -> 2.0
    assert volume_rel(m, t).tolist() == [2.0, 2.0]


def test_the_clock_of_the_big_orders_across_summer_time():
    t = pd.DatetimeIndex(["2026-06-15 09:30", "2026-06-15 09:00", "2026-01-15 10:30", "2026-06-15 12:30", "2026-06-15 03:00"], tz="UTC")
    # the London fix 10:30 local: summer = 09:30 UTC; winter = 10:30 UTC; far away is clipped at -240
    assert event_minutes(t, "Europe/London", 630).tolist() == [0, -30, 0, 180, -240]
    # the US data 08:30 New York = 12:30 UTC in summer
    assert event_minutes(t[3:4], "America/New_York", 510).tolist() == [0]


def test_round_numbers():
    px = np.array([4012.0, 4038.0, 4025.0])
    assert round_dist(px, 10.0).tolist() == [2.0, -2.0, 5.0] and round_dist(px, 50.0).tolist() == [12.0, -12.0, 25.0]


def test_the_move_before_uses_closes_known_at_each_time():
    idx = pd.date_range("2026-05-04 08:00", periods=30, freq="1min", tz="UTC")
    c = 100.0 + np.arange(30)
    c[20] = 500.0  # the bar opening at 08:20 is still forming at 08:20: it must not count
    m = frame(idx, c)
    t = np.array([pd.Timestamp("2026-05-04 08:20", tz="UTC").value])
    # the last bar complete by 08:20 is 08:19 (close 119); by 08:05 it is 08:04 (close 104)
    assert change(m, t, 15).tolist() == [15.0]


def test_the_dollar_points_up_when_it_gains():
    idx = pd.date_range("2026-05-04 00:00", periods=400, freq="1min", tz="UTC")
    rng = np.random.default_rng(2)
    others = {}
    for sym, sgn in USD_PAIRS.items():
        base = 1.2 if sgn < 0 else 140.0
        noise = np.cumsum(rng.normal(0, 1e-4, 400))
        drift = np.where(np.arange(400) >= 380, sgn * 0.002 * (np.arange(400) - 379), 0.0)  # the dollar gains at the end
        others[sym] = frame(idx, base * np.exp(noise + drift))
    t = np.array([pd.Timestamp("2026-05-04 06:40", tz="UTC").value])
    u = usd(others, t, scale_rows=300)
    assert u["usd15"][0] > 0 and u["usd60"][0] > 0
    others_flip = {s: frame(idx, 1.0 / f.close.to_numpy()) for s, f in others.items()}  # every pair upside down
    assert usd(others_flip, t, scale_rows=300)["usd15"][0] == pytest.approx(-u["usd15"][0], rel=1e-6)


def test_each_pair_counts_its_own_way():
    idx = pd.date_range("2026-05-04 00:00", periods=400, freq="1min", tz="UTC")
    rng = np.random.default_rng(5)
    others = {}
    for sym, sgn in USD_PAIRS.items():
        base = 1.2 if sgn < 0 else 140.0
        path = np.cumsum(rng.normal(0, 1e-4, 400))
        if sym == "EURUSD":  # only EURUSD moves at the end: it falls -> the dollar gains
            path = path + np.where(np.arange(400) >= 380, -0.003 * (np.arange(400) - 379), 0.0)
        else:
            path[380:] = path[379]
        others[sym] = frame(idx, base * np.exp(path))
    t = np.array([pd.Timestamp("2026-05-04 06:40", tz="UTC").value])
    assert usd(others, t, scale_rows=300)["usd15"][0] > 0
