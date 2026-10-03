"""Golden (must fire) and near-miss (must not fire) cases for the Fibonacci and level detectors."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pandas as pd
import pytest

from app.evidence.fibonacci import (
    FibCluster,
    FibExtension,
    FibGoldenZone,
    FibRetracement,
    _clusters,
    impulses,
)
from app.evidence.framework import Detector, Direction, Evidence, EvidenceContext
from app.evidence.levels import (
    PivotPoints,
    PrevHighLow,
    RoundNumber,
    SRBreakout,
    SRZone,
    pivot_levels,
    round_step,
)
from tests.evidence_harness import context, scan_one

Row = tuple[float, float, float, float]


def frame(rows: Sequence[Row], start: datetime = datetime(2026, 9, 30, 0, tzinfo=UTC)) -> EvidenceContext:
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    df.index = pd.date_range(start, periods=len(rows), freq="h")
    df["tick_volume"] = 100
    return context(df)


def run(detector: Detector, ctx: EvidenceContext) -> list[Evidence]:
    return scan_one(detector, ctx)


# --- Fibonacci --------------------------------------------------------------------------------------------
# Up impulse A = 99.5 (bar 0) -> B = 110.25 (bar 29, confirmed at bar 33); last impulse from bar 34.
# Retracements: 50 % = 104.875, 61.8 % = 103.6065, 78.6 % = 101.8005.

WARMUP: list[Row] = [(100, 100.5, 99.5, 100)] * 20
IMPULSE: list[Row] = [(c - 1, c + 0.25, c - 1.25, c) for c in range(101, 111)]
PULLBACK: list[Row] = [(c + 1, c + 1.25, c - 0.25, c) for c in (109, 108, 107, 106, 105)]
BASE = WARMUP + IMPULSE + PULLBACK  # bars 0..34
HAMMER: Row = (104.6, 105.0, 103.7, 104.9)  # bar 35: probes 61.8 %, closes back up with a long lower wick


def test_impulse_geometry() -> None:
    ctx = frame([*BASE, HAMMER])
    (imp,) = list(impulses(ctx.zigzag("intermediate"), ctx.last_pos))
    assert (imp.a.price, imp.b.price, imp.start, imp.direction) == (99.5, 110.25, 34, Direction.BULL)
    assert imp.retracement(0.618) == pytest.approx(103.6065)
    assert imp.extension(1.272) == pytest.approx(113.174)


class TestRetracement:
    def test_golden(self) -> None:
        out = run(FibRetracement(), frame([*BASE, HAMMER]))
        got = {(e.detail("ratio"), frame([*BASE, HAMMER]).pos_of(e.detected_at)) for e in out}
        # bar 34 closes just above 50 %; bar 35 probes 61.8 % and rejects it (it closed through 50 %)
        assert got == {(0.5, 34), (0.618, 35)}
        e618 = next(e for e in out if e.detail("ratio") == 0.618)
        assert e618.direction is Direction.BULL and e618.invalidation == 99.5
        assert e618.targets[0] == 110.25 and e618.i18n_key == "evidence.fib.retracement.61.8"

    def test_near_miss_closing_through_is_not_a_rejection(self) -> None:
        through = (104.0, 104.2, 103.5, 103.55)  # closes below 61.8 %
        out = run(FibRetracement(), frame([*BASE, through]))
        assert all(e.detail("ratio") != 0.618 for e in out)

    def test_spent_after_close_beyond_origin(self) -> None:
        crash = (100.0, 100.2, 98.0, 98.5)  # closes below A = 99.5
        out = run(FibRetracement(), frame([*BASE, crash, HAMMER]))
        assert all(frame([*BASE, crash, HAMMER]).pos_of(e.detected_at) < 35 for e in out)


class TestGoldenZone:
    def test_golden(self) -> None:
        (ev,) = run(FibGoldenZone(), frame([*BASE, HAMMER]))
        assert ev.direction is Direction.BULL
        assert ev.invalidation == pytest.approx(101.8005)
        assert ev.quality > 0.7

    @pytest.mark.parametrize(
        "bar",
        [
            (105.6, 106.0, 105.2, 105.9),  # too shallow: never reached 50 %
            (103.0, 105.0, 101.5, 104.9),  # too deep: through 78.6 %
            (104.9, 105.0, 103.7, 104.0),  # bearish candle: no rejection
            (103.8, 105.0, 103.7, 104.9),  # wick only 8 % of the range
        ],
    )
    def test_near_misses(self, bar: Row) -> None:
        assert run(FibGoldenZone(), frame([*BASE, bar])) == []

    def test_once_per_impulse(self) -> None:
        assert len(run(FibGoldenZone(), frame([*BASE, HAMMER, HAMMER]))) == 1


class TestExtension:
    RALLY: tuple[Row, ...] = tuple((c - 1, c + 0.25, c - 1.25, c) for c in (106, 107, 108, 109, 110, 111))

    def test_golden(self) -> None:
        ctx = frame([*BASE, HAMMER, *self.RALLY])
        (ev,) = run(FibExtension(), ctx)
        assert ctx.pos_of(ev.detected_at) == ctx.last_pos  # first close above B = 110.25
        assert ev.direction is Direction.BULL and ev.invalidation == 103.7
        assert ev.targets == pytest.approx((113.174, 116.8935))
        assert ev.quality == 1.0  # pullback depth 0.609 is in the 38.2-61.8 % band

    def test_near_miss_too_deep_pullback(self) -> None:
        deep = (102.0, 102.3, 100.6, 101.0)  # pullback low 100.6: depth 0.90 > 0.786
        ctx = frame(BASE + [deep] + [(c - 1, c + 0.25, c - 1.25, c) for c in range(102, 112)])
        assert run(FibExtension(), ctx) == []


def test_cluster_rule() -> None:
    a, b = (0, 5), (3, 9)  # two different impulses
    levels = [(1.1000, "minor_ret_61.8", a), (1.1002, "major_ret_38.2", b), (1.1003, "minor_ret_50.0", a)]
    (cluster,) = _clusters(levels, span=0.0005, min_levels=2)
    assert [name for _, name, _ in cluster] == ["minor_ret_61.8", "major_ret_38.2", "minor_ret_50.0"]
    assert _clusters(levels, span=0.00005, min_levels=2) == []  # too far apart
    same = [(1.1000, "minor_ret_61.8", a), (1.1001, "minor_ext_127.2", a)]
    assert _clusters(same, span=0.0005, min_levels=2) == []  # one impulse is not a confluence


def test_cluster_requires_distinct_impulses() -> None:
    # minor and intermediate see the same single impulse here: their levels coincide but are not a cluster
    assert run(FibCluster(), frame([*BASE, HAMMER])) == []


# --- round numbers ----------------------------------------------------------------------------------------

FX_WARMUP: list[Row] = [(1.1030, 1.1035, 1.1025, 1.1030)] * 20  # ATR 0.001: tolerance 0.00015


class TestRoundNumber:
    def test_step(self) -> None:
        assert round_step(1.1) == pytest.approx(0.01)
        assert round_step(150.2) == pytest.approx(1.0)
        assert round_step(4139.3) == pytest.approx(10.0)

    def test_golden_major_level(self) -> None:
        (ev,) = run(RoundNumber(), frame([*FX_WARMUP, (1.1012, 1.102, 1.1001, 1.1016)]))
        assert ev.direction is Direction.BULL
        assert ev.i18n_key == "evidence.levels.round_number.major"
        assert ev.key_levels[0].price == pytest.approx(1.1)

    def test_resistance_at_half_level(self) -> None:
        (ev,) = run(RoundNumber(), frame([*FX_WARMUP, (1.104, 1.1049, 1.1036, 1.1038)]))
        assert ev.direction is Direction.BEAR and ev.i18n_key.endswith(".half")

    def test_near_miss(self) -> None:
        assert run(RoundNumber(), frame([*FX_WARMUP, (1.1012, 1.102, 1.1003, 1.1016)])) == []


# --- pivot points and previous day high/low ---------------------------------------------------------------
# Session timezone Europe/Athens (EEST, UTC+3): 21:00 UTC is the start of a trading day.
DAY0 = datetime(2026, 9, 28, 21, tzinfo=UTC)
FLAT: Row = (1.1000, 1.1005, 1.0995, 1.1000)


def three_days(day3: Sequence[Row]) -> EvidenceContext:
    day1 = [FLAT] * 24  # first day of the frame: possibly partial, never used as a source
    day2 = [FLAT] * 10 + [(1.1000, 1.1100, 1.0995, 1.1000)] + [FLAT] * 6 + [(1.1000, 1.1005, 1.0900, 1.1000)]
    day2 += [FLAT] * 6  # day 2: H 1.1100, L 1.0900, C 1.1000 -> P 1.1, S1 1.09, R1 1.11
    return frame(day1 + day2 + [FLAT] * 12 + list(day3), start=DAY0)


def test_pivot_formulas() -> None:
    classic = pivot_levels("classic", 1.11, 1.09, 1.10)
    assert classic["P"] == pytest.approx(1.10) and classic["S1"] == pytest.approx(1.09)
    assert classic["R2"] == pytest.approx(1.12)
    fib = pivot_levels("fibonacci", 1.11, 1.09, 1.10)
    assert fib["R1"] == pytest.approx(1.10 + 0.382 * 0.02)
    cam = pivot_levels("camarilla", 1.11, 1.09, 1.10)
    assert cam["S3"] == pytest.approx(1.10 - 0.02 * 1.1 / 4)


class TestPivotsAndPreviousDay:
    S1_PROBE: Row = (1.0960, 1.0965, 1.0902, 1.0958)

    def test_pivot_golden(self) -> None:
        ctx = three_days([self.S1_PROBE])
        out = run(PivotPoints(), ctx)
        (s1,) = [e for e in out if e.i18n_key.endswith("classic.S1")]
        assert s1.direction is Direction.BULL and ctx.pos_of(s1.detected_at) == ctx.last_pos

    def test_first_day_is_never_a_source(self) -> None:
        ctx = three_days([])
        day2_bars = range(24, 48)
        assert all(ctx.pos_of(e.detected_at) not in day2_bars for e in run(PivotPoints(), ctx))

    def test_previous_low_rejected(self) -> None:
        ctx = three_days([self.S1_PROBE])
        events = {
            e.i18n_key.rsplit(".", 2)[-2] + "." + e.i18n_key.rsplit(".", 1)[-1]
            for e in run(PrevHighLow(), ctx)
        }
        assert "pdl.reject" in events

    def test_previous_high_break_once(self) -> None:
        ctx = three_days([(1.1050, 1.1130, 1.1045, 1.1120), (1.1120, 1.1140, 1.1110, 1.1135)])
        breaks = [e for e in run(PrevHighLow(), ctx) if e.i18n_key.endswith("pdh.break")]
        assert len(breaks) == 1 and breaks[0].direction is Direction.BULL and breaks[0].invalidation == 1.11

    def test_near_miss_probe_short_of_level(self) -> None:
        ctx = three_days([(1.0960, 1.0965, 1.0915, 1.0958)])
        assert not [e for e in run(PrevHighLow(), ctx) if e.i18n_key.endswith("pdl.reject")]


# --- S/R zones and breakouts ------------------------------------------------------------------------------


def saw(peaks: int) -> list[Row]:
    """Swing highs at exactly 1.1050 (resistance) and lows at 1.1000, 7 bars per tooth (k = 3)."""
    rows: list[Row] = []
    for _ in range(peaks):
        for c in (1.1010, 1.1020, 1.1030, 1.1040, 1.1030, 1.1020, 1.1010):
            top = 1.1050 if c == 1.1040 else c + 0.0005
            rows.append((c - 0.0002, top, c - 0.0008, c))
    return rows


SR_BASE = FX_WARMUP + saw(4)
BELOW: list[Row] = [(1.1020, 1.1030, 1.1015, 1.1025)] * 6  # a base closing under the zone


class TestSRZone:
    def test_golden_resistance_rejection(self) -> None:
        star = (1.1028, 1.1050, 1.1024, 1.1026)  # probes the zone, long upper wick, closes back below
        # BELOW twice: the probe comes after the 10-bar cooldown that follows the last tooth's own test
        ctx = frame(SR_BASE + BELOW * 2 + [star])
        out = [e for e in run(SRZone(), ctx) if ctx.pos_of(e.detected_at) == ctx.last_pos]
        assert len(out) == 1 and out[0].direction is Direction.BEAR
        assert out[0].detail("touches") >= 3

    def test_near_miss_without_wick(self) -> None:
        flat_top = (1.1020, 1.1047, 1.1018, 1.1045)  # closes near its high: no rejection
        ctx = frame(SR_BASE + BELOW * 2 + [flat_top])
        assert not [e for e in run(SRZone(), ctx) if ctx.pos_of(e.detected_at) == ctx.last_pos]


class TestSRBreakout:
    BREAK: Row = (1.1030, 1.1075, 1.1028, 1.1070)

    def test_confirmed_breakout(self) -> None:
        hold = [(1.1070, 1.1085, 1.1062, 1.1080)] * 3
        ctx = frame(SR_BASE + BELOW + [self.BREAK] + hold)
        (ev,) = [e for e in run(SRBreakout(), ctx) if e.i18n_key.endswith("confirmed")]
        assert ev.direction is Direction.BULL
        assert ctx.pos_of(ev.detected_at) == ctx.last_pos  # decided after 3 bars, never earlier

    def test_false_breakout_is_bearish(self) -> None:
        back = [(1.1070, 1.1072, 1.1030, 1.1035), (1.1035, 1.1040, 1.1020, 1.1025), FLAT]
        ctx = frame(SR_BASE + BELOW + [self.BREAK] + back)
        (ev,) = [e for e in run(SRBreakout(), ctx) if e.i18n_key.endswith("false")]
        assert ev.direction is Direction.BEAR

    def test_pending_breakout_is_not_reported(self) -> None:
        ctx = frame(SR_BASE + BELOW + [self.BREAK, (1.1070, 1.1085, 1.1062, 1.1080)])
        assert not [e for e in run(SRBreakout(), ctx) if ctx.pos_of(e.detected_at) >= len(SR_BASE + BELOW)]

    def test_near_miss_whipsaw_without_base(self) -> None:
        # a close above the zone that fails, then a second break: the 5 closes before it were not a base
        spike, fall = (1.1040, 1.1075, 1.1038, 1.1068), (1.1068, 1.1069, 1.1030, 1.1032)
        below = [(1.1030, 1.1035, 1.1025, 1.1030)] * 2
        hold = [(1.1070, 1.1085, 1.1062, 1.1080)] * 3
        ctx = frame(SR_BASE + BELOW + [spike, fall] + below + [self.BREAK] + hold)
        events = run(SRBreakout(), ctx)
        assert [e.i18n_key.rsplit(".", 1)[-1] for e in events if ctx.pos_of(e.detected_at) > 54] == ["false"]
