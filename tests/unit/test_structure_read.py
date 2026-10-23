"""Structure, clarity, phase and trend (app/strategy/structure_read.py) on bars built by hand, answers worked on
paper."""

from __future__ import annotations

import numpy as np

from app.strategy import structure_read as sr
from app.strategy.plan1_b2 import Bars

NS_H = 3600 * 10**9
T0 = 1_790_000_000 * 10**9


def bars(h: list[float], lo: list[float], c: list[float] | None = None) -> Bars:
    n = len(h)
    t_open = T0 + np.arange(n, dtype=np.int64) * NS_H
    hi, low = np.array(h, float), np.array(lo, float)
    close = np.array(c, float) if c is not None else (hi + low) / 2
    return Bars(t_open, t_open + NS_H, close, hi, low, close)


# highs (k = 1) at bars 1, 3, 5: 12, 13, 14 (the one at 5 needs bar 6); lows at bars 2, 4: 9.5, 10
UP_H = [10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 13.0]
UP_L = [9.0, 11.0, 9.5, 12.0, 10.0, 13.0, 12.0]


class TestStructure:
    def test_higher_highs_and_higher_lows(self) -> None:
        b = bars(UP_H, UP_L)
        s = sr.structure(b, int(b.avail[-1]))
        assert s.sign == 1
        assert s.highs == (13.0, 14.0)
        assert s.lows == (9.5, 10.0)

    def test_the_forming_bar_is_not_read(self) -> None:
        # with bar 6 not closed, the high at bar 5 has no right-hand bar yet
        b = bars(UP_H, UP_L)
        assert sr.structure(b, int(b.avail[5])).highs == (12.0, 13.0)
        assert sr.structure(b, int(b.avail[6]) - 1).highs == (12.0, 13.0)

    def test_the_mirror_is_lower_highs_lower_lows(self) -> None:
        b = bars([-x for x in UP_L], [-x for x in UP_H])
        assert sr.structure(b, int(b.avail[-1])).sign == -1

    def test_mixed(self) -> None:
        lo = [9.0, 11.0, 9.5, 12.0, 9.0, 13.0, 12.0]  # the second low 9.0 < 9.5: higher highs, a lower low
        b = bars(UP_H, lo)
        assert sr.structure(b, int(b.avail[-1])).sign == 0

    def test_too_few_swings(self) -> None:
        b = bars([10.0, 12.0, 11.0], [9.0, 10.0, 9.5])
        s = sr.structure(b, int(b.avail[-1]))
        assert (s.sign, s.clear) == (0, False)

    def test_equal_highs_side_by_side_are_no_fractal(self) -> None:
        # bars 1 and 2 both reach 12: neither tops its neighbour strictly
        b = bars([10.0, 12.0, 12.0, 11.0, 10.5], [9.0, 10.0, 10.0, 9.8, 9.6])
        assert sr.structure(b, int(b.avail[-1])).highs == ()

    def test_order_two(self) -> None:
        # with k = 2 a high must top two bars on each side: bar 1 lacks two left bars, bar 3 (13) is topped by
        # bar 5 (14), bar 5 lacks two right bars -> no highs
        b = bars(UP_H, UP_L)
        assert sr.structure(b, int(b.avail[-1]), k=2).highs == ()


def wave(period: int, n: int, amp: float, pad: float) -> Bars:
    """Closes on a triangle wave 100 <-> 100 + amp, ``period`` bars a full cycle; high / low = close +- pad."""
    half = period // 2
    c = [100 + amp * (i % period if i % period <= half else period - i % period) / half for i in range(n)]
    return bars([x + pad for x in c], [x - pad for x in c], c)


class TestClarity:
    def test_a_clean_wave_is_clear(self) -> None:
        # legs 121 - 99 = 22; a rising bar's true range = 4 (the close's move) + 1 (pad) = 5, so the ATR is
        # about 5 or less: 22 >= 2 x 5
        b = wave(10, 60, 20.0, 1.0)
        assert sr.structure(b, int(b.avail[-1])).clear

    def test_noise_is_not_clear(self) -> None:
        # closes 100 / 101 alternating: highs 102, lows 99 -> legs of 3; every true range is 2 (102 - 100 up,
        # 101 - 99 down), the ATR 2: 3 < 2 x 2
        b = wave(2, 60, 1.0, 1.0)
        assert not sr.structure(b, int(b.avail[-1])).clear

    def test_swings_must_alternate(self) -> None:
        pts = [(1, 1, 10.0), (3, 1, 12.0), (5, -1, 5.0), (7, 1, 11.0)]
        h = np.full(20, 10.0)
        assert not sr._clear(pts, h, h - 1, h)


class TestPhase:
    def c(self, closes: list[float]) -> Bars:
        return bars([x + 1 for x in closes], [x - 1 for x in closes], closes)

    def test_three_up_closes(self) -> None:
        b = self.c([1.0, 2.0, 3.0, 4.0])
        assert sr.phase(b, int(b.avail[-1])) == 1

    def test_three_down_closes(self) -> None:
        b = self.c([4.0, 3.0, 2.0, 1.0])
        assert sr.phase(b, int(b.avail[-1])) == -1

    def test_a_turn_is_no_run(self) -> None:
        b = self.c([1.0, 2.0, 3.0, 2.0])
        assert sr.phase(b, int(b.avail[-1])) == 0

    def test_all_n_closes_count(self) -> None:
        # the last three moves: -4, +1, +1 -> not a run (two up moves are not three)
        b = self.c([5.0, 1.0, 2.0, 3.0])
        assert sr.phase(b, int(b.avail[-1])) == 0

    def test_alternating_is_no_run(self) -> None:
        # moves +1, -1, +1: two of three agree with the last one - still no run
        b = self.c([1.0, 2.0, 1.0, 2.0])
        assert sr.phase(b, int(b.avail[-1])) == 0

    def test_a_flat_close_is_no_run(self) -> None:
        b = self.c([1.0, 1.0, 1.0, 1.0])
        assert sr.phase(b, int(b.avail[-1])) == 0

    def test_only_closed_bars(self) -> None:
        b = self.c([1.0, 2.0, 3.0, 4.0, 1.0])
        assert sr.phase(b, int(b.avail[3])) == 1
        assert sr.phase(b, int(b.avail[4])) == 0

    def test_too_few(self) -> None:
        b = self.c([1.0, 2.0, 3.0])
        assert sr.phase(b, int(b.avail[-1])) == 0


class TestTrend:
    def test_signs_times_the_side(self) -> None:
        up = bars(UP_H, UP_L)
        down = bars([-x for x in UP_L], [-x for x in UP_H])
        t = int(up.avail[-1])
        assert sr.trend([up, down], t, 1) == [1, -1]
        assert sr.trend([up, down], t, -1) == [-1, 1]
