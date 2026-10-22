"""Setup OWN PLAN-1, Asia B2 (app/strategy/plan1_b2.py): every building block against numbers worked by hand in the
comments, and the strategy's decisions, journal and exits on hand-built readings."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.core.enums import Action, ExitReason, Side, Timeframe
from app.strategy import plan1_b2 as B
from app.strategy.base_strategy import PastEntry
from app.strategy.catalog import default_registry
from app.strategy.plan1_b2 import (
    Bars,
    Candidate,
    LevelInputs,
    Pivots,
    Plan1B2,
    Plan1B2M5,
    Plan1B2Params,
    at_level,
    confirm_b,
    find_base,
    find_buy,
    fractals,
    in_window,
    level_inputs,
    levels_at,
    m_structure,
    merge,
    mt5_atr,
    next_level,
    patterns_at,
    structure,
    tf_bars,
    zigzag,
)
from app.strategy.signal_models import MarketContext, OpenPosition, ReasonCode, StrategyContext
from tests.risk_data import XAUUSD_SPEC
from tests.unit.test_plan1 import h1_days, wide_h1
from tests.unit.test_strategy_models import state


def utc(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz="UTC")


# --- ATR, ZigZag, structure ---------------------------------------------------------------------------------


def test_mt5_atr_is_the_simple_average_of_true_ranges() -> None:
    # true ranges: bar 0 none; bar 1 max(12, 10) - min(9, 10) = 3; bar 2 max(11, 11) - min(10, 11) = 1;
    # bar 3 a gap up from 10.5: max(14, 10.5) - min(13, 10.5) = 3.5
    h, lo, c = np.array([10.0, 12, 11, 14]), np.array([9.0, 9, 10, 13]), np.array([10.0, 11, 10.5, 13.5])
    atr = mt5_atr(h, lo, c, n=2)
    assert np.isnan(atr[0]) and np.isnan(atr[1])
    assert atr[2] == pytest.approx((3 + 1) / 2) and atr[3] == pytest.approx((1 + 3.5) / 2)


def zz_series() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ATR 1 everywhere (a swing = 2): highs / lows by hand.
    bar: 0     1     2     3     4     5     6     7     8     9
    h:   10.5  11.0  12.5  12.5  11.0  10.6  11.0  12.0  12.7  12.0
    lo:  10.0  10.4  12.0  11.8  10.4  10.0  10.5  11.5  12.2  10.6
    - start: the lowest low 10.0 at bar 0, the highest high 12.5 at bar 2 -> 2.5 >= 2: the first pivot is the
      trough at bar 0 (confirmed at bar 2); then a peak is tracked from bar 2;
    - bar 3's high 12.5 >= 12.5 extends the peak to bar 3 (ties move it later); bar 4's low 10.4: 12.5 - 10.4 =
      2.1 >= 2 confirms the peak at bar 3 (12.5) at bar 4; the trough is tracked from bar 4;
    - bar 5's low 10.0 extends it; bar 6's high 11.0 is only 1.0 above it; bar 7's high 12.0 - 10.0 = 2.0 >= 2
      confirms the trough at bar 5 (10.0) at bar 7, and the peak is tracked from bar 7;
    - bar 8's high 12.7 extends it; bar 9's low 10.6: 12.7 - 10.6 = 2.1 confirms the peak at bar 8 at bar 9."""
    h = np.array([10.5, 11.0, 12.5, 12.5, 11.0, 10.6, 11.0, 12.0, 12.7, 12.0])
    lo = np.array([10.0, 10.4, 12.0, 11.8, 10.4, 10.0, 10.5, 11.5, 12.2, 10.6])
    return h, lo, np.ones(10)


def test_zigzag_by_hand() -> None:
    h, lo, atr = zz_series()
    p = zigzag(h, lo, atr)
    assert list(p.b) == [0, 3, 5, 8] and list(p.p) == [10.0, 12.5, 10.0, 12.7]
    assert list(p.k) == [-1, 1, -1, 1] and list(p.conf) == [2, 4, 7, 9]


def test_zigzag_is_causal_and_waits_for_the_atr() -> None:
    h, lo, atr = zz_series()
    full = zigzag(h, lo, atr)
    changed = zigzag(np.r_[h[:6], [20.0, 20, 20, 20]], np.r_[lo[:6], [19.0, 19, 19, 19]], atr)
    # bars after 5 changed: every pivot confirmed by bar 5 is the same
    k = int(np.searchsorted(full.conf, 5, side="right"))
    assert list(changed.b[:k]) == list(full.b[:k]) and list(changed.conf[:k]) == list(full.conf[:k])
    nan_atr = np.r_[np.full(3, np.nan), atr[3:]]
    assert zigzag(h, lo, nan_atr).b[0] >= 3  # nothing before the first ATR


