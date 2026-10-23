"""Strong levels and liquidity pools (app/strategy/strong_levels.py) on bars built by hand, answers worked on
paper."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.strategy import strong_levels as sl
from app.strategy.plan1_b2 import Bars

NS_H = 3600 * 10**9
T0 = 1_790_000_000 * 10**9


def bars(h: list[float], lo: list[float], hours: int = 4) -> Bars:
    n = len(h)
    t_open = T0 + np.arange(n, dtype=np.int64) * hours * NS_H
    hi, low = np.array(h, float), np.array(lo, float)
    mid = (hi + low) / 2
    return Bars(t_open, t_open + hours * NS_H, mid, hi, low, mid)


# a peak at bar 3 (110) between highs 101-104, then a fall; a trough at bar 7 (90)
H = [101.0, 102.0, 103.0, 110.0, 104.0, 100.0, 96.0, 95.0, 97.0, 99.0, 100.0]
L = [99.0, 100.0, 101.0, 104.0, 98.0, 94.0, 92.0, 90.0, 93.0, 95.0, 96.0]


class TestSwings:
    def test_a_peak_is_known_only_after_k_bars_close(self) -> None:
        b = bars(H, L)
        before = int(b.avail[4])  # bar 5 (the 2nd bar after the peak) not closed yet
        assert all(s.bar != 3 for s in sl.swings(b, before))
        after = int(b.avail[5])
        peak = [s for s in sl.swings(b, after) if s.bar == 3]
        assert len(peak) == 1
        assert peak[0].kind == 1
        assert peak[0].price == 110.0
        # the turn counts only the closed bars after it: lows 98, 94 -> 110 - 94 = 16
        assert peak[0].turn == pytest.approx(16.0)

    def test_the_turn_grows_as_bars_close(self) -> None:
        b = bars(H, L)
        peak = next(s for s in sl.swings(b, int(b.avail[-1])) if s.bar == 3)
        assert peak.turn == pytest.approx(110.0 - 90.0)

    def test_a_trough(self) -> None:
        b = bars(H, L)
        trough = [s for s in sl.swings(b, int(b.avail[-1])) if s.kind == -1]
        assert [(s.bar, s.price) for s in trough] == [(7, 90.0)]
        # the highs after it: 97, 99, 100 -> 100 - 90
        assert trough[0].turn == pytest.approx(10.0)

    def test_a_tie_is_no_swing(self) -> None:
        h = [101.0, 102.0, 110.0, 110.0, 104.0, 100.0, 99.0]
        lo = [99.0, 100.0, 104.0, 104.0, 98.0, 94.0, 93.0]
        b = bars(h, lo)
        assert not [s for s in sl.swings(b, int(b.avail[-1])) if s.kind == 1]

    def test_the_turn_starts_after_the_swing_bar(self) -> None:
        # the peak bar's own long lower wick (to 90) is not part of the turn: the lows after it are 100, 101
        h = [101.0, 102.0, 110.0, 104.0, 103.0]
        lo = [99.0, 100.0, 90.0, 100.0, 101.0]
        b = bars(h, lo)
        peak = next(s for s in sl.swings(b, int(b.avail[-1])) if s.kind == 1)
        assert peak.turn == pytest.approx(10.0)

    def test_last_limits_the_search(self) -> None:
        b = bars(H, L)
        assert [s.bar for s in sl.swings(b, int(b.avail[-1]), last=5)] == [7]


class TestMerge:
    def test_running_mean(self) -> None:
        s = [sl.Swing(0, p, 1, 1.0) for p in (100.0, 100.5, 101.4, 110.0)]
        # 100 and 100.5 merge (mean 100.25); 101.4 is 1.15 away > 1.0 -> its own level
        got = sl.merge(s, 1.0)
        assert [(lv.price, lv.touches) for lv in got] == [(100.25, 2), (101.4, 1), (110.0, 1)]

    def test_kinds(self) -> None:
        s = [sl.Swing(0, 100.0, 1, 1.0), sl.Swing(1, 100.2, -1, 3.0), sl.Swing(2, 120.0, -1, 2.0)]
        got = sl.merge(s, 1.0)
        assert [(lv.kinds, lv.turn) for lv in got] == [(0, 3.0), (-1, 2.0)]


class TestStrong:
    def test_two_touches_or_a_major_turn(self) -> None:
        # step 10: merge within 1.5; strong = 2+ touches or a turn >= 10
        b = bars(H, L)
        d1 = bars([200.0] * 3, [199.0] * 3, hours=24)  # no D1 swings
        got = sl.strong_levels(b, d1, int(b.avail[-1]), 10.0, shift_anchors=[150.0])
        swings_ = [lv for lv in got if lv.source == "swings"]
        # the peak 110 turned 20 (strong); the trough 90 turned 10 (strong, exactly the threshold)
        assert [lv.price for lv in swings_] == [90.0, 110.0]
        assert [lv.price for lv in got if lv.source == "shift"] == [150.0]
        assert sorted(lv.price for lv in got if lv.source == "extreme") == [90.0, 110.0]

    def test_a_weak_single_touch_is_dropped(self) -> None:
        b = bars(H, L)
        d1 = bars([200.0] * 3, [199.0] * 3, hours=24)
        got = sl.strong_levels(b, d1, int(b.avail[-1]), 25.0)  # turns 20 and 10 < 25
        assert not [lv for lv in got if lv.source == "swings"]

    def test_no_step_no_levels(self) -> None:
        b = bars(H, L)
        assert sl.strong_levels(b, b, int(b.avail[-1]), math.nan) == []


class TestRoom:
    levels = [
        sl.Level(80.0, 2, 5.0, -1, "swings"),
        sl.Level(99.0, 2, 5.0, -1, "swings"),
        sl.Level(120.0, 2, 5.0, 1, "swings"),
        sl.Level(140.0, 2, 5.0, 1, "swings"),
    ]

    def test_a_sell_aims_before_the_band(self) -> None:
        # sell 105, stop 108 (R 3); the nearest level below is 99 (not 80), band 1 -> its near edge 100 -> 5 / 3
        assert sl.room(self.levels, -1, 105.0, 108.0, 1.0) == pytest.approx(5.0 / 3.0)

    def test_a_buy(self) -> None:
        # buy 105, stop 103 (R 2); the nearest above is 120 (not 140): 120 - 1 = 119 -> 14 / 2
        assert sl.room(self.levels, 1, 105.0, 103.0, 1.0) == pytest.approx(7.0)

    def test_nothing_ahead(self) -> None:
        assert sl.room(self.levels, 1, 145.0, 143.0, 1.0) == math.inf


class TestStop:
    def test_the_owners_chart(self) -> None:
        # 2026-10-21/22: sell the re-test of 4,141 at 4,135; the swept wick 4,155.5 and the line 4,142.2 are pools;
        # step 74 -> band 3.7. A stop at 4,160 sits 4.5 beyond the wick: outside the zone; 4,160 is also a round
        # number, but the stop on it is the band's question below.
        band = sl.pool_band(74.0)
        assert band == pytest.approx(3.7)
        in_zone, margin = sl.stop_check([4155.5, 4142.2], -1, 4135.0, 4163.9, band)
        assert not in_zone
        assert margin == pytest.approx(3.9)  # beyond the round 4,160, the nearest pool to the stop

    def test_a_stop_just_past_the_line_is_in_the_zone(self) -> None:
        band = sl.pool_band(74.0)
        in_zone, margin = sl.stop_check([4155.5, 4142.2], -1, 4135.0, 4144.0, band)
        assert in_zone
        assert margin == pytest.approx(1.8)

    def test_a_stop_just_short_of_a_pool_is_in_the_zone(self) -> None:
        in_zone, _ = sl.stop_check([107.0], 1, 120.0, 108.0, 1.5)  # buy, stop 1 above the pool 107
        assert in_zone

    def test_a_buy_stop_beyond_the_pools(self) -> None:
        # buy 125, stop 101.5; pools 106 and the round 110, 120 between them: nearest to the stop 106 -> 4.5
        in_zone, margin = sl.stop_check([106.0], 1, 125.0, 101.5, 1.0)
        assert not in_zone
        assert margin == pytest.approx(4.5)

    def test_the_band_floor(self) -> None:
        assert sl.pool_band(10.0) == 1.0
        assert sl.pool_band(math.nan) == 1.0
