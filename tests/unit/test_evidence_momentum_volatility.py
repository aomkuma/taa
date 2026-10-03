"""Golden and near-miss cases for momentum, trend, volatility/volume and session detectors (TAA-2A5)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from app.evidence.framework import Detector, Direction, Evidence, EvidenceContext
from app.evidence.momentum import CciExtreme, Divergence, MomentumCross, OverboughtOversold
from app.evidence.sessions_ranges import AsianRangeBreakout, OpenRangeBreakout
from app.evidence.trend import AdxStrength, MaAlignment
from app.evidence.volatility import (
    AtrExpansion,
    BollingerSqueeze,
    DonchianBreakout,
    KeltnerBreakout,
    SessionVwap,
    TickVolumeSpike,
    session_vwap,
)
from tests.evidence_harness import context, scan_one
from tests.evidence_paths import bars, path

Row = tuple[float, float, float, float]


def keys(detector: Detector, ctx: EvidenceContext) -> list[tuple[int, str, Direction]]:
    prefix = f"evidence.{detector.id}"
    return [
        (ctx.pos_of(e.detected_at), e.i18n_key.removeprefix(prefix).lstrip("."), e.direction)
        for e in scan_one(detector, ctx)
    ]


def at_last(detector: Detector, ctx: EvidenceContext) -> list[Evidence]:
    return [e for e in scan_one(detector, ctx) if ctx.pos_of(e.detected_at) == ctx.last_pos]


# --- divergences ------------------------------------------------------------------------------------------


class TestDivergence:
    def test_regular_bearish_on_real_rsi(self) -> None:
        # a fast rally to 112, then a choppy grind to 114: a higher high on weaker RSI (77.4 -> 68.7)
        ctx = path(
            [100, 90, 112, 104, 108, 106.5, 110, 108.5, 112, 110.5, 114, 100],
            [6, 6, 6, 3, 2, 3, 2, 3, 2, 3, 6],
        )
        rsi = [e for e in scan_one(Divergence(), ctx) if e.detail("oscillator") == "rsi"]
        (ev,) = rsi
        assert ev.i18n_key.endswith("rsi.regular") and ev.direction is Direction.BEAR
        assert ev.invalidation == pytest.approx(114.1)  # the second high
        assert ctx.pos_of(ev.detected_at) == 56  # its confirmation bar, never the pivot bar

    @staticmethod
    def seeded(vertices: Sequence[float], at_pivots: dict[int, float]) -> EvidenceContext:
        """A zigzag path whose RSI is replaced by chosen values at given pivot bars (the classification logic
        under test is independent of how the oscillator got there)."""
        ctx = path(vertices)
        osc = np.full(ctx.n, 50.0)
        for pos, value in at_pivots.items():
            osc[pos] = value
        ctx.memo(("osc", "rsi"), lambda: osc)
        return ctx

    # pivots of path([100, 90, 110, 95, 112, 99, 115]): L25 89.9, H31 110.1, L37 94.9, H43 112.1, L49 98.9
    @pytest.mark.parametrize(
        ("osc", "expected"),
        [
            ({31: 70, 43: 60}, ("rsi.regular", Direction.BEAR)),  # higher high, lower RSI
            ({37: 40, 49: 30}, ("rsi.hidden", Direction.BULL)),  # higher low, lower RSI
        ],
    )
    def test_classification(self, osc: dict[int, float], expected: tuple[str, Direction]) -> None:
        ctx = self.seeded([100, 90, 110, 95, 112, 99, 115], osc)
        found = {(e.i18n_key.split("divergence.")[1], e.direction) for e in scan_one(Divergence(), ctx)}
        assert expected in found

    @pytest.mark.parametrize(
        ("osc", "expected"),
        [
            ({31: 60, 43: 70}, ("rsi.hidden", Direction.BEAR)),  # lower high, higher RSI
            ({25: 30, 37: 40}, ("rsi.regular", Direction.BULL)),  # lower low, higher RSI
        ],
    )
    def test_classification_falling_market(
        self, osc: dict[int, float], expected: tuple[str, Direction]
    ) -> None:
        # pivots of path([100, 110, 90, 105, 88, 102, 80]): H25 110.1, L31 89.9, H37 105.1, L43 87.9, H49 102.1
        ctx = self.seeded([100, 110, 90, 105, 88, 102, 80], {k + 6: v for k, v in osc.items()})
        found = {(e.i18n_key.split("divergence.")[1], e.direction) for e in scan_one(Divergence(), ctx)}
        assert expected in found

    def test_near_miss_agreeing_oscillator(self) -> None:
        ctx = self.seeded([100, 90, 110, 95, 112, 99, 115], {25: 30, 31: 60, 37: 40, 43: 70, 49: 45})
        assert [e for e in scan_one(Divergence(), ctx) if e.detail("oscillator") == "rsi"] == []


# --- oscillator extremes and crosses ----------------------------------------------------------------------


class TestOscillators:
    def test_rsi_overbought_exit(self) -> None:
        ctx = path([100, 115, 108], [15, 4])
        rsi_exits = [k for k in keys(OverboughtOversold(), ctx) if k[1] == "rsi.overbought_exit"]
        assert len(rsi_exits) == 1 and rsi_exits[0][2] is Direction.BEAR

    def test_macd_bullish_cross_below_zero_scores_higher(self) -> None:
        ctx = path([100, 85, 95], [20, 10])
        crosses = [e for e in scan_one(MomentumCross(), ctx) if e.i18n_key.endswith("macd")]
        bull = [e for e in crosses if e.direction is Direction.BULL]
        assert bull and bull[0].quality == 1.0  # MACD still below zero when it crossed up

    def test_cci_extreme_exit(self) -> None:
        ctx = path([100, 100, 112, 104], [20, 4, 6])
        assert ("extreme_exit", Direction.BEAR) in {k[1:] for k in keys(CciExtreme(), ctx)}


# --- trend ------------------------------------------------------------------------------------------------


class TestTrend:
    def test_alignment_and_golden_cross(self) -> None:
        # EMA200 must already exist while EMA50 is below it: a long decline first, then a long rise
        ctx = path([100, 80, 130], [250, 250])
        found = {k[1:] for k in keys(MaAlignment(), ctx)}
        assert ("golden_cross", Direction.BULL) in found and ("aligned_bull", Direction.BULL) in found

    def test_alignment_needs_warm_emas(self) -> None:
        assert keys(MaAlignment(), path([100, 120], [150])) == []  # EMA200 never defined

    def test_adx_strength(self) -> None:
        # flat bars have no directional movement, so ADX starts near 0 and must rise through 25
        ctx = path([100, 125], [25], warmup=40)
        found = keys(AdxStrength(), ctx)
        assert found and found[0][2] is Direction.BULL


# --- volatility -------------------------------------------------------------------------------------------

QUIET: list[Row] = [(100.0, 100.4, 99.6, 100.1), (100.1, 100.5, 99.7, 100.0)] * 70  # range 0.8


class TestVolatility:
    def test_bollinger_squeeze_breakout(self) -> None:
        wide = [(100.0, 103.0, 97.0, 102.0), (102.0, 104.0, 98.0, 98.5)] * 60
        tight = [(100.0, 100.2, 99.8, 100.05), (100.05, 100.25, 99.85, 100.0)] * 15
        ctx = bars([*wide, *tight, (100.0, 101.2, 99.9, 101.1)])
        (ev,) = at_last(BollingerSqueeze(), ctx)
        assert ev.direction is Direction.BULL

    def test_no_breakout_without_squeeze(self) -> None:
        wide = [(100.0, 103.0, 97.0, 102.0), (102.0, 104.0, 98.0, 98.5)] * 70
        assert at_last(BollingerSqueeze(), bars([*wide, (100.0, 106.0, 99.9, 105.5)])) == []

    def test_keltner_breakout(self) -> None:
        (ev,) = at_last(KeltnerBreakout(), bars([*QUIET, (100.0, 102.6, 99.9, 102.5)]))
        assert ev.direction is Direction.BULL

    def test_donchian_breakout_needs_a_close(self) -> None:
        assert [
            e.direction for e in at_last(DonchianBreakout(), bars([*QUIET, (100.0, 100.9, 99.9, 100.8)]))
        ] == [Direction.BULL]
        assert at_last(DonchianBreakout(), bars([*QUIET, (100.0, 100.9, 99.9, 100.3)])) == []  # wick only

    def test_range_expansion(self) -> None:
        (ev,) = at_last(AtrExpansion(), bars([*QUIET, (100.0, 101.9, 99.9, 101.8)]))
        assert ev.direction is Direction.BULL
        assert at_last(AtrExpansion(), bars([*QUIET, (100.0, 101.9, 99.9, 100.9)])) == []  # closed mid-range


# --- tick volume ------------------------------------------------------------------------------------------


class TestVolume:
    @staticmethod
    def frame(rows: Sequence[Row], volume: Sequence[float]) -> EvidenceContext:
        df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
        df.index = pd.date_range(datetime(2026, 9, 30, tzinfo=UTC), periods=len(rows), freq="h")
        df["tick_volume"] = np.asarray(volume, dtype=float)
        return context(df)

    def test_spike(self) -> None:
        rows = [*QUIET, (100.0, 100.9, 99.9, 100.85)]
        (ev,) = at_last(TickVolumeSpike(), self.frame(rows, [100.0] * len(QUIET) + [400.0]))
        assert ev.i18n_key.endswith("spike") and ev.direction is Direction.BULL

    def test_selling_climax(self) -> None:
        decline = [(100.0 - k, 100.1 - k, 98.9 - k, 99.0 - k) for k in range(10)]
        climax = (90.0, 90.5, 87.0, 89.9)  # heavy volume, closes off the lows
        rows = [*QUIET, *decline, climax]
        (ev,) = at_last(TickVolumeSpike(), self.frame(rows, [100.0] * (len(rows) - 1) + [500.0]))
        assert ev.i18n_key.endswith("climax") and ev.direction is Direction.BULL

    def test_near_miss_normal_volume(self) -> None:
        rows = [*QUIET, (100.0, 100.9, 99.9, 100.85)]
        assert at_last(TickVolumeSpike(), self.frame(rows, [100.0] * len(rows))) == []

    def test_vwap_and_reclaim(self) -> None:
        # one Athens trading day starts at 21:00 UTC; VWAP of equal volumes is the mean typical price
        start = datetime(2026, 9, 29, 21, tzinfo=UTC)
        rows = (
            [(100.0, 100.2, 99.8, 100.0)] * 4 + [(99.0, 99.2, 98.8, 99.0)] * 4 + [(99.0, 100.6, 98.9, 100.5)]
        )
        ctx = bars(rows, start=start)
        vwap = session_vwap(ctx)
        assert vwap[3] == pytest.approx(100.0)
        (ev,) = at_last(SessionVwap(), ctx)
        assert ev.i18n_key.endswith("reclaim") and ev.direction is Direction.BULL


# --- sessions ---------------------------------------------------------------------------------------------


def day_bars(
    day: datetime, asian: Row, london_break: Row | None, *, drop: int | None = None
) -> EvidenceContext:
    """H1 bars from 08:00 UTC the previous day (warm-up) through 12:00 UTC on *day*. Tokyo 09:00-15:00 is
    00:00-06:00 UTC; in October London 08:00 is 07:00 UTC (BST)."""
    start = day - pd.Timedelta(hours=16)
    rows: list[Row] = []
    t = start
    while t < day + pd.Timedelta(hours=12):
        hour = t.hour if t >= day else None
        if hour is not None and hour == 8 and london_break is not None:
            rows.append(london_break)
        elif hour is not None and 0 <= hour < 6:
            rows.append(asian)
        else:
            rows.append((1.1010, 1.1015, 1.1005, 1.1010))
        t += pd.Timedelta(hours=1)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    df.index = pd.date_range(start, periods=len(rows), freq="h")
    df["tick_volume"] = 100.0
    if drop is not None:
        df = df.drop(df.index[drop])
    return context(df)


class TestSessions:
    DAY = datetime(2026, 10, 1, tzinfo=UTC)
    ASIAN: Row = (1.1005, 1.1020, 1.1000, 1.1015)

    def test_asian_range_breakout(self) -> None:
        ctx = day_bars(self.DAY, self.ASIAN, (1.1015, 1.1035, 1.1012, 1.1032))
        (ev,) = scan_one(AsianRangeBreakout(), ctx)
        assert ev.direction is Direction.BULL and ev.targets == pytest.approx((1.1040,))
        assert ctx.time_at(ctx.pos_of(ev.detected_at)) == datetime(
            2026, 10, 1, 9, tzinfo=UTC
        )  # 08:00 bar closes 09:00

    def test_asian_range_with_a_missing_bar_is_unknown(self) -> None:
        ctx = day_bars(self.DAY, self.ASIAN, (1.1015, 1.1035, 1.1012, 1.1032), drop=16 + 2)
        assert scan_one(AsianRangeBreakout(), ctx) == []

    def test_london_opening_range_follows_daylight_saving(self) -> None:
        # October (BST): the London 08:00 opening bar is 07:00 UTC; January (GMT): 08:00 UTC
        for day, opening_utc in (
            (datetime(2026, 10, 1, tzinfo=UTC), 7),
            (datetime(2027, 1, 13, tzinfo=UTC), 8),
        ):
            start = day + pd.Timedelta(hours=opening_utc - 20)
            rows: list[Row] = [(1.1010, 1.1015, 1.1005, 1.1010)] * 20  # ATR(14) warm-up
            rows += [(1.1010, 1.1030, 1.1000, 1.1020)]  # the opening-range bar
            rows += [(1.1020, 1.1045, 1.1018, 1.1040)]  # first close above it
            ctx = bars(rows, start=start)
            london = [e for e in scan_one(OpenRangeBreakout(), ctx) if e.i18n_key.endswith("london")]
            assert len(london) == 1, day
            assert london[0].key_levels[0].price == pytest.approx(1.1030)
