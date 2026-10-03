"""Golden and near-miss cases for Ichimoku, structure and smart-money detectors (TAA-2A6)."""

from __future__ import annotations

from collections.abc import Sequence

from app.evidence.framework import Detector, Direction, EvidenceContext
from app.evidence.ichimoku import Chikou, KumoBreakout, TkCross, ichimoku
from app.evidence.structure_smc import (
    BosChoch,
    DowStructure,
    FairValueGap,
    LiquiditySweep,
    OrderBlock,
    SupplyDemand,
    Trendline,
    WyckoffSpring,
)
from tests.evidence_harness import scan_one
from tests.evidence_paths import bars, path, path_frame

Row = tuple[float, float, float, float]
Q: list[Row] = [(100.0, 100.4, 99.6, 100.1), (100.1, 100.5, 99.7, 100.0)]


def found(detector: Detector, ctx: EvidenceContext) -> list[tuple[int, str, Direction]]:
    prefix = f"evidence.{detector.id}"
    return [
        (ctx.pos_of(e.detected_at), e.i18n_key.removeprefix(prefix).lstrip("."), e.direction)
        for e in scan_one(detector, ctx)
    ]


def rows_of(vertices: Sequence[float], legs: int | Sequence[int] = 6) -> list[Row]:
    df = path_frame(vertices, legs)
    return [(r.open, r.high, r.low, r.close) for r in df.itertuples()]


# --- Ichimoku ---------------------------------------------------------------------------------------------


class TestIchimoku:
    TURN = ([100, 85, 105], [80, 60])  # a long decline under the cloud, then a rally through it

    def test_cloud_is_shifted_forward_not_backward(self) -> None:
        ctx = path(*self.TURN)
        ich = ichimoku(ctx)
        assert ich.cloud_a[60] == ich.lead_a[60 - 26]  # the cloud at bar t was computed 26 bars earlier

    def test_kumo_breakout_tk_cross_and_chikou_on_the_rally(self) -> None:
        ctx = path(*self.TURN)
        bottom = 20 + 80
        assert any(
            k[1] == "breakout" and k[2] is Direction.BULL and k[0] > bottom
            for k in found(KumoBreakout(), ctx)
        )
        assert any(k[2] is Direction.BULL and k[0] > bottom for k in found(TkCross(), ctx))
        assert any(k[2] is Direction.BULL and k[0] > bottom for k in found(Chikou(), ctx))

    def test_bullish_tk_cross_below_the_cloud_is_weak(self) -> None:
        ctx = path(*self.TURN)
        (bull,) = [e for e in scan_one(TkCross(), ctx) if e.direction is Direction.BULL]
        assert bull.quality == 0.4

    def test_near_miss_no_cloud_yet(self) -> None:
        assert found(KumoBreakout(), path([100, 110], [40])) == []  # 60 bars: Senkou B + shift need 77


# --- structure --------------------------------------------------------------------------------------------

UPTREND = [100, 90, 105, 97, 110, 102, 115]


class TestStructure:
    def test_dow_up(self) -> None:
        assert found(DowStructure(), path(UPTREND)) == [(39, "up", Direction.BULL)]

    def test_bos_then_choch(self) -> None:
        ctx = path([*UPTREND, 104, 108, 95])
        events = [k[1:] for k in found(BosChoch(), ctx)]
        assert events == [
            ("break", Direction.BULL),  # no trend yet
            ("bos", Direction.BULL),
            ("bos", Direction.BULL),
            ("choch", Direction.BEAR),  # the up-trend's last higher low gives way
        ]

    def test_trendline_bounce(self) -> None:
        # lows 89.9 (bar 25) and 94.9 (37) define a rising line; the next low at 100.6 sits on it
        ctx = path([100, 90, 105, 95, 110, 100.6, 115])
        assert found(Trendline(), ctx) == [(50, "bounce_support", Direction.BULL)]

    def test_trendline_break(self) -> None:
        ctx = path([100, 90, 105, 95, 110, 92])
        assert ("break_support", Direction.BEAR) in [k[1:] for k in found(Trendline(), ctx)]

    def test_near_miss_falling_lows_make_no_support_line(self) -> None:
        ctx = path([100, 95, 105, 90, 110, 88, 112])
        assert [k for k in found(Trendline(), ctx) if "support" in k[1]] == []


