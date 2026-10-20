"""Hand-worked tests for swings.py (V3-1; the rules in DEV_LOG.md). Every expected number below was worked out by hand
from the bars written in the test (the working is in the comments), not read from the code's output.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev2/test_swings.py -q
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
import indicators as IND  # noqa: E402
import swings as W  # noqa: E402

T0 = pd.Timestamp("2025-11-05 00:00", tz="UTC")  # a Wednesday in P1


def const10(t_ns):
    return np.full(len(t_ns), 10.0)


def bars_from(closes, start=100.0, t0=T0) -> pd.DataFrame:
    """M1 bars without wicks: open = the previous close, high / low = max / min of open and close."""
    o = np.r_[start, closes[:-1]]
    c = np.asarray(closes, float)
    idx = pd.date_range(t0, periods=len(c), freq="1min")
    return pd.DataFrame({"open": o, "high": np.maximum(o, c), "low": np.minimum(o, c), "close": c}, index=idx)


def walk(waypoints, step=2.0):
    """The closes from waypoints[0] through each waypoint in steps of at most `step` USD."""
    out, x = [], float(waypoints[0])
    for w in waypoints[1:]:
        while abs(w - x) > 1e-9:
            x = x + np.sign(w - x) * min(step, abs(w - x))
            out.append(round(x, 6))
    return out


# The main path (S = 10): 100 -> 120 -> 102 -> 121 -> 101 -> 115 -> 99 -> 118 -> 90 -> 98 -> 88 -> 110 -> 99.
# Bars (closes): 0-9 up to 120, 10-18 down to 102, 19-28 up to 121 (bar 28: 120 -> 121), 29-38 down to 101, 39-45 up
# to 115, 46-53 down to 99, 54-63 up to 118 (bar 63: 117 -> 118), 64-77 down to 90, 78-81 up to 98, 82-86 down to 88,
# 87-97 up to 110, 98-103 down to 99 (bar 103: 100 -> 99).
MAIN = [100, 120, 102, 121, 101, 115, 99, 118, 90, 98, 88, 110, 99]


@pytest.fixture(scope="module")
def main_m():
    return bars_from(walk(MAIN), start=100.0)


@pytest.fixture(scope="module")
def main_r(main_m):
    return W.analyze(main_m, "M1", inner=True, s_fn=const10)


# ------------------------------------------------------------------ rule 2: the swing detector
def test_zigzag_by_hand():
    # thr 10. Bar: (high, low)
    # 0 (100, 99); 1 (103, 100): hi 1, lo 0, 4 apart; 2 (111, 104): 111 - 99 = 12 >= 10 -> trough@0 (99), confirmed 2;
    # 3 (115, 110) new high -> peak bar 3; 4 (114, 106): 115 - 106 = 9; 5 (113, 104): 11 -> peak@3 (115), confirmed 5;
    # 6 (108, 101): new low; 7 (111, 103): 111 - 101 = 10 -> trough@6 (101), confirmed 7;
    # 8 (125, 99): a wide bar: a new high, so its low is not read (no two turns in one bar);
    # 9 (124, 116): 125 - 116 = 9; 10 (118, 114): 11 -> peak@8 (125), confirmed 10; the trough tracked from bar 10
    # (114), never from the wide bar 8's own low 99; 11 (117, 112): a new low; 12 (124, 115): 124 - 112 = 12 ->
    # trough@11 (112), confirmed 12.
    h = np.array([100, 103, 111, 115, 114, 113, 108, 111, 125, 124, 118, 117, 124], float)
    lo = np.array([99, 100, 104, 110, 106, 104, 101, 103, 99, 116, 114, 112, 115], float)
    pb, pp, pk, pc = W.zigzag(h, lo, np.full(13, 10.0))
    assert pb.tolist() == [0, 3, 6, 8, 11]
    assert pp.tolist() == [99, 115, 101, 125, 112]
    assert pk.tolist() == [-1, 1, -1, 1, -1]
    assert pc.tolist() == [2, 5, 7, 10, 12]
    assert all(c > b for b, c in zip(pb, pc))  # every pivot confirmed on a later bar


def test_zigzag_threshold_read_at_the_confirming_bar():
    # the same bars, thr[5] = 12: bar 5's 11-USD drop no longer confirms; bar 6 (low 101): 115 - 101 = 14 >= 10 ->
    # peak@3 confirmed at 6; the trough tracked from bar 6 (101); bar 7: 111 - 101 = 10 -> trough@6 confirmed 7.
    h = np.array([100, 103, 111, 115, 114, 113, 108, 111, 125, 124, 118], float)
    lo = np.array([99, 100, 104, 110, 106, 104, 101, 103, 99, 116, 114], float)
    thr = np.full(11, 10.0)
    thr[5] = 12.0
    pb, pp, pk, pc = W.zigzag(h, lo, thr)
    assert pb.tolist() == [0, 3, 6, 8] and pc.tolist() == [2, 6, 7, 10]


def test_zigzag_tie_keeps_the_first_bar_and_wide_first_bar():
    # 0 (100, 99); 1 (111, 104): 12 -> trough@0 confirmed 1; 2 (111, 108): a tie, the peak stays at 1; 3 (109, 100):
    # 111 - 100 = 11 -> peak@1 confirmed 3.
    pb, pp, pk, pc = W.zigzag(np.array([100, 111, 111, 109.0]), np.array([99, 104, 108, 100.0]), np.full(4, 10.0))
    assert pb.tolist() == [0, 1] and pc.tolist() == [1, 3]
    # a wide first bar (120 / 100) is both extremes: no pivot until another bar holds one of them; bar 2 (121, 112):
    # the high moves to 2, the low stays at 0: 21 apart -> trough@0 (100) confirmed 2.
    pb, pp, pk, pc = W.zigzag(np.array([120, 115, 121.0]), np.array([100, 105, 112.0]), np.full(3, 10.0))
    assert pb.tolist() == [0] and pp.tolist() == [100] and pc.tolist() == [2]
    # one wide bar alone never makes a pivot
    assert len(W.zigzag(np.array([130.0]), np.array([100.0]), np.array([10.0]))[0]) == 0


def test_main_path_pivots(main_r):
    # worked in the MAIN comment: thr 10 (S = 10, the M1 ATR about 2)
    pb, pp, pk, pc = main_r.piv
    assert pb.tolist() == [0, 9, 18, 28, 38, 45, 53, 63, 86, 97]
    assert pp.tolist() == [100, 120, 102, 121, 101, 115, 99, 118, 88, 110]
    assert pc.tolist() == [4, 14, 23, 33, 43, 50, 58, 68, 91, 102]
    assert np.allclose(main_r.thr, 10.0)


def test_known_at_and_running(main_m, main_r):
    h, lo = main_m.high.to_numpy(), main_m.low.to_numpy()
    k = W.known_at(main_r.piv, 37)  # pivots confirmed by bar 37: 0, 9, 18, 28
    assert k[0].tolist() == [0, 9, 18, 28]
    assert W.running(main_r.piv, h, lo, 37) == (37, 103.0, -1)  # after peak@28: lowest low of bars 29..37 = 103 (bar 37)
    assert W.running(main_r.piv, h, lo, 2) is None


def test_known_at_the_confirming_bar_exactly(main_r):
    # the measurer's gap (a): the MAIN pivots are confirmed at bars 4, 14, 23, 33, 43, ... At d = 32 the peak@28
    # (confirmed at 33) is not known yet; reading one bar ahead (d + 1 = 33) would include it. At d = 33 it is known.
    assert W.known_at(main_r.piv, 32)[0].tolist() == [0, 9, 18]
    assert W.known_at(main_r.piv, 33)[0].tolist() == [0, 9, 18, 28]
    assert W.known_at(main_r.piv, 3)[0].tolist() == []  # the first pivot is confirmed at bar 4
    assert W.known_at(main_r.piv, 4)[0].tolist() == [0]


def test_running_leaves_out_the_pivot_bar():
    # the measurer's gap (b): a pivot bar whose own low (for a peak) is below every later bar's low. The pivots are
    # given by hand: a trough at bar 0 (confirmed 1), a peak at bar 2 (high 120, low 90; confirmed 3).
    # bars:     0    1    2    3    4    5
    h = np.array([100, 110, 120, 108, 106, 109.0])
    lo = np.array([95, 100, 90, 96, 93, 97.0])
    piv = (np.array([0, 2]), np.array([95.0, 120.0]), np.array([-1, 1]), np.array([1, 3]))
    # at d = 5: the running leg after the peak@2 is bars 3..5 -> the lowest low 93 at bar 4 (bar 2's 90 not read)
    assert W.running(piv, h, lo, 5) == (4, 93.0, -1)
    # mirrored: a trough bar whose own high is above every later high. A peak at bar 0 (confirmed 1), a trough at
    # bar 2 (low 80, high 125; confirmed 3); bars 3..5 highs 100, 104, 99 -> the highest 104 at bar 4.
    h2 = np.array([120, 110, 125, 100, 104, 99.0])
    lo2 = np.array([110, 95, 80, 90, 92, 91.0])
    piv2 = (np.array([0, 2]), np.array([120.0, 80.0]), np.array([1, -1]), np.array([1, 3]))
    assert W.running(piv2, h2, lo2, 5) == (4, 104.0, 1)


# ------------------------------------------------------------------ rule 4 + 13: the structure and the bias
def test_structure_by_hand(main_r):
    s = main_r.struct
    # bar 33: peaks 120, 121 (HH), troughs 100, 102 (HL) -> up
    assert (s.highs[33], s.lows[33], s.label[33]) == (1, 1, 1)
    # bar 38: the running low 101 < the last trough 102 -> lows (102, 101) LL; highs HH -> mixed
    assert (s.highs[38], s.lows[38], s.label[38]) == (1, -1, 0) and s.lo_new[38] == 101
    # bar 50: peak 115 confirmed -> (121, 115) LH; troughs (102, 101) LL -> down
    assert (s.highs[50], s.lows[50], s.label[50]) == (-1, -1, -1)
    # bar 63: the running high 118 > the last peak 115 -> (115, 118) HH; lows (101, 99) LL -> mixed
    assert (s.highs[63], s.lows[63], s.label[63]) == (1, -1, 0) and s.hi_new[63] == 118
    # before two troughs exist the label is unknown
    assert np.isnan(s.label[10])


def test_bias_by_hand(main_r):
    s = main_r.struct
    # closes beyond the last confirmed pivot: bar 28 close 121 > peak 120 (+1); bar 38 close 101 < trough 102 (-1);
    # bar 53 close 99 < trough 101 (-1); bar 61 close 115 is not above 115, bar 62 close 117 is (+1); bar 73 close 98
    # < trough 99 (-1)
    for j, (b, bb) in {27: (np.nan, np.nan), 28: (1, 28), 37: (1, 28), 38: (-1, 38), 53: (-1, 53), 61: (-1, 53),
                       62: (1, 62), 73: (-1, 73), 100: (-1, 73)}.items():
        if np.isnan(b):
            assert np.isnan(s.bias[j])
        else:
            assert (s.bias[j], s.bias_bar[j]) == (b, bb), j


def test_edge_by_hand():
    # a bottom at 100 (rt 2.5). Bar: (close, high, low)
    # 0 (99.5, 100.5, 99.2): the first close below -> break; 1 (99.4, 99.8, 99.0): the second -> accepted, but the low
    # 99.0 is not 2.5 below -> not away yet; 2 (99.6, 100.2, 99.1), 3 (99.3, 99.9, 98.9): still not away, so the highs
    # near the level are no retest; 4 (97.0, 99.0, 96.8): away; 5 (96.5, 97.2, 96.0): high 97.2 < 97.5; 6 (98.0, 98.4,
    # 96.4): high >= 97.5 -> retest; 7 (97.0, 98.9, 96.9): the retest's high 98.9, close 97.0 < 97.5 -> fail at 98.9;
    # 8 (100.5, 100.8, 97.1): a new retest (away since 7); close > 100 once; 9 (101.0, 101.2, 100.2): twice -> reclaim
    seq = [(99.5, 100.5, 99.2), (99.4, 99.8, 99.0), (99.6, 100.2, 99.1), (99.3, 99.9, 98.9), (97.0, 99.0, 96.8),
           (96.5, 97.2, 96.0), (98.0, 98.4, 96.4), (97.0, 98.9, 96.9), (100.5, 100.8, 97.1), (101.0, 101.2, 100.2)]
    for side in (-1, 1):
        ev: list = []
        e = W.Edge(side, "x", 0)
        for j, (c, h, lo) in enumerate(seq):
            if side == 1:  # the mirror about 200: a top at 100 broken upward
                c, h, lo = 200 - c, 200 - lo, 200 - h
            e.step(j, c, h, lo, 100.0 if side == -1 else 100.0, 2.5, ev)
        assert [(x[0], x[2]) for x in ev] == [(0, "break"), (1, "accepted"), (6, "retest"), (7, "retest_fail"),
                                              (8, "retest"), (9, "reclaim")], side
        assert ev[3][5] == pytest.approx(98.9 if side == -1 else 101.1)
    # a sweep, then a new break: 99 (break), 101 (sweep), 99 (break), 98 (accepted)
    ev = []
    e = W.Edge(-1, "x", 0)
    for j, c in enumerate([99.0, 101.0, 99.0, 98.0]):
        e.step(j, c, c + 0.5, c - 0.5, 100.0, 2.5, ev)
    assert [x[2] for x in ev] == ["break", "sweep", "break", "accepted"]


def test_inner_swings():
    # 100 -> 112 -> 108 -> 115 -> 100 with S = 10: the inner swings (0.3 x 10 = 3) keep the 4-USD dip to 108 as a
    # trough; the trade-size swings (10) do not
    m = bars_from(walk([100, 112, 108, 115, 100]), start=100.0)
    r = W.analyze(m, "M1", inner=True, s_fn=const10)
    assert r.inner[1].tolist() == [100, 112, 108, 115]
    assert r.piv[1].tolist() == [100, 115]


def test_readings_at(main_r):
    # bar 61 (closes 115, the running high 115 is not above the peak 115): LH + LL = down, bias -1 (from bar 53);
    # bar 62 (high 117 > 115): HH + LL = mixed, bias +1 (bar 62); before any complete bar: unknown
    t = W._ns([T0 + pd.Timedelta(minutes=62), T0 + pd.Timedelta(minutes=63), T0])
    r = W.readings_at({"M1": main_r}, t, tfs=("M1",))
    assert list(r.columns) == ["M1_label", "M1_bias"]
    assert r.M1_label.tolist()[:2] == [-1.0, 0.0] and r.M1_bias.tolist()[:2] == [-1.0, 1.0]
    assert np.isnan(r.M1_label.iloc[2]) and np.isnan(r.M1_bias.iloc[2])
    assert r.index[0] == T0 + pd.Timedelta(minutes=62)


def test_side_and_trend_by_hand():
    # rows: (D1, H4, H1, M30, M15) labels; biases set to the same values except where noted
    rows = [
        (1, 1, 1, 1, 1),       # 0: buy side; trend up
        (1, 1, 0, 1, 1),       # 1: H1 mixed is not against -> buy side; trend 0 (H1 mixed)
        (1, 1, -1, -1, -1),    # 2: H1 against -> no side; trend down (M15, M30, H1 all down)
        (-1, -1, 0, -1, -1),   # 3: sell side; trend 0
        (-1, -1, -1, -1, -1),  # 4: sell side; trend down
        (1, -1, 1, 1, 1),      # 5: D1 and H4 disagree -> no side; trend up
        (0, 1, 1, 1, 1),       # 6: D1 mixed -> no side
        (np.nan, 1, 1, 1, 1),  # 7: D1 unknown -> side NaN; trend up
        (1, 1, 1, np.nan, 1),  # 8: buy side; M30 unknown -> trend NaN
    ]
    df = pd.DataFrame(rows, columns=["D1_label", "H4_label", "H1_label", "M30_label", "M15_label"], dtype=float)
    for tf in ("D1", "H4", "H1", "M30", "M15"):
        df[f"{tf}_bias"] = df[f"{tf}_label"]
    df.loc[1, "H1_bias"] = -1.0  # the bias reading: H1 against on row 1 -> no side (bias); its trend_bias: M15, M30 up, H1 down -> 0
    df.loc[3, ["H1_bias", "M30_bias", "M15_bias"]] = -1.0  # row 3: trend_bias down
    st = W.side_trend(df)
    nan = np.nan
    exp_side = [1, 1, 0, -1, -1, 0, 0, nan, 1]
    exp_trend = [1, 0, -1, 0, -1, 1, 1, 1, nan]
    exp_side_b = [1, 0, 0, -1, -1, 0, 0, nan, 1]
    exp_trend_b = [1, 0, -1, -1, -1, 1, 1, 1, nan]
    for col, exp in (("side", exp_side), ("trend", exp_trend), ("side_bias", exp_side_b), ("trend_bias", exp_trend_b)):
        got = st[col].tolist()
        assert all((np.isnan(g) and np.isnan(e)) or g == e for g, e in zip(got, exp)), (col, got)


def test_cmp_equal():
    assert W._cmp(5.0, 5.0) == 0 and W._cmp(6.0, 5.0) == 1 and W._cmp(4.0, 5.0) == -1 and np.isnan(W._cmp(np.nan, 1))


# ------------------------------------------------------------------ rule 5, 7, 11: the box, its breaks and retests
def test_box_by_hand(main_r):
    bx = main_r.boxes
    # born at bar 33 (the 4th pivot, peak 121): [100, 121] = 21 <= 30, mid 110.5; then 101 (43), 115 (50), 99 (58,
    # the sweep's trough: bottom -> 99), 118 (68) join; accepted down at bar 74 -> frozen. No box after it: the pivots
    # 88 (bar 86) and 110 (bar 97) are only two.
    assert len(bx) == 1
    r = bx.iloc[0]
    assert (r.born, r.first, r.n, r.top, r.bot, r.end, r.why) == (33, 0, 8, 121, 99, 74, "broken")
    s = main_r.struct
    assert s.box_live[73] == 1 and s.box_live[74] == 0 and s.box_bot[57] == 100 and s.box_bot[58] == 99
    ev = main_r.events
    e = ev[ev.tag == "box_bot"][["bar", "kind", "level", "price"]].values.tolist()
    # 53: close 99 < 100 (break); 54: close 101 back inside (sweep); 73: close 98 < 99 (break); 74: close 96 (accepted;
    # low 96 <= 99 - 2.5, away); 81: high 98 >= 96.5 (retest); 82: close 96 < 96.5 (fail, the retest's high 98);
    # 91: high 98 (a second retest); 92 close 100, 93 close 102 > 99 twice (reclaim)
    assert e == [[53, "break", 100, 99], [54, "sweep", 100, 101], [73, "break", 99, 98], [74, "accepted", 99, 96],
                 [81, "retest", 99, 98], [82, "retest_fail", 99, 98], [91, "retest", 99, 98], [93, "reclaim", 99, 102]]
    assert len(ev[ev.tag == "box_top"]) == 0


def test_box_outgrown_by_the_halves_rule():
    # 100 -> 120 -> 102 -> 121 -> 111 -> 125. Bars 29-33 fall to 111 (bar 33: low 111 = 121 - 10 confirms peak 121 ->
    # the box [100, 121] is born at 33); bars 34-38 rise to 121 (bar 38: 121 - 111 = 10 confirms trough 111). 111 lies
    # above the middle 110.5 -> box 0 ends, outgrown, at 38. The search from 111 back: 121, 102, 120 fit ([102, 121],
    # middle 111.5), 100 does not (the middle 110.5 again) -> box 1 = pivots 1..4, born at 38, first bar 9; bars 39 /
    # 40 close 123 / 125 above 121 -> accepted at 40.
    m = bars_from(walk([100, 120, 102, 121, 111, 125]), start=100.0)
    r = W.analyze(m, "M1", s_fn=const10)
    pb, pp, pk, pc = r.piv
    assert pp.tolist() == [100, 120, 102, 121, 111] and pc.tolist() == [4, 14, 23, 33, 38]
    b = r.boxes
    assert b[["born", "first", "n", "top", "bot", "end", "why"]].values.tolist() == [
        [33, 0, 4, 121, 100, 38, "outgrown"], [38, 9, 4, 121, 102, 40, "broken"]]
    assert b.members.iloc[1] == [1, 2, 3, 4]


def test_box_tests_of_the_edges(main_r):
    box = main_r.boxes.iloc[0]
    # inner swings (thr 3) give the same turning points; top quarter >= 121 - 0.25 x 22 = 115.5: peaks 120, 121, 118
    # (115 is below); bottom quarter <= 104.5: troughs 100, 102, 101, 99 (88 at bar 86 is after the end, bar 74)
    assert W.edge_tests(main_r, box, 74, 1) == [(9, 120.0), (28, 121.0), (63, 118.0)]
    assert [p for _, p in W.edge_tests(main_r, box, 74, -1)] == [100, 102, 101, 99]


# ------------------------------------------------------------------ rule 6: the lines
def test_lines_by_hand(main_r):
    L = main_r.lines
    sup = L[L.kind == -1]
    # trough 102 (bar 18, confirmed 23): one earlier trough, 100 at bar 0, slope 2/18 > 0 -> line 0, touches 2;
    # trough 101 (38, conf 43): slopes from 102: -1/20, from 100: 1/38 -> the anchor 100; the trough 102 between lies
    # |102 - (100 + 18/38)| = 1.53 <= 2 from it -> touches 3; trough 99 (conf 58) and 88 (conf 91): every slope < 0
    assert sup[["born", "a", "b", "touches"]].values.tolist() == [[23, 0, 2, 2], [43, 0, 4, 3]]
    assert sup.slope.tolist() == pytest.approx([2 / 18, 1 / 38])
    res = L[L.kind == 1]
    # peak 115 (45, conf 50): from 121 (bar 28) -6/17, from 120 (bar 9) -5/36 -> the steeper, 121; peak 118 (conf 68):
    # from 115 +3/18, from 121 -3/35, from 120 -2/54 -> 121; peak 110 (97, conf 102): from 118 -8/34, 115 -5/52,
    # 121 -11/69, 120 -10/88 -> 118
    assert res[["born", "a", "b", "touches"]].values.tolist() == [[50, 3, 5, 2], [68, 3, 7, 2], [102, 7, 9, 2]]
    ev = main_r.events
    e = ev[(ev.tag == "sup") & (ev.obj == 0)][["bar", "kind"]].values.tolist()
    # line 0 = 100 + j/9: bar 37 close 103 < 104.11 (break), 38 close 101 < 104.22 (accepted; low 101 <= 101.72,
    # away); 39 high 103 >= 101.83 (retest); 40 close 105 > 104.44, 41 close 107 > 104.56 (reclaim)
    assert e == [[37, "break"], [38, "accepted"], [39, "retest"], [41, "reclaim"]]
    assert L.id.tolist() == [0, 1, 2, 3, 4]  # one count across both kinds, in the order born (23, 43, 50, 68, 102)
    e = ev[(ev.tag == "res") & (ev.obj == 2)][["bar", "kind"]].values.tolist()
    # resistance 0 = 121 - 6/17 x (j - 28): bar 59 close 111 > 110.06 (break), 60 close 113 > 109.71 (accepted; high
    # 113 >= 112.21, away); no low comes back to within 2.5 before line 1 replaces it at bar 68
    assert e == [[59, "break"], [60, "accepted"]]
    assert main_r.struct.sup_val[50] == pytest.approx(100 + 50 / 38)


def test_no_line_when_a_close_between_is_below_it():
    # trough 100 at bar 0, a crawl (closes 100.2, 100.4, 100.6), up to 120, down to 110 (bar 17), up to 125: the line
    # 100 -> 110 rises 10/17 a minute, at bar 1 it is 100.59 > the close 100.4 -> no support line
    closes = [100.2, 100.4, 100.6] + walk([100.6, 120, 110, 125])
    m = bars_from(closes, start=100.0)
    r = W.analyze(m, "M1", s_fn=const10)
    pb, pp, pk, pc = r.piv
    assert pb.tolist()[:3] == [0, 12, 17] and pp.tolist()[:3] == [100, 120, 110]
    assert len(r.lines) == 0 and list(r.lines.columns) == W.LINE_COLS  # empty, with its columns (an empty frame keeps them)
    assert list(r.boxes.columns) == W.BOX_COLS


# ------------------------------------------------------------------ rule 8: the Fibonacci
def test_fib_by_hand(main_r):
    f = W.fib_at(main_r, 60)  # the last two pivots known at bar 60: 115 (start) -> 99 (end): levels 99 + 16 f
    assert (f["start"], f["end"], f["kind"]) == (115, 99, -1)
    assert f["levels"] == pytest.approx({0.236: 102.776, 0.382: 105.112, 0.5: 107.0, 0.618: 108.888})
    f = W.fib_at(main_r, 70)  # 99 -> 118: levels 118 - 19 f
    assert f["levels"][0.618] == pytest.approx(118 - 19 * 0.618)
    assert W.fib_at(main_r, 3) is None


# ------------------------------------------------------------------ rule 1 and 3: the swing size and the thresholds
def _hours(spec):
    """M1 bars: each hour flat at `mid`, one bar at minute 10 with the hour's high, one at minute 20 with its low, the
    last bar closing at `close`."""
    rows = []
    for k, (mid, hi, low, close) in enumerate(spec):
        for mi in range(60):
            o = c = mid
            hh, ll = mid, mid
            if mi == 10:
                hh = hi
            if mi == 20:
                ll = low
            if mi == 59:
                c = close
                hh, ll = max(hh, c), min(ll, c)
            rows.append((T0 + pd.Timedelta(hours=k, minutes=mi), o, hh, ll, c))
    d = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close"]).set_index("t")
    return d


def test_swing_size_by_hand():
    # hour 0: high 2030, low 2000, close 2020 -> TR 30 (the first bar: high - low)
    # hour 1: high 2025, low 2015, close 2016; previous close 2020 -> TR 10
    # hour 2: mid 2030, high 2050, low 2020; previous close 2016 -> TR 2050 - 2016 = 34
    m = _hours([(2020, 2030, 2000, 2020), (2020, 2025, 2015, 2016), (2030, 2050, 2020, 2030)])
    s = W.swing_size(m)
    i = {t: k for k, t in enumerate(m.index)}
    at = lambda hh, mm: s[i[T0 + pd.Timedelta(hours=hh, minutes=mm)]]  # noqa: E731
    assert at(0, 58) == 10.0  # no complete H1 bar at 00:59
    assert at(0, 59) == pytest.approx(18.0)  # the M1 bar 00:59 closes at 01:00 = H1 0 complete: 0.6 x 30
    assert at(1, 30) == pytest.approx(18.0)
    assert at(1, 59) == pytest.approx(12.0)  # mean(30, 10) = 20 -> 12
    assert at(2, 59) == pytest.approx(0.6 * (30 + 10 + 34) / 3)  # 14.8
    assert W.h1_atr(m)[i[T0 + pd.Timedelta(hours=1, minutes=59)]] == pytest.approx(20.0)


def test_swing_size_floor():
    # two calm hours, each 2005 / 1995, closing at 2000: true range 10 -> 0.6 x 10 = 6 < 10 -> S = the floor 10
    m = _hours([(2000, 2005, 1995, 2000), (2000, 2005, 1995, 2000)])
    s = W.swing_size(m)
    assert s[59] == 10.0 and s[119] == 10.0
    assert W.h1_atr(m)[119] == pytest.approx(10.0)


def test_swing_size_full_atr14():
    # 16 hours; hour 0's range 50, every other 20, all closing at their mid (no gaps): the warm-up mean after hour 13 is
    # (50 + 13 x 20) / 14 = 22.142857 -> S = 13.285714; ATR14 at hour 14 = the mean of the true ranges of hours 1..14
    # = 20 -> S = 12 exactly (MetaTrader's ATR drops the first bar)
    spec = [(2000, 2025, 1975, 2000)] + [(2000, 2010, 1990, 2000)] * 15
    m = _hours(spec)
    s = W.swing_size(m)
    i = {t: k for k, t in enumerate(m.index)}
    assert s[i[T0 + pd.Timedelta(hours=13, minutes=59)]] == pytest.approx(0.6 * (50 + 13 * 20) / 14)
    assert s[i[T0 + pd.Timedelta(hours=14, minutes=59)]] == pytest.approx(12.0)
    assert s[i[T0 + pd.Timedelta(hours=15, minutes=59)]] == pytest.approx(12.0)


def test_tf_threshold_takes_the_tf_atr_when_larger():
    # M1 bars each 20 USD tall with no gaps (true range 20): the threshold = max(10, 20) = 20 on every bar
    idx = pd.date_range(T0, periods=30, freq="1min")
    m = pd.DataFrame({"open": 2000.0, "high": 2010.0, "low": 1990.0, "close": 2000.0}, index=idx)
    thr = W.tf_threshold(m, W.tf_bars(m, "M1"), "M1", s_fn=const10)
    assert np.allclose(thr, 20.0)


def test_tf_bars_match_indicators_bars():
    rng = np.random.default_rng(7)
    idx = pd.date_range("2025-11-03 21:00", periods=60 * 30, freq="1min", tz="UTC")
    c = 2000 + np.cumsum(rng.normal(0, 1, len(idx)))
    m = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c}, index=idx)
    for tf, rule in (("M5", "5min"), ("M15", "15min"), ("M30", "30min"), ("H1", "1h"), ("H4", "4h"), ("D1", "1D")):
        a, b = W.tf_bars(m, tf), IND.bars(m, rule)
        for k in ("open", "high", "low", "close", "last", "avail"):
            assert (a[k].to_numpy() == b[k].to_numpy()).all(), (tf, k)
    h1 = W.tf_bars(m, "H1")
    assert h1.t.iloc[0] == pd.Timestamp("2025-11-03 21:00", tz="UTC") and h1.avail.iloc[0] == pd.Timestamp("2025-11-03 22:00", tz="UTC")


def test_at_reads_the_bar_complete_at_the_moment(main_m):
    r = W.analyze(main_m, "M5", s_fn=const10)
    t5 = W._ns([T0 + pd.Timedelta(minutes=5)])  # the M5 bar 00:00 is complete at 00:05 exactly
    assert r.at(t5).tolist() == [0]
    assert r.at(t5 - 1).tolist() == [-1]


# ------------------------------------------------------------------ mirror: a sell reads like a buy
def test_mirror(main_m, main_r):
    mm = pd.DataFrame({"open": -main_m.open, "high": -main_m.low, "low": -main_m.high, "close": -main_m.close},
                      index=main_m.index) + 1000.0
    r = W.analyze(mm, "M1", s_fn=const10)
    assert r.piv[0].tolist() == main_r.piv[0].tolist() and (r.piv[2] == -main_r.piv[2]).all()
    assert np.allclose(r.piv[1], 1000.0 - main_r.piv[1])
    s, s0 = r.struct, main_r.struct
    ok = np.isfinite(s0.label)
    assert (s.label[ok] == -s0.label[ok]).all() and np.array_equal(np.isfinite(s.label), ok)
    a = r.events[["bar", "kind", "side"]].values.tolist()
    b = main_r.events[["bar", "kind", "side"]].values.tolist()
    flip = {"box_top": "box_bot", "box_bot": "box_top", "sup": "res", "res": "sup"}
    assert sorted((x, flip[t], k, -sd) for (x, k, sd), t in zip(a, r.events.tag)) == sorted(
        (x, t, k, sd) for (x, k, sd), t in zip(b, main_r.events.tag))


# ------------------------------------------------------------------ the loaders keep out the exam
def test_loaders_never_hold_the_exam():
    live = W.load_live()
    assert live.index.min() >= pd.Timestamp("2026-10-18", tz="UTC")
    learn = W.load_learning()
    assert learn.index.max() < pd.Timestamp("2026-04-18", tz="UTC")
    assert learn.index.min() >= pd.Timestamp("2025-08-01", tz="UTC")