def test_structure_appends_the_running_extreme() -> None:
    h, lo, atr = zz_series()
    p = zigzag(h, lo, atr)
    # at bar 6 the pivots confirmed: the trough 0, the peak 3 (at bar 4); bar 5's trough is confirmed only at 7, so
    # after the peak the running low of bars 4..6 (10.4, 10.0, 10.5) is the provisional trough: bar 5 at 10.0
    assert structure(p, h, lo, 6) == [(0, 10.0, -1, False), (3, 12.5, 1, False), (5, 10.0, -1, True)]
    # at bar 7 that trough is confirmed; after it the running high of bars 6..7 is bar 7's 12.0
    assert structure(p, h, lo, 7)[2:] == [(5, 10.0, -1, False), (7, 12.0, 1, True)]
    # at bar 9 every pivot is confirmed; the last one is bar 8 < 9: the running low of bar 9, 10.6
    assert structure(p, h, lo, 9)[-1] == (9, 10.6, -1, True)
    assert structure(p, h, lo, 9, keep=2)[0] == (5, 10.0, -1, False)


def test_m_structure_and_last_swing() -> None:
    p = Pivots(
        np.array([0, 2, 4, 6]),
        np.array([10.0, 12.0, 11.0, 13.0]),
        np.array([-1, 1, -1, 1]),
        np.array([1, 3, 5, 7]),
    )
    assert m_structure(p, 7) == "up"  # troughs 10 -> 11, peaks 12 -> 13
    assert m_structure(p, 6) == "none"  # the second peak is confirmed only at 7
    down = Pivots(p.b, np.array([13.0, 12.0, 10.0, 11.0]), np.array([1, -1, 1, -1]), p.conf)
    assert m_structure(down, 7) == "down"
    assert (
        B.last_swing(p, 6, -1) == 11.0 and B.last_swing(p, 4, -1) == 10.0 and np.isnan(B.last_swing(p, 0, 1))
    )


# --- patterns -----------------------------------------------------------------------------------------------


def closes(n: int, up_to: float, last: float) -> np.ndarray:
    c = np.full(n, up_to)
    c[-1] = last
    return c


def test_w_swept_w_and_the_sweep_turn() -> None:
    # L1 100.0 at bar 10, P 105.0 at 15, L2 at bar 20; ATR 1; the breakout close 105.5 at bar 25 (bars 20-24 at 104)
    c = closes(26, 104.0, 105.5)
    h = lo = c  # find_buy reads only the closes and the given swings

    def seq(l2: float) -> list[tuple[int, float, int, bool]]:
        return [(10, 100.0, -1, False), (15, 105.0, 1, False), (20, l2, -1, False)]

    # height 105 - 100 = 5, "equal" within max(0.5 x ATR, 0.15 x 5) = 0.75
    w = find_buy(h, lo, c, 1.0, seq(100.2), 25)
    assert [p["variant"] for p in w] == ["W"] and w[0]["extreme"] == 100.0 and w[0]["trigger"] == 105.0
    # L2 99.0: height 6, equal 0.9; swept: 100 - 0.35 x 6 = 97.9 <= 99 < 100 - 0.9 = 99.1
    sw = find_buy(h, lo, c, 1.0, seq(99.0), 25)
    assert [p["variant"] for p in sw] == ["W, the 2nd low swept the 1st"] and sw[0]["extreme"] == 99.0
    # L2 101.5 > 100 + 0.75: the sweep then the higher low (extreme = the swept low)
    st = find_buy(h, lo, c, 1.0, seq(101.5), 25)
    assert [p["family"] for p in st] == ["st"] and st[0]["extreme"] == 100.0 and st[0]["higher_low"] == 101.5
    # a close at bars 20-24 above the trigger already: not the first close above
    at_trigger = c.copy()
    at_trigger[22] = (
        105.0  # a close AT the trigger before the breakout still lets it be the first close above
    )
    assert [p["variant"] for p in find_buy(h, lo, at_trigger, 1.0, seq(100.2), 25)] == ["W"]
    early = c.copy()
    early[22] = 105.2
    assert find_buy(h, lo, early, 1.0, seq(100.2), 25) == []
    # the breakout close exactly AT the trigger (105.0) is not above it: no break
    assert find_buy(h, lo, closes(26, 104.0, 105.0), 1.0, seq(100.2), 25) == []
    # more than 40 bars from L1: too old
    assert find_buy(np.r_[c, c], np.r_[c, c], np.r_[np.full(26, 104.0), c], 1.0, seq(100.2), 51) == []


