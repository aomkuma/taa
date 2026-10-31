"""Tests for eye/state11.py: M30 built from M15, and the looks (eye/BOT_RULES.md "Data", "The looks")."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

s11 = importlib.import_module("eye.state11")


def m15(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(r[0], tz="UTC") for r in rows])
    return pd.DataFrame(
        {
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
        },
        index=idx,
    )


PAIR = [("2026-04-06 10:00", 10, 15, 9, 12), ("2026-04-06 10:15", 12, 14, 8, 11)]


def test_normal_pair_makes_one_bar() -> None:
    out = s11.m30_from_m15(m15(PAIR))
    assert len(out) == 1


def test_label_is_first_bars_open_time() -> None:
    out = s11.m30_from_m15(m15(PAIR))
    assert out.index[0] == pd.Timestamp("2026-04-06 10:00", tz="UTC")


def test_ohlc_aggregation() -> None:
    r = s11.m30_from_m15(m15(PAIR)).iloc[0]
    assert (r.open, r.high, r.low, r.close) == (10, 15, 8, 11)


def test_second_half_slot_pairs_30_and_45() -> None:
    out = s11.m30_from_m15(m15([("2026-04-06 10:30", 1, 2, 0, 1.5), ("2026-04-06 10:45", 1.5, 3, 1, 2)]))
    assert out.index[0] == pd.Timestamp("2026-04-06 10:30", tz="UTC")
    assert out.iloc[0].close == 2


def test_slot_with_only_the_00_bar_has_no_bar() -> None:
    assert s11.m30_from_m15(m15(PAIR[:1])).empty


def test_slot_with_only_the_15_bar_has_no_bar() -> None:
    assert s11.m30_from_m15(m15(PAIR[1:])).empty


def test_out_of_order_input_is_sorted() -> None:
    rows = [PAIR[1], ("2026-04-06 10:45", 1, 2, 0, 1), ("2026-04-06 10:30", 1, 2, 0, 1), PAIR[0]]
    out = s11.m30_from_m15(m15(rows))
    assert list(out.index) == [
        pd.Timestamp("2026-04-06 10:00", tz="UTC"),
        pd.Timestamp("2026-04-06 10:30", tz="UTC"),
    ]
    assert out.iloc[0].open == 10 and out.iloc[0].close == 11


def test_15_bar_with_missing_00_partner_next_to_complete_slot() -> None:
    rows = [("2026-04-06 09:15", 5, 6, 4, 5), *PAIR]
    out = s11.m30_from_m15(m15(rows))
    assert list(out.index) == [pd.Timestamp("2026-04-06 10:00", tz="UTC")]


def test_other_columns_are_left_out() -> None:
    df = m15(PAIR)
    df["volume"] = 1
    assert list(s11.m30_from_m15(df).columns) == ["open", "high", "low", "close"]


def frame(n: int, gap: bool = False) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC")
    if gap:
        idx = idx[: n // 2].append(idx[n // 2 :] + pd.Timedelta(days=2))
    return pd.DataFrame({"close": range(n)}, index=idx)


@pytest.mark.parametrize(("tf", "days", "n"), [("M30", 4, 184), ("M30", 7, 322), ("M5", 2, 548)])
def test_look_exact_count(tf: str, days: float, n: int) -> None:
    out = s11.look(frame(1000), tf, days)
    assert len(out) == n
    assert out["close"].iloc[-1] == 999


def test_short_frame_returned_whole() -> None:
    assert len(s11.look(frame(50), "M30", 4)) == 50


def test_weekend_gap_does_not_shorten_count() -> None:
    assert len(s11.look(frame(1000, gap=True), "M30", 4)) == 184


def test_unknown_timeframe_raises() -> None:
    with pytest.raises(ValueError):
        s11.look(frame(10), "M10", 1)


# --- added after review: each test names the mutation it kills -------------------------------------


def test_high_is_max_of_both_bars_second_higher() -> None:
    """Kills: high max -> first (the second bar holds the higher high)."""
    rows = [("2026-04-06 10:00", 10, 11, 9, 10), ("2026-04-06 10:15", 10, 20, 9.5, 10)]
    assert s11.m30_from_m15(m15(rows)).iloc[0].high == 20


def test_low_is_min_of_both_bars_first_lower() -> None:
    """Kills: low min -> last (the first bar holds the lower low)."""
    rows = [("2026-04-06 10:00", 10, 11, 2, 10), ("2026-04-06 10:15", 10, 11, 9, 10)]
    assert s11.m30_from_m15(m15(rows)).iloc[0].low == 2


def test_open_is_first_bars_open_not_min() -> None:
    """Kills: open first -> min (the first bar's open is the higher one)."""
    rows = [("2026-04-06 10:00", 10, 12, 4, 6), ("2026-04-06 10:15", 5, 12, 4, 7)]
    r = s11.m30_from_m15(m15(rows)).iloc[0]
    assert (r.open, r.close) == (10, 7)


def test_second_half_slot_full_ohlc() -> None:
    """Kills: high max -> first, low min -> last, open first -> min, in the :30/:45 slot too."""
    rows = [("2026-04-06 10:30", 9, 10, 1, 5), ("2026-04-06 10:45", 4, 30, 3, 6)]
    r = s11.m30_from_m15(m15(rows)).iloc[0]
    assert (r.open, r.high, r.low, r.close) == (9, 30, 1, 6)


def test_look_zero_days_is_empty() -> None:
    """Kills: removing the n <= 0 branch (iloc[-0:] would return the whole frame)."""
    assert s11.look(frame(100), "M30", 0).empty


def test_look_negative_days_is_empty() -> None:
    """Kills: removing the n <= 0 branch (iloc[-(-n):] would return a tail-cut frame)."""
    assert s11.look(frame(100), "M30", -1).empty


def test_bars_per_day_m15_and_h1() -> None:
    """Kills: BARS_PER_DAY M15 / H1 changed."""
    assert len(s11.look(frame(1000), "M15", 2)) == 184
    assert len(s11.look(frame(1000), "H1", 4)) == 92


def test_bars_per_day_table() -> None:
    """Kills: any BARS_PER_DAY entry changed."""
    assert s11.BARS_PER_DAY == {"M30": 46, "M5": 274, "M15": 92, "H1": 23}


def test_off_grid_bar_inside_complete_slot_is_ignored() -> None:
    """Kills: removing the :00/:15 filter (a 10:05 bar must not stop the slot or change its values)."""
    rows = [PAIR[0], ("2026-04-06 10:05", 99, 99, 0, 50), PAIR[1]]
    out = s11.m30_from_m15(m15(rows))
    assert len(out) == 1
    r = out.iloc[0]
    assert (r.open, r.high, r.low, r.close) == (10, 15, 8, 11)


def test_off_grid_bar_does_not_complete_a_slot() -> None:
    """Kills: removing the :00/:15 filter (a :00 bar plus a 10:05 bar is not a pair)."""
    rows = [PAIR[0], ("2026-04-06 10:05", 1, 2, 0, 1)]
    assert s11.m30_from_m15(m15(rows)).empty


def test_duplicate_timestamp_keeps_first_in_input_order() -> None:
    """Kills: dedupe keep first -> last, and dedupe removed (input is already sorted, so the order is stable)."""
    rows = [PAIR[0], ("2026-04-06 10:00", 77, 88, 1, 66), PAIR[1]]
    out = s11.m30_from_m15(m15(rows))
    assert len(out) == 1
    r = out.iloc[0]
    assert (r.open, r.high, r.low, r.close) == (10, 15, 8, 11)


def test_fractional_days_floor_not_round_or_ceil() -> None:
    """Kills: floor -> round / ceil (H1 0.5 d = 11.5 -> 11; M30 0.51 d = 23.46 -> 23)."""
    assert len(s11.look(frame(1000), "H1", 0.5)) == 11
    assert len(s11.look(frame(1000), "M30", 0.51)) == 23
    assert len(s11.look(frame(1000), "M30", 0.5)) == 23


def test_float_error_just_under_integer_still_gives_integer() -> None:
    """Kills: removing the 1e-9 (0.49999999999999994 * 46 = 22.999999999999996 must give 23)."""
    assert len(s11.look(frame(1000), "M30", 0.49999999999999994)) == 23
    assert len(s11.look(frame(1000), "M30", 0.9999999999999999)) == 46


# --- the rule 11 walk (piece 2) ----------------------------------------------------------------------
# Common range: LOW 0 at bar 10 and HIGH 100 at bar 20 -> lo 0, hi 100, h 100; touch HIGH >= 88, LOW <= 12;
# break line up > 127, down < -27. Positions are bar positions; closes are flat unless set.

import numpy as np  # noqa: E402

from app.indicators.price_action import Swing, SwingKind  # noqa: E402


def pv(kind: str, price: float, pos: int) -> Swing:
    return Swing(SwingKind(kind), price, pos, pos + 2, pos, pos + 2)


def L(price: float, pos: int) -> Swing:
    return pv("LOW", price, pos)


def H(price: float, pos: int) -> Swing:
    return pv("HIGH", price, pos)


def closes(n: int, fill: float, **at: float) -> np.ndarray:
    c = np.full(n, fill, dtype=float)
    for k, v in at.items():
        c[int(k[1:])] = v  # c35=128 -> bar 35
    return c


def test_walk_first_pair_is_the_first_range_and_earlier_closes_are_untested() -> None:
    # pivots L0@10, H100@20; closes 500 at bars 5 and 15 lie before the second pivot: not tested.
    w = s11.walk([L(0, 10), H(100, 20)], closes(30, 50, c5=500, c15=500))
    r = w.range
    assert r is not None
    assert (r.e.pivot_pos, r.b.pivot_pos, r.lo, r.hi, r.legs, r.last_touch) == (10, 20, 0, 100, 1, "HIGH")
    assert w.last_break is None  # also: no break at all -> last break None


def test_walk_pair_with_h_zero_is_dropped() -> None:
    # (L50@10, H50@20) h=0 dropped; the next pair L0@30, H100@40 starts the range; close 500 at bar 15 untested.
    w = s11.walk([L(50, 10), H(50, 20), L(0, 30), H(100, 40)], closes(50, 50, c15=500))
    assert w.range is not None
    assert (w.range.e.pivot_pos, w.range.b.pivot_pos) == (30, 40)
    assert w.last_break is None


def test_walk_two_pairs_with_h_zero_in_a_row() -> None:
    # (L50@5,H50@10) and (L70@15,H70@20) both h=0 ("and so on"); L0@30,H100@40 starts the range.
    w = s11.walk([L(50, 5), H(50, 10), L(70, 15), H(70, 20), L(0, 30), H(100, 40)], closes(50, 50))
    assert w.range is not None
    assert (w.range.e.pivot_pos, w.range.b.pivot_pos) == (30, 40)


def test_walk_every_pair_h_zero_gives_nothing() -> None:
    assert s11.walk([L(5, 10), H(5, 20)], closes(30, 5)) == s11.Walk(None, None)


def test_walk_middle_pivot_is_ignored() -> None:
    # after L0,H100 (last touch HIGH): L50@30 and H87.99@40 are in the middle (LOW > 12, HIGH < 88).
    w = s11.walk([L(0, 10), H(100, 20), L(50, 30), H(87.99, 40)], closes(50, 50))
    assert w.range is not None
    assert (w.range.legs, w.range.last_touch) == (1, "HIGH")


def test_walk_touch_of_the_other_edge_adds_a_leg() -> None:
    # last touch HIGH (B=H100); L10@30 <= 12 touches the low edge -> legs 2, last touch LOW.
    w = s11.walk([L(0, 10), H(100, 20), L(10, 30)], closes(40, 50))
    assert w.range is not None
    assert (w.range.legs, w.range.last_touch) == (2, "LOW")


def test_walk_touch_beyond_the_edge_is_a_touch_and_the_edge_does_not_move() -> None:
    # L-20@30 is below lo=0 but no close is beyond -27 (closes 50): a touch, legs 2, lo stays 0.
    w = s11.walk([L(0, 10), H(100, 20), L(-20, 30)], closes(40, 50))
    assert w.range is not None
    assert (w.range.legs, w.range.last_touch, w.range.lo, w.range.hi) == (2, "LOW", 0, 100)


def test_walk_two_touches_of_one_edge_add_one_leg_only() -> None:
    # last HIGH; L50 (middle), H95@40 touches HIGH again: no leg (1). Then L5@50: other edge -> 2; H60 middle; L8@70 same edge -> 2.
    w = s11.walk([L(0, 10), H(100, 20), L(50, 30), H(95, 40)], closes(50, 50))
    assert w.range is not None
    assert w.range.legs == 1
    w = s11.walk([L(0, 10), H(100, 20), L(50, 30), H(95, 40), L(5, 50), H(60, 60), L(8, 70)], closes(80, 50))
    assert w.range is not None
    assert w.range.legs == 2


def test_walk_legs_count_to_four() -> None:
    # HIGH(B) -> L5 (2) -> H95 (3) -> L10 (4)
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30), H(95, 40), L(10, 50)], closes(60, 50))
    assert w.range is not None
    assert (w.range.legs, w.range.last_touch) == (4, "LOW")


