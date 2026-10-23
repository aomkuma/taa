"""The big picture's trend (app/strategy/big_trend.py) on price walks built by hand: bars step evenly between the
points (high = low = the price), so every turn can be followed on paper."""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np

from app.strategy import big_trend as bt
from app.strategy.plan1_b2 import Bars

NS_H = 3600 * 10**9
T0 = 1_790_000_000 * 10**9


def path(points: list[float], per_leg: int = 5) -> tuple[np.ndarray, np.ndarray]:
    prices: list[float] = []
    for a, b in pairwise(points):
        prices += list(np.linspace(a, b, per_leg, endpoint=False))
    prices.append(points[-1])
    p = np.array(prices)
    return p.copy(), p.copy()


def bars(h: np.ndarray, lo: np.ndarray) -> Bars:
    t_open = T0 + np.arange(len(h), dtype=np.int64) * NS_H
    c = (h + lo) / 2
    return Bars(t_open, t_open + NS_H, c, h, lo, c)


class TestZigzag:
    def test_swings_need_the_size_to_turn(self) -> None:
        # size 15: the first low 100 confirmed on the way up (115), 130 confirmed at 115 on the way down, 110 at
        # 125, 140 at 125 (the last bar, exactly 15 back); the leg down from 140 is running at 125
        h, lo = path([100.0, 130.0, 110.0, 140.0, 125.0])
        pts, leg, ext = bt.zigzag(h, lo, 15.0)
        assert [(k, p) for _, k, p in pts] == [(-1, 100.0), (1, 130.0), (-1, 110.0), (1, 140.0)]
        assert (leg, ext) == (-1, 125.0)

    def test_a_small_pullback_is_not_a_swing(self) -> None:
        # 100 -> 130 -> 120 (10 back < 15) -> 150: the low 100 confirmed on the way up, then one up leg to 150
        h, lo = path([100.0, 130.0, 120.0, 150.0])
        pts, leg, ext = bt.zigzag(h, lo, 15.0)
        assert [(k, p) for _, k, p in pts] == [(-1, 100.0)]
        assert (leg, ext) == (1, 150.0)

    def test_a_dip_smaller_than_the_size_is_no_swing(self) -> None:
        # 100 -> 90 (10 < 15) -> 120: the start is no swing; the low 90 is confirmed by the rise
        h, lo = path([100.0, 90.0, 120.0])
        pts, leg, ext = bt.zigzag(h, lo, 15.0)
        assert [(k, p) for _, k, p in pts] == [(-1, 90.0)]
        assert (leg, ext) == (1, 120.0)

    def test_no_size_no_swings(self) -> None:
        h, lo = path([100.0, 130.0, 110.0])
        pts, leg, ext = bt.zigzag(h, lo, math.nan)
        assert (pts, leg) == ([], 0)
        assert math.isnan(ext)


class TestTrend:
    def test_lower_highs_and_lower_lows(self) -> None:
        # size 18, every leg 20 or 30: highs 200, 190, 180; lows 170, 160, 150; the last leg up to 170 runs
        h, lo = path([200.0, 170.0, 190.0, 160.0, 180.0, 150.0, 170.0])
        r = bt.trend_from(h, lo, 18.0)
        assert (r.highs, r.lows) == ((200.0, 190.0, 180.0), (170.0, 160.0, 150.0))
        assert (r.sign, r.lower_highs, r.lower_lows) == (-1, 2, 2)

    def test_the_running_leg_makes_the_lower_low(self) -> None:
        # size 12: highs 200, 190, 180, lows 160, 165 (a higher low); the running leg from 180 reaches 140 < 165
        h, lo = path([200.0, 160.0, 190.0, 165.0, 180.0, 140.0])
        r = bt.trend_from(h, lo, 12.0)
        assert (r.highs, r.lows) == ((200.0, 190.0, 180.0), (160.0, 165.0, 140.0))
        assert (r.sign, r.lower_highs, r.lower_lows) == (-1, 2, 1)

    def test_a_running_leg_short_of_the_last_swing_is_not_counted(self) -> None:
        # the last leg 180 -> 170 (10 < 12) never turns: the up leg from 165 runs at 180, under the high 190
        h, lo = path([200.0, 160.0, 190.0, 165.0, 180.0, 170.0])
        r = bt.trend_from(h, lo, 12.0)
        assert (r.highs, r.lows) == ((200.0, 190.0), (160.0, 165.0))
        assert r.sign == 0  # a lower high with a higher low: a squeeze, no trend

    def test_an_uptrend(self) -> None:
        h, lo = path([100.0, 130.0, 110.0, 140.0, 120.0, 150.0, 135.0])
        r = bt.trend_from(h, lo, 12.0)
        assert (r.highs, r.lows) == ((130.0, 140.0, 150.0), (100.0, 110.0, 120.0))
        assert (r.sign, r.higher_highs, r.higher_lows) == (1, 2, 2)


class TestBigTrend:
    def test_the_size_is_the_atr_times_three(self) -> None:
        # legs of 10 over 5 bars: every true range 2, the ATR 2 -> the size 6; equal highs and lows -> no trend
        h, lo = path([100.0, 110.0] * 5)
        b = bars(h, lo)
        r = bt.big_trend(b, int(b.avail[-1]))
        assert r.size == 6.0
        assert r.sign == 0

    def test_the_atr_is_fourteen_bars(self) -> None:
        # 15 bars stepping 4, then 14 bars stepping 2: the ATR(14) is 2 (an ATR(20) would be 2.6) -> the size 6
        h1, _ = path([100.0, 120.0, 100.0, 120.0])
        h2, _ = path([120.0, 106.0, 120.0], per_leg=7)
        h = np.concatenate([h1, h2[1:]])
        b = bars(h, h.copy())
        assert bt.big_trend(b, int(b.avail[-1])).size == 6.0

    def test_the_forming_bar_is_not_read(self) -> None:
        # the walk of the running-leg test with size_atr 3 on its own ATR; read when bar 20 (the high 180) has
        # just closed: the leg down to 140 has not happened yet
        h, lo = path([200.0, 160.0, 190.0, 165.0, 180.0, 140.0])
        b = bars(h, lo)
        assert 140.0 not in bt.big_trend(b, int(b.avail[20])).lows
        assert bt.big_trend(b, int(b.avail[20]) - 1).lows == bt.big_trend(b, int(b.avail[19])).lows
