"""MetaTrader 5's ZigZag (app/strategy/zigzag.py). Every series below is worked by hand: closes as given, each
bar's high = close + 0.5 and low = close - 0.5."""

from __future__ import annotations

from itertools import pairwise

import numpy as np

from app.strategy.zigzag import Swing, zigzag


def hl(closes: list[float]) -> tuple[np.ndarray, np.ndarray]:
    c = np.array(closes, float)
    return c + 0.5, c - 0.5


def test_up_down_up_gives_the_top_the_bottom_and_a_forming_top():
    # bars 0-29 rise 100 .. 129, bars 30-49 fall 130 .. 111, bars 50-89 rise 110 .. 149 (depth 5)
    closes = list(np.arange(100, 130.0)) + list(np.arange(130, 110.0, -1)) + list(np.arange(110, 150.0))
    confirmed, last = zigzag(*hl(closes), depth=5)
    # the top is bar 30 (close 130, high 130.5); the bottom bar 50 (close 110, low 109.5); the newest high
    # (bar 89, 149.5) is still forming. No low before the first top: bars 0-4 come before the first window,
    # and from bar 5 on each window's lowest low lies 4 under the bar's own
    assert confirmed == [Swing(30, 130.5, 1), Swing(50, 109.5, -1)]
    assert last == Swing(89, 149.5, 1)


def test_points_alternate_and_a_new_extreme_moves_the_point():
    # down 120 .. 101 (bars 0-19), up 101 .. 110 (bars 20-29), down 109 .. 95 (bars 30-44), up 96 .. 115 (45-64)
    closes = (
        list(np.arange(120, 100.0, -1)) + list(np.arange(101, 111.0)) + list(np.arange(109, 94.0, -1))
        + list(np.arange(96, 116.0))
    )  # fmt: skip
    confirmed, last = zigzag(*hl(closes), depth=5)
    kinds = [s.kind for s in confirmed] + [last.kind]  # type: ignore[union-attr]
    assert all(a != b for a, b in pairwise(kinds))  # strictly alternating
    # the low of the first fall is bar 19 (close 101, low 100.5 - bar 20 repeats it and is not a new low); the
    # high of the bounce bar 29 (110.5); the second low bar 44 (close 95, low 94.5) - a new point
    assert Swing(19, 100.5, -1) in confirmed and Swing(29, 110.5, 1) in confirmed
    assert Swing(44, 94.5, -1) in confirmed
    assert last == Swing(64, 115.5, 1)


def test_a_dip_inside_the_backstep_does_not_split_a_leg():
    # a rise with a one-bar dip of 2 (bar 10) then on up: no low point in the middle of the leg
    closes = (
        [100.0 + i for i in range(10)]
        + [107.0]
        + [110.0 + i for i in range(10)]
        + [100.0 - i for i in range(15)]
    )
    confirmed, last = zigzag(*hl(closes), depth=12)
    assert [s for s in [*confirmed, last] if s is not None and s.kind == -1 and 5 < s.bar < 20] == []
    tops = [s for s in confirmed if s.kind == 1]
    assert tops and tops[-1] == Swing(20, 119.5, 1)  # the leg's top: bar 20, close 119


def test_too_few_bars_give_nothing():
    assert zigzag(*hl([100.0, 101.0, 102.0])) == ([], None)


def test_a_lower_low_after_a_small_bounce_moves_the_point_and_depth_decides_the_bounce():
    # bars 0-15 rise 90 .. 105; 16-25 fall 104 .. 95; 26-27 bounce 96, 97; 28-32 fall 96 .. 92; 33-50 rise
    # 93 .. 110
    closes = (
        list(range(90, 106)) + list(range(104, 94, -1)) + [96, 97] + list(range(96, 91, -1)) + list(range(93, 111))
    )  # fmt: skip
    h, lo = hl([float(c) for c in closes])
    # depth 12: the bounce's 97.5 is not the highest of its 12 bars (104.5 is), so no point; the low moves from
    # bar 25 (94.5) to the lower bar 32 (91.5); the window minimum repeated at bars 26-27 is not a new low
    assert zigzag(h, lo, depth=12) == ([Swing(15, 105.5, 1), Swing(32, 91.5, -1)], Swing(50, 110.5, 1))
    # depth 5: bar 27's 97.5 is the highest of bars 23-27 and new (bar 26's window held 98.5): the bounce is a
    # swing of its own
    assert zigzag(h, lo, depth=5) == (
        [Swing(15, 105.5, 1), Swing(25, 94.5, -1), Swing(27, 97.5, 1), Swing(32, 91.5, -1)],
        Swing(50, 110.5, 1),
    )


def test_an_equal_low_still_inside_the_window_is_not_a_new_point():
    # closes 100 101 102 101 100 101 102 101 100 101 101 100 101 (depth 3): lows at bars 4 and 8 (99.5), the high
    # at bar 6 (102.5), then bar 9's 101.5 starts a peak (the highest of bars 7-9 and new). Bar 11 touches 99.5
    # again, but bar 8's 99.5 was the window's lowest at bars 9 and 10 as well, so it is the same minimum, not
    # a new one: no point at bar 11 (MetaTrader 5's "val == lastlow" rule); the peak at bar 9 stays forming
    closes = [100.0, 101, 102, 101, 100, 101, 102, 101, 100, 101, 101, 100, 101]
    assert zigzag(*hl(closes), depth=3) == (
        [Swing(4, 99.5, -1), Swing(6, 102.5, 1), Swing(8, 99.5, -1)],
        Swing(9, 101.5, 1),
    )