def test_walk_touch_equality_edges_are_touches() -> None:
    # B=L0 (last LOW); H exactly 88 = lo + 0.88 h touches the high edge -> legs 2.
    w = s11.walk([H(100, 10), L(0, 20), H(88, 30)], closes(40, 50))
    assert w.range is not None
    assert w.range.legs == 2
    # B=H100 (last HIGH); L exactly 12 = lo + 0.12 h touches the low edge -> legs 2.
    w = s11.walk([L(0, 10), H(100, 20), L(12, 30)], closes(40, 50))
    assert w.range is not None
    assert w.range.legs == 2


def test_walk_break_up_wins_over_the_touch_and_e_lies_after_the_breaking_close() -> None:
    # L0@10,H100@20,L5@30 (touch, legs 2),H90@40: the close 128 at bar 35 (> 127) lies in segment (30,40] and is
    # tested before H90 is taken in. Up: E = the HIGH of (L5@30,H90@40) = H90@40, after bar 35; B = L60@50.
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30), H(90, 40), L(60, 50)], closes(70, 75, c35=128))
    assert w.last_break == s11.Break("up", 35)
    r = w.range
    assert r is not None
    assert (r.e.pivot_pos, r.b.pivot_pos, r.lo, r.hi, r.legs, r.last_touch) == (40, 50, 60, 90, 1, "LOW")


