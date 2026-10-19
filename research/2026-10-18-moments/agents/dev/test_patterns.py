"""patterns by hand: the ZigZag and its confirmations, the structure at a bar, the inverse H&S / W / sweep-turn / base
rules and their edges, the mirror (sells), the level test, the next level, the TF structure, the bars of a TF, the
reader that never reads the exam, the news levels, locate and agree.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_patterns.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patterns as P  # noqa: E402
from patterns import (  # noqa: E402
    EXAM_START,
    ExamPeriodError,
    agree,
    at_level,
    find_base,
    find_buy,
    first_close_above,
    load_m1,
    locate,
    m_structure,
    next_level,
    patterns_at,
    structure,
    tf_bars,
    zigzag,
)

ONE = np.ones(40)


def bars_from_closes(c, half=0.2):
    c = np.asarray(c, float)
    return c + half, c - half, c


# --- the ZigZag and the structure -------------------------------------------------------------------------------


def test_zigzag_by_hand():
    # ATR 1, threshold 2 (reached at 2.0 or more). Bar 1: 10.8 - 9 = 1.8, not yet; bar 2: 12 - 9 (bar 0) = 3 -> the
    # trough at 0 (9) confirmed at 2, a peak tracked from 2; bar 3: 12 - 9.5 = 2.5 -> the peak at 2 (12) confirmed at
    # 3; bar 4 low 8 extends the trough; bar 5: 10.5 - 8 = 2.5 -> the trough at 4 (8) confirmed at 5
    h = np.array([10, 10.8, 12, 11, 10, 10.5])
    lo = np.array([9, 10, 11, 9.5, 8, 9])
    pb, pp, pk, pc = zigzag(h, lo, ONE[:6])
    assert pb.tolist() == [0, 2, 4] and pp.tolist() == [9, 12, 8] and pk.tolist() == [-1, 1, -1] and pc.tolist() == [2, 3, 5]


def test_zigzag_confirms_at_exactly_the_threshold():
    # 11 - 9 = 2.0 on bar 1: the trough at 0 is confirmed there (2.0 or more)
    pb, pp, pk, pc = zigzag(np.array([10.0, 11.0, 10.5]), np.array([9.0, 10.0, 9.8]), ONE[:3])
    assert pb.tolist() == [0] and pc.tolist() == [1]
    # then the peak at 1 (11) by a low of exactly 9.0 on bar 2, and the trough at 2 by a high of exactly 11.0 on bar 3
    pb, pp, pk, pc = zigzag(np.array([10.0, 11.0, 10.5, 11.0]), np.array([9.0, 10.0, 9.0, 10.0]), ONE[:4])
    assert pb.tolist() == [0, 1, 2] and pk.tolist() == [-1, 1, -1] and pc.tolist() == [1, 2, 3]


def test_zigzag_an_equal_extreme_moves_the_pivot_later():
    # the peak 12 at bar 2, an equal high at bar 3: the peak moves to bar 3, confirmed by bar 4 (9.5); then the
    # trough 9.5 at bar 4, an equal low at bar 5: the trough moves to bar 5, confirmed by bar 6 (11.6)
    h = np.array([10.0, 10.8, 12.0, 12.0, 11.0, 10.5, 11.6])
    lo = np.array([9.0, 10.0, 11.0, 11.5, 9.5, 9.5, 11.0])
    pb, pp, pk, pc = zigzag(h, lo, ONE[:7])
    assert pb.tolist() == [0, 3, 5] and pc.tolist() == [2, 4, 6]


def test_zigzag_skips_the_warm_up_and_extends_on_an_outside_bar():
    # NaN ATR on bars 0-1 (their prices are not used); then a peak is tracked; bar 5 makes a new high (14) AND a low
    # 3 below the old peak: the new high wins (extends), no confirmation on that bar; bar 6 (low 11.5) confirms 14
    h = np.array([50, 50, 10, 12, 13, 14, 12.5])
    lo = np.array([0, 0, 9, 11, 12, 10, 11.5])
    atr = np.array([np.nan, np.nan, 1, 1, 1, 1, 1])
    pb, pp, pk, pc = zigzag(h, lo, atr)
    assert pb.tolist() == [2, 5] and pk.tolist() == [-1, 1] and pc.tolist() == [3, 6] and pp.tolist() == [9, 14]


def test_zigzag_equals_the_precursors_zigzag_on_real_bars():
    # an independent implementation (fingerprint.zigzag) on the real M1 of 2026-01-05 .. 2026-01-10
    import fingerprint

    m = load_m1(pd.Timestamp("2026-01-05", tz="UTC"), pd.Timestamp("2026-01-10", tz="UTC"))
    h, lo = m.high.to_numpy(float), m.low.to_numpy(float)
    atr = P.atr14(m)
    mine, theirs = zigzag(h, lo, atr), fingerprint.zigzag(h, lo, atr, P.ZZ_K)
    assert len(mine[0]) > 300 and all(np.array_equal(a, b) for a, b in zip(mine, theirs, strict=True))


def test_structure_at_a_bar():
    h = np.array([10, 10.8, 12, 11, 10, 10.5])
    lo = np.array([9, 10, 11, 9.5, 8, 9])
    piv = zigzag(h, lo, ONE[:6])
    # d 2: only the trough at 0 confirmed; the running peak over bars 1..2 = bar 2 (12)
    assert structure(piv, h, lo, 2) == [(0, 9.0, -1, False), (2, 12.0, 1, True)]
    # d 4: trough 0, peak 2 confirmed; the running trough over bars 3..4 = bar 4 (8)
    assert structure(piv, h, lo, 4) == [(0, 9.0, -1, False), (2, 12.0, 1, False), (4, 8.0, -1, True)]
    # d 5: all three confirmed; the running peak over bar 5 (10.5); keep=2 keeps the last two confirmed
    assert structure(piv, h, lo, 5, keep=2) == [(2, 12.0, 1, False), (4, 8.0, -1, False), (5, 10.5, 1, True)]
    # equal lows: the earliest is the running trough
    h2, lo2 = np.array([10, 13, 12, 11, 11]), np.array([9, 12, 10, 10, 10.5])
    piv2 = (np.array([0, 1]), np.array([9.0, 13.0]), np.array([-1, 1]), np.array([1, 2]))
    assert structure(piv2, h2, lo2, 4)[-1] == (2, 10.0, -1, True)
    # the running trough starts after the peak's bar, even when the peak bar's own low is lower (an outside bar)
    lo3 = np.array([9.0, 10.0, 10.5, 10.4])
    assert structure(piv2, np.array([10.0, 13.0, 12.0, 11.0]), lo3, 3)[-1] == (3, 10.4, -1, True)


def test_first_close_above():
    c = np.array([1.0, 5.0, 5.0, 6.0])
    assert first_close_above(c, np.full(3, 5.0), 1, 3)  # closes 5, 5 at the line (not above), then 6
    assert not first_close_above(c, np.full(3, 4.9), 1, 3)  # 5 > 4.9 already at bar 1
    assert not first_close_above(c, np.full(3, 6.0), 1, 3)  # 6 is not above 6
    assert not first_close_above(np.array([1.0, 5.5, 4.0, 6.0]), np.full(3, 5.0), 1, 3)  # bar a itself closed above


# --- the swing patterns (buy side, the sequence given by hand) ---------------------------------------------------


def seq3(t3, p2=106.0, t2=100.0):
    return [(2, t2, -1, False), (5, p2, 1, False), (8, t3, -1, True)]


def closes(d=10, last=106.5, before=105.0):
    c = np.full(d + 1, 100.0)
    c[8:d] = before
    c[d] = last
    return c


def test_w_equal_lows():
    # T2 100, P2 106, T3 100.3; H = 6, EQ = max(0.5, 0.9) = 0.9: |0.3| <= 0.9 -> W; trigger 106, breakout at 10
    x = find_buy(None, None, closes(), 1.0, seq3(100.3), 10)
    assert [p["family"] for p in x] == ["w"] and x[0]["variant"] == "W"
    assert x[0]["trigger"] == 106.0 and x[0]["extreme"] == 100.0 and x[0]["height"] == 6.0 and x[0]["start"] == 2
    assert [lab for _, _, lab in x[0]["points"]] == ["L1", "P", "L2"]


def test_w_whose_second_low_sweeps_the_first():
    # T3 98.5: H 7.5, EQ 1.125; 100 - 2.625 = 97.375 <= 98.5 < 98.875 -> the swept W, extreme 98.5
    x = find_buy(None, None, closes(), 1.0, seq3(98.5), 10)
    assert [p["variant"] for p in x] == ["W, the 2nd low swept the 1st"] and x[0]["extreme"] == 98.5
    # T3 99.0: H 7, EQ 1.05, |1.0| <= 1.05 -> a plain W
    assert [p["variant"] for p in find_buy(None, None, closes(), 1.0, seq3(99.0), 10)] == ["W"]
    # T3 96.5: H 9.5, EQ 1.425, the floor 100 - 3.325 = 96.675 > 96.5 -> too deep, nothing
    assert find_buy(None, None, closes(), 1.0, seq3(96.5), 10) == []


def test_the_higher_low_turn_candidate():
    # T3 102 > T2 100 + EQ 0.9 -> the sweep-turn candidate (its level is checked by at_level), extreme = T2
    x = find_buy(None, None, closes(), 1.0, seq3(102.0), 10)
    assert [p["family"] for p in x] == ["st"] and x[0]["extreme"] == 100.0 and x[0]["higher_low"] == 102.0
    # the edge with exact numbers: ATR 4 -> EQ = max(2.0, 0.15 x H < 2) = 2.0; T3 102.0 is exactly EQ above: a W;
    # 102.25 is above it: the higher low
    assert [p["family"] for p in find_buy(None, None, closes(), 4.0, seq3(102.0), 10)] == ["w"]
    assert [p["family"] for p in find_buy(None, None, closes(), 4.0, seq3(102.25), 10)] == ["st"]


def test_only_the_first_close_above_and_the_span():
    c = closes()
    c[9] = 106.2  # already above at bar 9
    assert find_buy(None, None, c, 1.0, seq3(100.3), 10) == []
    assert find_buy(None, None, closes(last=106.0), 1.0, seq3(100.3), 10) == []  # at the trigger is not above
    # from T2 (bar 2) to d 43 = 41 bars > 40
    c = np.full(44, 100.0)
    c[43] = 107.0
    assert find_buy(None, None, c, 1.0, seq3(100.3), 43) == []
    # the running extreme is a peak: T3 is the confirmed trough before it
    s = [*seq3(100.3)[:2], (8, 100.3, -1, False), (9, 105.5, 1, True)]
    assert [p["family"] for p in find_buy(None, None, closes(), 1.0, s, 10)] == ["w"]


IHS = [(0, 101.0, -1, False), (3, 106.0, 1, False), (6, 99.0, -1, False), (9, 106.5, 1, False), (12, 101.2, -1, True)]


def ihs_closes(last=107.0):
    c = np.full(15, 103.0)
    c[12], c[13], c[14] = 101.5, 104.0, last
    return c


def test_inverse_head_and_shoulders():
    # neckline through (3, 106) and (9, 106.5): slope 1/12 a bar; at bar 14: 106.9167; at the head (6): 106.25 ->
    # height 7.25. Head 99 < min(101, 101.2) - 0.5; shoulders 0.2 apart <= 3.625; neck points 0.5 apart <= 3.625.
    # Closes 101.5, 104 below, 107 above -> breakout at 14. The inner T2-P2-T3 is also a higher-low candidate.
    x = {p["family"]: p for p in find_buy(None, None, ihs_closes(), 1.0, IHS, 14)}
    assert set(x) == {"ihs", "st"}
    p = x["ihs"]
    assert p["trigger"] == pytest.approx(106.0 + 11 / 12) and p["height"] == pytest.approx(7.25) and p["extreme"] == 99.0
    assert p["neck"] == ((3, 106.0), (9, 106.5)) and p["start"] == 0
    assert [lab for _, _, lab in p["points"]] == ["LS", "N1", "Head", "N2", "RS"]
    assert "ihs" not in {q["family"] for q in find_buy(None, None, ihs_closes(106.9), 1.0, IHS, 14)}  # below 106.9167


@pytest.mark.parametrize(("k", "price", "why"), [
    (None, None, "the hand case itself (a close of 120 is above any of these necklines)"),
    (2, 100.6, "the head not 0.5 ATR below the shoulders (100.5)"),
    (0, 105.5, "the shoulders 4.3 apart > 0.5 x the height 3.625"),
    (3, 111.0, "the neckline points 5 apart > 0.5 x the height 4.75 (neck at the head 108.5)"),
])
def test_inverse_head_and_shoulders_edges(k, price, why):
    s = list(IHS)
    if k is not None:
        s[k] = (s[k][0], price, s[k][2], s[k][3])
    found = "ihs" in {p["family"] for p in find_buy(None, None, ihs_closes(120.0), 1.0, s, 14)}
    assert found is (k is None), why


def test_inverse_head_and_shoulders_span():
    # the left shoulder at bar 0: a breakout at bar 60 is inside the 60 bars, at bar 61 it is not
    for d, ok in ((60, True), (61, False)):
        c = np.full(d + 1, 103.0)
        c[12], c[d] = 101.5, 120.0
        assert ("ihs" in {p["family"] for p in find_buy(None, None, c, 1.0, IHS, d)}) is ok


# --- end to end: the ZigZag, the mirror (an M), the base ---------------------------------------------------------


M_PATH = [100, 100, 100, 102, 104, 106, 104, 102, 101, 103, 105, 106.2, 104, 102.5, 100.5]


def test_an_m_end_to_end_through_the_mirror():
    # closes +- 0.2, ATR 1.5 (threshold 3): the trough 99.8 (0) confirmed at bar 4 (104.2: 4.4 up; bar 3 only 2.4), the
    # peak 106.2 (5) at bar 7 (101.8), the trough 100.8 (8) at bar 10 (105.2), the peak 106.4 (11) at bar 13 (102.3);
    # at bar 14 the close 100.5 is the first below the middle low 100.8 -> M (the tops 0.2 apart <= EQ max(0.75,
    # 0.84)), height 5.6 <= 4 x 1.5, extreme 106.4, stop 106.4 + 0.2 x 1.5 = 106.7
    h, lo, c = bars_from_closes(M_PATH)
    atr = np.full(15, 1.5)
    piv = zigzag(h, lo, atr)
    assert piv[0].tolist() == [0, 5, 8, 11] and piv[3].tolist() == [4, 7, 10, 13]
    x = patterns_at(h, lo, c, atr, piv, 14)
    assert len(x) == 1
    p = x[0]
    assert (p["family"], p["side"], p["variant"]) == ("w", -1, "M") and p["height"] == pytest.approx(5.6)
    assert p["trigger"] == pytest.approx(100.8) and p["extreme"] == pytest.approx(106.4) and p["stop"] == pytest.approx(106.7)
    assert [(b, round(v, 1), lab) for b, v, lab in p["points"]] == [(5, 106.2, "H1"), (8, 100.8, "T"), (11, 106.4, "H2")]
    assert patterns_at(h, lo, c, atr, piv, 13) == []  # 102.5 is not below 100.8
    # the same with the precomputed mirror
    mir = (-lo, -h, -c, P.mirror_piv(piv))
    assert patterns_at(h, lo, c, atr, piv, 14, mir) == x
    # the height cap: with ATR 1.39 the same M (5.6) is taller than 4 x 1.39 = 5.56 - dropped; without the cap it is there
    atr = np.full(15, 1.39)
    piv = zigzag(h, lo, atr)
    assert patterns_at(h, lo, c, atr, piv, 14) == []
    P.HEIGHT_ATR = 5.0
    try:
        assert [q["variant"] for q in patterns_at(h, lo, c, atr, piv, 14)] == ["M"]
    finally:
        P.HEIGHT_ATR = 4.0


def test_the_sell_side_names():
    # every buy variant has its sell name, and the mirror uses it
    assert P.SELL_NAMES == {"W": "M", "W, the 2nd low swept the 1st": "M, the 2nd high swept the 1st",
                            "inverse H&S": "H&S", "sweep, higher low": "sweep, lower high"}
    p = P.unmirror(dict(variant="W, the 2nd low swept the 1st", extreme=-10.0, trigger=-5.0, higher_low=-9.0,
                        points=[(1, -10.0, "L1"), (2, -5.0, "P"), (3, -9.5, "L2")], neck=((1, -5.0), (2, -6.0))))
    assert p["variant"] == "M, the 2nd high swept the 1st" and p["extreme"] == 10.0 and p["trigger"] == 5.0
    assert p["points"] == [(1, 10.0, "H1"), (2, 5.0, "T"), (3, 9.5, "H2")]
    assert p["higher_low"] == 9.0 and p["neck"] == ((1, 5.0), (2, 6.0)) and p["side"] == -1
    # the sweep-turn's and the H&S's points
    q = P.unmirror(dict(variant="sweep, higher low", extreme=-10.0, trigger=-5.0, higher_low=-8.0,
                        points=[(1, -10.0, "S"), (2, -5.0, "P"), (3, -8.0, "HL")]))
    assert [lab for _, _, lab in q["points"]] == ["S", "T", "LH"] and q["variant"] == "sweep, lower high"
    q = P.unmirror(dict(variant="inverse H&S", extreme=-1.0, trigger=-1.0, higher_low=-1.0,
                        points=[(0, -1.0, "LS"), (1, -1.0, "N1"), (2, -1.0, "Head"), (3, -1.0, "N2"), (4, -1.0, "RS")]))
    assert [lab for _, _, lab in q["points"]] == ["LS", "N1", "Head", "N2", "RS"] and q["variant"] == "H&S"


def test_a_base_then_its_break():
    # bars 0..9 within 99.6 .. 100.6 (1.0 <= 1.5 x ATR 1); bar 10 closes 101.0 above -> a 10-bar base, side +1
    h, lo = np.full(11, 100.6), np.full(11, 99.6)
    c = np.full(11, 100.1)
    c[10] = 101.0
    x = find_base(h, lo, c, ONE[:11], 10)
    assert len(x) == 1 and x[0]["side"] == 1 and x[0]["box"] == (0, 9, 99.6, 100.6)
    assert x[0]["extreme"] == 99.6 and x[0]["trigger"] == 100.6
    h[1] = 102.0  # bar 1 too high: the longest tight run is bars 2..9 (8 bars)
    assert find_base(h, lo, c, ONE[:11], 10)[0]["box"] == (2, 9, 99.6, 100.6)
    h[2] = 102.0  # only 7 tight bars left
    assert find_base(h, lo, c, ONE[:11], 10) == []
    h[1] = h[2] = 100.6
    c[10] = 100.5  # closes inside
    assert find_base(h, lo, c, ONE[:11], 10) == []
    c[10] = 100.6  # closes exactly at the base's high: not above
    assert find_base(h, lo, c, ONE[:11], 10) == []
    c[10] = 99.0  # closes below: side -1, extreme the base's high
    x = find_base(h, lo, c, ONE[:11], 10)
    assert x[0]["side"] == -1 and x[0]["extreme"] == 100.6 and x[0]["trigger"] == 99.6


def test_a_base_reads_the_atr_before_the_breakout_bar():
    h, lo = np.full(11, 100.6), np.full(11, 99.6)
    c = np.full(11, 100.1)
    c[10] = 101.0
    atr = np.ones(11)
    atr[10] = 0.1  # the breakout bar's own ATR does not set the width
    assert len(find_base(h, lo, c, atr, 10)) == 1
    atr[9] = 0.5  # 1.0 > 1.5 x 0.5 = 0.75: no base
    assert find_base(h, lo, c, atr, 10) == []


# --- the level, the next level, the TF structure ------------------------------------------------------------------


LV = pd.DataFrame(dict(price=[100.0, 98.0], kind=["x2", "PDL"]))


def pat(family="w", side=1, extreme=99.6, higher_low=np.nan, box=None):
    return dict(family=family, side=side, extreme=extreme, higher_low=higher_low, box=box)


def test_at_level_by_hand():
    z, sw = 0.5, 2.0
    assert at_level(pat(extreme=99.6), 101, LV, z, sw)["how"] == "at"  # 0.4 from 100
    assert at_level(pat(extreme=99.5), 101, LV, z, sw)["how"] == "at"  # exactly one zone (0.5) from 100
    r = at_level(pat(extreme=99.0), 101, LV, z, sw)  # 0.5 past the zone (99.5), close back above
    assert (r["level"], r["how"]) == (100.0, "swept")
    assert at_level(pat(extreme=99.0), 99.4, LV, z, sw) is None  # the close did not come back above 99.5
    r = at_level(pat(extreme=97.4), 101, LV, z, sw)  # 2.1 past 100's zone (> 2), 0.1 past 98's: swept 98
    assert (r["level"], r["how"]) == (98.0, "swept")
    assert at_level(pat(extreme=95.0), 101, LV, z, sw) is None
    # sells mirrored: an extreme 100.4 is at 100; 101.0 is swept when the close is back below 100.5
    assert at_level(pat(side=-1, extreme=100.4), 99, LV, z, sw)["how"] == "at"
    assert at_level(pat(side=-1, extreme=101.0), 100.4, LV, z, sw)["how"] == "swept"
    assert at_level(pat(side=-1, extreme=101.0), 100.6, LV, z, sw) is None


def test_at_level_for_the_sweep_turn_and_the_base():
    z, sw = 0.5, 2.0
    assert at_level(pat("st", extreme=100.2, higher_low=101), 102, LV, z, sw) is None  # at, not swept
    assert at_level(pat("st", extreme=99.0, higher_low=99.6), 102, LV, z, sw)["how"] == "swept"
    assert at_level(pat("st", extreme=99.0, higher_low=99.4), 102, LV, z, sw) is None  # the higher low not back at the zone
    assert at_level(pat("base", box=(0, 9, 100.6, 101.5)), 102, LV, z, sw) is None  # 100.6 > 100.5
    assert at_level(pat("base", box=(0, 9, 100.4, 101.5)), 102, LV, z, sw)["how"] == "base"
    # the nearest of two levels in reach
    two = pd.DataFrame(dict(price=[100.0, 99.5], kind=["x2", "PDL"]))
    assert at_level(pat(extreme=99.6), 101, two, z, sw)["level"] == 99.5


def test_next_level():
    lv = np.array([95.0, 100.0, 104.0, 108.0])
    assert next_level(lv, 101.0, 1, 0.5, 100.0) == 104.0
    assert next_level(lv, 101.0, -1, 0.5, 100.0) == 95.0
    assert next_level(lv, 103.7, 1, 0.5, 100.0) == 108.0  # 104 is only 0.3 above the entry
    assert np.isnan(next_level(lv, 109.0, 1, 0.5, 100.0))


def test_the_tf_structure():
    piv = (np.arange(6), np.array([100.0, 105, 101, 106, 102, 104]), np.array([-1, 1, -1, 1, -1, 1]), np.arange(6) + 1)
    assert m_structure(piv, 4) == "up"  # troughs 100 -> 101, peaks 105 -> 106 (pivots confirmed by bar 4)
    assert m_structure(piv, 6) == "mixed"  # troughs 101 -> 102, peaks 106 -> 104
    assert m_structure(piv, 2) == "none"
    piv = (np.arange(4), np.array([105.0, 100, 104, 99]), np.array([1, -1, 1, -1]), np.arange(4) + 1)
    assert m_structure(piv, 4) == "down"


# --- the bars, the reader, news, locate, agree --------------------------------------------------------------------


def test_tf_bars_on_the_clock():
    idx = pd.date_range("2026-01-05 10:00", periods=12, freq="1min", tz="UTC")
    close = np.arange(12.0) + 0.5
    close[4] = 2.0  # the first M5 bar's last close (2.0) is not its highest close (3.5)
    m = pd.DataFrame(dict(open=np.arange(12.0), high=np.arange(12.0) + 1, low=np.arange(12.0) - 1, close=close), index=idx)
    b = tf_bars(m, 5)
    assert b.open.tolist() == [0, 5, 10] and b.high.tolist() == [5, 10, 12] and b.low.tolist() == [-1, 4, 9]
    assert b.close.tolist() == [2.0, 9.5, 11.5]
    assert b.avail.tolist() == [pd.Timestamp(f"2026-01-05 10:{mm:02d}", tz="UTC") for mm in (5, 10, 15)]  # the partial bar too
    assert tf_bars(m, 1).avail.iloc[0] == pd.Timestamp("2026-01-05 10:01", tz="UTC")


def test_load_m1_never_reads_the_exam():
    with pytest.raises(ExamPeriodError):
        load_m1(end=EXAM_START + pd.Timedelta(minutes=1))
    m = load_m1(pd.Timestamp("2026-01-09 13:25", tz="UTC"), pd.Timestamp("2026-01-09 13:35", tz="UTC"))
    # the release bar (bid): low 4459.03 = the lowest bid of the 13:30 ticks (sweep_detector's tick table)
    assert m.index[0] == pd.Timestamp("2026-01-09 13:25", tz="UTC") and len(m) == 10
    assert m.loc["2026-01-09 13:30:00+00:00", "low"] == pytest.approx(4459.03, abs=0.01)
    last = load_m1(pd.Timestamp("2026-04-17", tz="UTC"))
    assert last.index.max() < EXAM_START


def test_news_levels_reads_the_first_minute_only(monkeypatch):
    # one event: the first minute's tick mid goes 4 down; the M1 release bar's low is the level
    import sweep_detector as sdm

    rel = pd.Timestamp("2026-01-09 13:30", tz="UTC")
    S = 10**9
    t = np.array([rel.value - 5 * S, rel.value + 10 * S, rel.value + 120 * S], np.int64)
    bid, ask = np.array([100.0, 96.0, 130.0]), np.array([100.2, 96.2, 130.2])
    monkeypatch.setattr(sdm, "learning_ticks", lambda d: (t, bid, ask))
    monkeypatch.setattr(sdm, "fixed_events", lambda: pd.DataFrame(dict(t=[rel], ny=["08:30"])))
    idx = pd.date_range("2026-01-09 13:00", periods=40, freq="1min", tz="UTC")
    m = pd.DataFrame(dict(open=100.0, high=101.0, low=99.0, close=100.0), index=idx)
    m.loc[rel, "low"] = 95.5
    tf = P.TF(m, 1)
    n = P.news_levels(tf)
    assert len(n) == 1 and n.iloc[0]["first"] == -1 and n.iloc[0]["level"] == 95.5 and n.iloc[0]["t_rel"] == rel.value
    # the 130 two minutes later (what came after) changes nothing
    bid[2], ask[2] = 50.0, 50.2
    assert P.news_levels(tf).equals(n)


def synthetic_m_tf():
    """The M path as M1 bars from 2026-01-06 14:00 UTC, preceded by 30 flat bars (the ATR warm-up), plus one bar after."""
    path = [100.0] * 30 + M_PATH + [100.4]
    idx = pd.date_range("2026-01-06 13:30", periods=len(path), freq="1min", tz="UTC")
    c = np.array(path)
    m = pd.DataFrame(dict(open=c, high=c + 0.2, low=c - 0.2, close=c), index=idx)
    tf = P.TF(m, 1)
    tf.atr = np.full(len(c), 1.5)  # ATR 1.5 as in the hand-worked M
    tf.piv = zigzag(tf.h, tf.lo, tf.atr)
    tf.mir = (-tf.lo, -tf.h, -tf.c, P.mirror_piv(tf.piv))
    return tf


def test_locate_at_a_level_and_its_next_level(monkeypatch):
    import zones

    tf = synthetic_m_tf()
    # the 33 flat bars are themselves a base that breaks up at bar 33 (102): scan from bar 34
    assert [(p["family"], p["side"]) for p in tf.scan(33, 34)] == [("base", 1)]
    X = tf.scan(34, len(tf.c))
    assert [(p["family"], p["side"], p["d"]) for p in X] == [("w", -1, 44)]
    levels = pd.DataFrame(dict(price=[106.3, 98.0, 95.0], kind=["x3+ / flip", "PDL", "5d low"], touches=[3, 0, 0]))
    seen = []

    def fake_levels(Y, t_ns, price):
        seen.append((t_ns, price))
        return levels, 6.0  # zone 0.6, sweep 3.0; the M's height 5.6 <= 1 x 6.0

    monkeypatch.setattr(zones, "levels_at", fake_levels)
    news = pd.DataFrame(columns=["t_rel", "ny", "first", "leg1", "level"])
    L = locate(X, tf, {}, news)
    assert len(L) == 1
    r = L.iloc[0]
    assert (r.tf, r["name"], r.level, r.how, r.level_kind) == ("M1", "M", 106.3, "at", "x3+ / flip")
    t_dec = pd.Timestamp("2026-01-06 14:15", tz="UTC").value  # bar 44 opens 14:14, closes 14:15
    assert r.t_dec == t_dec and seen == [(t_dec, 100.5)]
    assert r.entry == 100.4 and r.next_level == 98.0 and r.zone == pytest.approx(0.6) and not r.at_news
    # a level 0.8 away is out of the zone (0.6) and not a sweep for a top (the extreme 106.4 is below it)
    levels = pd.DataFrame(dict(price=[107.2], kind=["x2"], touches=[2]))
    assert locate(X, tf, {}, news).empty
    levels = pd.DataFrame(dict(price=[106.3], kind=["x3+ / flip"], touches=[3]))
    # a decision before the learning start (2025-10-18) is not located
    levels = pd.DataFrame(dict(price=[106.3], kind=["x3+ / flip"], touches=[3]))
    tf.avail = tf.avail - 100 * 86400 * 10**9
    assert locate(X, tf, {}, news).empty


def test_locate_after_a_news_leg(monkeypatch):
    import zones

    tf = synthetic_m_tf()
    X = tf.scan(34, len(tf.c))
    monkeypatch.setattr(zones, "levels_at", lambda Y, t, p: (pd.DataFrame(columns=["price", "kind", "touches"]), 6.0))
    rel = pd.Timestamp("2026-01-06 14:05", tz="UTC").value  # a first leg UP to 106.35 at 14:05; the M sells after it
    news = pd.DataFrame(dict(t_rel=[rel], ny=["09:05"], first=[1], leg1=[4.0], level=[106.35]))
    r = locate(X, tf, {}, news).iloc[0]
    assert r.at_news and not r.at_h1 and r.level == 106.35 and r.level_kind == "news leg" and r.news_t == rel
    news.loc[0, "first"] = -1  # a down first leg: the sell is the same side, not counted
    assert locate(X, tf, {}, news).empty
    news.loc[0, "first"] = 1
    news.loc[0, "t_rel"] = rel - 11 * 60 * 10**9  # the decision (14:15) is 21 minutes after: too late
    assert locate(X, tf, {}, news).empty


def test_agree_with_the_other_tf():
    t0 = pd.Timestamp("2026-01-06 14:15", tz="UTC").value
    mn = 60 * 10**9
    A = pd.DataFrame(dict(side=[-1], level=[106.3], zone=[0.2], t_dec=[t0]))
    B = pd.DataFrame({"side": [-1, -1, 1, -1], "level": [106.4, 106.4, 106.3, 106.8],
                      "t_dec": [t0 - 10 * mn, t0 - 31 * mn, t0 - 5 * mn, t0 - 5 * mn],
                      "name": ["M", "H&S", "W", "base, break down"]})

    class Other:
        piv = (np.arange(4), np.array([105.0, 100, 104, 99]), np.array([1, -1, 1, -1]), np.arange(4) + 1)

        @staticmethod
        def last_complete(t):
            return 10

    r = agree(A, B, Other).iloc[0]
    # B row 0 counts (same side, 0.1 apart <= 0.2, 10 minutes before); row 1 is 31 minutes before; row 2 the other
    # side; row 3 is 0.5 apart
    assert r.other_pattern == "M" and r.other_structure == "down"