# --- smart money ------------------------------------------------------------------------------------------

# a V that leaves a swing low at 98.5, a range, then a probe below it
SWEEP_BASE: list[Row] = [
    *(Q * 10),
    (100.0, 100.1, 99.0, 99.2),
    (99.2, 99.3, 98.5, 98.7),
    (98.7, 99.4, 98.6, 99.3),
    (99.3, 100.0, 99.2, 99.9),
    (99.9, 100.2, 99.7, 100.0),
    (100.0, 100.3, 99.8, 100.1),
    *(Q * 3),
]


class TestSmartMoney:
    def test_liquidity_sweep(self) -> None:
        ctx = bars([*SWEEP_BASE, (99.8, 99.9, 98.2, 99.5)])
        (event,) = scan_one(LiquiditySweep(), ctx)
        assert event.direction is Direction.BULL and event.invalidation == 98.2

    def test_closing_through_the_pool_is_a_breakout_not_a_sweep(self) -> None:
        assert scan_one(LiquiditySweep(), bars([*SWEEP_BASE, (99.8, 99.9, 98.0, 98.2)])) == []

    FVG: tuple[Row, ...] = (
        *(Q * 10),
        (100.0, 100.3, 99.9, 100.2),
        (100.2, 102.0, 100.1, 101.9),
        (101.9, 102.5, 100.9, 102.3),
    )

    def test_fvg_retest(self) -> None:
        # gap between 100.3 (bar 20 high) and 100.9 (bar 22 low); bar 24 dips to 100.5 and closes above
        ctx = bars([*self.FVG, (102.3, 102.4, 101.5, 101.6), (101.6, 101.7, 100.5, 101.2)])
        assert found(FairValueGap(), ctx) == [(24, "", Direction.BULL)]

    def test_filled_fvg_is_dead(self) -> None:
        ctx = bars([*self.FVG, (102.3, 102.4, 100.0, 100.1), (100.1, 101.0, 100.0, 100.8)])
        assert found(FairValueGap(), ctx) == []

    def test_order_block_retest(self) -> None:
        rows = [
            *(Q * 10),
            (100.2, 100.3, 99.5, 99.6),  # the last bearish candle before the leg
            (99.6, 101.0, 99.5, 100.9),
            (100.9, 102.2, 100.8, 102.1),  # displacement: +2.5 in two bars, above the prior highs
            (102.1, 102.2, 101.0, 101.2),
            (101.2, 101.3, 100.2, 100.4),  # back into the candle's range, closes above it
        ]
        (event,) = scan_one(OrderBlock(), bars(rows))
        assert event.direction is Direction.BULL and event.invalidation == 99.5

    def test_demand_zone_retest(self) -> None:
        base: list[Row] = [(100.0, 100.1, 99.95, 100.05)] * 3  # a tight base
        rows = [
            *(Q * 10),
            *base,
            (100.05, 101.4, 100.0, 101.3),
            (101.3, 102.6, 101.2, 102.5),
            (102.5, 102.6, 101.0, 101.2),
            (101.2, 101.3, 100.05, 100.4),
        ]
        (event,) = scan_one(SupplyDemand(), bars(rows))
        assert event.direction is Direction.BULL and event.invalidation == 99.95

    def test_wyckoff_spring(self) -> None:
        rng = rows_of([100, 98.5, 101.5, 98.5, 101.5, 98.5, 101.5, 100], 5)
        ctx = bars([*rng, (100.0, 100.2, 97.9, 99.0)])  # under the 98.4 range low, closes back inside
        (event,) = scan_one(WyckoffSpring(), ctx)
        assert event.i18n_key.endswith("spring") and event.direction is Direction.BULL

    def test_spring_needs_a_sideways_range(self) -> None:
        trend = rows_of([100, 110], 30)
        ctx = bars([*trend, (110.0, 110.2, 99.0, 104.0)])
        assert scan_one(WyckoffSpring(), ctx) == []