def test_walk_break_down() -> None:
    # close -28 at bar 25 (< -27) in segment (20,30] bounded by H100@20, L5@30. Down: E = the LOW = L5@30,
    # B = H60@40: range lo 5, hi 60.
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30), H(60, 40)], closes(50, 30, c25=-28))
    assert w.last_break == s11.Break("down", 25)
    r = w.range
    assert r is not None
    assert (r.e.pivot_pos, r.b.pivot_pos, r.lo, r.hi) == (30, 40, 5, 60)


def test_walk_first_breaking_close_in_time_decides_up_then_down() -> None:
    # segment (30,40]: 130 at bar 32 (up), -30 at bar 34 (down): up decides. E = H90@40, B = L60@50.
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30), H(90, 40), L(60, 50)], closes(60, 75, c32=130, c34=-30))
    assert w.last_break == s11.Break("up", 32)
    assert w.range is not None
    assert w.range.e.pivot_pos == 40


def test_walk_first_breaking_close_in_time_decides_down_then_up() -> None:
    # same segment, -30 at bar 32 then 130 at bar 34: down decides. E = the LOW = L5@30 (= P(i-1)), B = H90@40.
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30), H(90, 40), L(60, 50)], closes(60, 40, c32=-30, c34=130))
    assert w.last_break == s11.Break("down", 32)
    r = w.range
    assert r is not None
    assert (r.e.pivot_pos, r.b.pivot_pos) == (30, 40)


def test_walk_e_is_the_previous_pivot_when_it_is_of_the_breaks_kind() -> None:
    # segment (20,30] bounded by H100@20 and L5@30: close 130 at bar 25 breaks up; E = the HIGH = H100@20 = P(i-1),
    # B = L5@30 (the pivot after E): range lo 5, hi 100.
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30)], closes(40, 50, c25=130))
    assert w.last_break == s11.Break("up", 25)
    r = w.range
    assert r is not None
    assert (r.e.pivot_pos, r.b.pivot_pos, r.lo, r.hi, r.legs, r.last_touch) == (20, 30, 5, 100, 1, "LOW")