def test_inverse_head_and_shoulders() -> None:
    """LS 101 at bar 5, N1 104.5 at 8, Head 99 at 12, N2 105 at 16, RS 101.2 at 20; the neckline slope 0.5 / 8 =
    0.0625: at bar 24 it is 104.5 + 0.0625 x 16 = 105.5, at the head 104.75 (height 5.75); the close 105.6 at 24."""
    c = closes(25, 104.0, 105.6)
    seq = [
        (5, 101.0, -1, False),
        (8, 104.5, 1, False),
        (12, 99.0, -1, False),
        (16, 105.0, 1, False),
        (20, 101.2, -1, False),
    ]
    got = {p["family"]: p for p in find_buy(c, c, c, 1.0, seq, 24)}
    assert set(got) == {"ihs", "st"}  # the same swings are also a sweep-turn (101.2 > 99 + 0.9)
    ihs = got["ihs"]
    assert (
        ihs["trigger"] == pytest.approx(105.5)
        and ihs["height"] == pytest.approx(5.75)
        and ihs["extreme"] == 99.0
    )
    # a head only 0.4 below the shoulders (< 0.5 ATR): no H&S
    seq2 = [*seq[:2], (12, 100.7, -1, False), *seq[3:]]
    assert "ihs" not in {p["family"] for p in find_buy(c, c, c, 1.0, seq2, 24)}


def test_base_then_its_break() -> None:
    # bars 0..19 inside 100 .. 101 (1.0 <= 1.5 x ATR 1), bar 20 closes 101.3 above: a base of the longest run (20 bars
    # back to bar 0); the box 100 .. 101
    h, lo = np.r_[np.full(20, 101.0), 101.5], np.r_[np.full(20, 100.0), 100.8]
    c = np.r_[np.full(20, 100.5), 101.3]
    (b,) = find_base(h, lo, c, np.ones(21), 20)
    assert (b["side"], b["start"], b["box"], b["extreme"], b["trigger"]) == (
        1,
        0,
        (0, 19, 100.0, 101.0),
        100.0,
        101.0,
    )
    assert find_base(h, lo, np.r_[np.full(20, 100.5), 100.9], np.ones(21), 20) == []  # inside: no break
    # a close exactly AT the base's high (101.0) or low (100.0) is not a break either way
    assert find_base(h, lo, np.r_[np.full(20, 100.5), 101.0], np.ones(21), 20) == []
    assert find_base(h, lo, np.r_[np.full(20, 100.5), 100.0], np.ones(21), 20) == []
    # a wide bar 10 bars back (102 - 100 > 1.5): the run stops at 9 bars (11 .. 19)
    h2 = h.copy()
    h2[10] = 102.0
    (b2,) = find_base(h2, lo, c, np.ones(21), 20)
    assert b2["start"] == 11


def test_patterns_at_mirrors_sells_and_caps_the_height() -> None:
    """An M: the mirror of a W (highs 100 / 100.2 around a trough 95; the breakdown close 94.5)."""
    n = 26
    h = np.full(n, 97.0)
    lo = np.full(n, 96.0)
    c = np.full(n, 96.5)
    h[10], lo[15], h[20], c[25], lo[25] = 100.0, 95.0, 99.8, 94.5, 94.4
    piv = Pivots(
        np.array([10, 15, 20]), np.array([100.0, 95.0, 99.8]), np.array([1, -1, 1]), np.array([12, 17, 22])
    )
    # height 100 - 95 = 5: allowed with ATR 1.3 (4 x 1.3 = 5.2), refused with ATR 1.2 (4.8)
    atr = np.full(n, 1.3)
    got = patterns_at(Bars(np.arange(n), np.arange(n) + 1, c, h, lo, c), atr, piv, 25)
    m = [p for p in got if p["family"] == "w"]
    assert len(m) == 1 and m[0]["side"] == -1 and m[0]["variant"] == "M"
    assert m[0]["extreme"] == 100.0 and m[0]["trigger"] == 95.0
    assert m[0]["stop"] == pytest.approx(100.26)  # 0.2 ATR (1.3) beyond the extreme
    assert [lab for _, _, lab in m[0]["points"]] == ["H1", "T", "H2"]
    refused = patterns_at(Bars(np.arange(n), np.arange(n) + 1, c, h, lo, c), np.full(n, 1.2), piv, 25)
    assert [p for p in refused if p["family"] == "w"] == []


