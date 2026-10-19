"""zones by hand: the swings and when they are known, the merge with kinds, the zones at a moment, the first touch.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_zones.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundation as F  # noqa: E402
from zones import first_touch, levels_at, merge, swings, zones_at  # noqa: E402

H = 3600 * 10**9


def hbars(highs, lows):
    n = len(highs)
    t0 = pd.Timestamp("2026-01-05 00:00", tz="UTC")
    return pd.DataFrame(dict(open=lows, high=highs, low=lows, close=highs,
                             avail=[t0 + pd.Timedelta(hours=i + 1) for i in range(n)]))


def test_a_swing_is_known_two_bars_later():
    # highs 1 2 5 2 1 3 1: a top at bar 2 (5), known at bar 4's avail (05:00); bar 5 (3) is a top of its window but
    # bar 6 is the last bar - only one bar after it: not known yet
    b = hbars([1, 2, 5, 2, 1, 3, 1], [0.5, 1.5, 4, 1.5, 0.2, 2, 0.5])
    S = swings(b)
    tops = S[S.kind == 1]
    assert tops.i.tolist() == [2]
    assert tops.known.iloc[0] == pd.Timestamp("2026-01-05 05:00", tz="UTC").value
    lows = S[S.kind == -1]
    assert lows.i.tolist() == [4]  # 0.2, known at bar 6


def test_merge_keeps_the_kinds_and_matches_merge_levels():
    p = np.array([100.0, 100.4, 101.2, 105.0, 100.2])
    k = np.array([1, -1, 1, -1, 1])
    Z = merge(p, k, 1.0)
    # sorted 100.0 100.2 100.4 | 101.2 | 105.0 (101.2 - 100.0 > 1.0: a new zone; no chaining)
    assert Z.touches.tolist() == [3, 1, 1] and Z.tops.tolist() == [2, 1, 0] and Z.lows.tolist() == [1, 0, 1]
    assert Z.price.iloc[0] == pytest.approx(100.2)
    rng = np.random.default_rng(3)
    q = rng.uniform(4000, 4100, 60)
    lv, cnt = F.merge_levels(q, 2.5)
    Z = merge(q, rng.choice([-1, 1], 60), 2.5)
    assert np.allclose(Z.price, lv) and Z.touches.tolist() == cnt.tolist()


def test_zones_at_uses_only_the_known_swings_of_the_window():
    S = pd.DataFrame(dict(i=[1, 5, 8, 9], price=[100.0, 110.0, 120.0, 130.0], kind=[1, -1, 1, -1],
                          known=[3 * H, 7 * H, 10 * H, 11 * H]))
    avail = np.arange(1, 13) * H  # bar i complete at (i + 1) h
    atr = np.full(12, 4.0)
    Z, a = zones_at(S, avail, atr, 10 * H, win=6)
    # at 10 h: bar 9 is the last complete; the window is bars 4..9: bar 1's swing is out, bar 8's (known at 10 h) in,
    # bar 9's (known at 11 h) not yet
    assert Z.price.tolist() == [110.0, 120.0] and a == 4.0
    Z, _ = zones_at(S, avail, atr, 10 * H - 1, win=6)
    assert Z.price.tolist() == [110.0]  # a nanosecond before: bar 8's swing is not known


def test_the_first_touch_and_nothing_before_it():
    t = pd.date_range("2026-01-05 14:30", periods=6, freq="1min", tz="UTC")
    m = pd.DataFrame(dict(open=100.0, high=[101, 102, 103, 104.95, 106, 100], low=[99, 100, 101, 103, 104, 99], close=100.0), index=t)
    S = pd.DataFrame(dict(i=[0], price=[105.0], kind=[1], known=[t[0].value - H]))
    avail = np.array([t[0].value - H])
    atr = np.array([1.0])
    fn = lambda t_, p: zones_at(S, avail, atr, t_)  # noqa: E731
    j, Z, a = first_touch(m, 0, 6, fn)
    assert j == 3  # 104.95 is within 0.1 (0.1 x ATR 1.0) of 105; bar 2's 103 is not
    assert first_touch(m, 0, 3, fn) is None


def test_the_zones_do_not_change_when_the_future_is_replaced():
    rng = np.random.default_rng(7)
    n = 200
    c = 4000 + np.cumsum(rng.normal(0, 3, n))
    b = hbars(c + rng.uniform(0.5, 3, n), c - rng.uniform(0.5, 3, n))
    t = int(pd.Timestamp(b["avail"].iloc[150]).value)
    atr = F.atr(b.high.to_numpy(), b.low.to_numpy(), b.high.to_numpy(), 14)
    av = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
    Z1, _ = zones_at(swings(b), av, atr, t)
    b2 = b.copy()
    b2.loc[151:, ["high", "low"]] = b2.loc[151:, ["high", "low"]].to_numpy()[::-1] + 50  # every later bar replaced
    atr2 = F.atr(b2.high.to_numpy(), b2.low.to_numpy(), b2.high.to_numpy(), 14)
    Z2, _ = zones_at(swings(b2), av, atr2, t)
    assert Z1.equals(Z2) and len(Z1) > 3


def test_the_owners_four_kinds_of_levels():
    S = pd.DataFrame(dict(i=[1, 2, 3, 4, 5, 6, 7, 8], price=[100.0, 120.0, 90.0, 120.5, 90.4, 89.8, 110.0, 95.0],
                          kind=[1, 1, -1, 1, 1, -1, 1, -1], known=np.array([3, 4, 5, 6, 7, 8, 9, 10]) * H))
    Y = dict(S=S, avail=np.arange(1, 13) * H, atr=np.full(12, 4.0),
             h=np.array([100, 101, 125, 99, 121, 98, 97, 111, 100, 106, 130, 130.0]),
             lo=np.array([95, 96, 99, 85, 97, 89, 88, 100, 94, 100, 70, 70.0]),
             d_avail=np.array([5, 11]) * H, d_high=np.array([120.6, 150.0]), d_low=np.array([80.0, 60.0]))
    L, a = levels_at(Y, 10 * H, 105.0)
    # at 10 h (bars 0..9 complete; the D1 complete at 5 h is the previous day): the zone 89.8 / 90 / 90.4 (3 swings, tops
    # and lows) and 120 / 120.5 (2 tops) kept; 100 (1 swing, not the latest top) dropped; the five-day 125 / 85; PDH
    # 120.6 is within 1.0 (0.25 x ATR 4) of the 2-swing zone: dropped; PDL 80; the latest top above 105 is 110 (bar 7),
    # the latest low below it 95 (bar 8); bars 10-11 (130 / 70) and the next day (150 / 60) are not known yet
    assert L.kind.tolist() == ["x3+ / flip", "x2", "5d high", "5d low", "PDL", "last top", "last low"]
    assert L.price.tolist() == pytest.approx([90.0667, 120.25, 125.0, 85.0, 80.0, 110.0, 95.0], abs=1e-3)
    assert a == 4.0


def test_a_two_swing_flip_is_strong_and_the_latest_low_inside_it_is_not_repeated():
    S = pd.DataFrame(dict(i=[1, 2], price=[100.0, 100.5], kind=[1, -1], known=np.array([3, 4]) * H))
    Y = dict(S=S, avail=np.arange(1, 13) * H, atr=np.full(12, 4.0), h=np.full(12, 140.0), lo=np.full(12, 60.0),
             d_avail=np.array([5]) * H, d_high=np.array([150.0]), d_low=np.array([50.0]))
    L, _ = levels_at(Y, 10 * H, 105.0)
    # a top and a low within 1.0: a flipped level (strong though only 2 swings); the latest low below 105 is 100.5,
    # inside it: not repeated; no top above 105
    assert L.kind.tolist() == ["x3+ / flip", "5d high", "5d low", "PDH", "PDL"]
    assert L.price.iloc[0] == pytest.approx(100.25)


def test_the_levels_are_read_with_the_bars_open_not_its_close():
    t = pd.date_range("2026-01-05 14:30", periods=3, freq="1min", tz="UTC")
    m = pd.DataFrame(dict(open=[100.0, 101.0, 102.0], high=[100.5, 101.5, 102.5], low=[99.5, 100.5, 101.5],
                          close=[100.9, 101.9, 102.9]), index=t)
    seen = []

    def fn(t_ns, price):
        seen.append(price)
        return pd.DataFrame(columns=["price"]), 1.0

    assert first_touch(m, 0, 3, fn) is None and seen == [100.0, 101.0, 102.0]  # the close is not known at the open