# After the first break up: range E=H90@40, B=L60@50 (lo 60, hi 90, h 30; up line 98.1, down line 51.9).
BASE = [L(0, 10), H(100, 20), L(5, 30), H(90, 40), L(60, 50)]


def test_walk_second_break_the_same_way_takes_new_e_b_and_updates_last_break() -> None:
    # H88@60 touches the high edge (88 >= 60 + 26.4); close 100 at bar 65 (> 98.1) in (60,70]: up again.
    # E = the HIGH of (H88@60, L70@70) = H88@60 (P(i-1)), B = L70@70.
    w = s11.walk([*BASE, H(88, 60), L(70, 70)], closes(80, 75, c35=128, c65=100))
    assert w.last_break == s11.Break("up", 65)
    r = w.range
    assert r is not None
    assert (r.e.pivot_pos, r.b.pivot_pos, r.lo, r.hi, r.legs) == (60, 70, 70, 88, 1)


def test_walk_break_the_other_way_is_a_trend_the_other_way() -> None:
    # same, but close 40 at bar 65 (< 51.9): down. E = the LOW of (H88@60, L70@70) = L70@70, B not fixed -> no range.
    w = s11.walk([*BASE, H(88, 60), L(70, 70)], closes(80, 75, c35=128, c65=40))
    assert w.last_break == s11.Break("down", 65)
    assert w.range is None


def test_walk_closes_between_e_and_b_are_ignored_even_beyond_the_old_lines() -> None:
    # E=H90@40, B=L60@50: the close -500 at bar 45 lies between them and is not tested; nothing after B breaks.
    w = s11.walk(BASE, closes(70, 75, c35=128, c45=-500))
    assert w.last_break == s11.Break("up", 35)
    assert w.range is not None
    assert (w.range.e.pivot_pos, w.range.b.pivot_pos) == (40, 50)


def test_walk_b_not_yet_fixed_gives_no_range_but_the_last_break() -> None:
    # break up at bar 35; E = H90@40 is the last pivot: no B, no range. Close 500 at bar 45 (after E) is untested.
    w = s11.walk(BASE[:4], closes(60, 75, c35=128, c45=500))
    assert w.range is None
    assert w.last_break == s11.Break("up", 35)


def test_walk_break_after_the_last_pivot_leaves_no_range() -> None:
    # range L0,H100,L5,H90 (touches, legs 3); close 130 at bar 45 after the last pivot (bar 40): break up, no range.
    w = s11.walk(BASE[:4], closes(50, 50, c45=130))
    assert w == s11.Walk(None, s11.Break("up", 45))
    w = s11.walk(BASE[:4], closes(50, 50, c45=-30))
    assert w == s11.Walk(None, s11.Break("down", 45))


def test_walk_close_exactly_on_the_break_line_is_not_a_break() -> None:
    # lo 0, hi 100: 127 and -27 exactly (strict comparison), in a segment and after the last pivot.
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30)], closes(40, 50, c25=127, c26=-27, c35=127, c36=-27))
    assert w.last_break is None
    assert w.range is not None
    assert w.range.legs == 2


def test_walk_pair_after_a_break_with_h_zero_is_dropped_and_none_left() -> None:
    # Kills: no h <= 0 check after a break. Break up at bar 35 (130 > 127); E=H140@40, B=L140@50 has h=0:
    # dropped; the next pair would be H200@60 alone -> no range, the break stands.
    w = s11.walk(
        [L(0, 10), H(100, 20), L(50, 30), H(140, 40), L(140, 50), H(200, 60)], closes(70, 75, c35=130)
    )
    assert w == s11.Walk(None, s11.Break("up", 35))


def test_walk_pair_after_a_break_with_h_zero_next_pair_takes_over() -> None:
    # Kills: dropping only E,B but not trying the next pair. Same, with L150@70 after H200@60:
    # the pair (H200@60, L150@70) starts the range: lo 150, hi 200.
    w = s11.walk(
        [L(0, 10), H(100, 20), L(50, 30), H(140, 40), L(140, 50), H(200, 60), L(150, 70)],
        closes(80, 175, c35=130),
    )
    assert w.range is not None
    assert (w.range.e.pivot_pos, w.range.b.pivot_pos, w.range.lo, w.range.hi) == (60, 70, 150, 200)


def test_walk_pivots_that_do_not_alternate_raise() -> None:
    # Kills: the "or pair" fallback / no alternation check.
    with pytest.raises(ValueError):
        s11.walk([L(0, 10), H(100, 20), H(95, 30)], closes(40, 50))


def test_walk_close_on_bs_own_bar_is_not_tested() -> None:
    # Kills: segment starting at prev_bar instead of prev_bar + 1 (130 at B's bar 20).
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30)], closes(40, 50, c20=130))
    assert w.last_break is None
    assert w.range is not None
    assert (w.range.e.pivot_pos, w.range.b.pivot_pos, w.range.lo, w.range.hi) == (10, 20, 0, 100)
    assert (w.range.legs, w.range.last_touch) == (2, "LOW")


def test_walk_close_on_the_pivots_own_bar_is_tested() -> None:
    # Kills: segment excluding P(i)'s bar (130 at bar 40 = H140's own bar).
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30), H(140, 40), L(100, 50)], closes(51, 75, c40=130))
    assert w.last_break == s11.Break("up", 40)
    assert w.range is not None
    assert (w.range.e.pivot_pos, w.range.b.pivot_pos, w.range.lo, w.range.hi) == (40, 50, 100, 140)


def test_walk_breaking_close_on_the_last_closed_bar_is_found() -> None:
    # Kills: the after-last test stopping one bar early (130 at bar 39 of 40).
    w = s11.walk([L(0, 10), H(100, 20), L(5, 30)], closes(40, 50, c39=130))
    assert w == s11.Walk(None, s11.Break("up", 39))