def test_confirmation_b_by_hand() -> None:
    """Breakout bar d = 0 (high 10); bar 1 a new high 11; bar 2's low 9.9 is 1.1 >= 1 ATR below it: the pullback
    (the high frozen at 11); bar 3 dips to 9.8; bar 4 closes 11.2 above 11: confirmed at bar 4."""
    h = np.array([10.0, 11.0, 10.5, 10.4, 11.3])
    lo = np.array([9.5, 10.2, 9.9, 9.8, 10.6])
    c = np.array([9.9, 10.9, 10.0, 10.5, 11.2])
    assert confirm_b(h, lo, c, 0, 9.0, 1.0, 1) == {"k": 4.0, "hi": 11.0, "pull": 9.8}
    assert confirm_b(h, lo, c, 0, 9.85, 1.0, 1) is None  # bar 3's low reaches the extreme first
    assert confirm_b(h, lo, c, 0, 9.8, 1.0, 1) is None  # touching the extreme (9.8) is reaching it
    assert confirm_b(h, lo, c, 0, 9.0, 1.0, 1, max_wait=3) is None  # bar 4 is 4 bars after d
    assert confirm_b(h, lo, c[:4], 0, 9.0, 1.0, 1) is None  # not yet confirmed at bar 3
    # the sell mirrors it exactly
    s = confirm_b(-lo, -h, -c, 0, -9.0, 1.0, -1)
    assert s == {"k": 4.0, "hi": -11.0, "pull": -9.8}


def test_at_level_at_swept_base_and_the_sweep_turn_rule() -> None:
    w = dict(family="w", side=1, extreme=100.0, higher_low=100.1, box=None)
    levels = [(100.3, "x2"), (99.0, "PDL")]
    # z 0.5: |100 - 100.3| <= 0.5 -> at; the nearest level wins
    assert at_level(w, 101.0, levels, 0.5, 2.0) == dict(
        level=100.3, level_kind="x2", how="at", dist=pytest.approx(0.3)
    )
    # a level at 101.0: the extreme 100 is 1.0 past it, minus the zone 0.5 = 0.5 <= sweep 2, the close 101.6 back
    # above 101 - 0.5 -> swept
    assert at_level(w, 101.6, [(101.0, "x2")], 0.5, 2.0)["how"] == "swept"
    assert at_level(w, 100.4, [(101.0, "x2")], 0.5, 2.0) is None  # the close not back above 100.5
    st = dict(w, family="st")
    assert at_level(st, 101.6, [(100.3, "x2")], 0.5, 2.0) is None  # a sweep-turn needs 'swept'
    st_ok = dict(st, higher_low=100.6)
    assert at_level(st_ok, 101.6, [(101.0, "x2")], 0.5, 2.0)["how"] == "swept"
    assert (
        at_level(dict(st, higher_low=100.4), 101.6, [(101.0, "x2")], 0.5, 2.0) is None
    )  # higher low below the zone
    base = dict(family="base", side=1, extreme=100.0, box=(0, 9, 100.0, 101.0), higher_low=np.nan)
    assert at_level(base, 101.2, [(101.4, "x2")], 0.5, 2.0)["how"] == "base"  # 101 >= 101.4 - 0.5
    assert at_level(base, 101.2, [(101.6, "x2")], 0.5, 2.0) is None
    # two qualifying levels ('at' both, z 0.5): the nearer to the extreme 100.0 wins (99.8 at 0.2, not 100.4 at
    # 0.4), whatever their order
    two = [(100.4, "x2"), (99.8, "PDL")]
    assert at_level(w, 101.0, two, 0.5, 2.0)["level"] == 99.8
    assert at_level(w, 101.0, two[::-1], 0.5, 2.0)["level"] == 99.8


def test_next_level() -> None:
    lv = np.array([95.0, 100.2, 101.0, 103.0, 106.0])
    # a buy from 100.5 (z 0.5, own level 100.2): beyond 101.0 by more than the zone: 103.0 (101.0 is only 0.5 away)
    assert next_level(lv, 100.5, 1, 0.5, 100.2) == 103.0
    assert next_level(lv, 100.5, -1, 0.5, 100.2) == 95.0
    assert np.isnan(next_level(lv, 107.0, 1, 0.5, 100.2))


# --- the owner's H1 levels ----------------------------------------------------------------------------------


