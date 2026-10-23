"""Trigger T2, a rejection at a zone line (app/strategy/zone_reject.py), on bars built by hand: anchor 100,
step 40 -> lines every 20 (80, 100, 120, ...), band 6, the stop 2 beyond the extreme since the arrival. Every
bar stays clear of the bands of 80 and 120, so only the line 100 is in play."""

from __future__ import annotations

import numpy as np

from app.strategy import zone_reject as zj

FAR = [
    (150.0, 151.0, 149.0, 150.0)
] * 32  # (open, high, low, close): far above, clear of the bands of 140 / 160


def run(rows):
    o, h, lo, c = (np.array(x, float) for x in zip(*rows, strict=True))
    n = len(c)
    return zj.zone_rejections(o, h, lo, c, np.full(n, 100.0), np.full(n, 40.0))


class TestRejection:
    def test_a_long_lower_wick_at_the_arrival(self) -> None:
        # open 112, high 113, low 98 (under the line: swept), close 110 -> range 15, lower wick 110 - 98 = 12
        ev = run([*FAR, (112.0, 113.0, 98.0, 110.0)])
        assert [(e.arrival, e.side, e.entry_bar, e.entry, e.stop, e.swept) for e in ev] == [
            (32, 1, 32, 110.0, 96.0, True)
        ]

    def test_the_rejection_a_bar_later(self) -> None:
        # bar 32 arrives without a long wick (3 of 11); bar 33: low 99, wick 3 of 8 - no; bar 34: open 104, high
        # 105.5, low 99.5, close 105 -> wick 4.5 of 6: the rejection; the lowest low since the arrival is bar
        # 33's 99 (not the rejection bar's) -> stop 97
        rows = [*FAR, (112.0, 112.0, 101.0, 104.0), (102.0, 107.0, 99.0, 106.0), (104.0, 105.5, 99.5, 105.0)]
        assert [(e.entry_bar, e.entry, e.stop, e.swept) for e in run(rows)] == [(34, 105.0, 97.0, True)]

    def test_not_swept_when_the_wick_stays_above_the_line(self) -> None:
        ev = run([*FAR, (112.0, 113.0, 101.0, 111.0)])  # wick 10 of 12, low 101 > 100
        assert [(e.swept, e.stop) for e in ev] == [(False, 99.0)]

    def test_a_short_wick_is_no_rejection(self) -> None:
        # range 14, wick 98 -> 103 = 5 < 7; the next bars' wicks 0.2 of 1.2
        rows = [*FAR, (112.0, 112.0, 98.0, 103.0), *[(103.5, 104.0, 102.8, 103.0)] * 2]
        assert run(rows) == []

    def test_a_close_through_the_line_ends_it(self) -> None:
        # bar 32 closes 93 (7 through the line, more than the band 6): bar 33 (wick 10 of 11, closing above the
        # line) would be a rejection, but the search has ended
        rows = [*FAR, (110.0, 110.0, 92.0, 93.0), (104.0, 105.0, 94.0, 104.5)]
        assert run(rows) == []

    def test_the_close_must_be_back_on_the_approach_side(self) -> None:
        assert run([*FAR, (99.8, 100.0, 90.0, 99.5)]) == []  # a long wick, but the close is under the line

    def test_only_three_bars(self) -> None:
        rows = [
            *FAR,
            (112.0, 112.0, 101.0, 104.0),
            *[(104.0, 104.5, 102.0, 103.0)] * 2,
            (104.0, 105.5, 99.5, 105.0),
        ]
        assert run(rows) == []

    def test_the_mirror_at_a_resistance(self) -> None:
        rows = [
            (200.0 - o, 200.0 - lo, 200.0 - h, 200.0 - c)
            for o, h, lo, c in [*FAR, (112.0, 113.0, 98.0, 110.0)]
        ]
        assert [(e.side, e.entry, e.stop, e.swept) for e in run(rows)] == [(-1, 90.0, 104.0, True)]
