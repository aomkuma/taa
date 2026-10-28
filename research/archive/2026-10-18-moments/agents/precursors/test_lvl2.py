"""Tests for LV2 (lvl2.py) - the owner's requirements R1-R12 in notes.md - with answers worked out by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_lvl2.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lvl2  # noqa: E402
import plib  # noqa: E402

NS = 60_000_000_000


def minutes_ns(n: int) -> np.ndarray:
    return pd.date_range("2026-01-05", periods=n, freq="1min", tz="UTC").asi8


# ---------------------------------------------------------------- R1 the owner's windows, DST-aware
def test_windows_follow_the_events_through_dst():
    t = pd.DatetimeIndex(["2026-07-15 12:30", "2026-01-15 13:30", "2026-01-15 12:30", "2026-07-15 00:00",
                          "2026-01-15 00:00", "2026-07-15 07:00", "2026-01-15 08:00", "2026-01-15 07:00"], tz="UTC")
    W = plib.window_mask(t)
    assert W.NY1930.tolist()[:3] == [True, True, False]  # 08:30 New York = 19:30 Thai in summer, 20:30 in winter
    assert W.A07.tolist()[3:5] == [True, True]  # 07:00 Thai both seasons
    assert W.LO14.tolist()[5:8] == [True, True, False]  # London 08:00 = 14:00 Thai summer, 15:00 Thai winter


# ---------------------------------------------------------------- R4 / R5 which timeframes
def test_trend_timeframes_are_every_larger_one_up_to_h4():
    assert lvl2.trend_tfs("M1") == ("M5", "M15", "M30", "H1", "H4")
    assert lvl2.trend_tfs("M5") == ("M15", "M30", "H1", "H4")
    assert lvl2.trend_tfs("M30") == ("H1", "H4")


def test_level_timeframes_are_the_larger_of_m15_m30_h1():
    assert lvl2.level_tfs("M1") == ("M15", "M30", "H1")
    assert lvl2.level_tfs("M5") == ("M15", "M30", "H1")
    assert lvl2.level_tfs("M15") == ("M30", "H1")
    assert lvl2.level_tfs("M30") == ("H1",)


class TestZones:
    def test_swings_within_the_tolerance_merge(self):
        # sorted 100.0 100.2 | 103.0 103.1(H1) | 103.3 (0.3 from 103.0: a zone is at most 0.25 wide)
        z = lvl2.merge_zones(np.array([103.3, 100.0, 103.0, 100.2, 103.1]), np.array([0, 0, 0, 0, 1], bool), 0.25)
        assert len(z) == 3
        assert z[0][0] == pytest.approx(100.1) and z[0][1:] == (2, False)
        assert z[1][0] == pytest.approx(103.05) and z[1][1:] == (2, True)
        assert z[2][0] == pytest.approx(103.3) and z[2][1:] == (1, False)

    def test_no_chaining_into_a_wide_band(self):
        # each neighbour is 0.2 apart: chaining would make one 0.6-wide zone; a zone may be at most 0.25 wide
        z = lvl2.merge_zones(np.array([100.0, 100.2, 100.4, 100.6]), np.zeros(4, bool), 0.25)
        assert [round(x[0], 3) for x in z] == [100.1, 100.5]

    def test_importance_counts_the_finest_timeframe_once(self):
        # the same swing seen on M15, M30 and H1 (one event) and a second M15 swing nearby
        px = np.array([100.0, 100.05, 100.1, 100.2])
        h1 = np.array([False, False, True, False])
        finest = np.array([True, False, False, True])  # M15, M30, H1, M15
        assert lvl2.merge_zones(px, h1, 0.25, finest) == [(pytest.approx(100.0875), 2, True)]

    def test_the_tolerance_boundary(self):
        assert len(lvl2.merge_zones(np.array([100.0, 100.25]), np.zeros(2, bool), 0.25)) == 1
        assert len(lvl2.merge_zones(np.array([100.0, 100.26]), np.zeros(2, bool), 0.25)) == 2

    def test_level_in_front_and_importance(self):
        zones = [(95.0, 1, False), (103.0, 1, False), (106.0, 3, False), (110.0, 1, True)]
        assert lvl2.level_in_front(zones, 101.0, -1, False)[0] == 103.0  # a sell: the nearest above
        assert lvl2.level_in_front(zones, 101.0, -1, True)[0] == 106.0  # important: 3 swings
        assert lvl2.level_in_front(zones, 107.0, -1, True)[0] == 110.0  # important: an H1 swing
        assert lvl2.level_in_front(zones, 101.0, 1, False)[0] == 95.0  # a buy: the nearest below
        assert lvl2.level_in_front(zones, 101.0, 1, True) is None
        assert lvl2.level_in_front([], 101.0, 1, False) is None


# ---------------------------------------------------------------- R7 the stop learned from the data
class TestLearnedStop:
    def test_only_earlier_resolved_winners_count(self):
        over = np.array([0.1, 0.5, 0.9, 2.0, 0.3])
        resolved = np.array([1, 2, 3, 4, 10])
        won = np.array([True, True, False, True, True])
        # eligible at t=5: 0.1, 0.5, 2.0 (the third lost, the fifth is not known yet) -> median 0.5
        assert lvl2.learned_buffer(over, resolved, won, 5, 50, 2) == pytest.approx(0.5)
        assert lvl2.learned_buffer(over, resolved, won, 5, 50, 4) is None  # not enough history yet
        assert lvl2.learned_buffer(over, resolved, won, 10, 50, 4) == pytest.approx(0.4)  # 0.1 0.3 0.5 2.0

    def test_outcome_without_a_stop(self):
        ot = minutes_ns(3)
        o = np.array([100.0, 100.0, 99.5])
        h, lo = np.array([100.5, 101.6, 99.0]), np.array([99.5, 99.0, 94.9])
        won, over, res = lvl2.outcome(o, h, lo, np.zeros(3), ot, 0, -1, 100.0, 101.0, 5.0, int(ot[2] + 10 * NS))
        assert won and over == pytest.approx(0.6) and res == ot[2] + NS  # 1.6 above the entry = 0.6 beyond 101
        won, over, res = lvl2.outcome(o, h, lo, np.zeros(3), ot, 0, -1, 100.0, 101.0, 5.0, int(ot[2]))
        assert not won and res == ot[2]  # time ran out before the target bar

    def test_outcome_of_a_sell_uses_the_ask(self):
        ot = minutes_ns(2)
        h, lo = np.array([100.5, 100.8]), np.array([99.5, 95.0])
        won, over, _ = lvl2.outcome(np.array([100.0, 100.0]), h, lo, np.full(2, 0.3), ot, 0, -1, 100.0, 101.0, 5.0,
                                    int(ot[1] + 5 * NS))
        assert not won  # the ask low 95.3 is 4.7 from the entry
        assert over == pytest.approx(0.1)  # the ask high 101.1


# ---------------------------------------------------------------- R3 exits on the entry timeframe
class TestManage2:
    @staticmethod
    def run(o, h, lo, c, etf_every=1, sp=0.0, side=-1, entry=100.0, sl=3.0, tp=5.0, level=101.0, n_end=None):
        n = len(o)
        ot = minutes_ns(n)
        etf_done = ot[etf_every - 1::etf_every] + NS
        etf_close = np.asarray(c, float)[etf_every - 1::etf_every]
        end = int(ot[0] + (n if n_end is None else n_end) * NS)
        return lvl2.manage(np.asarray(o, float), np.asarray(h, float), np.asarray(lo, float), np.asarray(c, float),
                           np.full(n, sp), ot, 0, side, entry, sl, tp, level, etf_done, etf_close, 0.6, end, 0.07, 0.15)

    def test_an_entry_tf_close_beyond_the_level_exits_at_the_next_open(self):
        r = self.run(o=[100.0, 100.2, 101.4], h=[100.5, 101.5, 101.6], lo=[99.8, 100.1, 101.0], c=[100.2, 101.2, 101.3])
        assert r["exit"] == "close" and r["xj"] == 2 and r["pnl"] == pytest.approx(100.0 - (101.4 + 0.07))

    def test_on_m5_only_a_m5_close_counts(self):
        # M1 closes above the level at minutes 1-3 but the M5 bar (minutes 0-4) closes back below it at minute 4
        o = [100.0, 100.5, 101.2, 101.3, 100.8, 100.0]
        h = [100.6, 101.5, 101.6, 101.5, 100.9, 100.2]
        lo = [99.8, 100.4, 101.0, 100.7, 100.0, 99.0]
        c = [100.5, 101.2, 101.3, 100.8, 100.0, 99.5]
        r = self.run(o, h, lo, c, etf_every=5, n_end=6)
        assert r["exit"] == "time" and r["xj"] == 5

    def test_the_stop_comes_first(self):
        r = self.run(o=[100.0, 100.0], h=[100.5, 103.1], lo=[99.5, 94.0], c=[100.0, 101.5])
        assert r["exit"] == "stop" and r["pnl"] == pytest.approx(-3.15)

    def test_target_and_break_even(self):
        assert self.run(o=[100.0, 99.0], h=[100.5, 99.5], lo=[99.5, 94.9], c=[99.6, 95.5])["exit"] == "win"
        r = self.run(o=[100.0, 98.0, 99.0], h=[100.5, 98.5, 100.2], lo=[99.5, 96.9, 98.8], c=[99.0, 97.5, 100.1])
        assert r["exit"] == "be" and r["pnl"] == pytest.approx(-0.15)

    def test_buy_close_below_the_level(self):
        r = self.run(o=[100.0, 99.8, 98.6], h=[100.2, 99.9, 99.0], lo=[99.5, 98.5, 98.4], c=[99.8, 98.8, 98.7], side=1,
                     level=99.0)
        assert r["exit"] == "close" and r["xj"] == 2 and r["pnl"] == pytest.approx((98.6 - 0.07) - 100.0)


# ---------------------------------------------------------------- the owner's example on real data
@pytest.fixture(scope="module")
def market():
    import jlib  # noqa: PLC0415

    m = jlib.m1_frame("XAUUSD")
    m = m[(m.index >= pd.Timestamp("2026-06-20", tz="UTC")) & (m.index < pd.Timestamp("2026-09-03", tz="UTC"))]
    return lvl2.Market(m, m.spread.to_numpy(float) * 0.01 + 0.08)


def test_times_are_nanoseconds_and_nothing_is_seen_before_it_happens(market):
    """2026-10-18: the real data's index is in microseconds; adding a nanosecond minute put the bot 16 hours ahead."""
    M = market
    assert (M.ot_ns == M.ot.tz_convert("UTC").as_unit("ns").asi8).all()
    t = int(np.searchsorted(M.ot, pd.Timestamp("2026-09-02 02:38", tz="UTC")))
    t_ns = int(M.ot_ns[t] + lvl2.NS_MIN)
    assert pd.Timestamp(t_ns, tz="UTC") == pd.Timestamp("2026-09-02 02:39", tz="UTC")
    for tf in lvl2.LADDER:
        T = M.tf[tf]
        i = M.last(tf, t_ns)
        assert T["done"][i] <= t_ns < (T["done"][i + 1] if i + 1 < len(T["done"]) else np.inf)
        assert T["start"][i] < t_ns  # the bar began before the decision
        for b_, k_ in (("zz_b", "zz_known"), ("fr_b", "fr_known")):
            if k_ in T:
                kk = np.searchsorted(T[k_], t_ns, side="right")
                if kk:
                    assert (T["start"][T[b_][:kk]] < t_ns).all()  # every known swing happened before


