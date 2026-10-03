from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

from app.core.errors import ConfigError, InsufficientDataError
from app.indicators.price_action import (
    Breakout,
    BreakoutStatus,
    StructureLabel,
    Swing,
    SwingKind,
    Zone,
    candle_anatomy,
    detect_breakouts,
    find_swings,
    label_structure,
    market_structure,
    sr_zones,
    swing_points,
)
from app.indicators.volatility import atr
from tests.indicator_data import mutate_after, random_ohlc


def series(values: Sequence[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


def zigzag(up: bool) -> tuple[pd.Series, pd.Series]:
    path = [0, 2, 1, 3, 2, 4, 3, 5, 4, 6]
    price = np.array(path, dtype=float) if up else -np.array(path, dtype=float)
    return pd.Series(price + 0.1), pd.Series(price - 0.1)


def swing(kind: SwingKind, price: float, pivot: int, k: int = 1) -> Swing:
    return Swing(kind, price, pivot, pivot + k, pivot, pivot + k)


class TestCandleAnatomy:
    def test_reference(self) -> None:
        out = candle_anatomy(series([10, 12]), series([14, 13]), series([9, 8]), series([12, 9]))
        bull, bear = out.iloc[0], out.iloc[1]
        assert bull["range"] == 5 and bull["body"] == 2 and bull["direction"] == 1
        assert bull["body_ratio"] == pytest.approx(0.4)
        assert bull["upper_wick_ratio"] == pytest.approx(0.4)
        assert bull["lower_wick_ratio"] == pytest.approx(0.2)
        assert bear["direction"] == -1
        assert bear["upper_wick_ratio"] == pytest.approx(0.2)
        assert bear["lower_wick_ratio"] == pytest.approx(0.2)

    def test_ratios_sum_to_one_and_zero_range_is_nan(self) -> None:
        df = random_ohlc(200)
        out = candle_anatomy(df["open"], df["high"], df["low"], df["close"])
        total = out["body_ratio"] + out["upper_wick_ratio"] + out["lower_wick_ratio"]
        np.testing.assert_allclose(total, 1.0)
        doji = candle_anatomy(series([1]), series([1]), series([1]), series([1]))
        assert doji[["body_ratio", "upper_wick_ratio", "lower_wick_ratio"]].isna().all().all()


class TestSwings:
    HIGH = (1, 2, 5, 3, 2, 4, 6, 4, 3, 2)
    LOW = (0, 1, 3, 2, 1, 2, 4, 3, 1, 0.5)

    def test_reference_and_confirmation_lag(self) -> None:
        out = find_swings(series(self.HIGH), series(self.LOW), k=2)
        assert [(s.kind, s.pivot_pos, s.confirm_pos, s.price) for s in out] == [
            (SwingKind.HIGH, 2, 4, 5.0),
            (SwingKind.LOW, 4, 6, 1.0),
            (SwingKind.HIGH, 6, 8, 6.0),
        ]

    def test_last_k_bars_are_never_pivots(self) -> None:
        # bar 9 is the lowest low of all but has no k bars after it yet
        out = find_swings(series(self.HIGH), series(self.LOW), k=2)
        assert all(s.pivot_pos <= 7 for s in out)

    def test_flat_top_yields_one_swing_at_first_bar(self) -> None:
        out = find_swings(series([1, 3, 3, 1, 0]), series([0, 2, 2, 0, -1]), k=1)
        highs = [s for s in out if s.kind is SwingKind.HIGH]
        assert [(s.pivot_pos, s.price) for s in highs] == [(1, 3.0)]

    def test_labels_are_index_labels(self) -> None:
        df = random_ohlc(100)
        for s in find_swings(df["high"], df["low"], 3):
            assert s.pivot_at == df.index[s.pivot_pos]
            assert s.confirm_at == df.index[s.pivot_pos + 3]

    def test_swing_points_frame(self) -> None:
        out = swing_points(series(self.HIGH), series(self.LOW), k=2)
        assert out["swing_high"].iloc[4] == 5.0 and out["high_pivot_pos"].iloc[4] == 2
        assert out["swing_low"].iloc[6] == 1.0
        assert out["swing_high"].notna().sum() == 2

    def test_nan_bar_is_never_a_pivot_neighbour(self) -> None:
        high = series([1, 2, 5, np.nan, 2, 1, 0])
        assert not [s for s in find_swings(high, high - 1, k=2) if s.pivot_pos == 2]


class TestStructure:
    def test_labels(self) -> None:
        swings = [
            swing(SwingKind.HIGH, 2.0, 1),
            swing(SwingKind.LOW, 1.0, 2),
            swing(SwingKind.HIGH, 3.0, 3),
            swing(SwingKind.LOW, 0.5, 4),
            swing(SwingKind.HIGH, 3.05, 5),
        ]
        labels = [ls.label for ls in label_structure(swings, equal_tolerance=0.1)]
        assert labels == [None, None, StructureLabel.HH, StructureLabel.LL, StructureLabel.EQH]

    def test_uptrend_zigzag(self) -> None:
        high, low = zigzag(up=True)
        out = market_structure(high, low, k=1)
        assert out["trend"].iloc[:5].isna().all()
        assert (out["trend"].iloc[5:] == "UP").all()
        assert out["last_high_label"].iloc[-1] == "HH"
        assert out["last_low_label"].iloc[-1] == "HL"

    def test_downtrend_zigzag(self) -> None:
        high, low = zigzag(up=False)
        out = market_structure(high, low, k=1)
        assert out["trend"].iloc[:5].isna().all()
        assert (out["trend"].iloc[5:] == "DOWN").all()

    def test_straight_line_has_no_swings(self) -> None:
        line = pd.Series(np.arange(10.0))
        assert find_swings(line + 0.1, line - 0.1, k=1) == []
        assert market_structure(line + 0.1, line - 0.1, k=1)["trend"].isna().all()

    def test_negative_tolerance_rejected(self) -> None:
        with pytest.raises(ConfigError):
            label_structure([], equal_tolerance=-1)


class TestZones:
    SWINGS = (
        swing(SwingKind.LOW, 1.0, 1),
        swing(SwingKind.LOW, 1.02, 3),
        swing(SwingKind.HIGH, 1.5, 5),
        swing(SwingKind.HIGH, 1.51, 7),
        swing(SwingKind.LOW, 1.505, 9),
        swing(SwingKind.HIGH, 2.0, 11),
    )

    def test_clustering_and_strength_order(self) -> None:
        zones = sr_zones(self.SWINGS, as_of_pos=100, atr_value=0.1, tolerance_atr=0.5)
        assert [(z.low, z.high, z.touches) for z in zones] == [(1.5, 1.51, 3), (1.0, 1.02, 2), (2.0, 2.0, 1)]
        top = zones[0]
        assert (top.high_touches, top.low_touches) == (2, 1)
        assert top.role(1.2) == "RESISTANCE" and top.role(1.6) == "SUPPORT" and top.role(1.505) == "INSIDE"

    def test_only_confirmed_swings_count(self) -> None:
        zones = sr_zones(self.SWINGS, as_of_pos=8, atr_value=0.1, tolerance_atr=0.5)
        assert sorted(z.touches for z in zones) == [2, 2]

    def test_min_touches(self) -> None:
        zones = sr_zones(self.SWINGS, as_of_pos=100, atr_value=0.1, tolerance_atr=0.5, min_touches=2)
        assert len(zones) == 2

    def test_width_never_exceeds_tolerance(self) -> None:
        chain = [swing(SwingKind.LOW, 1.0 + 0.03 * i, i) for i in range(10)]
        zones = sr_zones(chain, as_of_pos=100, atr_value=0.1, tolerance_atr=0.5)
        assert all(z.high - z.low <= 0.05 + 1e-12 for z in zones)

    @pytest.mark.parametrize("bad_atr", [float("nan"), 0.0, -1.0])
    def test_no_atr_fails_closed(self, bad_atr: float) -> None:
        with pytest.raises(InsufficientDataError):
            sr_zones(self.SWINGS, as_of_pos=100, atr_value=bad_atr, tolerance_atr=0.5)


class TestBreakouts:
    ZONE = Zone(
        low=1.0, high=1.1, touches=3, high_touches=2, low_touches=1, first_pivot_pos=0, last_pivot_pos=0
    )

    def run(self, closes: list[float]) -> list[Breakout]:
        c = series(closes)
        return detect_breakouts(
            c, pd.Series(np.full(len(c), 0.1)), [self.ZONE], buffer_atr=0.1, false_breakout_bars=3
        )

    def test_confirmed_up(self) -> None:
        (b,) = self.run([1.05, 1.05, 1.15, 1.2, 1.25, 1.3])
        assert (b.direction, b.pos, b.status, b.resolved_pos) == (1, 2, BreakoutStatus.CONFIRMED, 5)
        assert b.level == pytest.approx(1.11)

    def test_false_up(self) -> None:
        (b,) = self.run([1.05, 1.05, 1.15, 1.08, 1.05, 1.05])
        assert (b.status, b.resolved_pos) == (BreakoutStatus.FALSE, 3)

    def test_pending_when_data_ends(self) -> None:
        (b,) = self.run([1.05, 1.05, 1.15, 1.2])
        assert (b.status, b.resolved_pos) == (BreakoutStatus.PENDING, None)

    def test_confirmed_down(self) -> None:
        (b,) = self.run([1.05, 1.05, 0.95, 0.9, 0.85, 0.8])
        assert (b.direction, b.status) == (-1, BreakoutStatus.CONFIRMED)

    def test_inside_buffer_is_not_a_breakout(self) -> None:
        assert self.run([1.05, 1.105, 1.109, 1.05]) == []

    def test_start_pos(self) -> None:
        c = series([1.05, 1.05, 1.15, 1.2, 1.25, 1.3])
        out = detect_breakouts(
            c, pd.Series(np.full(6, 0.1)), [self.ZONE], buffer_atr=0.1, false_breakout_bars=3, start_pos=3
        )
        assert out == []

    def test_status_never_uses_bars_after_resolution(self) -> None:
        df = random_ohlc(400, seed=3)
        a = atr(df["high"], df["low"], df["close"])
        swings = find_swings(df["high"], df["low"], 3)
        zones = sr_zones(swings, as_of_pos=150, atr_value=float(a.iloc[150]), tolerance_atr=0.5)
        full = detect_breakouts(df["close"], a, zones, buffer_atr=0.1, false_breakout_bars=3, start_pos=151)
        for t in (200, 300):
            cut = detect_breakouts(
                df["close"].iloc[: t + 1],
                a.iloc[: t + 1],
                zones,
                buffer_atr=0.1,
                false_breakout_bars=3,
                start_pos=151,
            )
            seen = [b for b in full if b.pos <= t]
            assert len(cut) == len(seen)
            for early, late in zip(cut, seen, strict=True):
                if early.resolved_pos is None:
                    assert late.resolved_pos is None or late.resolved_pos > t
                else:
                    assert early == late


@pytest.mark.parametrize("t", [100, 298])
def test_no_look_ahead(t: int) -> None:
    df = random_ohlc(300)
    mutated = mutate_after(df, t)
    for fn in (
        lambda d: candle_anatomy(d["open"], d["high"], d["low"], d["close"]),
        lambda d: swing_points(d["high"], d["low"], 3),
        lambda d: market_structure(d["high"], d["low"], 3),
    ):
        before, after = fn(df), fn(mutated)
        pd.testing.assert_frame_equal(before.iloc[: t + 1], after.iloc[: t + 1])
