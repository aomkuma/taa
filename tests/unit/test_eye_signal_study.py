"""eye/signal_study.py piece 1: strip B, the events, the counter-move, the count, the M / W shape.

Constructed data only (eye/SIGNAL_STUDY.md rows S3, C2, C3, C4).
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.indicators.price_action import Swing, SwingKind
from eye import signal_study as ss
from eye import state11
from eye.signal_study import Pivot


def low(price: float, pos: int, confirm: int | None = None) -> Pivot:
    return Pivot("LOW", price, pos, pos + 2 if confirm is None else confirm)


def high(price: float, pos: int, confirm: int | None = None) -> Pivot:
    return Pivot("HIGH", price, pos, pos + 2 if confirm is None else confirm)


# closes with a constant latest fixed HIGH 11 / LOW 9 from bar 1: BUY at 2, SELL at 4, BUY at 5
CLOSES = [10.0, 10.0, 12.0, 10.0, 8.0, 13.0]
HIGHS = [None, 11.0, 11.0, 11.0, 11.0, 11.0]
LOWS = [None, 9.0, 9.0, 9.0, 9.0, 9.0]


def test_strip_b_changes_and_holds() -> None:
    assert ss.strip_sides(CLOSES, HIGHS, LOWS) == ["none", "none", "BUY", "BUY", "SELL", "BUY"]


def test_strip_b_none_before_first_break_and_equal_close_is_no_break() -> None:
    assert ss.strip_sides([11.0, 9.0, 10.0], [11.0, 11.0, 11.0], [9.0, 9.0, 9.0]) == ["none"] * 3
    assert ss.strip_sides([5.0], [None], [None]) == ["none"]


def test_first_break_is_not_an_event_but_starts_the_stretch() -> None:
    brks = ss.find_breaks(CLOSES, HIGHS, LOWS)
    assert [b.pos for b in brks] == [4, 5]  # the none -> BUY at 2 is not an event
    first = brks[0]
    assert (first.side, first.prev_side, first.start_pos) == ("SELL", "BUY", 2)


def test_event_h_and_stretch_bounded_by_previous_side_change() -> None:
    sell, buy = ss.find_breaks(CLOSES, HIGHS, LOWS)
    assert sell.h == 9.0  # the swing LOW the SELL close went under
    assert buy.h == 11.0  # the swing HIGH the BUY close went over
    assert (buy.prev_side, buy.start_pos) == ("SELL", 4)  # not 2: the SELL stretch starts at the last change


def test_counter_move_bounded_by_the_stretch() -> None:
    lows = [low(95, 1), low(99, 5), low(98, 8), low(97, 12)]
    got = ss.counter_move(lows, "BUY", start_pos=5, event_pos=20)
    assert [p.pivot_pos for p in got] == [5, 8, 12]  # the pivot at 1 is before the stretch
    assert ss.counter_move(lows, "BUY", 5, 10) == (lows[1], lows[2])  # the pivot at 12 is after the event


def test_counter_move_excludes_swings_not_yet_fixed_and_other_kind() -> None:
    piv = [low(99, 5, confirm=8), low(98, 9, confirm=21), high(120, 7)]
    got = ss.counter_move(piv, "BUY", 0, 20)
    assert got == (piv[0],)  # confirm 21 > event 20: not fixed; the HIGH is not a counter-move LOW
    assert ss.counter_move(piv, "SELL", 0, 20) == (piv[2],)


def test_l_star_buy_lowest_and_sell_highest_latest_among_equals() -> None:
    lows = [low(100, 1), low(98, 5), low(99, 9)]
    assert ss.extreme_of(lows, "BUY") == lows[1]
    highs = [high(100, 1), high(103, 5), high(101, 9)]
    assert ss.extreme_of(highs, "SELL") == highs[1]
    ties = [low(99, 1), low(99, 5)]
    assert ss.extreme_of(ties, "BUY") == ties[1]
    assert ss.extreme_of([], "BUY") is None


def test_count_run_of_three_and_five() -> None:
    assert ss.run_count([low(p, i) for i, p in enumerate([103, 102, 101])], "BUY") == 3
    assert ss.run_count([low(p, i) for i, p in enumerate([105, 104, 103, 102, 101])], "BUY") == 5


def test_count_broken_by_a_higher_low() -> None:
    # L* = 98 (last); 100 >= 98 continues, then 99 < 100 breaks the run
    assert ss.run_count([low(p, i) for i, p in enumerate([101, 99, 100, 98])], "BUY") == 2


def test_count_equal_lows_continue_the_run() -> None:
    assert ss.run_count([low(p, i) for i, p in enumerate([100, 100, 99])], "BUY") == 3
    assert ss.run_count([low(p, i) for i, p in enumerate([99, 99])], "BUY") == 2  # L* = the later tie


def test_count_ends_at_l_star_not_at_the_last_low() -> None:
    # L* = 97 is first; the later higher lows are not part of the run
    assert ss.run_count([low(p, i) for i, p in enumerate([97, 100, 99])], "BUY") == 1


def test_count_sell_mirror() -> None:
    assert ss.run_count([high(p, i) for i, p in enumerate([100, 101, 102])], "SELL") == 3
    assert ss.run_count([high(p, i) for i, p in enumerate([98, 102, 101, 103])], "SELL") == 2
    assert ss.run_count([], "SELL") == 0


def test_m_shape_inside_and_outside_35_percent() -> None:
    peak = [high(110, 6)]
    # height 110 - 101 = 9, |101 - 100| = 1 <= 3.15
    inside = [low(100, 3), low(101, 9)]
    assert ss.is_mw(inside, inside + peak, "BUY")
    # second low lower: height 110 - 100 = 10 (higher of the two), diff 3 <= 3.5
    assert ss.is_mw([low(100, 3), low(97, 9)], [low(100, 3), low(97, 9), *peak], "BUY")
    # height 110 - 104 = 6, diff 4 > 2.1
    outside = [low(100, 3), low(104, 9)]
    assert not ss.is_mw(outside, outside + peak, "BUY")


def test_m_shape_uses_the_highest_high_between_and_needs_two_lows_and_a_high() -> None:
    lows = [low(100, 3), low(104, 9)]
    # a second, taller HIGH between the lows widens the height to 120 - 104 = 16, diff 4 <= 5.6
    assert ss.is_mw(lows, [*lows, high(110, 5), high(120, 7)], "BUY")
    assert not ss.is_mw(lows[:1], [*lows[:1], high(110, 5)], "BUY")
    assert not ss.is_mw(lows, lows, "BUY")  # no HIGH between: no shape


def test_w_shape_mirror() -> None:
    trough = [low(90, 6)]
    inside = [high(100, 3), high(99, 9)]  # height = 99 - 90 = 9, diff 1
    assert ss.is_mw(inside, inside + trough, "SELL")
    outside = [high(100, 3), high(96, 9)]  # height = 96 - 90 = 6, diff 4 > 2.1
    assert not ss.is_mw(outside, outside + trough, "SELL")


def test_build_event_fields_and_first_event_handling() -> None:
    piv = [
        low(101, 3),
        high(110, 6),
        low(100, 9),
        high(111, 14),  # the BUY close at 20 is above it
        low(102, 19, confirm=25),  # not fixed at the event
    ]
    brk = ss.Break(pos=20, side="BUY", h=111.0, prev_side="SELL", start_pos=2)
    ev = ss.build_event(brk, piv, pd.Timestamp("2026-01-01 10:00", tz="UTC"))
    assert (ev.side, ev.h, ev.start_pos) == ("BUY", 111.0, 2)
    assert [p.price for p in ev.moves] == [101, 100]
    assert ev.extreme == piv[2]
    assert ev.count == 2
    assert ev.shape  # height 110 - 101 = 9, diff 1


def test_build_event_without_swings() -> None:
    brk = ss.Break(pos=5, side="SELL", h=9.0, prev_side="BUY", start_pos=2)
    ev = ss.build_event(brk, [], pd.Timestamp("2026-01-01", tz="UTC"))
    assert (ev.moves, ev.extreme, ev.count, ev.shape) == ((), None, 0, False)


def test_pivots_at_shifts_to_absolute_positions(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    seen: list[int] = []

    def fake(frame: pd.DataFrame) -> list[Swing]:
        seen.append(len(frame))
        return [Swing(SwingKind.LOW, 5.0, 1, 2, frame.index[1], frame.index[2])]

    monkeypatch.setattr(state11, "_zigzag", fake)
    monkeypatch.setattr(state11, "FRAME_BARS", 3)
    assert ss.pivots_at(df, 4) == [Pivot("LOW", 5.0, 3, 4)]  # frame = bars 2..4, offset 2
    assert seen == [3]


# --- C4 mutation killers (each named for the mutant it kills) -------------------------------------------


def _m(a: float, b: float, peak: float) -> bool:
    lows = [low(a, 3), low(b, 9)]
    return ss.is_mw(lows, [*lows, high(peak, 6)], "BUY")


def _w(a: float, b: float, trough: float) -> bool:
    highs = [high(a, 3), high(b, 9)]
    return ss.is_mw(highs, [*highs, low(trough, 6)], "SELL")


def test_kills_tolerance_raised_to_half_buy() -> None:
    assert not _m(100, 60, 200)  # height 100, diff 40 = 40 %


def test_kills_strict_less_than_buy() -> None:
    assert _m(100, 65, 200)  # height 100, diff exactly 35 %


def test_kills_height_from_min_buy() -> None:
    # max: height 130 - 100 = 30, diff 12 > 10.5 -> no M; (min would give 40, 12 <= 14 -> M)
    assert not _m(100, 88, 130)


def test_kills_unfixed_high_counted_between_buy() -> None:
    piv = [low(100, 3), low(101, 9), high(110, 6, confirm=25)]  # the only HIGH is fixed after the event
    brk = ss.Break(pos=20, side="BUY", h=111.0, prev_side="SELL", start_pos=0)
    ev = ss.build_event(brk, piv, pd.Timestamp("2026-01-01", tz="UTC"))
    assert len(ev.moves) == 2
    assert not ev.shape


def test_kills_tolerance_raised_to_half_sell() -> None:
    assert not _w(100, 140, 0)  # height 100, diff 40 %


def test_kills_strict_less_than_sell() -> None:
    assert _w(100, 135, 0)  # height 100, diff exactly 35 %


def test_kills_height_from_max_sell() -> None:
    # min: height 100 - 70 = 30, diff 12 > 10.5 -> no W; (max would give 42, 12 <= 14.7 -> W)
    assert not _w(100, 112, 70)


def test_kills_unfixed_low_counted_between_sell() -> None:
    piv = [high(100, 3), high(99, 9), low(90, 6, confirm=25)]
    brk = ss.Break(pos=20, side="SELL", h=89.0, prev_side="BUY", start_pos=0)
    ev = ss.build_event(brk, piv, pd.Timestamp("2026-01-01", tz="UTC"))
    assert len(ev.moves) == 2
    assert not ev.shape


def test_high_fixed_between_second_low_and_event_still_counts() -> None:
    piv = [low(100, 3), low(101, 9), high(110, 6, confirm=15)]  # fixed at 15 <= event 20
    brk = ss.Break(pos=20, side="BUY", h=111.0, prev_side="SELL", start_pos=0)
    assert ss.build_event(brk, piv, pd.Timestamp("2026-01-01", tz="UTC")).shape
