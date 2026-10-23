"""Momentum at a level (app/strategy/level_momentum.py) on bars built by hand, answers worked on paper.
The level 100, band 1, a support (bounces up)."""

from __future__ import annotations

import math

import numpy as np

from app.strategy import level_momentum as lm
from app.strategy.plan1_b2 import Bars

NS_H = 3600 * 10**9
T0 = 1_790_000_000 * 10**9


def bars(h: list[float], lo: list[float], c: list[float] | None = None) -> Bars:
    n = len(h)
    t_open = T0 + np.arange(n, dtype=np.int64) * NS_H
    hi, low = np.array(h, float), np.array(lo, float)
    close = np.array(c, float) if c is not None else (hi + low) / 2
    return Bars(t_open, t_open + NS_H, close, hi, low, close)


# three visits to 100 (bars 1, 6, 11) with bounces 8, 5, 3; four bars out between them
H = [105, 102, 104, 108, 103, 104, 101, 105, 103, 104, 104, 101, 103, 102, 103]
L = [103, 99.5, 102, 104, 102, 103, 99.8, 102, 102, 103, 102, 100.5, 101.5, 101.6, 101.7]


def read(b: Bars, t: int | None = None, side: int = 1) -> lm.LevelMomentum:
    return lm.level_momentum(b, int(b.avail[-1]) if t is None else t, 100.0, 1.0, side, T0)


class TestVisits:
    def test_three_visits_and_their_bounces(self) -> None:
        m = read(bars([float(x) for x in H], [float(x) for x in L]))
        assert m.touches == 3
        # bar 1: the highs of bars 1-7 reach 108 -> 8; bar 6: bars 6-12 reach 105 -> 5; bar 11: bars 11-14 -> 103
        assert m.bounces == (8.0, 5.0, 3.0)
        assert m.worn

    def test_bars_close_together_are_one_visit(self) -> None:
        # in the band at bars 1, 2 and 4 (gaps of 1 and 2, not more than 3) -> one visit
        h = [105.0, 101.0, 100.5, 104.0, 100.8, 104.0, 105.0, 106.0]
        lo = [103.0, 99.5, 99.0, 102.0, 99.9, 102.0, 103.0, 104.0]
        m = read(bars(h, lo))
        assert m.touches == 1

    def test_a_gap_of_exactly_three_is_the_same_visit(self) -> None:
        # in the band at bars 1 and 4: 4 - 1 = 3, not more than 3 -> one visit
        h = [105.0, 101.0, 104.0, 104.0, 101.0, 104.0]
        lo = [103.0, 99.5, 102.0, 102.0, 99.5, 102.0]
        assert read(bars(h, lo)).touches == 1

    def test_the_bounce_window_is_seven_bars(self) -> None:
        # a visit at bar 1; the highs of bars 1-7 peak at bar 7 (110), bar 8 reaches 120 but is outside
        h = [105.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 110.0, 120.0]
        lo = [103.0, 99.5, 101.5, 102.0, 103.0, 104.0, 105.0, 106.0, 110.0]
        assert read(bars(h, lo)).bounces == (10.0,)

    def test_a_gap_of_four_bars_is_a_new_visit(self) -> None:
        h = [105.0, 101.0, 104.0, 104.0, 104.0, 101.0, 104.0]
        lo = [103.0, 99.5, 102.0, 102.0, 102.0, 99.5, 102.0]
        assert read(bars(h, lo)).touches == 2

    def test_a_resistance_reads_the_lows(self) -> None:
        # the mirror: prices 200 - x, level 100 stays; the bounces down are the same 8, 5, 3
        h = [200.0 - x for x in L]
        lo = [200.0 - x for x in H]
        m = read(bars(h, lo), side=-1)
        assert m.bounces == (8.0, 5.0, 3.0)

    def test_two_shrinking_of_three_is_not_worn(self) -> None:
        # bounces 3, 8, 5 (visit windows: bars 1-7 top 103, bars 6-12 top 108 at bar 9, bars 11-14 top 105):
        # the last two shrink, the first does not lead
        h = [105, 102, 103, 102, 103, 103, 101, 103, 103, 108, 104, 101, 105, 102, 103]
        lo = [103, 99.5, 102, 101.5, 102, 103, 99.8, 102, 102, 103, 102, 100.5, 101.5, 101.6, 101.7]
        m = read(bars([float(x) for x in h], [float(x) for x in lo]))
        assert m.bounces == (3.0, 8.0, 5.0)
        assert not m.worn

    def test_growing_bounces_are_not_worn(self) -> None:
        h = [105, 102, 104, 103, 103, 104, 101, 105, 103, 104, 104, 101, 108, 102, 103]
        assert not read(bars([float(x) for x in h], [float(x) for x in L])).worn

    def test_the_forming_bar_is_not_read(self) -> None:
        b = bars([float(x) for x in H], [float(x) for x in L])
        assert read(b, int(b.avail[10])).touches == 2
        assert read(b, int(b.avail[11]) - 1).touches == 2

    def test_bars_before_since_are_not_read(self) -> None:
        b = bars([float(x) for x in H], [float(x) for x in L])
        m = lm.level_momentum(b, int(b.avail[-1]), 100.0, 1.0, 1, T0 + 2 * NS_H)
        assert m.touches == 2


class TestAtTheLine:
    def test_bars_at_the_line(self) -> None:
        h = [105.0, 104.0, 101.0, 100.5, 101.0]
        lo = [103.0, 102.0, 99.5, 99.0, 99.8]
        assert read(bars(h, lo)).bars_at_line == 3

    def test_away_from_the_line(self) -> None:
        assert read(bars([float(x) for x in H], [float(x) for x in L])).bars_at_line == 0


class TestApproach:
    def test_toward_the_level_in_atr(self) -> None:
        # 15 closes falling 130 -> 102 by 2 a bar, high / low = close +- 1: every true range after the first is
        # max(high, previous close) - min(low, previous close) = (c + 2) - (c - 1) = 3,
        # so the ATR(14) of bar 14 is 3; ten bars back the close was 122 (22 from the level), now 102 (2 away)
        c = [130.0 - 2 * i for i in range(15)]
        b = bars([x + 1 for x in c], [x - 1 for x in c], c)
        assert read(b).approach == 20.0 / 3.0

    def test_too_few_bars(self) -> None:
        b = bars([101.0] * 5, [99.0] * 5)
        assert math.isnan(read(b).approach)
