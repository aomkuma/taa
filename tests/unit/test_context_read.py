"""Volatility, timing, volume and the D1 context (app/strategy/context_read.py), answers worked on paper."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.strategy import context_read as cr
from app.strategy.plan1_b2 import Bars

NS_H = 3600 * 10**9


def ns(s: str) -> int:
    return pd.Timestamp(s, tz="UTC").value


def bars(
    t0: str, h: list[float], lo: list[float], c: list[float], o: list[float] | None = None, hours: int = 1
) -> Bars:
    n = len(c)
    t_open = ns(t0) + np.arange(n, dtype=np.int64) * hours * NS_H
    op = np.array(o if o is not None else c, float)
    return Bars(
        t_open, t_open + hours * NS_H, op, np.array(h, float), np.array(lo, float), np.array(c, float)
    )


class TestVolatility:
    def flat(self, n: int, last_high: float = 101.0) -> Bars:
        h = [101.0] * (n - 1) + [last_high]
        return bars("2026-01-05 00:00", h, [99.0] * n, [100.0] * n)

    def test_ratio_to_the_median(self) -> None:
        # every true range 2, the last 4 (high 103): ATR = (13 x 2 + 4) / 14; the median of the ATRs is 2
        b = self.flat(200, 103.0)
        assert cr.vol_ratio(b, int(b.avail[-1])) == pytest.approx((13 * 2 + 4) / 14 / 2)

    def test_too_few_values(self) -> None:
        b = self.flat(60)
        assert math.isnan(cr.vol_ratio(b, int(b.avail[-1])))

    def test_the_forming_bar_is_not_read(self) -> None:
        b = self.flat(200, 103.0)
        assert cr.vol_ratio(b, int(b.avail[-1]) - 1) == pytest.approx(1.0)

    def test_the_window(self) -> None:
        # 300 bars of true range 2, then 200 of 4: the ATR is 2 up to bar 299, between 2 and 4 on bars 300-312,
        # 4 from bar 313. The last 480 ATRs (bars 20-499): 280 twos, 13 between, 187 fours -> the median 2,
        # the last ATR 4 -> 2.0
        h = [101.0] * 300 + [102.0] * 200
        lo = [99.0] * 300 + [98.0] * 200
        b = bars("2026-01-05 00:00", h, lo, [100.0] * 500)
        assert cr.vol_ratio(b, int(b.avail[-1])) == pytest.approx(2.0)
        # reversed (300 of 4, then 200 of 2): the median of the last 480 is 4, the last ATR 2 -> 0.5; over a
        # 300-bar window (bars 200-499: 100 fours, 13 between, 187 twos) the median is 2 -> 1.0
        h2 = [102.0] * 300 + [101.0] * 200
        lo2 = [98.0] * 300 + [99.0] * 200
        b2 = bars("2026-01-05 00:00", h2, lo2, [100.0] * 500)
        assert cr.vol_ratio(b2, int(b2.avail[-1])) == pytest.approx(0.5)
        assert cr.vol_ratio(b2, int(b2.avail[-1]), window=300) == pytest.approx(1.0)


class TestTiming:
    def test_minutes_from_the_new_york_data_hour(self) -> None:
        assert cr.minutes_from(ns("2026-01-15 15:30"), "10:00", "America/New_York") == 30  # EST
        assert cr.minutes_from(ns("2026-07-15 14:30"), "10:00", "America/New_York") == 30  # EDT
        assert cr.minutes_from(ns("2026-01-15 14:59"), "10:00", "America/New_York") == -1
        # 02:00 UTC on the 16th is still the 15th in New York (21:00): 11 hours after 10:00
        assert cr.minutes_from(ns("2026-01-16 02:00"), "10:00", "America/New_York") == 660

    def test_a_window_includes_its_start_not_its_end(self) -> None:
        assert cr.in_window(ns("2026-01-15 00:00"), "07:00", "09:00", "Asia/Bangkok")
        assert cr.in_window(ns("2026-01-15 01:59"), "07:00", "09:00", "Asia/Bangkok")
        assert not cr.in_window(ns("2026-01-15 02:00"), "07:00", "09:00", "Asia/Bangkok")
        assert not cr.in_window(ns("2026-01-14 23:59"), "07:00", "09:00", "Asia/Bangkok")


class TestVolume:
    def test_the_same_clock_time_on_previous_days(self) -> None:
        # hourly bars over 3 days; at 10:00 the volumes are 100, 200 and then 300 -> 300 / mean(100, 200)
        t_open = ns("2026-01-12 00:00") + np.arange(72, dtype=np.int64) * NS_H
        vol = np.full(72, 50.0)
        vol[10], vol[34], vol[58] = 100.0, 200.0, 300.0
        assert cr.rel_volume(t_open, vol, 58) == pytest.approx(2.0)

    def test_a_missing_day_is_skipped(self) -> None:
        t_open = ns("2026-01-12 00:00") + np.arange(72, dtype=np.int64) * NS_H
        vol = np.full(72, 50.0)
        vol[10], vol[58] = 100.0, 300.0
        keep = np.ones(72, bool)
        keep[34] = False  # day 2 has no 10:00 bar
        t2, v2 = t_open[keep], vol[keep]
        i = int(np.flatnonzero(t2 == t_open[58])[0])
        assert cr.rel_volume(t2, v2, i) == pytest.approx(3.0)

    def test_no_history(self) -> None:
        t_open = ns("2026-01-12 00:00") + np.arange(5, dtype=np.int64) * NS_H
        assert math.isnan(cr.rel_volume(t_open, np.ones(5), 4))


class TestDay:
    def days(self, last: tuple[float, float, float, float]) -> Bars:
        # 22 flat days (open = close = 100, high 105, low 95: true range 10) and the last (o, h, l, c)
        o = [100.0] * 22 + [last[0]]
        h = [105.0] * 22 + [last[1]]
        lo = [95.0] * 22 + [last[2]]
        c = [100.0] * 22 + [last[3]]
        return bars("2026-01-01 22:00", h, lo, c, o, hours=24)

    def test_a_strong_down_day(self) -> None:
        # the last day: open 100, high 101, low 87, close 88 -> body 12 over the ATR before it (10) = 1.2;
        # it closed 13 of 14 down its range -> 0.93
        b = self.days((100.0, 101.0, 87.0, 88.0))
        d = cr.last_day(b, int(b.avail[-1]))
        assert (d.direction, d.strong) == (-1, True)
        assert d.body_atr == pytest.approx(1.2)
        assert d.close_pos == pytest.approx(13 / 14)

    def test_a_weak_day(self) -> None:
        # body 8 / 10 = 0.8 with the close at its low end (high 100.5, low 91.5: position 8.5 / 9): only the
        # body fails
        b = self.days((100.0, 100.5, 91.5, 92.0))
        assert not cr.last_day(b, int(b.avail[-1])).strong

    def test_a_long_tail_is_not_strong(self) -> None:
        # body 12 but it closed mid-range: high 101, low 70, close 88 -> position 13 / 31
        b = self.days((100.0, 101.0, 70.0, 88.0))
        assert not cr.last_day(b, int(b.avail[-1])).strong

    def test_only_closed_days(self) -> None:
        b = self.days((100.0, 101.0, 87.0, 88.0))
        d = cr.last_day(b, int(b.avail[-1]) - 1)
        assert d.direction == 0  # the flat day before

    def test_the_day_so_far(self) -> None:
        # winter: the server day starts 22:00 UTC; bars 20:00 .. 01:00 UTC; today's first bar opens 200
        o = [190.0, 195.0, 200.0, 203.0, 206.0, 208.0]
        c = [195.0, 199.0, 203.0, 206.0, 208.0, 207.0]
        h = [196.0, 200.0, 204.0, 207.0, 209.0, 209.0]
        lo = [189.0, 194.0, 199.0, 202.0, 205.0, 206.0]
        b = bars("2026-01-14 20:00", h, lo, c, o)
        run, rng = cr.day_so_far(b, ns("2026-01-15 02:00"), 210.0, 1, 20.0)
        assert run == pytest.approx(0.5)  # (210 - 200) / 20
        assert rng == pytest.approx((209.0 - 199.0) / 20)
        run_s, _ = cr.day_so_far(b, ns("2026-01-15 02:00"), 210.0, -1, 20.0)
        assert run_s == pytest.approx(-0.5)