def test_walk_break_after_the_last_pivot_replaces_an_older_break() -> None:
    # Kills: keeping the older break. BASE breaks up at 35; range 60..90, up line 98.1; 100 at bar 55 breaks again.
    w = s11.walk(BASE, closes(60, 75, c35=128, c55=100))
    assert w == s11.Walk(None, s11.Break("up", 55))


def test_walk_touch_thresholds_pinned_on_both_sides() -> None:
    # Kills: >= 0.88 loosened (H87.99 is middle) and <= 0.12 loosened (L12.01 is middle).
    w = s11.walk([H(100, 10), L(0, 20), H(87.99, 30)], closes(40, 50))
    assert w.range is not None
    assert (w.range.legs, w.range.last_touch) == (1, "LOW")
    w = s11.walk([L(0, 10), H(100, 20), L(12.01, 30)], closes(40, 50))
    assert w.range is not None
    assert (w.range.legs, w.range.last_touch) == (1, "HIGH")


def test_walk_zero_one_or_dropped_pivots_give_nothing() -> None:
    # Kills: no guard for short input; a dropped pair leaving one pivot.
    assert s11.walk([], closes(10, 5)) == s11.Walk(None, None)
    assert s11.walk([L(0, 5)], closes(10, 5)) == s11.Walk(None, None)
    assert s11.walk([L(5, 10), H(5, 20), L(0, 30)], closes(40, 5)) == s11.Walk(None, None)


# --- the M30 state at now (piece 3) -----------------------------------------------------------------------

N, RB, TB = 1000, 184, 322  # frame bars, range look bars (4 days), trend look bars (7 days)
RANGE_FIRST, TREND_FIRST = N - RB, N - TB  # 816, 678: the first bar of each look


def rng(e_pos: int, legs: int) -> s11.Range:
    e, b = L(0, e_pos), H(100, e_pos + 10)
    return s11.Range(e, b, 0.0, 100.0, legs, "HIGH")


def cls(r: s11.Range | None, br: s11.Break | None, **kw: int) -> tuple[str, int]:
    return s11.classify(s11.Walk(r, br), kw.get("n", N), kw.get("rb", RB), kw.get("tb", TB))


def test_classify_case_1_sideways_with_e_in_the_range_look() -> None:
    assert cls(rng(900, 2), None) == ("sideways", 1)


def test_classify_case_1_wins_over_case_2() -> None:
    assert cls(rng(900, 2), s11.Break("up", 950)) == ("sideways", 1)


def test_classify_case_2_trending_way_of_the_break() -> None:
    assert cls(rng(900, 1), s11.Break("down", 900)) == ("down", 2)
    assert cls(None, s11.Break("up", 900)) == ("up", 2)


def test_classify_case_2_wins_over_case_3() -> None:
    assert cls(rng(500, 2), s11.Break("up", 700)) == ("up", 2)


def test_classify_case_3_old_e_and_no_break_in_the_trend_look() -> None:
    assert cls(rng(500, 2), None) == ("sideways", 3)
    assert cls(rng(500, 2), s11.Break("up", 100)) == ("sideways", 3)


def test_classify_case_4_legs_1_no_break_in_the_trend_look_or_no_range() -> None:
    assert cls(rng(900, 1), None) == ("none", 4)
    assert cls(rng(900, 1), s11.Break("up", 100)) == ("none", 4)
    assert cls(None, s11.Break("up", 100)) == ("none", 4)
    assert cls(None, None) == ("none", 4)


def test_classify_range_look_boundary_exact() -> None:
    assert cls(rng(RANGE_FIRST, 2), None) == ("sideways", 1)
    assert cls(rng(RANGE_FIRST - 1, 2), None) == ("sideways", 3)


def test_classify_trend_look_boundary_exact() -> None:
    assert cls(None, s11.Break("up", TREND_FIRST)) == ("up", 2)
    assert cls(None, s11.Break("up", TREND_FIRST - 1)) == ("none", 4)


def test_classify_look_sizes_move_the_boundaries() -> None:
    assert cls(rng(900, 2), None, rb=50) == ("sideways", 3)  # first bar of a 50-bar look is 950
    assert cls(rng(950, 2), None, rb=50) == ("sideways", 1)
    assert cls(None, s11.Break("up", 900), tb=50) == ("none", 4)
    assert cls(None, s11.Break("up", 950), tb=50) == ("up", 2)


def synth(legs: list[tuple[float, int]], start: str = "2026-03-02") -> pd.DataFrame:
    """A piecewise-linear close path (target, bars) on M30 bars from ``start`` (UTC); high/low = close +- 0.5."""
    c = [legs[0][0]]
    for tgt, nb in legs[1:]:
        c.extend(np.linspace(c[-1], tgt, nb + 1)[1:])
    a = np.array(c)
    idx = pd.date_range(start, periods=len(a), freq="30min", tz="UTC")
    return pd.DataFrame({"open": a, "high": a + 0.5, "low": a - 0.5, "close": a}, index=idx)


SAW = [
    (100, 0),
    (200, 30),
    (100, 30),
    (200, 30),
    (100, 30),
    (200, 30),
    (100, 30),
]  # 181 bars, 4 ZigZag pivots


def test_state_at_sideways_case_1_end_to_end() -> None:
    st = s11.state_at(synth(SAW))
    assert (st.kind, st.case) == ("sideways", 1)
    assert st.walk.range is not None
    assert (st.walk.range.legs, st.walk.range.e.pivot_pos, st.walk.range.b.pivot_pos) == (3, 30, 60)
    assert st.e_time == pd.Timestamp("2026-03-02 15:00", tz="UTC")
    assert st.b_time == pd.Timestamp("2026-03-03 06:00", tz="UTC")
    assert st.break_time is None