def test_fractals_and_merge() -> None:
    h = np.array([1.0, 2, 5, 2, 1, 2, 5, 3, 1])
    lo = h - 1
    hi_i, lo_i = fractals(h, lo, 2)
    assert list(hi_i) == [2, 6] and list(lo_i) == [4]
    # merge within 0.5 of the zone's FIRST price: 10.0, 10.3, 10.5 | 10.6 (0.6 from 10.0) starts a new zone
    z = merge(np.array([10.5, 10.0, 10.6, 10.3]), np.array([1, -1, 1, 1]), 0.5)
    assert z[0] == (pytest.approx((10.0 + 10.3 + 10.5) / 3), 3, 2, 1) and z[1] == (10.6, 1, 1, 0)


def li(**kw: object) -> LevelInputs:
    """Hand-built H1 inputs: 20 complete bars (avail 1..20), ATR 4 at the last; swings as given."""
    base: dict[str, object] = dict(
        avail=np.arange(1, 21, dtype=np.int64),
        h=np.full(20, 105.0),
        lo=np.full(20, 95.0),
        atr=np.full(20, 4.0),
        s_i=np.array([2, 5, 8, 11], int),
        s_p=np.array([101.0, 101.5, 98.0, 103.0]),
        s_k=np.array([1, -1, -1, 1]),
        s_known=np.array([4, 7, 10, 13], np.int64),
        d_avail=np.array([5, 15], np.int64),
        d_high=np.array([104.0, 104.2]),
        d_low=np.array([96.0, 96.5]),
    )
    base.update(kw)
    return LevelInputs(**base)  # type: ignore[arg-type]


def test_two_touches_on_one_side_are_an_x2_zone_not_a_flip() -> None:
    """Two tops 101.0 (bar 2) and 101.3 (bar 4) merge into a zone at 101.15 with 2 touches, both tops: 'x2' (3+
    touches or tops and lows would be 'x3+ / flip'); the latest top above 100 (101.3) sits inside the tolerance of
    that zone and is dropped; PDH 104.2 is 0.8 from the 5d high: dropped."""
    y = li(
        s_i=np.array([2, 4]),
        s_p=np.array([101.0, 101.3]),
        s_k=np.array([1, 1]),
        s_known=np.array([4, 6], np.int64),
    )
    got, _ = levels_at(y, 20, 100.0)
    assert got == [(pytest.approx(101.15), "x2"), (105.0, "5d high"), (95.0, "5d low"), (96.5, "PDL")]


def test_levels_at_by_hand() -> None:
    """At t = 20 (bar 19 complete, ATR 4, tolerance 1.0): the swings 101.0 (top) and 101.5 (low) merge into a
    flipped zone at 101.25; 98.0 and 103.0 stay single (no zone); the five-day high / low 105 / 95; the last server
    day (avail 15): PDH 104.2 is 0.8 from the 5d high and dropped, PDL 96.5 is 1.5 from the 5d low and kept; the
    latest top above 100 is 103.0 (bar 11), the latest low below it 98.0 (bar 8)."""
    got, a = levels_at(li(), 20, 100.0)
    assert a == 4.0
    assert got == [
        (101.25, "x3+ / flip"),
        (105.0, "5d high"),
        (95.0, "5d low"),
        (96.5, "PDL"),
        (103.0, "last top"),
        (98.0, "last low"),
    ]
    # at t = 12 the swing at bar 11 (known 13) is not known yet, and the last complete day is the first (104 / 96):
    # PDH 104.0 and PDL 96.0 are exactly 1.0 (the tolerance) from the 5d high / low: dropped; the last top above
    # 100 is 101.0 (bar 2), 0.25 from the flipped zone 101.25: dropped too
    got12, _ = levels_at(li(), 12, 100.0)
    assert got12 == [(101.25, "x3+ / flip"), (105.0, "5d high"), (95.0, "5d low"), (98.0, "last low")]
    assert levels_at(li(atr=np.full(20, np.nan)), 20, 100.0) == ([], pytest.approx(np.nan, nan_ok=True))


def test_level_inputs_keep_only_complete_hours_and_server_days() -> None:
    """M1 bars from Monday 2026-09-28 00:00 UTC to 02:29 at 4000 +- 1 (the 01:00 hour trades up to 4010): at 02:30
    the hours 00:00 and 01:00 are complete (avail = their last minute + 1), 02:00 is running; the server day of
    Monday (Athens, from 09-27 21:00 UTC) is running, so no D1 bar is complete."""
    opens = pd.date_range(utc("2026-09-28 00:00"), utc("2026-09-28 02:29"), freq="1min")
    h = np.full(len(opens), 4001.0)
    h[90] = 4010.0  # 01:30
    y = level_inputs(opens, h, h - 2.0, h - 1.0, utc("2026-09-28 02:30"))
    assert list(y.h) == [4001.0, 4010.0]
    assert list(y.avail) == [utc("2026-09-28 01:00").value, utc("2026-09-28 02:00").value]
    assert len(y.d_avail) == 0


