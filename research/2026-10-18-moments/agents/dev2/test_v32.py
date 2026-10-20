"""Hand-worked tests for V3-2 (v32.py, tsim32.py, v32_run.py's metrics) and rules 18-19 in swings.py. Every expected
number was worked out by hand from the bars / ticks written in the test (the working is in the comments).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev2/test_v32.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "precursors"))
import swings as W  # noqa: E402
import tsim32 as S  # noqa: E402
import v32  # noqa: E402
import v32_run as RUN  # noqa: E402
from test_swings import MAIN, T0, bars_from, const10, walk  # noqa: E402

MIN = S.NS_MIN


def mkt(m: pd.DataFrame, h_const: float = 8.0) -> v32.Mkt:
    """A market on synthetic bars with S = 10 everywhere and the H1 ATR set to a constant (no complete H1 bar)."""
    R = W.analyze_all(m, s_fn=const10, path=True)
    mk = v32.market(m, R)
    mk.H = np.full(len(m), h_const)
    mk.S = np.full(len(m), 10.0)  # the same S the swings were built with
    return mk


@pytest.fixture(scope="module")
def main_mk():
    return mkt(bars_from(walk(MAIN), start=100.0))


# ------------------------------------------------------------------ R1 / R2: the windows and the entry TF
def test_windows_follow_the_us_summer_time():
    ts = ["2025-11-05 00:30", "2025-11-05 01:59", "2025-11-05 02:00", "2025-11-05 06:00", "2025-11-05 07:00",
          "2025-10-29 12:30", "2025-10-29 13:29", "2025-10-29 13:30",  # EDT: 08:30 / 09:29 / 09:30 NY
          "2025-11-05 12:30", "2025-11-05 13:30", "2025-11-05 14:30", "2025-11-05 18:29", "2025-11-05 18:30"]  # EST
    t = W._ns(pd.DatetimeIndex(ts, tz="UTC"))
    assert v32.window_of(t).tolist() == ["Asia", "Asia", "other", "London", "other", "NY0830", "NY0830", "NYopen",
                                         "other", "NY0830", "NYopen", "NYopen", "other"]
    b = v32.ny_bucket(W._ns(pd.DatetimeIndex(["2025-11-05 14:30", "2025-11-05 15:05", "2025-11-05 18:29",
                                               "2025-11-05 13:30"], tz="UTC")))
    assert b.tolist() == ["09:30", "10:00", "13:00", ""]


def test_entry_tf_by_the_terciles():
    got = v32.choose_tf(np.array([10, 14.5, 16, 18.4, 30, np.nan]), 14.5, 18.4)
    assert got.tolist() == ["M1", "M5", "M5", "M15", "M15", ""]


def test_parts():
    t = W._ns(pd.DatetimeIndex(["2025-10-17 23:59", "2025-10-18 00:00", "2026-01-15 23:59", "2026-01-16 00:00",
                                "2026-04-17 23:59", "2026-04-18 00:00"], tz="UTC"))
    assert v32.part_of(t).tolist() == ["", "P1", "P1", "P2", "P2", ""]


# ------------------------------------------------------------------ R4: entry 1
def test_entry1_from_the_box_bottom_retest_fail(main_mk):
    # test_swings: the box bottom 99 accepted down at bar 74, retest at 81, retest_fail at 82 with the extreme 98.
    # -> a sell decided at bar 82's close (T0 + 83 min), stop 98 + 0.25 x 10 = 100.5, the first fail of the level.
    e = v32.entry1(main_mk, "M1")
    x = e[e.tag == "box_bot"]
    assert len(x) == 1
    r = x.iloc[0]
    assert r.t_dec == W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=83)]))[0]
    assert (r.side, r.ext, r.stop, r["first"], r.line, r.j_dec) == (-1, 98.0, 100.5, True, False, 82)
    # the M1 label at bar 82: highs (115, 118) HH, lows (99, the running 90) LL -> mixed: not aligned
    assert not r.al_label


# ------------------------------------------------------------------ R5: entry 2
BASE = walk([100, 120, 100]) + [101, 100, 101, 100, 101, 100, 101, 100]


def test_entry2_base_trigger(monkeypatch):
    # closes: bars 0-9 up to 120, 10-19 down to 100, 20-27 flat 101 / 100. The peak@9 (120) is confirmed at bar 14
    # (low 110). ATR14 of M1 = 2 (every walk bar's true range is 2). The six bars 18..23: highs max 104 (bar 18: 104 ->
    # 102), lows min 100 -> span 4 <= 2 x ATR(bar 17) = 4, all after bar 9, top 104 < 120 -> the base holds first at
    # bar 23 (bars 17..22 span 106 - 100 = 6 > 4). It keeps holding to bar 27: one trigger. A buy needs the bottom above
    # the last trough (100 at bar 0): 100 is not above -> none.
    m = bars_from(BASE, start=100.0)
    mk = mkt(m)
    monkeypatch.setattr(v32, "aligned", lambda mk_, tf, what, t, side, mode="path": np.ones(len(np.atleast_1d(side)), bool))
    b = v32.base_triggers(mk, "M1", "bias")
    assert b[["side", "j_dec", "piv", "top", "bot"]].values.tolist() == [[-1, 23, 120.0, 104.0, 100.0]]
    e = v32.entry2(mk, "M1", "bias")
    assert e.stop.tolist() == [122.5] and e.t_dec.tolist() == [W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=24)]))[0]]


def test_entry2_needs_alignment(monkeypatch):
    m = bars_from(BASE, start=100.0)
    mk = mkt(m)
    monkeypatch.setattr(v32, "aligned", lambda mk_, tf, what, t, side, mode="path": np.zeros(len(np.atleast_1d(side)), bool))
    assert len(v32.base_triggers(mk, "M1", "bias")) == 0


class _Stub:
    def __init__(self, avail_min, vals):
        self.av = W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=x) for x in avail_min]))
        self.struct = pd.DataFrame({"label": vals, "bias": vals}, dtype=float)

    def at(self, t):
        return np.searchsorted(self.av, np.asarray(t, np.int64), side="right") - 1


def test_aligned_reads_every_tf_up_to_h1_on_the_path():
    # M15 reads -1 from minute 15, M30@M1 -1 from 30, H1@M1 -1 from 60 but H1 (bars) +1; M5@M1 -1. At minute 61 the
    # path reading is aligned down from M5 up, the bar reading is not (H1 +1); at minute 45 H1@M1 is unknown.
    R = {"M5@M1": _Stub([5], [-1]), "M15@M1": _Stub([15], [-1]), "M30@M1": _Stub([30], [-1]), "H1@M1": _Stub([60], [-1]),
         "M5": _Stub([5], [-1]), "M15": _Stub([15], [-1]), "M30": _Stub([30], [-1]), "H1": _Stub([60], [1]),
         "M1": _Stub([1], [-1])}
    mk = v32.Mkt(None, R, None, None, None, (), {})
    t = W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=61), T0 + pd.Timedelta(minutes=45)]))
    assert v32.aligned(mk, "M5", "bias", t, [-1, -1], "path").tolist() == [True, False]
    assert v32.aligned(mk, "M5", "bias", t, [-1, -1], "bar").tolist() == [False, False]
    assert v32.aligned(mk, "M1", "label", t, [-1, -1], "path").tolist() == [True, False]
    assert v32.aligned(mk, "M5", "bias", t, [1, 1], "path").tolist() == [False, False]


# ------------------------------------------------------------------ R6: entry 3 on the box edges
def test_entry3_box_events(main_mk):
    # box bottom 99 (bar 53 break, 54 sweep; 73 break, 74 accepted, 82 retest_fail at 98, 93 reclaim); H = 8.
    # sweep@54: back inside = buy; the break's extreme = min low of bars 53..54 = 99 -> ext stop 99 - 2 = 97; close 101
    #   -> the mirror distance |101 - 97| = 4.
    # retest_fail@82 (ii): buy; extreme min low 73..82 = 90 (bar 77) -> 88; mirror_of = 98 + 2.5 = 100.5 (the sell's
    #   stop).
    # reclaim@93 (i): buy; min low 73..93 = 88 (bar 86) -> 86; close 102 -> distance 16.
    e = v32.entry3(main_mk, "M1", pd.DataFrame(), pd.DataFrame())
    got = e[["j_dec", "side", "kind3", "stop_ext"]].values.tolist()
    assert got == [[54, 1, "i", 97.0], [82, 1, "ii", 88.0], [93, 1, "i", 86.0]]
    assert e.mirror_dist.iloc[0] == pytest.approx(4.0) and e.mirror_dist.iloc[2] == pytest.approx(16.0)
    assert e.mirror_of.iloc[1] == pytest.approx(100.5) and np.isnan(e.mirror_of.iloc[0])


def test_entry3_dedupe_keeps_the_first_source():
    df = pd.DataFrame({"t_dec": [5, 5, 5, 7], "side": [1, 1, -1, 1], "prio": [2, 0, 1, 3], "x": ["b_ii", "b_i", "e_i", "e_ii"]})
    got = df.sort_values(["t_dec", "side", "prio"]).drop_duplicates(["t_dec", "side"], keep="first")
    assert got.x.tolist() == ["e_i", "b_i", "e_ii"]


# ------------------------------------------------------------------ R8: entry 4
FAKE = [101, 102, 103, 104, 102, 100, 99, 98, 97, 96]


def test_entry4_fake_leg(monkeypatch):
    # T0 = 2025-11-05 00:00 UTC (the Asia open). p0 = 100 (bar 0's open), A = 0.3 x 10 = 3: bar 2's high 103 reaches
    # p0 + 3 (its close 00:03). M1: bar 4 closes 102, bar 5 100 (not below), bar 6 99 < 100 -> decision 00:07; the
    # highest high of bars 0..6 = 104 -> stop 106.5. M5: bar 0 (00:00-00:04) closes 102; bar 1 (00:05-00:09) closes 96
    # -> decision 00:10, the highest high of bars 0..9 = 104 -> 106.5.
    m = bars_from(FAKE, start=100.0)
    mk = mkt(m)
    monkeypatch.setattr(v32.W, "readings_at", lambda R, t, tfs=None, mode="bar": pd.DataFrame(
        {"trend_bias": np.full(len(t), -1.0), "trend": np.full(len(t), 0.0)}))
    e1 = v32.entry4(mk, "M1", "bias")
    assert e1[["side", "p0", "ext", "stop", "open"]].values.tolist() == [[-1, 100.0, 104.0, 106.5, "Asia"]]
    assert e1.t_dec.iat[0] == W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=7)]))[0]
    e5 = v32.entry4(mk, "M5", "bias")
    assert e5.t_dec.iat[0] == W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=10)]))[0] and e5.stop.iat[0] == 106.5
    assert len(v32.entry4(mk, "M1", "label")) == 0  # the label trend is 0 -> no trade


# ------------------------------------------------------------------ R7: the target candidates and the trail
def test_pick_target():
    c = [101, 103, 105, np.nan]
    assert S.pick_target(100, 1, 1.0, c, 2.0, None) == 103
    assert S.pick_target(100, 1, 1.0, c, 1.0, 2.0) == 101
    assert S.pick_target(100, 1, 1.0, c, 6.0, 2.0) == 102
    assert np.isnan(S.pick_target(100, 1, 1.0, c, 6.0, None))
    assert S.pick_target(100, -1, 1.0, [97, 99.5, 101], 1.0, 2.0) == 97


def test_trail_steps(main_mk):
    # the M1 inner swings (thr 3) on MAIN turn at every waypoint. A sell decided at bar 64 (j_dec): the peaks against
    # it with bar >= 64 confirmed after 64: 98 at bar 81 (confirmed at 83, when the low 95 is 3 below) and 110 at 97
    # (confirmed at 99). Each -> its price + 2.5, dated at its confirming bar's close.
    pb, pp, pk, pc = main_mk.R["M1"].inner
    pk_ = [(int(b), float(p), int(c)) for b, p, k, c in zip(pb, pp, pk, pc) if k == 1 and b >= 64]
    assert pk_ == [(81, 98.0, 83), (97, 110.0, 99)]
    t_out = W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=200)]))[0]
    st = v32.trail_steps(main_mk, "M1", 64, -1, 10.0, t_out)
    assert st == [(W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=84)]))[0], 100.5),
                  (W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=100)]))[0], 112.5)]
    # a step after t_out is left out
    assert len(v32.trail_steps(main_mk, "M1", 64, -1, 10.0, W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=90)]))[0])) == 1


def test_candidates_hold_the_box_edges(main_mk):
    # at bar 60's close the M1 reference box is [99, 121]; no complete M15 / H1 / H4 bar holds pivots yet
    t = W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=61)]))
    c = v32.candidates(main_mk, "M1", t, [])[0]
    assert 121.0 in c and 99.0 in c


# ------------------------------------------------------------------ the tick simulator
def ticks(rows):
    t = np.array([int(r[0] * MIN) for r in rows], np.int64)
    return t, np.array([r[1] for r in rows], float), np.array([r[2] for r in rows], float)


def test_sim_stop_and_target():
    # a buy at 0: fill at the ask 100.2; stop 99 -> risk 1.2; 2 R -> target 102.6
    tk = ticks([(0, 100.0, 100.2), (1, 99.5, 99.7), (2, 98.9, 99.1), (3, 103, 103.2)])
    r = S.sim(*tk, t_in=0, side=1, t_out=60 * MIN, stop=99.0, target_r=2.0)
    assert (r["exit"], r["fill"], r["exit_px"]) == ("stop", 100.2, 98.9)
    assert r["pnl"] == pytest.approx(-1.3) and r["R"] == pytest.approx(-1.3 / 1.2)
    tk = ticks([(0, 100.0, 100.2), (1, 101.5, 101.7), (2, 102.6, 102.8), (3, 98, 98.2)])
    r = S.sim(*tk, t_in=0, side=1, t_out=60 * MIN, stop=99.0, target_r=2.0)
    assert r["exit"] == "target" and r["pnl"] == pytest.approx(2.4) and r["R"] == pytest.approx(2.0)
    assert r["mfe"] == pytest.approx(2.4) and r["mae"] == pytest.approx(1.3)


def test_sim_sell_uses_the_ask_and_the_time_exit():
    # a sell fills at the bid 100; stop 101 (risk 1); no target; the time: the first tick at / after 5 min, at its ask
    tk = ticks([(0, 100.0, 100.2), (2, 99.0, 99.2), (5, 99.5, 99.7), (6, 90, 90.2)])
    r = S.sim(*tk, t_in=0, side=-1, t_out=5 * MIN, stop=101.0)
    assert (r["exit"], r["exit_px"]) == ("time", 99.7) and r["pnl"] == pytest.approx(0.3)


def test_sim_gap_no_fill_and_fill_past_the_stop():
    tk = ticks([(0, 100.0, 100.2), (1, 100.5, 100.7), (41, 90, 90.2)])
    r = S.sim(*tk, t_in=0, side=1, t_out=120 * MIN, stop=99.0)
    assert (r["exit"], r["exit_px"]) == ("break", 100.5)  # out at the last tick before the 40-minute gap
    tk = ticks([(6, 100.0, 100.2), (7, 101, 101.2)])
    assert S.sim(*tk, t_in=0, side=1, t_out=60 * MIN, stop=99.0) is None  # no tick within 5 minutes
    tk = ticks([(0, 100.0, 100.2), (1, 101, 101.2)])
    assert S.sim(*tk, t_in=0, side=-1, t_out=60 * MIN, stop=99.0) is None  # a sell at 100 with its stop below


def test_sim_trail_only_tightens_and_starts_at_its_time():
    # a sell at the bid 100, stop 103. Steps: at 2 min -> 100.5 (tighter), at 2 min -> 104 (looser, ignored).
    # 1 min: ask 101 (under 103: no stop); 3 min: ask 100.6 >= 100.5 -> stopped at 100.6.
    tk = ticks([(0, 100.0, 100.2), (1, 100.8, 101.0), (3, 100.4, 100.6), (4, 95, 95.2)])
    r = S.sim(*tk, t_in=0, side=-1, t_out=60 * MIN, stop=103.0, trail=[(2 * MIN, 100.5), (2 * MIN, 104.0)])
    assert (r["exit"], r["exit_px"], r["stop_last"]) == ("stop", 100.6, 100.5) and r["R"] == pytest.approx(-0.6 / 3)
    # the same step dated at 1 min would have stopped the 1-minute tick (ask 101 >= 100.5)
    r = S.sim(*tk, t_in=0, side=-1, t_out=60 * MIN, stop=103.0, trail=[(1 * MIN, 100.5)])
    assert r["exit_px"] == 101.0


def test_sim_mirror_stop_dist_and_slip():
    tk = ticks([(0, 100.0, 100.2), (1, 50, 50.2)])
    # a sell (the opposite of a buy rule whose stop is 98): the buy's fill would be the ask 100.2 -> distance 2.2 ->
    # the sell's stop 100 + 2.2 = 102.2
    r = S.sim(*tk, t_in=0, side=-1, t_out=60 * MIN, mirror_of=98.0, target_r=1.0)
    assert r["stop0"] == pytest.approx(102.2) and r["risk"] == pytest.approx(2.2) and r["target"] == pytest.approx(97.8)
    r = S.sim(*tk, t_in=0, side=1, t_out=60 * MIN, stop_dist=1.5)
    assert r["stop0"] == pytest.approx(98.7)
    r = S.sim(*tk, t_in=0, side=1, t_out=60 * MIN, stop=99.0, slip=0.1)
    assert r["fill"] == pytest.approx(100.3)


def test_sim_ran_later():
    # a buy stopped at 1 min (bid 98.9); within the next hour the bid reaches 101.4 = fill + 1.2 = 1 R
    tk = ticks([(0, 100.0, 100.2), (1, 98.9, 99.1), (30, 101.4, 101.6), (70, 110, 110.2)])
    r = S.sim(*tk, t_in=0, side=1, t_out=120 * MIN, stop=99.0)
    assert r["after_best"] == pytest.approx(1.2)  # the 70-minute tick is outside the hour


def test_ticks_refuse_the_exam():
    with pytest.raises(RuntimeError):
        S.day_ticks(pd.Timestamp("2026-04-18"))
    assert S.Ticks()._day(pd.Timestamp("2026-04-18", tz="UTC")) is None  # the cache refuses without reading


# ------------------------------------------------------------------ the metrics
def test_metrics_by_hand():
    assert RUN.drawdown(np.array([1, -2, -1, 3.0])) == 3.0  # equity 0, 1, -1, -2, 1
    assert RUN.streak(np.array([1, -1, 0, -2, 1.0])) == 3  # a zero counts as a loss (win = pnl > 0)
    T = pd.DataFrame({"t_fill": [0, 5, 10, 25], "exit_t": [10, 12, 20, 30]})
    assert RUN.one_at_a_time(T).t_fill.tolist() == [0, 10, 25]
    T = pd.DataFrame({"t_fill": [3, 1, 2], "pnl": [2.0, -1.0, 0.0], "R": [1.0, -1.0, 0.0], "exit": ["target", "stop", "time"],
                      "part": "P1"})
    s = RUN.summ(T, "P1")
    assert (s["n"], s["R"], s["win"], s["dd"], s["streak"], s["usd"]) == (3, 0.0, pytest.approx(1 / 3), 1.0, 2, 1.0)
    assert RUN.summ2(T) == (3, 0.0, pytest.approx(1 / 3), 1.0, 2)


def test_loser_reason():
    T = pd.DataFrame({"risk": [2.0, 2.0, 2.0], "mfe": [0.5, 1.5, 1.5], "after_best": [5.0, 2.0, 1.0]})
    assert RUN.loser_reason(T).tolist() == ["wrong way", "ran later", "no run"]


# ------------------------------------------------------------------ rules 18 / 19 (swings.py)
def test_path_reading_h1_on_the_m1_path():
    # MAIN with S = 10: the first H1 bar (bars 0-59) is complete at bar 59's close, its true range 121 - 99 = 22 -> the
    # threshold is 10 to bar 58 and 22 from bar 59. To bar 58 the pivots are M1's (0, 9, 18, 28, 38, 45, 53, confirmed
    # 4 .. 58). Then the peak 118 (bar 63) is confirmed when the low reaches 96 (bar 74: 118 - 96 = 22); the trough
    # tracked from 74 moves to 90 (77) and 88 (86); 110 - 88 = 22 at bar 97 confirms it. 110 -> 99 (11) does not.
    m = bars_from(walk(MAIN), start=100.0)
    p = W.analyze_path(m, "H1", s_fn=const10)
    assert p.thr[58] == 10 and p.thr[59] == 22
    assert p.piv[0].tolist() == [0, 9, 18, 28, 38, 45, 53, 63, 86]
    assert p.piv[3].tolist() == [4, 14, 23, 33, 43, 50, 58, 74, 97]
    # bar 80: highs (115, 118) HH; lows (99, the running 90) LL -> mixed; the bias -1 from bar 73 (close 98 < 99)
    assert (p.struct.label[80], p.struct.bias[80], p.struct.bias_bar[80]) == (0, -1, 73)
    # bar 100: troughs (99, 88) LL, peaks (115, 118) HH -> mixed; the bar reading (M1, thr 10) has the peak 110 too
    R = {"M1": W.analyze(m, "M1", s_fn=const10), "H1@M1": p, "H1": W.analyze(m, "H1", s_fn=const10)}
    t = W._ns(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=81)]))
    assert W.readings_at(R, t, tfs=("H1",), mode="path").H1_label.tolist() == [0.0]
    assert np.isnan(W.readings_at(R, t, tfs=("H1",), mode="bar").H1_label.iat[0])  # one H1 bar: no pivots yet


def test_edge_visits_by_hand():
    # top 10, bottom 0 -> the top quarter from 7.5; S = 3 -> leaving = a low <= 4.5.
    # bar: (high, low): 0 (5, 4); 1 (8, 6) test; 2 (7, 5) not left; 3 (9, 7) not armed; 4 (6, 4) left; 5 (3, 2);
    # 6 (8, 6) test; 7 (7.5, 7) not armed; 8 (9, 4.4) leaves and reaches in one bar -> test
    h = np.array([5, 8, 7, 9, 6, 3, 8, 7.5, 9])
    lo = np.array([4, 6, 5, 7, 4, 2, 6, 7, 4.4])
    assert W.edge_visits(h, lo, np.full(9, 3.0), 10.0, 0.0, 1) == [1, 6, 8]
    assert W.edge_visits(-lo + 10, -h + 10, np.full(9, 3.0), 10.0, 0.0, -1) == [1, 6, 8]  # the bottom, mirrored


def test_ticks_cache_goes_back_in_time():
    # a later day, then an earlier one (a new spec file starts again at P1): the earlier day must load, not be evicted
    tk = S.Ticks()
    a = tk.span(pd.Timestamp("2026-01-20 05:00", tz="UTC").value)
    tk.span(pd.Timestamp("2026-01-22 05:00", tz="UTC").value)  # four later days loaded (01-20 .. 01-23)
    b = tk.span(pd.Timestamp("2025-10-20 05:00", tz="UTC").value)
    assert a is not None and b is not None and b[0][0] < a[0][0]
    assert pd.Timestamp(int(b[0][0]), tz="UTC").normalize() == pd.Timestamp("2025-10-20", tz="UTC")


def test_sim_one_tick_reaching_the_stop_and_the_target_is_a_stop():
    # a buy at 100.2, stop 99, target 2 R = 102.6; a trail step at 1 min lifts the stop to 103 (above the target).
    # The 1-minute tick (bid 102.7) reaches both -> the stop, at the market 102.7 (not the target's 102.6).
    tk = ticks([(0, 100.0, 100.2), (1, 102.7, 102.9), (2, 90, 90.2)])
    r = S.sim(*tk, t_in=0, side=1, t_out=60 * MIN, stop=99.0, target_r=2.0, trail=[(1 * MIN, 103.0)])
    assert (r["exit"], r["exit_px"]) == ("stop", 102.7)


def test_drawdown_from_the_start():
    assert RUN.drawdown(np.array([-2.0, 1.0])) == 2.0  # equity 0, -2, -1: the first loss is a fall from 0
