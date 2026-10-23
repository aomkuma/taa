"""Trigger T4, consolidation at a zone line then the box's break (app/strategy/zone_break.py), on bars built by
hand: anchor 100, step 20 -> lines every 10, band 3, a box at most 6 tall, the stop 1 beyond it."""

from __future__ import annotations

import math

import numpy as np

from app.strategy import zone_break as zb


def series(after: list[tuple[float, float, float]], box: tuple[float, float, float] = (103.0, 99.0, 101.0)):
    """32 bars far above at 125, a drop bar into the line 100, 8 box bars, then ``after`` (high, low, close)."""
    rows = [(126.0, 124.0, 125.0)] * 32 + [(125.0, 101.0, 102.0)] + [box] * 8 + list(after)
    h, lo, c = (np.array(x, float) for x in zip(*rows, strict=True))
    n = len(c)
    return h, lo, c, np.full(n, 100.0), np.full(n, 20.0)


class TestZoneBreak:
    def test_the_box_breaks_through_the_line(self) -> None:
        # arrival at bar 32 (came from above); the box = bars 33-40, 99..103; bar 41 closes 96 < 99 -> a sell
        # through the line, the stop 103 + 1
        ev = zb.zone_breaks(*series([(100.0, 95.5, 96.0)]))
        assert len(ev) == 1
        e = ev[0]
        assert (e.arrival, e.line, e.came, e.entry_bar, e.side, e.through) == (32, 100.0, 1, 41, -1, True)
        assert (e.entry, e.stop, e.box_lo, e.box_hi, e.bars_at_line) == (96.0, 104.0, 99.0, 103.0, 9)

    def test_the_box_breaks_back_the_way_price_came(self) -> None:
        ev = zb.zone_breaks(*series([(105.0, 101.0, 104.0)]))
        assert [(e.side, e.through, e.stop) for e in ev] == [(1, False, 98.0)]

    def test_the_box_grows_until_it_breaks(self) -> None:
        # bar 41 widens the box to 97..104 without closing out; bar 42 closes 96 < 97 -> stop 104 + 1
        ev = zb.zone_breaks(*series([(104.0, 97.0, 100.0), (99.0, 95.0, 96.0)]))
        assert [(e.entry_bar, e.stop, e.box_lo, e.box_hi) for e in ev] == [(42, 105.0, 97.0, 104.0)]

    def test_a_straight_break_is_no_consolidation(self) -> None:
        # bar 33 closes 96.9: through the line by 3.1 > the band 3 -> no box is looked for, even though bars
        # 34-41 then form a valid box that bar 42 breaks
        rows = [(126.0, 124.0, 125.0)] * 32 + [(125.0, 101.0, 102.0), (101.0, 96.5, 96.9)]
        rows += [(103.0, 99.0, 101.0)] * 8 + [(100.0, 95.5, 96.0)]
        h, lo, c = (np.array(x, float) for x in zip(*rows, strict=True))
        n = len(c)
        assert zb.zone_breaks(h, lo, c, np.full(n, 100.0), np.full(n, 20.0)) == []

    def test_a_close_inside_the_band_is_no_break(self) -> None:
        # bar 33 closes 97.1 (through by 2.9 < 3): the search goes on and the box 97..103 (bars 34-41 with
        # bar 33 outside it) is found
        rows = [(126.0, 124.0, 125.0)] * 32 + [(125.0, 101.0, 102.0), (101.0, 97.0, 97.1)]
        rows += [(103.0, 97.0, 101.0)] * 8 + [(100.0, 95.5, 96.0)]
        h, lo, c = (np.array(x, float) for x in zip(*rows, strict=True))
        n = len(c)
        assert [e.entry_bar for e in zb.zone_breaks(h, lo, c, np.full(n, 100.0), np.full(n, 20.0))] == [42]

    def test_a_half_line(self) -> None:
        # anchor 110, step 20: 100 is a half line - the same event
        h, lo, c, _, s = series([(100.0, 95.5, 96.0)])
        ev = zb.zone_breaks(h, lo, c, np.full(len(c), 110.0), s)
        assert [(e.line, e.entry_bar) for e in ev] == [(100.0, 41)]

    def test_the_band_edge_for_an_arrival(self) -> None:
        # the drop bar's low 103.5 stays 3.5 > 3 above the line: no arrival (its box would still form)
        h, lo, c, a, s = series([(100.0, 95.5, 96.0)])
        lo[32], c[32] = 103.5, 104.0
        assert all(e.arrival != 32 for e in zb.zone_breaks(h, lo, c, a, s))

    def test_seven_box_bars_are_not_a_box(self) -> None:
        # only 7 box bars before the break: the 8-bar window always holds the arrival bar (too tall)
        rows = [(126.0, 124.0, 125.0)] * 32 + [(125.0, 101.0, 102.0)] + [(103.0, 99.0, 101.0)] * 7
        rows += [(100.0, 95.5, 96.0)]
        h, lo, c = (np.array(x, float) for x in zip(*rows, strict=True))
        n = len(c)
        assert zb.zone_breaks(h, lo, c, np.full(n, 100.0), np.full(n, 20.0)) == []

    def test_where_price_came_from_is_read_before_the_arrival(self) -> None:
        # the arrival bar itself closes below the line (98.5): price still came from above -> the break down is
        # through the line
        h, lo, c, a, s = series([(100.0, 95.5, 96.0)])
        lo[32], c[32] = 98.0, 98.5
        ev = zb.zone_breaks(h, lo, c, a, s)
        assert [(e.came, e.side, e.through) for e in ev] == [(1, -1, True)]

    def test_a_close_on_the_box_edge_is_no_break(self) -> None:
        ev = zb.zone_breaks(*series([(100.0, 99.0, 99.0), (100.0, 95.5, 96.0)]))
        assert [e.entry_bar for e in ev] == [42]

    def test_a_tall_box_is_no_consolidation(self) -> None:
        # the box bars 97.5..104: 6.5 tall > 6
        assert zb.zone_breaks(*series([(100.0, 95.5, 96.0)], box=(104.0, 97.5, 101.0))) == []

    def test_a_box_exactly_at_the_limit(self) -> None:
        # 97..103 is exactly 6 tall: still a box
        ev = zb.zone_breaks(*series([(100.0, 95.5, 96.0)], box=(103.0, 97.0, 101.0)))
        assert [e.entry_bar for e in ev] == [41]

    def test_no_event_before_the_break_bar_closes(self) -> None:
        h, lo, c, a, s = series([(100.0, 95.5, 96.0)])
        assert zb.zone_breaks(h[:41], lo[:41], c[:41], a[:41], s[:41]) == []

    def test_no_grid_no_event(self) -> None:
        h, lo, c, _, s = series([(100.0, 95.5, 96.0)])
        assert zb.zone_breaks(h, lo, c, np.full(len(c), math.nan), s) == []

    def test_a_late_arrival_needs_distance(self) -> None:
        # the 32 bars before the drop sit at 105 (only 5 < 0.5 step = 10 above the line) -> no arrival
        h, lo, c, a, s = series([(100.0, 95.5, 96.0)])
        h[:32], lo[:32], c[:32] = 106.0, 104.0, 105.0
        assert zb.zone_breaks(h, lo, c, a, s) == []