def test_window_and_week6_rule() -> None:
    w, z = "07:00-09:00", "Asia/Bangkok"
    assert in_window(utc("2026-09-30 00:00"), w, z) and in_window(utc("2026-09-30 01:59"), w, z)
    assert not in_window(utc("2026-09-30 02:00"), w, z) and not in_window(utc("2026-09-29 23:59"), w, z)
    assert Plan1B2Params().second_same_side is True  # the frozen rules (CHECKLIST 61-63): on
    s = Plan1B2(Plan1B2Params(second_same_side=True))
    at = utc("2026-09-30 01:10")
    assert s.second_trade("XAUUSD", at, 1) == (True, "the first B2 of the morning")
    s.attach_entries(
        "XAUUSD",
        [
            PastEntry(datetime(2026, 9, 30, 0, 20, tzinfo=UTC), Side.SELL, "setup_plan1_b2m5"),
            PastEntry(datetime(2026, 9, 29, 0, 20, tzinfo=UTC), Side.BUY, "setup_plan1_b2"),
        ],
    )
    ok, text = s.second_trade(
        "XAUUSD", at, 1
    )  # the morning's first was a SELL (yesterday's BUY is another day)
    assert not ok and "a flip: skipped" in text and "SELL at 07:20" in text
    assert s.second_trade("XAUUSD", at, -1)[0]
    assert s.second_trade("EURUSD", at, 1)[0]  # another symbol's entries do not count
    assert Plan1B2(Plan1B2Params(second_same_side=False)).second_trade("XAUUSD", at, 1)[0]


def test_params_and_catalog() -> None:
    with pytest.raises(ValidationError):
        Plan1B2Params(window="09:00-07:00")
    with pytest.raises(ValidationError):
        Plan1B2Params(window_zone="Mars/Base")
    names = set(default_registry().names)
    assert {"setup_plan1_b2", "setup_plan1_b2m5"} <= names
    assert Plan1B2.entry_group == Plan1B2M5.entry_group == ("setup_plan1_b2", "setup_plan1_b2m5")


# --- the strategy on hand-built readings ---------------------------------------------------------------------


def m1_frame(last_open: str, n: int = 200) -> pd.DataFrame:
    opens = pd.date_range(end=utc(last_open), periods=n, freq="1min")
    df = pd.DataFrame(
        {"open_time": opens, "open": 4000.0, "high": 4001.0, "low": 3999.0, "close": 4000.0, "spread": 30.0},
        index=opens + pd.Timedelta(minutes=1),
    )
    return df


def ctx_at(df: pd.DataFrame, bid: float = 4000.0, ask: float = 4000.3) -> StrategyContext:
    at = pd.Timestamp(df.index[-1]).to_pydatetime()
    market = MarketContext(
        symbol="XAUUSD",
        decision_time_utc=at,
        entry_timeframe=Timeframe.M1,
        higher_timeframe=Timeframe.H4,
        states=(state(Timeframe.M1, at, close=bid), state(Timeframe.H4, at, close=bid)),
        bid=bid,
        ask=ask,
        spread_points=(ask - bid) / XAUUSD_SPEC.point,
    )
    return StrategyContext(market, {Timeframe.M1: df, Timeframe.H1: wide_h1(at)}, at, XAUUSD_SPEC)


def cand(side: int = 1, stop: float = 3990.0, nl: float = 4030.0) -> Candidate:
    pat = dict(
        family="w",
        variant="W",
        side=side,
        extreme=3992.0,
        height=8.0,
        trigger=4002.0,
        points=[(20, 3992.0, "L1"), (25, 4002.0, "P"), (30, 3992.2, "L2")],
    )
    return Candidate(
        side,
        stop,
        abs(4000.0 - stop),
        pat,
        dict(level=3992.5, level_kind="x2", how="at"),
        1.0,
        10.0,
        nl,
        utc("2026-09-30 01:00").value,
        {"k": 199.0, "hi": 3999.5, "pull": 3995.0},
        4000.0,
    )


