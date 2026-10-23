"""The owner's zone grid (app/strategy/zone_grid.py), on D1 bars built by hand with the answers worked on paper."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.strategy import zone_grid as zg

NS_H = 3600 * 10**9
T0 = 1_790_000_000 * 10**9  # an arbitrary start, int64 ns


def flat(n: int) -> dict[str, np.ndarray]:
    """n D1 bars, open = close = 100, high 105, low 95: every true range is 10, so the ATR(20) is 10."""
    return {
        "t_open": T0 + np.arange(n, dtype=np.int64) * 24 * NS_H,
        "o": np.full(n, 100.0),
        "h": np.full(n, 105.0),
        "lo": np.full(n, 95.0),
        "c": np.full(n, 100.0),
    }


def rows(b: dict[str, np.ndarray]) -> zg.GridRows:
    return zg.grid_rows(b["t_open"], b["o"], b["h"], b["lo"], b["c"])


class TestAtr:
    def test_mt5_warm_up(self) -> None:
        # bar 0 has no previous close, so 20 true ranges exist only from bar 20
        r = rows(flat(22))
        assert math.isnan(r.step[19])
        assert r.step[20] == pytest.approx(10.0)


class TestShift:
    def down_impulse(self) -> dict[str, np.ndarray]:
        # bar 21: open 100, close 84 (body -16 >= 1.5 x ATR), high 101, low 83: TR = 101 - 83 = 18,
        # ATR = (19 x 10 + 18) / 20 = 10.4; 1.5 x 10.4 = 15.6 <= 16 -> a down impulse
        b = flat(22)
        b["c"][21], b["h"][21], b["lo"][21] = 84.0, 101.0, 83.0
        # the base: bars 19 and 20 with bodies 100..103 and 98..101 -> the highest body edge is 103
        b["c"][19], b["h"][19] = 103.0, 105.0
        b["o"][20], b["c"][20] = 101.0, 98.0
        return b

    def test_anchor_is_the_highest_body_of_the_base_before_a_drop(self) -> None:
        r = rows(self.down_impulse())
        assert r.shift[21] == -1
        assert r.anchor[21] == pytest.approx(103.0)
        assert math.isnan(r.anchor[20])

    def test_not_known_before_the_bar_closes(self) -> None:
        b = self.down_impulse()
        r = rows(b)
        forming = int(b["t_open"][21]) + 23 * NS_H
        assert math.isnan(zg.grid_at(r, forming).anchor)
        closed = int(b["t_open"][21]) + 24 * NS_H
        s = zg.grid_at(r, closed)
        assert s.anchor == pytest.approx(103.0)
        assert s.last_shift == -1
        assert s.row == 21

    def test_anchor_is_the_lowest_body_of_the_base_before_a_rally(self) -> None:
        b = flat(22)
        b["c"][21], b["h"][21], b["lo"][21] = 116.0, 117.0, 99.0  # body +16, TR 18
        b["o"][19], b["lo"][19] = 97.0, 95.0  # base bodies 97..100 and 100..100 -> lowest edge 97
        r = rows(b)
        assert r.shift[21] == 1
        assert r.anchor[21] == pytest.approx(97.0)

    def test_a_body_just_under_the_threshold_is_no_impulse(self) -> None:
        b = flat(22)
        b["c"][21], b["h"][21], b["lo"][21] = 84.5, 101.0, 83.0  # body 15.5 < 15.6
        assert rows(b).shift[21] == 0

    def test_a_body_exactly_at_the_threshold_is_an_impulse(self) -> None:
        # numbers exact in binary: TR 30 (high 100, low 70), ATR = (190 + 30) / 20 = 11, 1.5 x 11 = 16.5;
        # body 100 - 83.5 = 16.5 exactly
        b = flat(22)
        b["c"][21], b["h"][21], b["lo"][21] = 83.5, 100.0, 70.0
        assert rows(b).shift[21] == -1

    def test_the_latest_shift_wins(self) -> None:
        # a down impulse at bar 21 (anchor 103), then an up impulse at bar 23: body +40 from 84 to 124, high 124,
        # low 84; its base = bars 21 and 22 (bodies 84..100 and 84..84) -> the lowest body edge 84
        b = self.down_impulse()
        for k, v in (("o", [84.0, 84.0]), ("h", [94.0, 124.0]), ("lo", [74.0, 84.0]), ("c", [84.0, 124.0])):
            b[k] = np.r_[b[k], v]
        b["t_open"] = np.r_[b["t_open"], b["t_open"][-1] + (1 + np.arange(2, dtype=np.int64)) * 24 * NS_H]
        r = rows(b)
        assert r.shift[23] == 1
        s = zg.grid_at(r, int(b["t_open"][23]) + 24 * NS_H)
        assert s.last_shift == 1
        assert s.anchor == pytest.approx(84.0)

    def test_the_anchor_is_carried_and_the_step_breathes(self) -> None:
        b = self.down_impulse()
        for k in ("t_open", "o", "h", "lo", "c"):
            extra = flat(3)[k]
            if k == "t_open":
                extra = b["t_open"][-1] + (1 + np.arange(3, dtype=np.int64)) * 24 * NS_H
            elif k in ("o", "c"):
                extra = np.full(3, 84.0)
            elif k == "h":
                extra = np.full(3, 94.0)  # TR = 94 - 74 = 20 each
            else:
                extra = np.full(3, 74.0)
            b[k] = np.r_[b[k], extra]
        r = rows(b)
        assert r.anchor[24] == pytest.approx(103.0)
        assert r.shift[22:].tolist() == [0, 0, 0]
        # bars 5..24: sixteen TRs of 10, bar 21 18, bars 22-24 20 each (94 - 74)
        assert r.step[24] == pytest.approx((16 * 10 + 18 + 3 * 20) / 20)


class TestLines:
    state = zg.GridState(anchor=100.0, step=10.0, last_shift=-1, row=0)

    @pytest.mark.parametrize(
        ("price", "line", "dist", "share"),
        [
            (113.0, 110.0, 3.0, 0.3),
            (117.0, 120.0, 3.0, 0.3),
            (100.0, 100.0, 0.0, 0.0),
            (86.0, 90.0, 4.0, 0.4),
        ],
    )
    def test_nearest_line(self, price: float, line: float, dist: float, share: float) -> None:
        got = zg.nearest_line(self.state, price)
        assert got == pytest.approx((line, dist, share))

    @pytest.mark.parametrize(
        ("price", "side", "target"),
        [(113.0, 1, 120.0), (118.0, 1, 130.0), (113.0, -1, 110.0), (112.0, -1, 100.0), (100.0, -1, 90.0)],
    )
    def test_next_line_at_least_a_quarter_step_away(self, price: float, side: int, target: float) -> None:
        assert zg.next_line(self.state, price, side) == pytest.approx(target)

    def test_no_grid_yet(self) -> None:
        empty = zg.GridState(math.nan, math.nan, 0, -1)
        assert all(math.isnan(v) for v in zg.nearest_line(empty, 100.0))
        assert math.isnan(zg.next_line(empty, 100.0, 1))
