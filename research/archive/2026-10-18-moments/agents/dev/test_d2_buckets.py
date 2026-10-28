"""d2_buckets by hand: the New York minutes (summer / winter time), the mid at a time, the gap rule, the moves per
bucket in R and in USD.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_d2_buckets.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d2_buckets as B  # noqa: E402

S = 10**9
MN = 60 * S
T0 = 1_768_000_000 * S


def test_the_new_york_minutes():
    x = B.ny_minutes(pd.Timestamp("2026-03-06", tz="UTC"), pd.Timestamp("2026-03-10", tz="UTC"))
    got = [(pd.Timestamp(t, tz="UTC").strftime("%m-%d %H:%M"), ny) for t, ny in x]
    assert got == [("03-06 13:30", "08:30"), ("03-06 14:30", "09:30"), ("03-06 15:00", "10:00"),
                   ("03-09 12:30", "08:30"), ("03-09 13:30", "09:30"), ("03-09 14:00", "10:00")]  # EST, then EDT
    with pytest.raises(B.ExamPeriodError):
        B.ny_minutes(pd.Timestamp("2026-04-01", tz="UTC"), pd.Timestamp("2026-04-19", tz="UTC"))


def test_the_mid_and_the_gap():
    t = np.array([T0, T0 + MN, T0 + 40 * MN], np.int64)
    bid, ask = np.array([100.0, 102.0, 90.0]), np.array([100.2, 102.2, 90.2])
    assert B.mid_at(t, bid, ask, T0 + MN) == pytest.approx(102.1)  # a tick exactly at the time counts
    assert B.mid_at(t, bid, ask, T0 + 39 * MN) == pytest.approx(102.1)
    assert np.isnan(B.mid_at(t, bid, ask, T0 - 1))
    assert B.crosses_gap(t, T0, T0 + 30 * MN)  # 39 minutes without a tick inside
    assert not B.crosses_gap(t, T0, T0 + MN)
    assert B.crosses_gap(t, T0, T0 + 41 * MN)  # past the data's end
    t3 = np.array([T0, T0 + MN, T0 + 2 * MN], np.int64)
    assert B.crosses_gap(t3, T0, T0 + 3 * MN) and not B.crosses_gap(t3, T0, T0 + 2 * MN)  # no tick at / after the end


def test_the_moves_per_bucket():
    # a buy filled at T0 + 10 s (mid 4002.6), risk 8; mids at T0 + 30 min 4010.6, + 60 min 4006.6, then ticks every 10
    # minutes at 4006.6 until + 240 min: bucket 1 +8 USD = +1 R, bucket 2 -4 USD = -0.5 R (size 4), buckets 3 - 8: 0
    times = [T0 + 10 * S] + [T0 + k * 10 * MN for k in range(1, 25)]
    mids = [4002.6] + [4010.6 if k <= 3 else 4006.6 for k in range(1, 25)]
    t = np.array(times, np.int64)
    bid = np.array(mids) - 0.2
    ask = np.array(mids) + 0.2
    x = dict(side=1, entry_t=T0 + 10 * S, risk=8.0)
    mv = B.bucket_moves(t, bid, ask, T0, x)
    assert mv[0] == pytest.approx((1.0, 8.0)) and mv[1] == pytest.approx((-0.5, 4.0))
    assert all(m == pytest.approx((0.0, 0.0)) for m in mv[2:])
    xs = dict(side=-1, entry_t=T0 + 10 * S, risk=8.0)  # a sell: the same moves the other way
    assert B.bucket_moves(t, bid, ask, T0, xs)[0] == pytest.approx((-1.0, 8.0))
    t2 = t.copy()
    t2[-1] = T0 + 300 * MN  # the last tick moved past a 60-minute hole: the last bucket crosses it
    mv2 = B.bucket_moves(t2, bid, ask, T0, x)
    assert np.isnan(mv2[7][0]) and mv2[6] == pytest.approx((0.0, 0.0))