def test_the_entry_its_target_and_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Plan1B2()
    monkeypatch.setattr(Plan1B2, "candidates", lambda self, f, y=None: [cand()])
    sig = s.evaluate(ctx_at(m1_frame("2026-09-30 01:09")))  # decided at 01:10 UTC = 08:10 Thai
    # the ask 4000.3, the stop 3990: risk 10.3; the next level 4030 is 29.7 > 10.3 away: the target
    assert sig.action is Action.BUY and (sig.entry_price, sig.stop_loss, sig.take_profit) == (
        4000.3,
        3990.0,
        4030.0,
    )
    assert sig.score == pytest.approx(90.0)  # 100 - the risk at the confirming close (10)
    names = [c.name for c in sig.conditions]
    assert names == [
        "rule",
        "h1_atr",
        "regime",
        "level",
        "pattern",
        "agreement",
        "pools",
        "h4_atr_change",
        "second_trade",
        "stop_distance",
        "spread",
    ]
    detail = {c.name: c.detail for c in sig.conditions}
    assert (
        detail["level"].startswith("3992.50 x2 (at)")
        and detail["second_trade"] == "the first B2 of the morning"
    )
    assert (
        detail["stop_distance"].startswith("10.30 to 3990.00")
        and "4030.00 (the next level)" in detail["stop_distance"]
    )
    # a next level only 5 away (< 1 risk): no target, the far cap 10 R: 4000.3 + 10 x 10.3
    monkeypatch.setattr(Plan1B2, "candidates", lambda self, f, y=None: [cand(nl=4005.0)])
    assert s.evaluate(ctx_at(m1_frame("2026-09-30 01:09"))).take_profit == pytest.approx(4103.3)


def test_holds_outside_the_window_off_its_bar_and_on_a_flip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Plan1B2, "candidates", lambda self, f, y=None: [cand()])
    s, s5 = Plan1B2(Plan1B2Params(second_same_side=True)), Plan1B2M5()
    assert ReasonCode.OUTSIDE_SESSION.value in s.evaluate(ctx_at(m1_frame("2026-09-30 02:00"))).reason_codes
    assert s.evaluate(ctx_at(m1_frame("2026-09-30 01:09"))).action is Action.BUY
    assert "not an M5 close" in s5.evaluate(ctx_at(m1_frame("2026-09-30 01:08"))).explanation  # 01:09
    assert s5.evaluate(ctx_at(m1_frame("2026-09-30 01:09"))).action is Action.BUY  # 01:10 is an M5 close
    s.attach_entries(
        "XAUUSD", [PastEntry(datetime(2026, 9, 30, 0, 5, tzinfo=UTC), Side.SELL, "setup_plan1_b2")]
    )
    held = s.evaluate(ctx_at(m1_frame("2026-09-30 01:09")))
    assert held.action is Action.HOLD and [c.name for c in held.conditions if not c.passed] == [
        "second_trade"
    ]


def test_exits_structure_and_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """A buy filled at 01:10:00.4: the structure exit when the last TF bar closes below the last confirmed trough;
    the time exit 60 bars after the entry bar (M1: 02:10; M5: 06:10)."""
    pos = OpenPosition(
        Side.BUY, 4000.3, 3990.0, 3990.0, 4030.0, datetime(2026, 9, 30, 1, 10, 0, 400_000, tzinfo=UTC)
    )

    def frame_with(close: float, trough: float, first_open: str = "2026-09-30 01:10"):  # type: ignore[no-untyped-def]
        def f(self, m1, at):  # type: ignore[no-untyped-def]
            t = np.array([pd.Timestamp(first_open, tz="UTC").value], np.int64)
            bars = Bars(
                t,
                t + 60 * 10**9,
                np.array([4000.0]),
                np.array([4001.0]),
                np.array([3994.0]),
                np.array([close]),
            )
            piv = Pivots(np.array([0]), np.array([trough]), np.array([-1]), np.array([0]))
            return B._Frame(bars, np.ones(1), piv)

        return f

    s = Plan1B2()
    monkeypatch.setattr(Plan1B2, "_frame", frame_with(3994.9, 3995.0))
    advice = s.manage_position(ctx_at(m1_frame("2026-09-30 01:10")), pos)
    assert advice is not None and advice.close is ExitReason.SIGNAL  # 3994.9 < the trough 3995.0
    monkeypatch.setattr(Plan1B2, "_frame", frame_with(3995.0, 3995.0))
    assert s.manage_position(ctx_at(m1_frame("2026-09-30 01:10")), pos) is None  # at the trough: not below
    monkeypatch.setattr(Plan1B2, "_frame", frame_with(3994.0, 3995.0, first_open="2026-09-30 01:09"))
    assert s.manage_position(ctx_at(m1_frame("2026-09-30 01:09")), pos) is None  # the bar before the entry
    monkeypatch.setattr(Plan1B2, "_frame", frame_with(4005.0, 3995.0))
    time_out = s.manage_position(ctx_at(m1_frame("2026-09-30 02:09")), pos)  # decided at 02:10 = 60 M1 bars
    assert time_out is not None and time_out.close is ExitReason.TIME_STOP
    assert s.manage_position(ctx_at(m1_frame("2026-09-30 02:08")), pos) is None
    s5 = Plan1B2M5()
    assert s5.manage_position(ctx_at(m1_frame("2026-09-30 02:09")), pos) is None  # M5: 60 bars = 5 hours
    assert s5.manage_position(ctx_at(m1_frame("2026-09-30 06:09")), pos).close is ExitReason.TIME_STOP  # type: ignore[union-attr]


