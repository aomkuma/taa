"""Hand-worked tests for app/strategy/rhythm.py (TAA-1802)."""

from __future__ import annotations

import itertools

import numpy as np

from app.strategy import rhythm as rh
from app.strategy.plan1_b2 import Bars

NS_H = 3600 * 10**9


def bars(closes: list[float], half_range: float = 0.5) -> Bars:
    c = np.asarray(closes, dtype=float)
    t = np.arange(len(c), dtype=np.int64) * NS_H
    return Bars(t, t + NS_H, c, c + half_range, c - half_range, c)


def zig(levels: list[float], steps: int = 10) -> list[float]:
    """Straight legs through ``levels`` (each leg ``steps`` bars)."""
    out: list[float] = []
    for a, b in itertools.pairwise(levels):
        out += list(np.linspace(a, b, steps, endpoint=False))
    return [*out, levels[-1]]


def test_falling_highs_and_lows_with_a_falling_big_trend_is_down():
    # 100 -> 80 -> 95 -> 70 -> 85 -> 60 -> 72: lower highs (95, 85) and lower lows (80, 70, 60) on every swing
    x = bars(zig([100, 80, 95, 70, 85, 60, 72]))
    r = rh.rhythm(x, int(x.avail[-1]))
    assert r.big.sign == -1
    assert r.sign == -1
    highs = [p for _, k, p in r.swings if k == 1]
    lows = [p for _, k, p in r.swings if k == -1]
    assert highs[-2:] == [95.5, 85.5]  # the bars' highs (close + 0.5) at the turns
    assert lows[-2:] == [79.5, 69.5] or lows[-1] < lows[-2]


def test_rising_swings_mirror_to_up():
    x = bars(zig([60, 80, 65, 90, 75, 100, 88]))
    r = rh.rhythm(x, int(x.avail[-1]))
    assert r.sign == 1


def test_mixed_swings_have_no_rhythm():
    # higher highs but lower lows (a widening range)
    x = bars(zig([80, 90, 75, 95, 70, 100, 85]))
    assert rh.rhythm(x, int(x.avail[-1])).sign == 0


def test_the_running_leg_and_the_atr():
    x = bars(zig([100, 80, 95, 70, 85, 60, 72]))
    r = rh.rhythm(x, int(x.avail[-1]))
    assert r.leg in (-1, 1)
    # every bar spans close +- 0.5 with straight legs of 1.5-2.5 a bar: the ATR(14) is 1-4
    assert 1.0 <= r.atr <= 4.0


def test_classify_needs_both_highs_and_lows_and_the_big_trend():
    assert rh.classify([95.0, 85.0], [80.0, 70.0], -1) == -1
    assert rh.classify([95.0, 85.0], [70.0, 80.0], -1) == 0  # lower highs, higher lows: a triangle
    assert rh.classify([95.0, 85.0], [80.0, 70.0], 0) == 0  # the big trend not down
    assert rh.classify([95.0, 85.0], [80.0, 70.0], 1) == 0
    assert rh.classify([85.0, 95.0], [70.0, 80.0], 1) == 1
    assert rh.classify([85.0, 95.0], [70.0, 80.0], -1) == 0
    assert rh.classify([95.0], [80.0, 70.0], -1) == 0  # one high is not a sequence
    assert rh.classify([100.0, 95.0, 85.0], [90.0, 80.0, 70.0], -1) == -1  # only the last two count
    assert rh.classify([80.0, 95.0, 85.0], [60.0, 80.0, 70.0], -1) == -1  # up first, then down: the last two


def test_the_atr_is_the_last_bars():
    # 300 flat bars spanning 1.0, then 20 spanning 4.0: MT5's ATR(14) is the mean true range of the last 14 = 4.0
    c = np.full(320, 100.0)
    half = np.r_[np.full(300, 0.5), np.full(20, 2.0)]
    t = np.arange(320, dtype=np.int64) * NS_H
    x = Bars(t, t + NS_H, c, c + half, c - half, c)
    assert rh.rhythm(x, int(x.avail[-1])).atr == 4.0