def test_state_at_trending_up_case_2_end_to_end() -> None:
    st = s11.state_at(synth([*SAW, (300, 60)]))
    assert (st.kind, st.case) == ("up", 2)
    assert st.walk.last_break == s11.Break("up", 219)
    assert st.break_time == pd.Timestamp("2026-03-02", tz="UTC") + pd.Timedelta(minutes=30 * 219)


def test_state_at_none_case_4_end_to_end() -> None:
    st = s11.state_at(synth([(100, 0), (200, 30), (100, 30), (150, 30)]))
    assert (st.kind, st.case) == ("none", 4)


def test_state_at_look_parameters_change_the_result() -> None:
    f = synth(SAW)
    assert s11.state_at(f, range_days=0.5).case == 3  # E at bar 30 of 181; a 23-bar look starts at 158
    up = synth([*SAW, (300, 60)])  # break at bar 219 of 241
    assert s11.state_at(up, trend_days=0.1).case == 4  # a 4-bar look starts at 237


def test_state_at_reads_only_the_last_1500_bars() -> None:
    tail = synth([(100, 0)] + [(200 if k % 2 == 0 else 100, 30) for k in range(50)], start="2027-01-01")
    old = synth([(0, 0), (5000, 50), (0, 50), (5000, 50), (0, 50)], start="2026-12-01")
    long = pd.concat([old, tail])
    assert len(long) > 1500
    st = s11.state_at(long)
    assert st.walk.range is not None
    assert (st.walk.range.lo, st.walk.range.hi) == (99.5, 200.5)  # the old part is not read
    assert st.case == 3  # E is far older than the range look, no break
    assert st == s11.state_at(long.iloc[-1500:])
    # the 1,500-bar constant is what cuts it: with a huge frame the old part changes the walk
    assert s11.state_at(long, frame_bars=10_000).walk.range.lo == -0.5  # type: ignore[union-attr]


def test_describe_sideways() -> None:
    st = s11.state_at(synth(SAW))
    assert s11.describe(st) == (
        "M30 sideways (case 1): lo 99.50, hi 200.50, E HIGH 200.50 02/03 22:00, "
        "B LOW 99.50 03/03 13:00, legs 3, leg 4, last touch LOW"
    )


def test_describe_trending() -> None:
    st = s11.state_at(synth([*SAW, (300, 60)]))
    assert s11.describe(st) == "M30 trending up (case 2): breaking close 06/03 20:30"


def test_describe_none() -> None:
    st = s11.state_at(synth([(100, 0), (200, 30), (100, 30), (150, 30)]))
    assert s11.describe(st) == "M30 none (case 4): no side"


def test_describe_thai_time_crosses_midnight() -> None:
    t = pd.Timestamp("2026-03-02 20:30", tz="UTC")  # Thai = UTC + 7 -> next day 03:30
    st = s11.M30State("up", 2, s11.Walk(None, s11.Break("up", 1)), None, None, t)
    assert s11.describe(st) == "M30 trending up (case 2): breaking close 03/03 03:30"


def _long_frame() -> pd.DataFrame:
    tail = synth([(100, 0)] + [(200 if k % 2 == 0 else 100, 30) for k in range(50)], start="2027-01-01")
    old = synth([(0, 0), (5000, 50), (0, 50), (5000, 50), (0, 50)], start="2026-12-01")
    return pd.concat([old, tail])  # 1,702 bars; the last 1,500 start one bar after the tail's first bar


def test_frame_is_exactly_1500_bars_kills_frame_bars_1499_or_1400() -> None:
    assert s11.FRAME_BARS == 1500
    st = s11.state_at(_long_frame())
    assert st.walk.range is not None
    assert st.walk.range.e.pivot_pos == 29  # 30 in the tail, minus the one tail bar cut off; 28 at 1,499 bars


def test_state_at_reads_close_not_open_kills_open_instead_of_close() -> None:
    f = synth(SAW)
    f.iloc[-1, f.columns.get_loc("open")] = 1000.0  # the last bar's open is wild; its close is unchanged
    st = s11.state_at(f)
    assert (st.kind, st.case) == ("sideways", 1)
    assert st.walk.last_break is None


def test_state_at_range_look_is_m30_bars_kills_m15_look_bars() -> None:
    # 2 days = 92 M30 bars: its first bar is 181 - 92 = 89 > E at 30 -> case 3 (an M15 look of 184 bars would give 1)
    assert s11.state_at(synth(SAW), range_days=2).case == 3


def test_describe_sideways_prints_the_case_kills_hardcoded_case_1() -> None:
    text = s11.describe(s11.state_at(synth(SAW), range_days=0.5))
    assert text.startswith("M30 sideways (case 3): lo 99.50, hi 200.50, E HIGH 200.50 02/03 22:00,")


def test_describe_follows_the_kind_not_the_range_kills_range_keyed_describe() -> None:
    t = pd.Timestamp("2026-03-02 20:30", tz="UTC")
    w = s11.Walk(s11.Range(L(0, 10), H(100, 20), 0, 100, 3, "LOW"), s11.Break("up", 5))
    st = s11.M30State("up", 2, w, t, t, t)
    assert s11.describe(st) == "M30 trending up (case 2): breaking close 03/03 03:30"


