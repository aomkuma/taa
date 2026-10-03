"""Golden (must fire) and near-miss (must not fire) cases for chart-pattern detectors.

Paths are straight legs between turning points (tests/evidence_paths.py): 6 bars per leg by default, 0.1 wicks,
so a pivot's price is its vertex ± 0.1.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from app.evidence.chart_patterns import (
    CupHandle,
    DoubleTopBottom,
    FlagPennant,
    HeadShoulders,
    Line,
    Rectangle,
    Triangle,
    TripleTopBottom,
    Wedge,
    volume_score,
)
from app.evidence.framework import Detector, Direction, Evidence, EvidenceContext
from tests.evidence_harness import context, scan_one
from tests.evidence_paths import path, path_frame


def fire(detector: Detector, ctx: EvidenceContext) -> list[tuple[int, str, Direction]]:
    return [
        (ctx.pos_of(e.detected_at), e.i18n_key.rsplit(".", 1)[-1], e.direction)
        for e in scan_one(detector, ctx)
    ]


def only(detector: Detector, ctx: EvidenceContext) -> Evidence:
    (ev,) = scan_one(detector, ctx)
    return ev


class TestDoubleTriple:
    M = (100, 90, 110, 100, 110, 92)

    def test_double_top_golden(self) -> None:
        ctx = path(self.M)
        ev = only(DoubleTopBottom(), ctx)
        # tops at 110.1 (bars 31, 43), neckline 99.9; the first close below it after the 2nd top is bar 47
        assert ctx.pos_of(ev.detected_at) == 47 and ev.direction is Direction.BEAR
        assert ev.invalidation == pytest.approx(110.1)
        assert ev.targets == pytest.approx((99.9 - 10.2,))
        assert [lv.name for lv in ev.key_levels] == ["first", "neck", "second", "neckline"]

    def test_double_bottom_golden(self) -> None:
        ctx = path([200 - v for v in self.M])
        assert fire(DoubleTopBottom(), ctx) == [(47, "bottom", Direction.BULL)]

    @pytest.mark.parametrize(
        "vertices",
        [
            (100, 90, 110, 100, 104, 92),  # second top far below the first
            (100, 90, 110, 100, 110, 101),  # never closes below the neckline
            (100, 90, 110, 100, 110, 104, 116, 92),  # rallies through the tops before breaking: invalidated
            (110, 100, 110, 92),  # first top is the frame's first pivot: no context, fails closed
        ],
    )
    def test_double_near_misses(self, vertices: Sequence[float]) -> None:
        assert [f for f in fire(DoubleTopBottom(), path(vertices)) if f[1] == "top"] == []

    def test_breakout_must_come_within_the_wait(self) -> None:
        vertices = [100, 90, 110, 100, 110, 103, 103, 92]
        prompt = path(vertices, [6, 6, 6, 6, 6, 2, 4])  # control: the same shape with a short pause fires
        assert [f[1] for f in fire(DoubleTopBottom(), prompt)] == ["top"]
        late = path(vertices, [6, 6, 6, 6, 6, 30, 4])
        assert fire(DoubleTopBottom(), late) == []

    def test_triple_top_golden(self) -> None:
        ctx = path([100, 90, 110, 100, 110, 100, 110, 92])
        assert fire(TripleTopBottom(), ctx) == [(59, "top", Direction.BEAR)]

    def test_volume_confirmation_raises_quality(self) -> None:
        n = len(path_frame(self.M))
        quiet = np.full(n, 100.0)
        loud = quiet.copy()
        loud[47] = 300.0  # the breakout bar
        q_quiet = only(DoubleTopBottom(), context(path_frame(self.M, volume=quiet))).quality
        q_loud = only(DoubleTopBottom(), context(path_frame(self.M, volume=loud))).quality
        assert q_loud > q_quiet

    def test_volume_score(self) -> None:
        n = 40
        v = np.full(n, 100.0)
        v[30] = 200.0
        ctx = context(path_frame([100, 100], n - 20, volume=v))
        assert volume_score(ctx, 30) == pytest.approx(1.0)
        assert volume_score(ctx, 25) == pytest.approx(1 / 3)
        assert volume_score(ctx, 5) == 0.5  # not enough history: neutral


class TestHeadShoulders:
    def test_top_golden(self) -> None:
        ctx = path([100, 90, 108, 100, 116, 100, 108, 92])
        ev = only(HeadShoulders(), ctx)
        assert ctx.pos_of(ev.detected_at) == 59 and ev.direction is Direction.BEAR
        assert ev.invalidation == pytest.approx(108.1)  # right shoulder
        assert ev.targets == pytest.approx((99.9 - (116.1 - 99.9),))

    def test_inverse_golden(self) -> None:
        ctx = path([100, 110, 92, 100, 84, 100, 92, 108])
        assert fire(HeadShoulders(), ctx) == [(59, "inverse", Direction.BULL)]

    def test_near_miss_head_not_prominent(self) -> None:
        ctx = path([100, 90, 108, 100, 108.5, 100, 108, 92])  # a triple top, not a head and shoulders
        assert fire(HeadShoulders(), ctx) == []
        assert fire(TripleTopBottom(), ctx) == [(59, "top", Direction.BEAR)]

    def test_near_miss_lopsided_shoulders(self) -> None:
        assert fire(HeadShoulders(), path([100, 90, 102, 96, 116, 100, 112, 92])) == []


class TestBoundaries:
    def test_line_fit(self) -> None:
        line = Line.fit([0, 10], [1.0, 2.0])
        assert line.at(5) == pytest.approx(1.5) and line.max_residual([0, 10], [1.0, 2.0]) < 1e-12

    def test_ascending_triangle_golden(self) -> None:
        ctx = path([100, 95, 110, 100, 110, 104, 116])
        assert fire(Triangle(), ctx) == [(53, "ascending", Direction.BULL)]

    def test_symmetrical_triangle_golden(self) -> None:
        ctx = path([100, 90, 112, 96, 108, 99, 105, 92])
        assert fire(Triangle(), ctx) == [(57, "symmetrical", Direction.BEAR)]

    def test_falling_wedge_golden(self) -> None:
        ctx = path([100, 115, 100, 110, 97, 105, 95, 110])
        ev = only(Wedge(), ctx)
        assert ev.i18n_key.endswith("falling_wedge") and ev.direction is Direction.BULL

    def test_rising_wedge_golden(self) -> None:
        ctx = path([100, 85, 100, 90, 103, 93, 105, 88])
        assert fire(Wedge(), ctx) == [(59, "rising_wedge", Direction.BEAR)]

    def test_wedge_break_in_its_own_direction_is_ignored(self) -> None:
        assert fire(Wedge(), path([100, 85, 100, 90, 103, 93, 105, 98, 115])) == []

    def test_rectangle_golden(self) -> None:
        ctx = path([100, 110, 90, 100, 90, 100, 90, 100, 112])
        assert fire(Rectangle(), ctx) == [(62, "rectangle", Direction.BULL)]

    def test_near_miss_not_on_a_line(self) -> None:
        # the highs 100 / 110 / 110 are not on one line: no wedge or triangle is read into a double top
        ctx = path([100, 90, 110, 100, 110, 92])
        assert fire(Wedge(), ctx) == [] and fire(Triangle(), ctx) == []


class TestFlag:
    def test_bull_flag_golden(self) -> None:
        ctx = path([100, 98, 114, 110, 116], [3, 5, 6, 2])
        ev = only(FlagPennant(), ctx)
        assert ev.i18n_key.endswith("bull_flag") and ev.direction is Direction.BULL
        assert ev.invalidation == pytest.approx(109.9)  # the flag low
        assert ev.detail("pole") == pytest.approx(16.2)

    def test_bear_flag_golden(self) -> None:
        ctx = path([200 - v for v in (100, 98, 114, 110, 116)], [3, 5, 6, 2])
        assert [f[1:] for f in fire(FlagPennant(), ctx)] == [("bear_flag", Direction.BEAR)]

    @pytest.mark.parametrize(
        ("vertices", "legs"),
        [
            ((100, 98, 114, 105, 116), (3, 5, 6, 3)),  # pullback 56 % of the pole: not a flag
            ((100, 98, 114, 110, 116), (3, 25, 6, 2)),  # slow pole: 25 bars
        ],
    )
    def test_near_misses(self, vertices: Sequence[float], legs: Sequence[int]) -> None:
        assert fire(FlagPennant(), path(vertices, legs)) == []


class TestCupHandle:
    @staticmethod
    def cup(shape: str, handle_low: float) -> EvidenceContext:
        x = np.linspace(0, 1, 31)
        bowl = 110 - 7.5 * (1 - np.cos(2 * np.pi * x)) if shape == "U" else 110 - 15 * (1 - np.abs(2 * x - 1))
        return path([100, 110, *bowl[1:], handle_low, 113], [8] + [1] * 30 + [4, 3])

    def test_golden(self) -> None:
        ctx = self.cup("U", 106)
        ev = only(CupHandle(), ctx)
        assert ev.direction is Direction.BULL and ctx.pos_of(ev.detected_at) == 63
        assert ev.invalidation == pytest.approx(105.9)  # the handle low
        assert ev.targets == pytest.approx((110.1 + 15.2,))

    def test_near_miss_v_shape(self) -> None:
        assert fire(CupHandle(), self.cup("V", 106)) == []

    def test_near_miss_deep_handle(self) -> None:
        assert fire(CupHandle(), self.cup("U", 101)) == []
