"""Trigger T1, the re-test of a broken zone line (app/strategy/zone_retest.py), on bars built by hand: anchor 100,
step 20 -> lines every 10, band 3, the stop 1 beyond the extreme."""

from __future__ import annotations

import numpy as np

from app.strategy import zone_retest as zr

ABOVE = [(106.0, 104.0, 105.0)] * 10  # bars 0-9: closes above the line 100, clear of every band
SELL = [
    *ABOVE,
    (104.0, 95.5, 96.0),  # 10: closes 4 under the line (> the band 3): the break down
    (99.0, 94.0, 95.0),  # 11: in the band, but bar 10 was too - no fresh touch
    (96.0, 92.0, 93.0),  # 12: below the band
    (98.0, 93.0, 95.0),  # 13: a fresh touch, closes under the line: re-test 1
    (101.0, 96.0, 99.5),  # 14: in the band again, bar 13 was too
    (95.0, 90.0, 91.0),  # 15: below
    (102.5, 94.0, 97.5),  # 16: a fresh touch: re-test 2, the extreme now 102.5
]


def run(rows, anchor: float = 100.0, step: float | np.ndarray = 20.0):
    h, lo, c = (np.array(x, float) for x in zip(*rows, strict=True))
    n = len(c)
    steps = np.full(n, step) if np.isscalar(step) else np.asarray(step, float)
    return zr.zone_retests(h, lo, c, np.full(n, anchor), steps)


class TestRetest:
    def test_two_retests_of_a_break_down(self) -> None:
        ev = run(SELL)
        assert [(e.break_bar, e.line, e.side, e.entry_bar, e.entry) for e in ev] == [
            (10, 100.0, -1, 13, 95.0),
            (10, 100.0, -1, 16, 97.5),
        ]
        # the extreme against the break: max(the break close 96, the highs since: 99, 96, 98) = 99, then 102.5
        assert [(e.extreme, e.stop) for e in ev] == [(99.0, 100.0), (102.5, 103.5)]

    def test_the_mirror_break_up(self) -> None:
        rows = [(200.0 - lo, 200.0 - h, 200.0 - c) for h, lo, c in SELL]
        ev = run(rows)
        assert [(e.side, e.entry_bar, e.entry, e.stop) for e in ev] == [
            (1, 13, 105.0, 100.0),
            (1, 16, 102.5, 96.5),
        ]

    def test_a_failed_break_ends_it(self) -> None:
        # bar 14 closes 103.5: back above the line by more than the band - the break of bar 10 ends (bar 14 is
        # the break up, failed at once by bar 15); bar 15 (close 91) breaks down again, bar 16 re-tests it
        rows = list(SELL)
        rows[14] = (104.0, 99.0, 103.5)
        assert [(e.break_bar, e.entry_bar) for e in run(rows)] == [(10, 13), (15, 16)]

    def test_the_failed_bar_is_the_break_back(self) -> None:
        # bar 14 closes 103.5: the break down failed and the line broke up at the same bar; bar 15 sits in the
        # band (bar 14 too: no fresh touch), bar 16 clears it, bar 17 touches from above and closes above: a buy
        rows = [
            *SELL[:14],
            (104.0, 99.0, 103.5),
            (104.5, 102.5, 104.0),
            (107.0, 104.0, 106.0),
            (106.0, 102.5, 104.5),
        ]
        ev = run(rows)
        assert [(e.break_bar, e.side, e.entry_bar) for e in ev] == [(10, -1, 13), (14, 1, 17)]

    def test_a_close_inside_the_band_is_no_break(self) -> None:
        # bar 10 closes 98 (2 under the line, inside the band): no break yet; bar 11 closes 96 - the break
        rows = [*ABOVE, (104.0, 97.5, 98.0), (98.0, 95.5, 96.0), (96.0, 92.0, 93.0), (98.0, 93.0, 95.0)]
        assert [(e.break_bar, e.entry_bar) for e in run(rows)] == [(11, 13)]

    def test_a_break_needs_a_close_on_the_other_side_before(self) -> None:
        # every close before bar 10 sits under the line: closing at 96 is no break of it
        rows = [*[(99.0, 94.0, 98.0)] * 10, *SELL[10:]]
        assert all(e.line != 100.0 for e in run(rows))

    def test_the_close_must_be_back_on_the_break_side(self) -> None:
        rows = list(SELL)
        rows[13] = (101.0, 97.5, 100.5)  # a fresh touch closing above the line: no re-test (and no failure)
        assert [e.entry_bar for e in run(rows)] == [16]

    def test_a_breathing_step_is_still_the_same_line(self) -> None:
        # the line 100 is the anchor 110 minus a half step; the step grows to 20.4 at bar 12, moving it to 99.8:
        # still one break (the same line), so still two re-tests
        steps = np.full(len(SELL), 20.0)
        steps[12:] = 20.4
        ev = run(SELL, anchor=110.0, step=steps)
        assert [(e.break_bar, e.entry_bar) for e in ev if abs(e.line - 100.0) < 0.5] == [(10, 13), (10, 16)]

    def test_an_expired_break_is_not_restarted_on_its_last_bar(self) -> None:
        # the break down at bar 10 is followed through bar 106 (96 bars). Bars 11-106 close 94 under the band,
        # except bar 90 (close 101: above the line, inside the band - not a failure, but a close on the other
        # side for a later break). Bar 106 still belongs to the old break; the new break is bar 107; bar 108
        # clears the band, bar 109 re-tests it
        low = (96.0, 93.0, 94.0)
        rows = [*SELL[:11], *[low] * 79, (101.5, 99.5, 101.0), *[low] * 16, low, low, (98.0, 93.0, 95.0)]
        assert [(e.break_bar, e.entry_bar) for e in run(rows)] == [(107, 109)]

    def test_no_event_before_the_retest_bar_closes(self) -> None:
        assert run(SELL[:13]) == []
