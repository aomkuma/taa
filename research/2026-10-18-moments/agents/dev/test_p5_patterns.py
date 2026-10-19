"""p5_patterns by hand: the scale (H on M1 bars, the shape-check day's H), each formation of the owner's set with its
edges, the mirror, the window opens, the fake first leg, the pictures in formation and their scenarios.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_p5_patterns.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5_patterns as F  # noqa: E402

MN = 60 * 10**9
U = lambda s: pd.Timestamp(s, tz="UTC").value  # noqa: E731
MAIN, INN = 10.0, 5.0  # EQ 2.5, SW 5.0


def closes(d, before=100.0, last=111.0, frm=0):
    c = np.full(d + 1, before)
    c[d] = last
    return c


# --- the scale -------------------------------------------------------------------------------------------------------


def test_h_on_m1_and_the_days_h():
    idx = pd.date_range("2026-01-12 10:00", periods=180, freq="1min", tz="UTC")
    rng = np.arange(180.0)
    m = pd.DataFrame(dict(open=100.0, high=100.0 + (rng // 60 + 1), low=100.0, close=100.0), index=idx)
    # H1 bars: high - low 1, 2, 3 (closes 100: true ranges 1, 2, 3); complete at 11:00, 12:00, 13:00
    H = F.day_h1_atr(m)
    assert np.isnan(H[58]) and H[59] == 1.0 and H[119] == 1.5 and H[179] == 2.0  # the bar 10:59 closes at 11:00
    vals = F.map_to_m1(np.array([5, 10]), np.array([1.0, 2.0]), np.array([4, 5, 9, 10, 11]))
    assert np.isnan(vals[0]) and vals[1:].tolist() == [1.0, 1.0, 2.0, 2.0]


# --- double / triple / H&S / retest (buy side by hand) ---------------------------------------------------------------


def s3(t3, p2=112.0, t2=100.0):
    return [(2, t2, -1, False), (5, p2, 1, False), (8, t3, -1, True)]


def test_double_bottom():
    x = F.find5_buy(None, None, closes(10, 105.0, 112.5), s3(100.5), 10, MAIN, INN)
    assert [(p["family"], p["variant"]) for p in x] == [("double", "equal")]
    assert (x[0]["trigger"], x[0]["extreme"], x[0]["height"]) == (112.0, 100.0, 12.0)
    x = F.find5_buy(None, None, closes(10, 105.0, 112.5), s3(96.0), 10, MAIN, INN)  # 4 below: a sweep (<= 5)
    assert [(p["family"], p["variant"]) for p in x] == [("double", "swept")] and x[0]["extreme"] == 96.0
    assert F.find5_buy(None, None, closes(10, 105.0, 112.5), s3(94.9), 10, MAIN, INN) == []  # 5.1 below: too deep
    assert F.find5_buy(None, None, closes(10, 105.0, 112.5), s3(102.6), 10, MAIN, INN) == []  # 2.6 above: not equal
    assert F.find5_buy(None, None, closes(10, 105.0, 112.5), s3(100.5, p2=109.0), 10, MAIN, INN) == []  # 9 tall < 10
    assert F.find5_buy(None, None, closes(10, 105.0, 112.0), s3(100.5), 10, MAIN, INN) == []  # at the trigger


T5 = [(0, 100.0, -1, False), (3, 111.0, 1, False), (6, 100.8, -1, False), (9, 112.0, 1, False), (12, 97.0, -1, True)]


def test_triple_bottom_with_a_sweep():
    # lows 100, 100.8 (within EQ), 97 (3 below the first: a sweep <= 5); highs 111 / 112; height 112 - 97 = 15
    c = closes(14, 105.0, 112.5)
    x = {p["family"]: p for p in F.find5_buy(None, None, c, T5, 14, MAIN, INN)}
    assert set(x) == {"triple", "double"} or set(x) == {"triple"}
    t = x["triple"]
    assert (t["variant"], t["trigger"], t["extreme"], t["height"]) == ("swept", 112.0, 97.0, 15.0)
    assert [lab for _, _, lab in t["points"]] == ["L1", "P1", "L2", "P2", "L3"]
    bad = list(T5)
    bad[2] = (6, 103.0, -1, False)  # the 2nd low 3 above the first (> EQ 2.5)
    assert "triple" not in {p["family"] for p in F.find5_buy(None, None, c, bad, 14, MAIN, INN)}


IHS5 = [(0, 102.0, -1, False), (3, 112.0, 1, False), (6, 96.0, -1, False), (9, 112.5, 1, False), (12, 102.3, -1, True)]


def test_inverse_head_and_shoulders_on_the_big_swings():
    # neckline (3, 112) -> (9, 112.5): at the head 112.25 -> height 16.25; head 96 < 102 - 2.5; at bar 14 the line is
    # 112.9167; the close 113 is above
    c = closes(14, 105.0, 113.0)
    x = {p["family"]: p for p in F.find5_buy(None, None, c, IHS5, 14, MAIN, INN)}
    assert "ihs" in x and x["ihs"]["height"] == pytest.approx(16.25) and x["ihs"]["trigger"] == pytest.approx(112.0 + 11 / 12)
    small = [(b, 100 + (x - 100) * 0.5, k, pv) for b, x, k, pv in IHS5]  # half the size: 8.1 < 10
    assert "ihs" not in {p["family"] for p in F.find5_buy(None, None, closes(14, 102.0, 107.0), small, 14, MAIN, INN)}
    shallow = list(IHS5)
    shallow[2] = (6, 101.0, -1, False)  # the head only 1 below the shoulders (< EQ 2.5); the height 11.25 is enough
    assert "ihs" not in {p["family"] for p in F.find5_buy(None, None, c, shallow, 14, MAIN, INN)}


def test_break_and_retest():
    # a peak 112 at bar 4 that rose 12 from the trough 100 at bar 2; closes above 112 from bar 6 (the break at 6, high
    # 115 at bar 7); the retest trough 110 at bar 10 (within 2.5 of 112); trigger = the high from the break to the
    # retest = 115 (a bounce of 5.0 = the inner swing); close 115.5 at bar 12
    seq = [(2, 100.0, -1, False), (4, 112.0, 1, False), (5, 108.0, -1, False), (7, 115.0, 1, False), (10, 110.0, -1, True)]
    c = np.array([100, 101, 100, 105, 112, 109, 113, 114, 113, 112, 111.5, 113, 115.5], float)
    h = c + 0.5
    h[7] = 115.0
    x = [p for p in F.find5_buy(h, h - 1, c, seq, 12, MAIN, INN) if p["family"] == "retest"]
    assert len(x) == 1 and (x[0]["trigger"], x[0]["extreme"]) == (115.0, 110.0)
    assert [(b, lab) for b, _, lab in x[0]["points"]] == [(4, "level"), (6, "break"), (10, "retest")]
    seq_far = seq[:-1] + [(10, 109.4, -1, True)]  # the retest 2.6 below the level: not held
    assert not [p for p in F.find5_buy(h, h - 1, c, seq_far, 12, MAIN, INN) if p["family"] == "retest"]
    seq_small = seq[:-1] + [(10, 110.1, -1, True)]  # the bounce 4.9 < the inner swing 5
    assert not [p for p in F.find5_buy(h, h - 1, c, seq_small, 12, MAIN, INN) if p["family"] == "retest"]
    seq_low = [(2, 104.0, -1, False)] + seq[1:]  # the level rose only 8 from its trough (< main 10): no level
    assert not [p for p in F.find5_buy(h, h - 1, c, seq_low, 12, MAIN, INN) if p["family"] == "retest"]


def test_the_mirror_names_and_labels():
    p = F.unmirror5(dict(family="triple", variant="swept", extreme=-97.0, trigger=-112.0, height=15.0,
                         points=[(0, -100.0, "L1"), (3, -111.0, "P1"), (12, -97.0, "L3")]))
    assert (p["side"], p["extreme"], p["trigger"]) == (-1, 97.0, 112.0)
    assert [(x, lab) for _, x, lab in p["points"]] == [(100.0, "H1"), (111.0, "T1"), (97.0, "H3")]
    assert F.NAMES5[("triple", -1)] == "triple top" and F.NAMES5[("fake_open", -1)] == "open: fake up, then down"


# --- channel, triangle, base --------------------------------------------------------------------------------------


def test_a_channel_break():
    # a descending channel: peaks 120 (bar 0) and 115 (bar 20), troughs 110 (bar 10) and 105 (bar 30): slopes -0.25
    # both; width at bar 30: upper 112.5 - lower 105 = 7.5 >= 5; 40 bars at bar 40; closes inside, then 111 > the upper
    # line at 40 (110.0) -> buy
    seq = [(0, 120.0, 1, False), (10, 110.0, -1, False), (20, 115.0, 1, False), (30, 105.0, -1, False), (35, 108.0, 1, True)]
    c = np.full(41, 107.0)
    c[40] = 111.0
    x = F.find_channel(c, seq, 40, INN)
    assert len(x) == 1 and (x[0]["side"], x[0]["variant"], x[0]["extreme"]) == (1, "descending", 105.0)
    assert x[0]["trigger"] == pytest.approx(110.0) and x[0]["height"] == pytest.approx(7.5)
    c[40] = 101.0  # below the lower line at 40 (102.5): sell
    assert F.find_channel(c, seq, 40, INN)[0]["side"] == -1
    c[40], c[36] = 111.0, 111.0  # a close exactly on the upper line (111.0 at bar 36) is inside
    assert len(F.find_channel(c, seq, 40, INN)) == 1
    c[36] = 111.1  # an earlier close outside: already broken
    assert F.find_channel(c, seq, 40, INN) == []
    c[36] = 107.0
    assert F.find_channel(c[:30], seq, 29, INN) == []  # 29 bars from the first pivot (< 30)
    steep = [(0, 120.0, 1, False), (10, 110.0, -1, False), (20, 115.0, 1, False), (30, 90.0, -1, False)]
    assert F.find_channel(c, steep, 40, INN) == []  # lower slope -1 against -0.25: not parallel


def test_a_channel_needs_30_bars():
    # peaks 120 (bar 0) and 118 (bar 8), troughs 112 (bar 4) and 110 (bar 12): slopes -0.25 both; the width at bar 12:
    # 117 - 110 = 7 >= 5; closes 111 inside; at bar 20 (20 bars from the first pivot) the close 116 > the upper line
    # 115: too short; the same channel broken at bar 30 (close 113 > 112.5): 30 bars, a break
    seq = [(0, 120.0, 1, False), (4, 112.0, -1, False), (8, 118.0, 1, False), (12, 110.0, -1, False)]
    c = np.full(31, 111.0)
    c[20] = 116.0
    assert F.find_channel(c, seq, 20, INN) == []
    c[20], c[30] = 111.0, 113.0
    x = F.find_channel(c, seq, 30, INN)
    assert len(x) == 1 and x[0]["side"] == 1 and x[0]["trigger"] == pytest.approx(112.5)


def test_a_triangle_break():
    # A 120 (0), B 100 (10), C 115 (20), D 104 (30), E 111 (40): highs fall, lows rise; |A - B| = 20 >= 10; the line
    # A-C at 50 is 107.5, B-D 108.0 -> the lines cross at 50: test at bar 45 (A-C 108.75, B-D 106.0)
    seq = [(0, 120.0, 1, False), (10, 100.0, -1, False), (20, 115.0, 1, False), (30, 104.0, -1, False), (40, 111.0, 1, False)]
    c = np.full(46, 107.0)
    c[45] = 109.0
    x = F.find_triangle(c, seq, 45, MAIN)
    assert len(x) == 1 and x[0]["side"] == 1 and x[0]["trigger"] == pytest.approx(108.75) and x[0]["height"] == 20.0
    assert [lab for _, _, lab in x[0]["points"]] == list("ABCDE")
    c[45] = 105.0
    assert F.find_triangle(c, seq, 45, MAIN)[0]["side"] == -1
    assert F.find_triangle(c, seq, 45, 25.0) == []  # 20 < main 25
    up = [(0, 120.0, 1, False), (10, 100.0, -1, False), (20, 121.0, 1, False), (30, 104.0, -1, False), (40, 111.0, 1, False)]
    assert F.find_triangle(c, up, 45, MAIN) == []  # C above A: not a triangle


def test_a_base5():
    # 25 bars within 9.0 (<= main 10), then a close above
    n = 30
    h, lo = np.full(n, 109.0), np.full(n, 100.0)
    c = np.full(n, 104.0)
    h[:4] = 130.0  # bars 0-3 are too high: the base is bars 4..28 (25 bars)
    c[29] = 110.0
    main = np.full(n, 10.0)
    r20 = (pd.Series(h).rolling(20).max() - pd.Series(lo).rolling(20).min()).to_numpy()
    x = F.find_base5(h, lo, c, main, 29, r20)
    assert len(x) == 1 and x[0]["side"] == 1 and x[0]["box"] == (4, 28, 100.0, 109.0) and x[0]["variant"] == "25 bars"
    main[28] = 8.0  # the base's width is read at d - 1: 9 > 8
    assert F.find_base5(h, lo, c, main, 29, r20) == []
    main[28], main[29] = 10.0, 8.0  # the breakout bar's own width is not read
    assert len(F.find_base5(h, lo, c, main, 29, r20)) == 1
    c[29] = 109.0  # a close at the box top is not beyond it
    assert F.find_base5(h, lo, c, main, 29, r20) == []


# --- the opens and the fake first leg -----------------------------------------------------------------------------


def test_window_opens():
    o = F.window_opens(pd.Timestamp("2026-01-09", tz="UTC"), pd.Timestamp("2026-01-13", tz="UTC"))
    names = [(pd.Timestamp(t, tz="UTC").strftime("%m-%d %H:%M"), n) for t, n in o]
    # Fri 9 Jan: 00:00 Asia, 06:00 London, 14:30 NY (EST); Sat / Sun none (Thai Saturday / Sunday); Mon 12 Jan
    assert names == [("01-09 00:00", "Asia"), ("01-09 06:00", "London"), ("01-09 14:30", "NY"),
                     ("01-12 00:00", "Asia"), ("01-12 06:00", "London"), ("01-12 14:30", "NY")]
    o = F.window_opens(pd.Timestamp("2026-03-09", tz="UTC"), pd.Timestamp("2026-03-10", tz="UTC"))
    assert [pd.Timestamp(t, tz="UTC").strftime("%H:%M") for t, n in o if n == "NY"] == ["13:30"]  # EDT


def fo_bars(path):
    idx = pd.date_range("2026-01-12 14:25", periods=len(path), freq="1min", tz="UTC")
    c = np.array(path, float)
    return idx.as_unit("ns").asi8, c + 0.5, c - 0.5, c


def test_the_fake_first_leg_at_an_open():
    # the NY open 14:30 UTC (bar 5); p0 = 100 (the close of 14:29); bar 7 reaches 106 (6 up >= inn 5): the fake leg up;
    # bar 12 closes 99.0 below p0: SELL there, extreme 107.5 (the highest high so far)
    path = [100] * 5 + [101, 103, 105.5, 107.0, 104, 102, 100.5, 99.0, 97]
    t, h, lo, c = fo_bars(path)
    inn = np.full(len(c), INN)
    x = F.fake_opens(t, h, lo, c, inn, [(U("2026-01-12 14:30"), "NY")])
    assert len(x) == 1 and (x[0]["side"], x[0]["d"], x[0]["trigger"], x[0]["extreme"]) == (-1, 12, 100.0, 107.5)
    # the leg only after 15 minutes: none
    path2 = [100] * 5 + [100.5] * 16 + [106.0, 99.0]
    assert F.fake_opens(*fo_bars(path2), np.full(len(path2), INN), [(U("2026-01-12 14:30"), "NY")]) == []
    # the reversal only after 60 minutes: none
    path3 = [100] * 5 + [106.0] + [103.0] * 61 + [99.0]
    assert F.fake_opens(*fo_bars(path3), np.full(len(path3), INN), [(U("2026-01-12 14:30"), "NY")]) == []


# --- pictures in formation ---------------------------------------------------------------------------------------


def test_two_tops_in_formation_and_its_scenarios():
    # P_a 120 (bar 2), T 108 (bar 5), P_b 120.5 (bar 8, the running peak); the close at bar 10 = 117.5 (3 below P_b >=
    # EQ 2.5); the lowest low since P_b 117.0; height 120.5 - 108 = 12.5 >= 10
    seq = [(0, 100.0, -1, False), (2, 120.0, 1, False), (5, 108.0, -1, False), (8, 120.5, 1, True)]
    c = np.full(11, 115.0)
    c[10] = 117.5
    lo = c - 0.5
    lo[9] = 117.0
    f = F.forming_tops(c + 0.5, lo, c, seq, 10, MAIN, INN)
    assert f["kind"] == "two tops" and f["top"] == 120.5 and f["low"] == 117.0 and f["height"] == 12.5
    assert f["a"] == dict(side=-1, trigger=117.0, stop=121.5, target=104.5)
    assert f["b"] == dict(side=1, trigger=120.5, stop=116.0, target=133.0)
    c2 = c.copy()
    c2[10] = 118.5  # only 2 below P_b (< EQ): not yet a pullback
    assert F.forming_tops(c2 + 0.5, lo, c2, seq, 10, MAIN, INN) is None
    c3 = c.copy()
    c3[9] = 121.0  # a close above the top since P_b: the picture broke up
    assert F.forming_tops(c3 + 0.5, lo, c3, seq, 10, MAIN, INN) is None
    far = seq[:-1] + [(8, 126.0, 1, True)]  # P_b 6 above P_a (> SW 5)
    assert F.forming_tops(np.full(11, 127.0), lo, c, far, 10, MAIN, INN) is None


def test_two_bottoms_by_the_mirror():
    # the same picture upside down through forming_at: P_a 80, T 92, P_b 79.5; the close 82.5
    h = np.full(11, 85.5)
    lo = np.full(11, 84.5)
    c = np.full(11, 85.0)
    c[10] = 82.5
    h[9] = h[10] = 83.0  # the highest high since P_b (bars 9 - 10): 83.0
    lo[2], h[5], lo[8] = 80.0, 92.0, 79.5
    piv = (np.array([0, 2, 5, 8]), np.array([100.0, 80.0, 92.0, 79.5]), np.array([1, -1, 1, -1]), np.array([1, 4, 7, 99]))
    pc = (piv[0][:3], piv[1][:3], piv[2][:3], piv[3][:3])
    mir = (-lo, -h, -c, F.P.mirror_piv(pc))
    out = F.forming_at(h, lo, c, np.full(11, MAIN / F.K_MAIN), pc, mir, 10)
    two = [x for x in out if x["kind"] == "two bottoms"]
    assert len(two) == 1 and two[0]["top"] == 79.5 and two[0]["low"] == 83.0
    # A (the bottoms hold): buy above 83.0, the stop 79.5 - 0.2 x 5 = 78.5, the target 83 + 12.5 = 95.5
    assert two[0]["a"] == dict(side=1, trigger=83.0, stop=pytest.approx(78.5), target=pytest.approx(95.5))
    assert two[0]["b"] == dict(side=-1, trigger=79.5, stop=pytest.approx(84.0), target=pytest.approx(67.0))