def test_state_at_frame_bars_changes_the_cut() -> None:
    f = synth(SAW)  # 181 bars; pivots H30 L60 H90 L120
    assert s11.state_at(f, frame_bars=181) == s11.state_at(f)
    st = s11.state_at(f, frame_bars=140)  # bars 41..180: pivots L(60) H(90) L(120) -> E = L at bar 60
    assert (st.kind, st.walk.range.legs) == ("sideways", 2)  # type: ignore[union-attr]
    assert st.e_time == f.index[60]
    assert st.b_time == f.index[90]


# --- eye/research/state11_check.py: the pure parts of rule 14's stability check ------------------------------

chk = importlib.import_module("eye.research.state11_check")


def T(h: int) -> pd.Timestamp:
    return pd.Timestamp("2026-03-02", tz="UTC") + pd.Timedelta(hours=h)


def sg(**kw: object) -> object:
    base = {
        "kind": "none", "case": 4, "e": None, "b": None, "lo": None, "hi": None,
        "legs": None, "last_touch": None, "brk_time": None, "brk_way": None,
    }  # fmt: skip
    return chk.Sig(**{**base, **kw})


STARTS = (T(0), T(0))


def test_check_a_equal_and_differing_states() -> None:
    a = sg(kind="sideways", case=1, e=T(1), b=T(2), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    assert chk.differing_fields(a, a) == []
    assert chk.differing_fields(
        a, sg(kind="sideways", case=3, e=T(1), b=T(2), lo=1.0, hi=2.5, legs=2, last_touch="LOW")
    ) == [
        "case",
        "hi",
    ]


def test_check_b_unchanged_state_has_no_change_and_no_causes() -> None:
    a = sg(kind="up", case=2, brk_time=T(5), brk_way="up")
    assert chk.change_causes(a, a, False, T(9), STARTS, STARTS) == []


def test_check_b_change_with_a_pivot_cause() -> None:
    prev = sg(kind="sideways", case=1, e=T(1), b=T(2), lo=1.0, hi=2.0, legs=1, last_touch="HIGH")
    cur = sg(kind="sideways", case=1, e=T(1), b=T(2), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    assert chk.change_causes(prev, cur, True, T(9), STARTS, STARTS) == ["pivot"]


def test_check_b_change_with_a_break_cause() -> None:
    cur = sg(kind="up", case=2, brk_time=T(9), brk_way="up")
    assert chk.change_causes(sg(), cur, False, T(9), STARTS, STARTS) == ["break"]


def test_check_b_change_with_a_range_look_cause() -> None:
    # E at T(5) was in the range look (first bar T(4)) and is out of it at this close (first bar T(6)).
    prev = sg(kind="sideways", case=1, e=T(5), b=T(6), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    cur = sg(kind="sideways", case=3, e=T(5), b=T(6), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    assert chk.change_causes(prev, cur, False, T(9), (T(4), T(0)), (T(6), T(0))) == ["range_look"]


def test_check_b_change_with_a_trend_look_cause() -> None:
    prev = sg(kind="up", case=2, brk_time=T(5), brk_way="up")
    assert chk.change_causes(prev, sg(), False, T(9), (T(0), T(4)), (T(0), T(6))) == ["trend_look"]


def test_check_b_change_without_any_cause_gives_an_empty_list() -> None:
    prev = sg(kind="up", case=2, brk_time=T(5), brk_way="up")
    assert chk.change_causes(prev, sg(), False, T(9), STARTS, STARTS) == []


def test_check_c_lo_hi_change_under_the_same_e_b_is_a_violation() -> None:
    a = sg(kind="sideways", case=1, e=T(1), b=T(2), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    moved = sg(kind="sideways", case=1, e=T(1), b=T(2), lo=1.0, hi=2.5, legs=2, last_touch="LOW")
    other = sg(kind="sideways", case=1, e=T(3), b=T(4), lo=0.5, hi=3.0, legs=1, last_touch="LOW")
    assert chk.edge_violations([a, a, moved, other, sg()]) == [2]
    assert chk.edge_violations([a, other, sg()]) == []


def test_check_b_break_cause_needs_the_break_on_this_bar_kills_any_break_set() -> None:
    cur = sg(kind="up", case=2, brk_time=T(5), brk_way="up")  # a break, but not at bar T(9)
    assert chk.change_causes(sg(), cur, False, T(9), STARTS, STARTS) == []


def test_check_b_range_look_needs_e_inside_the_previous_look_kills_missing_lower_bound() -> None:
    # E at T(3) was already outside the previous look (first bar T(5)): nothing passed at this close.
    prev = sg(kind="sideways", case=3, e=T(3), b=T(4), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    cur = sg(kind="none", case=4)
    assert chk.change_causes(prev, cur, False, T(9), (T(5), T(0)), (T(6), T(0))) == []


def test_check_b_trend_look_needs_the_break_inside_the_previous_look_kills_missing_lower_bound() -> None:
    prev = sg(kind="up", case=3, brk_time=T(3), brk_way="up")
    assert chk.change_causes(prev, sg(), False, T(9), (T(0), T(5)), (T(0), T(6))) == []


def test_check_b_range_look_boundaries_kill_lt_le_swaps() -> None:
    cur = sg(kind="none", case=4)

    def at(e: int) -> list[str]:
        prev = sg(kind="sideways", case=1, e=T(e), b=T(e + 1), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
        return chk.change_causes(prev, cur, False, T(9), (T(5), T(0)), (T(6), T(0)))

    assert at(5) == ["range_look"]  # E on the bar that just left the look (= the previous first bar)
    assert at(6) == []  # E on the new first bar: still inside
    assert at(7) == []


def test_check_b_trend_look_boundaries() -> None:
    def at(t: int) -> list[str]:
        prev = sg(kind="up", case=2, brk_time=T(t), brk_way="up")
        return chk.change_causes(prev, sg(), False, T(9), (T(0), T(5)), (T(0), T(6)))

    assert at(5) == ["trend_look"]
    assert at(6) == []


def test_check_b_range_look_reads_the_previous_e_kills_cur_e() -> None:
    prev = sg(kind="sideways", case=1, e=T(5), b=T(6), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    cur = sg(kind="sideways", case=1, e=T(8), b=T(9), lo=1.0, hi=2.0, legs=1, last_touch="LOW")  # a new range
    assert chk.change_causes(prev, cur, False, T(9), (T(5), T(0)), (T(6), T(0))) == ["range_look"]
    # and a cur.e that sits on the boundary does not make a cause when prev.e does not
    prev2 = sg(kind="sideways", case=1, e=T(8), b=T(9), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    cur2 = sg(kind="sideways", case=1, e=T(5), b=T(6), lo=1.0, hi=2.0, legs=1, last_touch="LOW")
    assert chk.change_causes(prev2, cur2, False, T(9), (T(5), T(0)), (T(6), T(0))) == []


def test_check_look_starts_are_the_first_bars_of_the_looks_kills_off_by_one() -> None:
    idx = pd.date_range("2026-03-02", periods=400, freq="30min", tz="UTC")
    assert chk._look_starts(idx, 399) == (idx[399 - 183], idx[399 - 321])  # 184 and 322 bars
    assert chk._look_starts(idx, 50) == (idx[0], idx[0])  # shorter than the looks: the first bar


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "up"), ("case", 3), ("e", T(7)), ("b", T(8)), ("lo", 9.0), ("hi", 9.0),
        ("legs", 5), ("last_touch", "HIGH"), ("brk_time", T(6)), ("brk_way", "down"),
    ],
)  # fmt: skip
def test_check_a_each_field_alone_is_reported_kills_a_missing_field(field: str, value: object) -> None:
    a = sg(kind="sideways", case=1, e=T(1), b=T(2), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    b = chk.Sig(**{**a.__dict__, field: value})  # type: ignore[attr-defined]
    assert chk.differing_fields(a, b) == [field]


def test_check_c_lo_alone_hi_alone_and_unrelated_changes() -> None:
    a = sg(kind="sideways", case=1, e=T(1), b=T(2), lo=1.0, hi=2.0, legs=2, last_touch="LOW")
    lo_only = chk.Sig(**{**a.__dict__, "lo": 0.5})  # type: ignore[attr-defined]
    hi_only = chk.Sig(**{**a.__dict__, "hi": 2.5})  # type: ignore[attr-defined]
    new_b = chk.Sig(**{**a.__dict__, "b": T(3), "lo": 0.5, "hi": 3.0})  # type: ignore[attr-defined]
    new_e = chk.Sig(**{**a.__dict__, "e": T(0), "lo": 0.5, "hi": 3.0})  # type: ignore[attr-defined]
    assert chk.edge_violations([a, lo_only]) == [1]
    assert chk.edge_violations([a, hi_only]) == [1]
    assert chk.edge_violations([a, new_b]) == []  # E same, B different
    assert chk.edge_violations([a, new_e]) == []  # B same, E different


def test_check_select_closes_by_close_time() -> None:
    idx = pd.date_range("2026-03-02 10:00", periods=5, freq="30min", tz="UTC")  # opens 10:00 .. 12:00
    start, end = T(0) + pd.Timedelta(hours=10, minutes=30), T(0) + pd.Timedelta(hours=11, minutes=30)
    # closes: 10:30, 11:00, 11:30, 12:00, 12:30 -> (10:30, 11:30] keeps the bars opening 10:30 and 11:00
    assert chk.select_closes(idx, start, end) == [1, 2]


def test_check_pivot_is_fixed_exactly_on_its_confirm_bar() -> None:
    from app.indicators.price_action import Swing, SwingKind

    p = Swing(SwingKind.HIGH, 1.0, 3, 6, T(3), T(6))
    assert chk.pivot_fixed_at([p], T(6))
    assert not chk.pivot_fixed_at([p], T(5))
    assert not chk.pivot_fixed_at([p], T(7))
    assert not chk.pivot_fixed_at([], T(6))


def _sw(kind: str, legs: int | None = None, touch: str = "HIGH") -> s11.M30State:
    r = None if legs is None else s11.Range(L(0, 10), H(100, 20), 0.0, 100.0, legs, touch)
    return s11.M30State(kind, 1, s11.Walk(r, None), None, None, None)


def test_side_of_trends() -> None:
    assert s11.side_of(_sw("up")) == "BUY"
    assert s11.side_of(_sw("down")) == "SELL"


def test_side_of_none() -> None:
    assert s11.side_of(_sw("none")) == "none"


def test_side_of_sideways_legs_2_to_4_go_away_from_the_last_touch() -> None:
    for legs in (2, 3, 4):  # legs traded 3, 4, 5
        assert s11.side_of(_sw("sideways", legs, "HIGH")) == "SELL"
        assert s11.side_of(_sw("sideways", legs, "LOW")) == "BUY"


def test_side_of_leg_5_versus_leg_6_boundary() -> None:
    assert s11.side_of(_sw("sideways", 4, "LOW")) == "BUY"  # legs 4 -> leg 5
    assert s11.side_of(_sw("sideways", 5, "LOW")) == "either"  # legs 5 -> leg 6
    assert s11.side_of(_sw("sideways", 9, "HIGH")) == "either"


def test_side_of_sideways_under_leg_3_is_none() -> None:
    assert s11.side_of(_sw("sideways", 1)) == "none"
