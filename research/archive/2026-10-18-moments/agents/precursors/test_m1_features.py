"""m1_features by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_m1_features.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m1_features import breaks, in_a_row, same_minutes, speed  # noqa: E402


def test_speed():
    c = np.array([100.0, 101, 103, 106])
    s = speed(c, 2)
    assert np.isnan(s[1]) and s[2:].tolist() == [3.0, 5.0]


def test_in_a_row():
    c = np.array([100.0, 101, 102, 103, 102, 101, 101, 102])
    # up, up, up (+3), down, down (-2), flat (0), up (+1)
    assert in_a_row(c).tolist() == [0, 1, 2, 3, -1, -2, 0, 1]


def test_breaks_use_the_bars_before_only():
    h = np.array([10.0, 11, 12, 11.5, 13])
    lo = np.array([9.0, 10, 11, 10.5, 9.5])
    c = np.array([9.5, 10.5, 11.5, 11.0, 12.5])
    # bar 4 closes 12.5: above the highest high of bars 1-3 (12) -> +1; its own high 13 is not used
    assert breaks(h, lo, c, 3).tolist()[3:] == [0, 1]
    c2 = c.copy()
    c2[4] = 9.9  # below the lowest low of bars 1-3 (10)
    assert breaks(h, lo, c2, 3).tolist()[4] == -1


def test_same_minutes_against_earlier_days():
    idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=k) for d in pd.date_range("2026-05-01 08:00", periods=21, freq="D", tz="UTC") for k in range(2)])
    v = pd.Series(np.where(idx.day == 21, 30.0, np.where(idx.day % 2 == 1, 10.0, 20.0)), index=idx)
    r = same_minutes(v)
    # day 21 (30) against days 1-20 (ten 10s, ten 20s: median 15) -> 2.0; with day 21 itself in the window the median
    # would be 20 -> 1.5. Day 20 (20) against days 1-19 (ten 10s, nine 20s: median 10) -> 2.0
    assert r[-1] == 2.0 and r[-3] == 2.0


def test_nothing_after_the_moment_changes_a_reading():
    from m1_features import features  # noqa: PLC0415

    rng = np.random.default_rng(5)
    n = 6 * 1440
    idx = pd.date_range("2026-05-04 00:00", periods=n, freq="1min", tz="UTC")
    c = 4000 + np.cumsum(rng.normal(0, 0.6, n))
    o = np.r_[c[0], c[:-1]]
    m = pd.DataFrame({"open": o, "high": np.maximum(o, c) + rng.random(n) * 0.5, "low": np.minimum(o, c) - rng.random(n) * 0.5,
                      "close": c, "tick_volume": rng.integers(50, 300, n).astype(float), "spread": 25.0}, index=idx)
    X = features(m)
    for k in (4 * 1440 + 17, 5 * 1440 + 333, 5 * 1440 + 334):
        # every bar after bar k replaced by other prices and volumes (the same times): bar k's readings must not move
        m2 = m.copy()
        junk = 3000 + np.cumsum(rng.normal(0, 3.0, n - k - 1))
        m2.iloc[k + 1:, m2.columns.get_loc("open")] = junk
        m2.iloc[k + 1:, m2.columns.get_loc("close")] = junk + 1
        m2.iloc[k + 1:, m2.columns.get_loc("high")] = junk + 5
        m2.iloc[k + 1:, m2.columns.get_loc("low")] = junk - 5
        m2.iloc[k + 1:, m2.columns.get_loc("tick_volume")] = 9999.0
        Y = features(m2)
        a, b = X.iloc[k], Y.iloc[k]
        for col in X.columns:
            assert (np.isnan(a[col]) and np.isnan(b[col])) or np.isclose(a[col], b[col], rtol=1e-9, atol=1e-9), (k, col, a[col], b[col])
