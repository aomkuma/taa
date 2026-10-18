"""Tests for LV (lvl.py) with prices whose answers are worked out by hand from the rule in notes.md "LV".

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_lvl.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lvl  # noqa: E402
from fingerprint import zigzag  # noqa: E402

T0 = pd.Timestamp("2026-01-05 00:00", tz="UTC")


def minutes(n: int) -> pd.DatetimeIndex:
    return pd.date_range(T0, periods=n, freq="1min")


# ---------------------------------------------------------------- the trend of a timeframe
class TestTrend:
    def test_rising_series_is_up_after_three_bars(self):
        s = lvl.trend_sign(np.linspace(100, 200, 200))
        assert list(s[:3]) == [0, 0, 0]  # EMA50 three bars back unknown
        assert s[-1] == 1

    def test_falling_series_is_down(self):
        assert lvl.trend_sign(np.linspace(200, 100, 200))[-1] == -1

    def test_flat_series_is_neither(self):
        assert lvl.trend_sign(np.full(100, 50.0))[-1] == 0

    def test_all_agree(self):
        assert lvl.all_agree([1, 1, 1]) == 1
        assert lvl.all_agree([-1, -1, -1]) == -1
        assert lvl.all_agree([1, 1, 0]) == 0
        assert lvl.all_agree([1, -1, 1]) == 0
        assert lvl.all_agree([0, 0, 0]) == 0


class TestEntryTimeframe:
    def test_smallest_timeframe_whose_atr_covers_5_usd(self):
        assert lvl.entry_tf({"M1": 5.2, "M5": 9.0, "M15": 14.0, "M30": 20.0}) == ("M1", 5.2)
        assert lvl.entry_tf({"M1": 3.0, "M5": 6.0, "M15": 9.0, "M30": 12.0}) == ("M5", 6.0)
        assert lvl.entry_tf({"M1": 3.0, "M5": 4.0, "M15": 8.0, "M30": 12.0}) == ("M15", 8.0)
        assert lvl.entry_tf({"M1": 1.0, "M5": 2.0, "M15": 4.0, "M30": 5.5}) == ("M30", 5.5)  # quiet 2023-24 gold
        assert lvl.entry_tf({"M1": np.nan, "M5": 6.0, "M15": 9.0, "M30": 12.0}) == ("M5", 6.0)

    def test_none_covers_5_usd_falls_back_to_m30(self):
        assert lvl.entry_tf({"M1": 1.0, "M5": 2.0, "M15": 3.0, "M30": 4.0}) == ("M30", 4.0)


# ---------------------------------------------------------------- swings
class TestZigZag:
    def test_pivots_and_the_bar_that_confirms_them(self):
        # up 100 -> 120 (bars 0..20), down to 105 (bar 35), up again; every bar spans +-0.5; ATR 2, k 2 -> 4 USD
        path = np.r_[100 + np.arange(21), 120 - np.arange(1, 16), 105 + np.arange(1, 11)].astype(float)
        h, lo = path + 0.5, path - 0.5
        bar, px, typ, conf = zigzag(h, lo, np.full(len(path), 2.0), 2.0)
        # trough 99.5 at bar 0 confirmed when a high is 4 above it (bar 3); peak 120.5 at bar 20 confirmed when a low
        # is 4 under it (116.5 at bar 23); trough 104.5 at bar 35 confirmed at bar 38 (high 108.5)
        assert list(bar) == [0, 20, 35]
        assert list(px) == [99.5, 120.5, 104.5]
        assert list(typ) == [-1, 1, -1]
        assert list(conf) == [3, 23, 38]
        assert (conf > bar).all()  # never known before it happened


# ---------------------------------------------------------------- the bounce and the level
BARS = np.array([10, 20, 30, 40])
TYP_SELL = np.array([1, -1, 1, -1])  # peak, trough, peak, trough (the last trough = the bounce's start)
ALL = np.ones(4, bool)


class TestFindSetupSell:
    def test_level_a_is_the_nearest_earlier_peak_above(self):
        px = np.array([110.0, 100.0, 108.0, 95.0])
        assert lvl.find_setup(BARS, px, TYP_SELL, ALL, 0, 103.0, -1, 2.0) == (40, 95.0, 108.0, "A")

    def test_level_b_is_an_earlier_trough_price_broke(self):
        px = np.array([120.0, 105.0, 112.0, 95.0])  # 105 is a trough above the price: broken on the way to 95
        assert lvl.find_setup(BARS, px, TYP_SELL, ALL, 0, 103.0, -1, 2.0) == (40, 95.0, 105.0, "B")

    def test_no_setup_when_the_latest_swing_is_a_peak(self):
        assert lvl.find_setup(BARS[:3], np.array([110.0, 100.0, 108.0]), TYP_SELL[:3], ALL[:3], 0, 104.0, -1, 2.0) is None

    def test_no_setup_when_the_bounce_is_too_small(self):
        px = np.array([110.0, 100.0, 108.0, 95.0])
        assert lvl.find_setup(BARS, px, TYP_SELL, ALL, 0, 96.0, -1, 2.0) is None  # 1 above the start, needs 2

    def test_the_lookback_drops_older_swings(self):
        px = np.array([120.0, 105.0, 112.0, 95.0])
        assert lvl.find_setup(BARS, px, TYP_SELL, ALL, 25, 103.0, -1, 2.0) == (40, 95.0, 112.0, "A")

    def test_a_swing_not_yet_confirmed_is_not_used(self):
        px = np.array([110.0, 100.0, 108.0, 95.0])
        known = np.array([True, True, True, False])  # the trough is not confirmed: the latest known is a peak
        assert lvl.find_setup(BARS, px, TYP_SELL, known, 0, 103.0, -1, 2.0) is None

    def test_no_level_above_the_price(self):
        px = np.array([110.0, 100.0, 108.0, 95.0])
        assert lvl.find_setup(BARS, px, TYP_SELL, ALL, 0, 115.0, -1, 2.0) is None


class TestFindSetupBuy:
    TYP = np.array([-1, 1, -1, 1])  # trough, peak, trough, peak (the last peak = the dip's start)

    def test_level_a_is_the_nearest_earlier_trough_below(self):
        px = np.array([90.0, 100.0, 92.0, 105.0])
        assert lvl.find_setup(BARS, px, self.TYP, ALL, 0, 97.0, 1, 2.0) == (40, 105.0, 92.0, "A")

    def test_level_b_is_an_earlier_peak_price_broke(self):
        px = np.array([80.0, 95.0, 85.0, 110.0])
        assert lvl.find_setup(BARS, px, self.TYP, ALL, 0, 100.0, 1, 2.0) == (40, 110.0, 95.0, "B")


class TestVoidAndStall:
    def test_a_close_beyond_the_level_by_the_buffer_voids_it(self):
        assert lvl.voided(np.array([100.0, 104.0, 106.3]), 106.0, 0.25, -1)
        assert not lvl.voided(np.array([100.0, 106.2]), 106.0, 0.25, -1)
        assert lvl.voided(np.array([100.0, 93.7]), 94.0, 0.25, 1)
        assert not lvl.voided(np.array([]), 94.0, 0.25, 1)

    def test_sell_stall(self):
        assert lvl.stall(99.6, 99.8, 98.9, 99.0, 100.0, 1.0, -1)  # reached 99 or above, closed down, below 100
        assert not lvl.stall(99.0, 99.8, 98.9, 99.5, 100.0, 1.0, -1)  # closed up
        assert not lvl.stall(98.4, 98.5, 98.0, 98.1, 100.0, 1.0, -1)  # never within 1 of the level
        assert not lvl.stall(101.0, 101.5, 100.2, 100.5, 100.0, 1.0, -1)  # closed above the level

    def test_buy_stall(self):
        assert lvl.stall(100.4, 101.2, 100.6, 101.0, 100.0, 1.0, 1)
        assert not lvl.stall(101.0, 101.2, 100.6, 100.8, 100.0, 1.0, 1)  # closed down


class TestLimitFill:
    def test_sell_limit_fills_at_the_limit(self):
        o, h, lo = np.array([100.0, 101.0, 103.0]), np.array([101.0, 103.0, 105.5]), np.array([99.0, 100.0, 102.0])
        ot = minutes(3)
        assert lvl.limit_fill(o, h, lo, np.zeros(3), ot, 0, ot[-1] + pd.Timedelta(minutes=1), 105.0, -1, 95.0) == (2, 105.0)

    def test_sell_limit_gap_fills_at_the_open(self):
        o, h, lo = np.array([100.0, 106.0]), np.array([101.0, 107.0]), np.array([99.0, 105.5])
        ot = minutes(2)
        assert lvl.limit_fill(o, h, lo, np.zeros(2), ot, 0, ot[-1] + pd.Timedelta(minutes=1), 105.0, -1, 95.0) == (1, 106.0)

    def test_cancelled_when_the_start_breaks_first_or_in_the_same_bar(self):
        ot = minutes(2)
        end = ot[-1] + pd.Timedelta(minutes=1)
        o, h, lo = np.array([100.0, 98.0]), np.array([101.0, 99.0]), np.array([99.0, 94.0])
        assert lvl.limit_fill(o, h, lo, np.zeros(2), ot, 0, end, 105.0, -1, 95.0) is None
        o, h, lo = np.array([100.0, 100.0]), np.array([101.0, 105.5]), np.array([99.0, 94.0])
        assert lvl.limit_fill(o, h, lo, np.zeros(2), ot, 0, end, 105.0, -1, 95.0) is None

    def test_expires_after_its_time(self):
        o, h, lo = np.array([100.0, 101.0, 103.0]), np.array([101.0, 103.0, 105.5]), np.array([99.0, 100.0, 102.0])
        ot = minutes(3)
        assert lvl.limit_fill(o, h, lo, np.zeros(3), ot, 0, ot[2], 105.0, -1, 95.0) is None  # bar 2 opens at the end

    def test_buy_limit_on_the_ask(self):
        o, h, lo = np.array([100.0, 97.0, 95.5]), np.array([101.0, 98.0, 96.0]), np.array([99.0, 96.0, 94.6])
        sp = np.full(3, 0.3)  # ask low 99.3, 96.3, 94.9 -> reaches 95 in bar 2
        ot = minutes(3)
        assert lvl.limit_fill(o, h, lo, sp, ot, 0, ot[-1] + pd.Timedelta(minutes=1), 95.0, 1, 105.0) == (2, 95.0)


class TestPlan:
    P = lvl.Params(stop_buf=0.25, min_stop=3.0, min_stop_atr=0.5, min_target=5.0)

    def test_sell_stop_beyond_the_level_with_the_floors(self):
        # stop at 100 + 0.25 x 4 = 101: 2 from the entry -> the 3 USD floor; T1 = 3 -> the 5 USD floor
        assert lvl.plan(99.0, 100.0, 90.0, 4.0, -1, self.P) == (3.0, 5.0)
        assert lvl.plan(95.0, 100.0, 90.0, 4.0, -1, self.P) == (6.0, 6.0)  # stop 101: 6 away; T1 = 6

    def test_targets(self):
        p15 = lvl.Params(target="T15")
        p2 = lvl.Params(target="T2")
        assert lvl.plan(95.0, 100.0, 90.0, 4.0, -1, p15) == (6.0, 9.0)
        assert lvl.plan(99.0, 100.0, 90.0, 4.0, -1, p2) == (3.0, 9.0)  # back to the start 90

    def test_buy_mirror(self):
        p2 = lvl.Params(target="T2")
        assert lvl.plan(101.0, 100.0, 110.0, 4.0, 1, p2) == (3.0, 9.0)  # stop 99 -> 2 -> 3; back to 110


class TestManage:
    @staticmethod
    def run(h, lo, c, side=-1, entry=100.0, sl=3.0, tp=5.0, sp=None, n_end=None, at_open=False):
        n = len(h)
        o = np.asarray(c, float)
        sp = np.zeros(n) if sp is None else np.asarray(sp, float)
        ot = minutes(n)
        end = ot[0] + pd.Timedelta(minutes=n if n_end is None else n_end)
        return lvl.manage(o, np.asarray(h, float), np.asarray(lo, float), np.asarray(c, float), sp, ot, 0, side, entry,
                          sl, tp, 0.6, end, 0.07, 0.15, at_open)

    def test_sell_target(self):
        r = self.run(h=[100.5, 100.0, 99.0], lo=[99.5, 97.0, 94.9], c=[100.0, 98.0, 95.5])
        assert (r["exit"], r["pnl"], r["xj"]) == ("win", 5.0, 2)

    def test_sell_stop_pays_the_stop_slippage(self):
        r = self.run(h=[100.5, 103.1], lo=[99.5, 100.0], c=[100.0, 102.0])
        assert r["exit"] == "stop" and r["xj"] == 1 and r["pnl"] == pytest.approx(-3.15)

    def test_both_in_one_bar_is_the_stop(self):
        r = self.run(h=[100.5, 103.5], lo=[99.5, 94.0], c=[100.0, 99.0])
        assert r["exit"] == "stop"

    def test_break_even_after_six_tenths_of_the_target(self):
        r = self.run(h=[100.5, 99.0, 100.2], lo=[99.5, 96.9, 99.0], c=[100.0, 97.5, 100.1])
        assert r["exit"] == "be" and r["xj"] == 2 and r["pnl"] == pytest.approx(-0.15)

    def test_time_stop_at_the_last_close_on_the_ask_with_slippage(self):
        r = self.run(h=[100.5, 101.0, 101.0, 101.0], lo=[99.5, 99.0, 99.0, 99.0], c=[100.0, 100.5, 101.0, 100.0],
                     sp=[0.3] * 4, n_end=3)
        assert r["exit"] == "time" and r["xj"] == 2 and r["pnl"] == pytest.approx(100.0 - (101.0 + 0.3 + 0.07))

    def test_the_fill_bar_target_counts_only_for_a_fill_at_the_open(self):
        assert self.run(h=[100.5, 100.5], lo=[94.0, 99.5], c=[95.0, 100.0], n_end=2)["exit"] == "time"
        assert self.run(h=[100.5, 100.5], lo=[94.0, 99.5], c=[95.0, 100.0], at_open=True)["exit"] == "win"

    def test_a_sells_target_is_on_the_ask(self):
        # the bid low 95.0 is 5 below the entry, but the ask is 95.3: not yet the target
        r = self.run(h=[100.5, 100.0], lo=[99.5, 95.0], c=[100.0, 96.0], sp=[0.3, 0.3], n_end=2)
        assert r["exit"] == "time"

    def test_buy_target_and_stop(self):
        assert self.run(h=[100.5, 105.0], lo=[99.5, 100.0], c=[100.0, 104.0], side=1)["exit"] == "win"
        r = self.run(h=[100.5, 101.0], lo=[99.5, 96.9], c=[100.0, 97.0], side=1)
        assert r["exit"] == "stop" and r["pnl"] == pytest.approx(-3.15)


# ---------------------------------------------------------------- the owner's example, on real data
@pytest.fixture(scope="module")
def sept2():
    import jlib  # noqa: PLC0415

    m = jlib.m1_frame("XAUUSD")
    m = m[(m.index >= pd.Timestamp("2026-07-15", tz="UTC")) & (m.index < pd.Timestamp("2026-09-03", tz="UTC"))]
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    return lvl.Market(m, sp)


def test_the_owners_sept_2_case_sells_the_w_bounce_into_the_broken_4316_low(sept2):
    """2026-09-02 (all timeframes falling): the W's bounce reached 4314.7 at 09:38 Thai time, just under the 07:02
    low 4316 that price broke at 08:00. LV (stall, k 0.5) should sell it there."""
    M = sept2
    th = M.ot.tz_convert("Asia/Bangkok")
    dec = np.nonzero((th >= pd.Timestamp("2026-09-02 09:00", tz="Asia/Bangkok"))
                     & (th < pd.Timestamp("2026-09-02 12:00", tz="Asia/Bangkok")))[0]
    t = lvl.scan(M, dec, lvl.Params(form="stall", k=0.5, target="T1"), np.zeros(len(M.o), bool))
    assert not t.empty
    first = t.iloc[0]
    when = first.t.tz_convert("Asia/Bangkok")
    assert first.side == -1
    assert abs(first.level - 4316.2) <= 1.0, first.level
    assert pd.Timestamp("2026-09-02 09:30", tz="Asia/Bangkok") <= when <= pd.Timestamp("2026-09-02 10:00", tz="Asia/Bangkok")


def test_placebo_shift_is_drawn_once_per_bounce_and_level(sept2):
    """The placebo level must stay the same for every minute of one bounce, and a pair (start, level) is used once
    whether it is real or shifted (a bug found 2026-10-18: a new random level every minute)."""
    M = sept2
    th = M.ot.tz_convert("Asia/Bangkok")
    dec = np.nonzero((th >= pd.Timestamp("2026-08-03", tz="Asia/Bangkok"))
                     & (th < pd.Timestamp("2026-09-03", tz="Asia/Bangkok")))[0]
    ny = np.zeros(len(M.o), bool)
    real = lvl.scan(M, dec, lvl.Params(form="limit", k=0.5, target="T1"), ny)
    plac = lvl.scan(M, dec, lvl.Params(form="limit", k=0.5, target="T1", placebo=True), ny)
    assert not real.empty and not plac.empty
    # one trade at most per (bounce start, side, real level), real or placebo
    assert not real.duplicated(["start", "side", "level_real"]).any()
    assert not plac.duplicated(["start", "side", "level_real"]).any()
    # the placebo level lies 1-3 ATR (of the first minute's draw) from the real one; the real run is unshifted
    gap = (plac.level - plac.level_real).abs()
    assert (gap > 0).all() and (real.level == real.level_real).all()
