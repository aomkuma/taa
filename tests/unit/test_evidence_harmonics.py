"""Golden (must fire) and near-miss (must not fire) cases for the harmonic-pattern detectors."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import pytest
from pydantic import ValidationError

from app.core.errors import ConfigError
from app.evidence.catalog import default_registry
from app.evidence.framework import Detector, Direction, EvidenceContext
from app.evidence.harmonics import (
    SPECS,
    AbCd,
    Bat,
    Butterfly,
    Crab,
    Cypher,
    Gartley,
    HarmonicParams,
    Shark,
    prz,
    ratio_error,
)
from tests.evidence_harness import assert_no_lookahead, scan_one
from tests.evidence_paths import path, path_frame

STEP = 4.0  # price per bar: legs get bars in proportion to their length, so every turn is a zigzag pivot


def legs(vertices: Sequence[float]) -> list[int]:
    return [max(2, round(abs(b - a) / STEP)) for a, b in pairwise(vertices)]


def hpath(vertices: Sequence[float], bars_per_leg: Sequence[int] | None = None) -> EvidenceContext:
    return path(vertices, bars_per_leg or legs(vertices))


# Bullish vertices X, A, B, C, D (ideal ratios, XA = 100), then a bounce; (A, B, C, D) for AB=CD after a
# lead-in. Expected: the bar that first reaches the PRZ (the D vertex is a few bars later).
GOLDEN: dict[str, tuple[Detector, list[float], int]] = {
    # B 61.8 %, C 61.8 % of AB, D 78.6 % of XA
    "gartley": (Gartley(), [1000, 1100, 1038.2, 1076.39, 1021.4, 1060], 82),
    # B 45 %, C 70 % of AB, D 88.6 % of XA
    "bat": (Bat(), [1000, 1100, 1055, 1086.5, 1011.4, 1050], 81),
    # B 78.6 %, C 61.8 % of AB, D 127.2 % of XA
    "butterfly": (Butterfly(), [1000, 1100, 1021.4, 1069.97, 972.8, 1020], 99),
    # B 50 %, C 88.6 % of AB, D 161.8 % of XA
    "crab": (Crab(), [1000, 1100, 1050, 1094.3, 938.2, 1000], 105),
    # B 50 %, C 127.2 % of AB, D 78.6 % of XC
    "cypher": (Cypher(), [1000, 1100, 1050, 1113.6, 1024.31, 1060], 93),
    # B 50 %, C 127 % of AB, D 100 % of XC
    "shark": (Shark(), [1000, 1100, 1050, 1113.5, 1000, 1050], 97),
    # C 61.8 % of AB, CD = AB
    "abcd": (AbCd(), [1050, 1100, 1000, 1061.8, 961.8, 1000], 95),
}


def mirror(vertices: Sequence[float]) -> list[float]:
    return [2200 - v for v in vertices]


class TestGolden:
    @pytest.mark.parametrize("name", GOLDEN)
    @pytest.mark.parametrize("bullish", [True, False], ids=["bullish", "bearish"])
    def test_completes_in_the_prz(self, name: str, bullish: bool) -> None:
        detector, vertices, bar = GOLDEN[name]
        verts = vertices if bullish else mirror(vertices)
        ctx = hpath(verts)
        (ev,) = scan_one(detector, ctx)
        assert ctx.pos_of(ev.detected_at) == bar
        assert ev.direction is (Direction.BULL if bullish else Direction.BEAR)
        assert ev.i18n_key == f"evidence.{detector.id}.{'bullish' if bullish else 'bearish'}"
        assert ev.quality > 0.98  # ideal ratios: the only error is the 0.1 wicks on the pivots
        levels = {k.name: k.price for k in ev.key_levels}
        near, far, d = levels["prz_near"], levels["prz_far"], levels["D"]
        sign = 1 if bullish else -1
        # the D vertex lies in the PRZ; the probe is clipped to it; the stop is beyond the far edge
        assert (far - verts[-2]) * sign <= 0 <= (near - verts[-2]) * sign
        assert (far - d) * sign <= 0 <= (near - d) * sign
        assert ev.invalidation is not None and (ev.invalidation - far) * sign < 0
        a = levels["A"]
        assert ev.targets == pytest.approx([d + r * (a - d) for r in (0.382, 0.618)])

    def test_ratios_reported(self) -> None:
        detector, vertices, _ = GOLDEN["gartley"]
        (ev,) = scan_one(detector, hpath(vertices))
        assert ev.detail("ab_xa") == pytest.approx(0.618, abs=0.005)
        assert ev.detail("bc_ab") == pytest.approx(0.618, abs=0.005)
        assert ev.detail("degree") == "minor"

    @pytest.mark.parametrize("name", ["gartley", "crab", "abcd"])
    def test_no_lookahead_around_completion(self, name: str) -> None:
        detector, vertices, bar = GOLDEN[name]
        found = assert_no_lookahead(
            detector, path_frame(vertices, legs(vertices)), positions=(bar - 12, bar - 1, bar, bar + 3)
        )
        assert found  # not vacuous


class TestNearMiss:
    def test_b_off_ratio(self) -> None:
        # B at 50 % of XA is a Bat's B, not a Gartley's 61.8 %
        assert scan_one(Gartley(), hpath([1000, 1100, 1050, 1076.39, 1021.4, 1060])) == []

    def test_blown_through(self) -> None:
        # C -> D in two bars: the second closes far beyond the PRZ, so the zone never held
        vertices = [1000, 1100, 1038.2, 1076.39, 990, 1030]
        bars = legs(vertices)
        bars[3] = 2
        assert scan_one(Gartley(), hpath(vertices, bars)) == []

    def test_cd_leg_fails_before_the_prz(self) -> None:
        # after C the price turns up through C before reaching the PRZ: that X-A-B-C is dead (a later,
        # different window may still form its own pattern)
        ctx = hpath([1000, 1100, 1038.2, 1076.39, 1050, 1090, 1021.4, 1060])
        assert all(e.key_levels[0].price != pytest.approx(999.9) for e in scan_one(Gartley(), ctx))

    def test_only_shark_and_cypher_have_c_beyond_a(self) -> None:
        # the Shark path (C beyond A) is no Gartley, Bat, Butterfly or Crab
        ctx = hpath(GOLDEN["shark"][1])
        for detector in (Gartley(), Bat(), Butterfly(), Crab()):
            assert scan_one(detector, ctx) == []


class TestRules:
    def test_ratio_error(self) -> None:
        assert ratio_error(0.5, (0.382, 0.886), 0.05) == 0.0
        assert ratio_error(0.618, (0.618, 0.618), 0.05) == 0.0
        assert ratio_error(0.618 * 1.05, (0.618, 0.618), 0.05) == pytest.approx(1.0)
        assert ratio_error(0.382 * 0.9, (0.382, 0.886), 0.05) == pytest.approx(2.0)

    def test_prz_is_the_intersection(self) -> None:
        # Gartley X 0, A 100, B 38.2, C 61.8 (BC 23.6), bands widened by 5 %: 78.6 % of XA puts D at
        # 17.5..25.3, the 1.272-1.618 BC projection at 21.7..33.3; the PRZ is their overlap
        points = {"X": 0.0, "A": 100.0, "B": 38.2, "C": 61.8}
        zone = prz(points, SPECS["gartley"], 0.05)
        assert zone is not None
        assert zone[0] == pytest.approx(61.8 - 1.618 * 1.05 * 23.6)
        assert zone[1] == pytest.approx(100 - 0.786 * 0.95 * 100)
        assert prz(points, SPECS["gartley"], 0.01) is None  # stricter: the ratios disagree

    def test_tolerance_bounds(self) -> None:
        with pytest.raises(ValidationError):
            HarmonicParams(ratio_tol=0.5)
        with pytest.raises(ValidationError):
            HarmonicParams(ratio_tol=0)

    def test_tolerance_from_config(self) -> None:
        registry = default_registry()
        params = registry.parse_params("harmonic.gartley", {"ratio_tol": 0.03})
        assert isinstance(params, HarmonicParams) and params.ratio_tol == 0.03
        with pytest.raises(ConfigError):
            registry.parse_params("harmonic.gartley", {"ratio_tol": 0.3})

    def test_stricter_tolerance_rejects_a_looser_fit(self) -> None:
        # B at 60 % of XA is within 5 % of 61.8 % but not within 2 %
        vertices = [1000, 1100, 1040, 1077, 1021.4, 1060]
        assert len(scan_one(Gartley(), hpath(vertices))) == 1
        assert scan_one(Gartley(), hpath(vertices), params=HarmonicParams(ratio_tol=0.02)) == []