def test_tf_bars_keep_complete_bars_only() -> None:
    opens = pd.date_range(utc("2026-09-30 00:00"), utc("2026-09-30 00:12"), freq="1min")
    v = np.arange(13, dtype=float)
    b = tf_bars(opens, v, v + 1, v - 1, v + 0.5, 5, utc("2026-09-30 00:13"))
    # 00:00 and 00:05 are complete; 00:10 runs to 00:15
    assert list(b.t_open) == [utc("2026-09-30 00:00").value, utc("2026-09-30 00:05").value]
    assert (
        list(b.o) == [0.0, 5.0]
        and list(b.h) == [5.0, 10.0]
        and list(b.lo) == [-1.0, 4.0]
        and list(b.c) == [4.5, 9.5]
    )
    # at 00:14 the 00:10 bar still runs (to 00:15)
    assert len(tf_bars(opens, v, v + 1, v - 1, v + 0.5, 5, utc("2026-09-30 00:14")).c) == 2
    one = tf_bars(opens, v, v + 1, v - 1, v + 0.5, 1, utc("2026-09-30 00:13"))
    assert len(one.c) == 13 and one.avail[-1] == utc("2026-09-30 00:13").value


def test_the_regime_switch_stops_new_b2_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """D1 ATR(20) 59.99 < 60: the B2 entry is held with the failed 'regime' condition; 60.00 trades."""
    monkeypatch.setattr(Plan1B2, "candidates", lambda self, f, y=None: [cand()])
    df = m1_frame("2026-09-30 01:09")
    for rng, action in ((59.99, Action.HOLD), (60.0, Action.BUY)):
        base = ctx_at(df)
        ctx = StrategyContext(
            base.market,
            {**base.frames, Timeframe.H1: h1_days([rng] * 20, "2026-09-10")},
            base.now_utc,
            base.spec,
        )
        sig = Plan1B2().evaluate(ctx)
        assert sig.action is action
        assert {c.name: c.passed for c in sig.conditions}["regime"] is (action is Action.BUY)


def test_the_bars_each_piece_wants() -> None:
    """The backtest skips a bar no plan1 strategy wants while the lane is flat: B2 in 07:00-09:00 Thai on its own
    TF's closes, the ORB from the close of the bar after the range to the window's end, the straddle never (quotes)."""
    from app.strategy.plan1 import Plan1Orb, Plan1Straddle

    b1, b5, orb = Plan1B2(), Plan1B2M5(), Plan1Orb()
    assert b1.wants_bar(datetime(2026, 9, 30, 0, 0, tzinfo=UTC)) and b1.wants_bar(
        datetime(2026, 9, 30, 1, 59, tzinfo=UTC)
    )
    assert not b1.wants_bar(datetime(2026, 9, 30, 2, 0, tzinfo=UTC))
    assert b5.wants_bar(datetime(2026, 9, 30, 1, 5, tzinfo=UTC)) and not b5.wants_bar(
        datetime(2026, 9, 30, 1, 6, tzinfo=UTC)
    )
    assert not orb.wants_bar(datetime(2026, 9, 30, 6, 15, tzinfo=UTC))  # the range's last bar closes here
    assert orb.wants_bar(datetime(2026, 9, 30, 6, 16, tzinfo=UTC)) and orb.wants_bar(
        datetime(2026, 9, 30, 7, 15, tzinfo=UTC)
    )
    assert not orb.wants_bar(datetime(2026, 9, 30, 7, 16, tzinfo=UTC))
    assert not orb.wants_bar(datetime(2026, 10, 3, 6, 30, tzinfo=UTC))  # Saturday
    assert not Plan1Straddle().wants_bar(datetime(2026, 9, 30, 12, 30, tzinfo=UTC))
