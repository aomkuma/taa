"""Hand-worked tests for behaviors.py - each draft behaviour's reading on bars built by hand.

    .venv/Scripts/python -m pytest research/2026-10-23-entry/knowledge/test_behaviors.py -q
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import behaviors as bh  # noqa: E402


def test_efficiency_one_way_and_back_and_forth():
    assert bh.efficiency(np.arange(13.0), 12) == pytest.approx(1.0)  # 12 steps of +1: net 12 / path 12
    assert bh.efficiency(np.arange(13.0)[::-1], 12) == pytest.approx(1.0)  # one way down is one way too
    # +2, -1, +2, -1 ... (12 moves): net +6, path 18 -> 1/3
    c = np.cumsum([100.0, 2, -1, 2, -1, 2, -1, 2, -1, 2, -1, 2, -1])
    assert bh.efficiency(c, 12) == pytest.approx(6 / 18)
    assert bh.efficiency(np.array([5.0, 6, 5, 6, 5]), 4) == pytest.approx(0.0)  # back where it started


def test_efficiency_reads_only_the_last_n_moves_and_needs_them():
    c = np.array([0.0, 50, 100, 101, 102])  # the big early moves are outside n = 2
    assert bh.efficiency(c, 2) == pytest.approx(1.0)
    assert math.isnan(bh.efficiency(np.array([1.0, 2.0]), 2))
    assert math.isnan(bh.efficiency(np.array([3.0, 3.0, 3.0]), 2))  # no movement at all


@pytest.mark.parametrize(("closes", "want"), [
    ([99.0, 99.5, 100.5, 101, 101.5], "up"),     # cell 1 (95..100) four bars ago -> cell 2 (100..105) now
    ([101.0, 100.5, 99.5, 99, 98], "down"),
    ([101.0, 99, 98, 99, 101.5], "none"),        # dipped under 100 and came back: the same cell as 4 bars ago
    ([99.0, 101, 102, 103, 99.9], "none"),       # broke and fell back by now
    ([94.0, 96, 99, 103, 106], "up"),            # two cells: still up
])
def test_line_break_compares_the_cell_now_with_k_bars_ago(closes, want):
    assert bh.line_break(np.array(closes), anchor=90.0, unit=5.0, k=4) == want


def test_line_break_needs_bars_and_a_grid():
    assert bh.line_break(np.array([99.0, 101]), 90.0, 5.0, 4) == "none"
    assert bh.line_break(np.array([99.0, 99, 99, 99, 101]), math.nan, 5.0, 4) == "none"


@pytest.mark.parametrize(("bar", "want"), [
    ((100, 110, 99, 101, 2000), "top"),       # range 11 >= 2 x 5; upper wick 110 - 101 = 9 >= 5.5
    ((101, 102, 91, 100, 2000), "bottom"),    # lower wick 100 - 91 = 9
    ((100, 110, 99, 109, 2000), "none"),      # a wide heavy bar without a wick (a run, not a turn)
    ((100, 110, 99, 101, 1999), "none"),      # volume just under 2 x the mean
    ((100, 109.9, 100, 101, 2000), "none"),   # range 9.9 < 2 ATR
    ((100, 110, 100, 105, 2000), "top"),      # range exactly 2 ATR (10), upper wick exactly half: 110 - 105 = 5
    ((105, 110, 100, 100.01, 2000), "top"),   # a down bar: the upper wick is from the open (110 - 105 = 5), not the close
    ((108, 110, 100, 104, 2000), "none"),     # upper wick from the open 2, lower 4: no wick of half (from the close: 6)
    ((100, 110, 100, 106, 2000), "none"),     # an upper wick of 4 = 0.4 of the range is not enough
])
def test_climax_needs_width_volume_and_a_wick(bar, want):
    o, h, lo, c, v = bar
    assert bh.climax(o, h, lo, c, v, atr=5.0, v_mean=1000.0) == want


@pytest.mark.parametrize(("price", "run", "want"), [
    (2010.0, 1.0, "up"), (2010.0, 0.99, "none"), (1999.0, 1.5, "none"),
    (1980.0, -1.0, "down"), (1985.0, -1.2, "none"), (2010.0, -1.5, "none"),
])
def test_runaway_needs_the_run_and_yesterdays_extreme(price, run, want):
    assert bh.runaway(price, y_high=2000.0, y_low=1985.0, run_step=run) == want


def _bars(thai_times, highs, lows):
    idx = pd.DatetimeIndex([pd.Timestamp(f"2026-10-21 {x}", tz="Asia/Bangkok") for x in thai_times]).tz_convert("UTC")
    return idx, np.array(highs, dtype=float), np.array(lows, dtype=float)


def test_asia_break_after_london_opens():
    idx, h, lo = _bars(["06:45", "07:00", "10:00", "12:45", "13:00", "14:00"],
                       [130, 105, 110, 108, 109, 112], [90, 100, 101, 99, 100, 102])
    # Asia 07:00-13:00: high 110, low 99 (the 06:45 bar is outside); after: high 112 > 110 -> up
    assert bh.asia_break(idx, h, lo, pd.Timestamp("2026-10-21 14:15", tz="Asia/Bangkok").tz_convert("UTC")) == "up"
    h2 = h.copy()
    h2[5] = 110.0
    assert bh.asia_break(idx, h2, lo, pd.Timestamp("2026-10-21 14:15", tz="Asia/Bangkok").tz_convert("UTC")) == "none"
    lo2 = lo.copy()
    lo2[4] = 98.0
    assert bh.asia_break(idx, h, lo2, pd.Timestamp("2026-10-21 14:15", tz="Asia/Bangkok").tz_convert("UTC")) == "both"
    assert bh.asia_break(idx, h2, lo2, pd.Timestamp("2026-10-21 14:15", tz="Asia/Bangkok").tz_convert("UTC")) == "down"


def test_asia_break_before_1300_thai_is_none():
    idx, h, lo = _bars(["07:00", "12:45", "13:00"], [105, 120, 130], [100, 90, 80])  # even if handed a later bar
    assert bh.asia_break(idx, h, lo, pd.Timestamp("2026-10-21 12:59", tz="Asia/Bangkok").tz_convert("UTC")) == "none"


def _pool_bars():
    """Two equal bottoms at 100.0 (bars 3 and 7, each lower than its neighbours), price over them, then bar 10
    sweeps to 99.0 (0.1 ATR = 0.1 under 100 needed) and closes back at 100.6 from a close of 101 before it."""
    lo = np.array([103, 102, 101, 100.0, 101, 102, 101, 100.05, 101, 101.5, 99.0, 100.5, 101])
    h = lo + 1.5
    c = lo + 1.0
    c[10] = 100.6
    v = np.full(len(lo), 100.0)
    v[10] = 300.0
    return h, lo, c, v


def test_recent_sweep_finds_the_pool_swept_and_closed_back():
    h, lo, c, v = _pool_bars()
    assert bh.recent_sweep(h, lo, c, v, atr=1.0, recent=6) == "low"


def test_recent_sweep_only_inside_the_recent_bars():
    h, lo, c, v = _pool_bars()
    assert bh.recent_sweep(h, lo, c, v, atr=1.0, recent=2) == "none"  # bar 10 is 3 bars from the end (13 bars)


def test_no_sweep_when_the_bar_closes_under_the_pool():
    h, lo, c, v = _pool_bars()
    c[10] = 99.5  # went under and stayed under: a break, not a sweep
    assert bh.recent_sweep(h, lo, c, v, atr=1.0, recent=6) == "none"


def _m15(thai_start, lows, highs):
    idx = pd.date_range(pd.Timestamp(thai_start, tz="Asia/Bangkok"), periods=len(lows), freq="15min").tz_convert("UTC")
    return pd.DataFrame({"low": lows, "high": highs}, index=idx)


def test_day_start_is_0500_thai():
    assert bh.day_start(pd.Timestamp("2026-10-23 22:00", tz="Asia/Bangkok")) == pd.Timestamp("2026-10-22 22:00", tz="UTC")
    assert bh.day_start(pd.Timestamp("2026-10-24 03:00", tz="Asia/Bangkok")) == pd.Timestamp("2026-10-22 22:00", tz="UTC")
    assert bh.day_start(pd.Timestamp("2026-10-23 05:00", tz="Asia/Bangkok")) == pd.Timestamp("2026-10-22 22:00", tz="UTC")


def test_day_levels_swings_extremes_and_yesterday():
    # 04:45 (before the day), then 05:00 .. 06:00 Thai; the 06:00 bar closes at 06:15
    m15 = _m15("2026-10-23 04:45", [90.0, 100, 98, 99, 97, 101], [130.0, 104, 106, 103, 105, 104])
    d1 = pd.DataFrame({"high": [120.0, 125.0], "low": [80.0, 85.0]},
                      index=pd.DatetimeIndex([pd.Timestamp("2026-10-21 21:00", tz="UTC"), pd.Timestamp("2026-10-22 21:00", tz="UTC")]))
    out = bh.day_levels(m15, d1, pd.Timestamp("2026-10-23 06:15", tz="Asia/Bangkok"))
    # bars 05:00 .. 06:00: lows 100 98 99 97 101, highs 104 106 103 105 104; 04:45 is outside the day
    assert out == ["M15 swing low 98.00 at 05:15", "M15 swing high 106.00 at 05:15",
                   "M15 swing low 97.00 at 05:45", "M15 swing high 105.00 at 05:45",
                   "the day's high 106.00 at 05:15, low 97.00 at 05:45",
                   "yesterday's D1 high 120.00, low 80.00"]  # the D1 bar of 22 Oct 21:00 UTC is still forming


def test_day_levels_read_only_closed_bars():
    m15 = _m15("2026-10-23 05:00", [100.0, 98, 99, 90], [104.0, 106, 103, 110])
    d1 = pd.DataFrame({"high": [120.0], "low": [80.0]}, index=pd.DatetimeIndex([pd.Timestamp("2026-10-21 21:00", tz="UTC")]))
    out = bh.day_levels(m15, d1, pd.Timestamp("2026-10-23 05:59", tz="Asia/Bangkok"))  # the 05:45 bar is not closed
    assert out == ["M15 swing low 98.00 at 05:15", "M15 swing high 106.00 at 05:15",
                   "the day's high 106.00 at 05:15, low 98.00 at 05:15", "yesterday's D1 high 120.00, low 80.00"]


def test_day_levels_a_falling_run_has_one_swing_low():
    m15 = _m15("2026-10-23 05:00", [100.0, 98, 96, 99, 100], [104.0, 103, 102, 101, 103])
    d1 = pd.DataFrame({"high": [120.0], "low": [80.0]}, index=pd.DatetimeIndex([pd.Timestamp("2026-10-21 21:00", tz="UTC")]))
    out = bh.day_levels(m15, d1, pd.Timestamp("2026-10-23 06:15", tz="Asia/Bangkok"))
    assert [x for x in out if x.startswith("M15 swing low")] == ["M15 swing low 96.00 at 05:30"]  # not 98 (still falling)