def test_sept_2_sells_the_w_bounce_into_the_broken_4316_low(market):
    M = market
    th = M.ot.tz_convert("Asia/Bangkok")
    dec = np.nonzero(plib.window_mask(M.ot).any(axis=1).to_numpy() & (M.ot >= pd.Timestamp("2026-07-01", tz="UTC")))[0]
    S = lvl2.signals(M, dec, lvl2.Params(k=0.5))
    S["th"] = th[S.t.to_numpy()]
    day = S[(S.th >= pd.Timestamp("2026-09-02 09:30", tz="Asia/Bangkok")) & (S.th <= pd.Timestamp("2026-09-02 10:00", tz="Asia/Bangkok"))]
    assert not day.empty, "no LV2 signal on the W bounce"
    r = day.iloc[0]
    assert r.side == -1 and abs(r.level - 4316.2) <= 1.5, (r.level, r.th)
    # the learned stop exists by then and only uses signals resolved before the decision
    assert r.b80 is not None and np.isfinite(r.b80)
    earlier = S[(S.resolved <= r.t_ns) & S.won]
    assert len(earlier) >= 30
    assert r.b80 == pytest.approx(np.percentile(earlier.over_A, 80))


def test_the_trade_uses_the_learned_stop_and_the_owners_floors(market):
    M = market
    dec = np.nonzero(plib.window_mask(M.ot).any(axis=1).to_numpy() & (M.ot >= pd.Timestamp("2026-07-01", tz="UTC")))[0]
    S = lvl2.signals(M, dec, lvl2.Params(k=0.5))
    for tg in ("T2", "T1"):
        T = lvl2.trades(M, S, lvl2.Params(k=0.5, target=tg, p=80.0), np.zeros(len(M.o), bool))
        assert not T.empty
        for r in T.itertuples():
            s = S[S.j0 == r.j0].iloc[0]
            stop_px = s.level - s.side * s.b80 * s.a
            assert r.sl == pytest.approx(max((stop_px - s.entry) * -s.side, 0.5 * s.a))
            exp_tp = max(s.tgt2, 5.0) if tg == "T2" else max(r.sl, 5.0)
            assert r.tp == pytest.approx(exp_tp)
            assert r.tp >= 5.0  # the owner's floor
        # one position at a time: a trade starts only after the previous one ended
        assert (T.j0.to_numpy()[1:] > T.xj.to_numpy()[:-1]).all()



