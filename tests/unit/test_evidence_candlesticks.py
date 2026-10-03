"""Golden and near-miss cases for candlestick detectors, plus a TA-Lib cross-check of the bare geometry."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pytest

from app.evidence.candlesticks import (
    Bars,
    Doji,
    Engulfing,
    Hammer,
    Harami,
    InsideOutside,
    Marubozu,
    ShootingStar,
    Star,
    ThreeSoldiersCrows,
    Tweezer,
    doji_mask,
    engulfing_mask,
    harami_mask,
    marubozu_mask,
    trailing_mean,
)
from app.evidence.catalog import ALL_DETECTORS
from app.evidence.framework import Detector, Direction, Evidence, EvidenceContext, Family, Tier
from tests.evidence_harness import scan_one
from tests.evidence_paths import bars, path_rows
from tests.indicator_data import random_ohlc

Row = tuple[float, float, float, float]

# Prices near 1012 keep round numbers (step 10, half 5) away from the pattern bars unless a test wants one.
WARM: list[Row] = [(1012.0, 1012.5, 1011.5, 1012.2), (1012.2, 1012.7, 1011.7, 1012.0)] * 8  # ref range 1.0
# 7 bars, so that even a 3-bar pattern's prior-trend window (5 bars before it) lies inside the move
DOWN: list[Row] = [(1019.0 - k, 1019.2 - k, 1017.8 - k, 1018.0 - k) for k in range(7)]  # closes 1018 -> 1012
UP: list[Row] = [(1005.0 + k, 1006.2 + k, 1004.8 + k, 1006.0 + k) for k in range(7)]  # closes 1006 -> 1012


def found(detector: Detector, rows: Sequence[Row]) -> list[Evidence]:
    ctx = bars(rows)
    return [e for e in scan_one(detector, ctx, ALL_DETECTORS) if ctx.pos_of(e.detected_at) == ctx.last_pos]


def one(detector: Detector, rows: Sequence[Row]) -> Evidence:
    (ev,) = found(detector, rows)
    return ev


def variant(ev: Evidence) -> str:
    return ev.i18n_key.rsplit(".", 1)[-1]


class TestSingleBar:
    def test_hammer_after_decline(self) -> None:
        ev = one(Hammer(), [*WARM, *DOWN, (1012.2, 1012.3, 1010.2, 1012.25)])
        assert ev.direction is Direction.BULL and ev.invalidation == 1010.2

    def test_hammer_needs_a_prior_decline(self) -> None:
        assert found(Hammer(), [*WARM, *UP, (1012.2, 1012.3, 1010.2, 1012.25)]) == []

    def test_hammer_near_miss_upper_shadow(self) -> None:
        assert found(Hammer(), [*WARM, *DOWN, (1012.2, 1013.0, 1010.2, 1012.25)]) == []

    def test_shooting_star_after_rise(self) -> None:
        ev = one(ShootingStar(), [*WARM, *UP, (1011.8, 1013.8, 1011.7, 1011.75)])
        assert ev.direction is Direction.BEAR and ev.invalidation == 1013.8

    def test_doji_family(self) -> None:
        assert variant(one(Doji(), [*WARM, *DOWN, (1012.0, 1012.05, 1010.6, 1012.02)])) == "dragonfly"
        assert variant(one(Doji(), [*WARM, *UP, (1012.0, 1013.4, 1011.95, 1011.98)])) == "gravestone"
        neutral = one(Doji(), [*WARM, (1012.0, 1013.0, 1011.0, 1012.01)])
        assert variant(neutral) == "long_legged" and neutral.direction is Direction.NEUTRAL

    def test_marubozu(self) -> None:
        ev = one(Marubozu(), [*WARM, (1012.0, 1014.03, 1011.97, 1014.0)])
        assert ev.direction is Direction.BULL
        assert found(Marubozu(), [*WARM, (1012.0, 1014.5, 1011.5, 1014.0)]) == []  # long shadows


class TestTwoBar:
    def test_bullish_engulfing(self) -> None:
        ev = one(Engulfing(), [*WARM, *DOWN, (1011.9, 1013.3, 1011.8, 1013.2)])
        assert ev.direction is Direction.BULL and ev.detail("bars") == 2

    def test_engulfing_near_miss_body_not_covered(self) -> None:
        assert found(Engulfing(), [*WARM, *DOWN, (1012.1, 1013.3, 1011.8, 1012.9)]) == []

    def test_bullish_harami(self) -> None:
        long_black: Row = (1014.0, 1014.1, 1011.9, 1012.0)
        ev = one(Harami(), [*WARM, *DOWN, long_black, (1012.5, 1012.9, 1012.4, 1012.8)])
        assert ev.direction is Direction.BULL

    def test_inside_and_outside(self) -> None:
        mother: Row = (1012.0, 1014.0, 1010.0, 1013.0)
        assert variant(one(InsideOutside(), [*WARM, mother, (1012.5, 1013.0, 1011.0, 1012.8)])) == "inside"
        small: Row = (1012.0, 1012.6, 1011.6, 1012.2)
        outside = one(InsideOutside(), [*WARM, small, (1011.9, 1013.0, 1011.0, 1012.9)])
        assert variant(outside) == "outside_bull" and outside.direction is Direction.BULL

    def test_inside_needs_a_wide_mother_bar(self) -> None:
        small: Row = (1012.0, 1012.3, 1011.8, 1012.1)
        assert found(InsideOutside(), [*WARM, small, (1012.0, 1012.2, 1011.9, 1012.1)]) == []

    def test_tweezer_bottom(self) -> None:
        rows = [*WARM, *DOWN, (1012.5, 1012.6, 1011.0, 1011.2), (1011.3, 1012.6, 1011.02, 1012.5)]
        ev = one(Tweezer(), rows)
        assert variant(ev) == "bottom" and ev.direction is Direction.BULL


class TestThreeBar:
    STAR_START: tuple[Row, ...] = (
        *WARM,
        *DOWN,
        (1014.0, 1014.1, 1011.9, 1012.0),
        (1011.9, 1012.0, 1011.5, 1011.8),
    )

    def test_morning_star(self) -> None:
        ev = one(Star(), [*self.STAR_START, (1011.9, 1013.6, 1011.8, 1013.5)])
        assert variant(ev) == "morning" and ev.direction is Direction.BULL and ev.invalidation == 1011.5

    def test_morning_star_near_miss_weak_third_bar(self) -> None:
        # the third bar closes below the first bar's midpoint (1013.0)
        assert found(Star(), [*self.STAR_START, (1011.9, 1012.9, 1011.8, 1012.8)]) == []

    def test_three_white_soldiers(self) -> None:
        soldiers = [
            (1012.0, 1013.1, 1011.9, 1013.0),
            (1012.5, 1014.1, 1012.4, 1014.0),
            (1013.5, 1015.1, 1013.4, 1015.0),
        ]
        ev = one(ThreeSoldiersCrows(), [*WARM, *soldiers])
        assert variant(ev) == "soldiers" and ev.direction is Direction.BULL

    def test_three_soldiers_near_miss_long_upper_shadow(self) -> None:
        soldiers = [
            (1012.0, 1013.1, 1011.9, 1013.0),
            (1012.5, 1014.1, 1012.4, 1014.0),
            (1013.5, 1016.0, 1013.4, 1015.0),
        ]
        assert found(ThreeSoldiersCrows(), [*WARM, *soldiers]) == []


def _source(det_id: str, *, report: bool = False, variant: str | None = None) -> Detector:
    """A stand-in level source: silent, or reporting one BULL record (of *variant*) on the last bar."""

    class Source(Detector):
        id = det_id
        name = "stub"
        family = Family.LEVELS
        tier = Tier.T1

        def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
            if not report:
                return []
            return [self.make(ctx, ctx.last_pos, Direction.BULL, 1.0, variant=variant)]

    return Source()


HAMMER_ROWS: list[Row] = [*WARM, *DOWN, (1012.2, 1012.3, 1010.0, 1012.25)]  # probes the round number 1010


def last_bar(detector: Detector, rows: Sequence[Row], sources: Sequence[Detector]) -> Evidence:
    ctx = bars(rows)
    (ev,) = [e for e in scan_one(detector, ctx, sources) if ctx.pos_of(e.detected_at) == ctx.last_pos]
    return ev


def test_location_weighting() -> None:
    """The same hammer scores higher when a level source reports a rejection on its bar (here the round number
    1010) than when every level source is silent."""
    at_level = one(Hammer(), HAMMER_ROWS)
    mid_air = last_bar(Hammer(), HAMMER_ROWS, [_source(d) for d in Hammer.depends_on])
    assert at_level.detail("at_level") is True and mid_air.detail("at_level") is False
    assert at_level.detail("at_levels") == "evidence.levels.round_number.minor"  # step 10 near 1012
    assert mid_air.detail("at_levels") == ""
    assert at_level.quality == pytest.approx(mid_air.quality / 0.6)


@pytest.mark.parametrize(
    ("det_id", "variant", "counts"),
    [
        ("structure.trendline", "bounce_support", True),
        ("structure.trendline", "break_resistance", False),  # a break goes through the line
        ("levels.prev_high_low", "pdl.reject", True),
        ("levels.prev_high_low", "pdh.break", False),
        ("fib.cluster", None, True),
    ],
)
def test_location_variant_filter(det_id: str, variant: str | None, counts: bool) -> None:
    sources = [_source(d) for d in Hammer.depends_on if d != det_id]
    ev = last_bar(Hammer(), HAMMER_ROWS, [*sources, _source(det_id, report=True, variant=variant)])
    key = f"evidence.{det_id}.{variant}" if variant else f"evidence.{det_id}"
    assert ev.detail("at_level") is counts
    assert ev.detail("at_levels") == (key if counts else "")


def test_shooting_star_at_fib_extension() -> None:
    """A shooting star rejecting the 161.8 % extension of the up leg 999.9 -> 1010.1 (level 1016.4036)."""
    star: Row = (1015.6, 1016.5, 1015.45, 1015.5)
    ev = one(ShootingStar(), [*path_rows([1000, 1010, 1005, 1015.5]), star])
    assert ev.detail("at_level") is True
    assert ev.detail("at_levels") == "evidence.fib.extension_level.external.161.8"
    assert ev.quality == pytest.approx(1.0)  # full geometry, undiscounted for location


class TestTalibCrossCheck:
    """The bare geometry matches TA-Lib's definitions (TA-Lib starts reporting a few bars later)."""

    @pytest.fixture
    def b(self) -> Bars:
        df = random_ohlc(5000, seed=3)
        return Bars(*(df[k].to_numpy() for k in ("open", "high", "low", "close")))

    def test_trailing_mean_excludes_the_bar(self) -> None:
        out = trailing_mean(np.arange(1.0, 6.0), 2)
        np.testing.assert_allclose(out, [np.nan, np.nan, 1.5, 2.5, 3.5])

    @pytest.mark.parametrize(
        ("name", "ours"),
        [
            ("CDLENGULFING", engulfing_mask),
            ("CDLDOJI", lambda b: doji_mask(b).astype(np.int64)),
            ("CDLHARAMI", harami_mask),
            ("CDLMARUBOZU", marubozu_mask),
        ],
    )
    def test_matches_talib(self, b: Bars, name: str, ours: Callable[[Bars], np.ndarray]) -> None:
        talib = pytest.importorskip("talib")
        ref = getattr(talib, name)(b.o, b.h, b.l, b.c)
        mine = ours(b)
        skip = 12  # TA-Lib lookback
        np.testing.assert_array_equal(np.sign(mine[skip:]), np.sign(ref[skip:]))
        assert (mine[skip:] != 0).sum() > 30  # not vacuous