def test_the_bounce_start_is_the_entry_timeframes_zigzag_swing(market):
    """2026-10-18 (found by the independent check): on an M15 / M30 entry the start came from the level fractals."""
    from fingerprint import zigzag  # noqa: PLC0415

    M = market
    for tf in ("M1", "M5", "M15", "M30"):
        T = M.tf[tf]
        pb, pp, pt, pc = zigzag(T["h"], T["lo"], T["atr"], 2.0)
        assert (T["zz_b"] == pb).all() and (T["zz_p"] == pp).all()
    dec = np.nonzero(plib.window_mask(M.ot).any(axis=1).to_numpy() & (M.ot >= pd.Timestamp("2026-07-01", tz="UTC")))[0]
    S = lvl2.signals(M, dec, lvl2.Params(k=0.5))
    for r in S.itertuples():
        z = M.tf[r.etf]
        known = z["zz_known"] <= r.t_ns
        assert r.t_px == z["zz_p"][known][-1]  # the latest known ZigZag swing of the entry TF


def test_r_and_usd_and_the_new_york_stop_slippage(market):
    """R = the result / (the stop distance + the stop's slippage); a full stop is exactly -1 R; the slippage is New
    York's (0.20) for a decision in the New York windows, else 0.15; USD = price units at 0.01 lot (1 oz)."""
    M = market
    ny = plib.ny_mask(M.ot)
    dec = np.nonzero(plib.window_mask(M.ot).any(axis=1).to_numpy() & (M.ot >= pd.Timestamp("2026-07-01", tz="UTC")))[0]
    S = lvl2.signals(M, dec, lvl2.Params(k=0.5))
    T = lvl2.trades(M, S, lvl2.Params(k=0.5, target="T1", p=80.0), ny)
    t_idx = M.ot.get_indexer(T.t)
    ss = np.where(ny[t_idx], 0.20, 0.15)
    assert ny[t_idx].any() and (~ny[t_idx]).any()  # both kinds are in the sample
    np.testing.assert_allclose(T.R, T.pnl / (T.sl + ss), rtol=0, atol=1e-12)
    stop = (T.exit == "stop").to_numpy()
    assert stop.any()
    np.testing.assert_allclose(T.R[stop], -1.0, rtol=0, atol=1e-9)
    np.testing.assert_allclose(T.pnl[stop], -(T.sl + ss)[stop], rtol=0, atol=1e-9)
    win = (T.exit == "win").to_numpy()
    np.testing.assert_allclose(T.pnl[win], T.tp[win], rtol=0, atol=1e-12)  # a target pays exactly the target
