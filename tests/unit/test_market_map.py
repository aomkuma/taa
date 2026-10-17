"""Higher-timeframe market map (TAA-L809): states, hysteresis, zones, no look-ahead, trade features."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.indicators.market_map import (
    MapParams,
    MapState,
    MapZone,
    MarketMap,
    RangeBox,
    TimeframeMap,
    ZoneKind,
    ZoneSource,
    _hysteresis,
    efficiency_ratio,
    signal_features,
    state_frame,
    timeframe_map,
    zones_at,
)

T0 = datetime(2025, 1, 6, tzinfo=UTC)
H4 = timedelta(hours=4)
P = MapParams()


def frame(closes: np.ndarray, *, wick: float = 0.0006, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) + rng.uniform(0.2, 1.0, len(closes)) * wick
    lows = np.minimum(opens, closes) - rng.uniform(0.2, 1.0, len(closes)) * wick
    index = pd.DatetimeIndex([T0 + (i + 1) * H4 for i in range(len(closes))])
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes}, index=index)


def trend(n: int = 600, slope: float = 0.0008, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(1.1 + slope * np.arange(n) + rng.normal(0, 0.0012, n).cumsum() * 0.2, seed=seed)


def sideways(n: int = 600, seed: int = 2) -> pd.DataFrame:
    """Mean-reverting closes (AR(1) around a level): no swings long enough to trend."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.6 * x[i - 1] + rng.normal(0, 0.0015)
    return frame(1.1 + x, seed=seed)


class TestStates:
    def test_an_uptrend_is_up_and_a_downtrend_down(self) -> None:
        assert state_frame(trend(), P)["state"].iloc[-1] == MapState.UP
        assert state_frame(trend(slope=-0.0008), P)["state"].iloc[-1] == MapState.DOWN

    def test_a_sideways_market_is_a_range_with_a_box(self) -> None:
        candles = sideways()
        states = state_frame(candles, P)
        assert (states["state"].iloc[300:] == MapState.RANGE).mean() > 0.6
        pos = int(np.flatnonzero(states["state"].to_numpy() == MapState.RANGE.value)[-1])
        m = timeframe_map("H4", candles, states, pos, P)
        assert m.state is MapState.RANGE and m.box is not None
        assert m.box.low < m.close < m.box.high and m.box.width_atr > 0

    def test_warm_up_is_unknown(self) -> None:
        assert state_frame(trend(), P)["state"].iloc[10] == MapState.UNKNOWN

    def test_hysteresis_ignores_a_single_bar(self) -> None:
        raw = ["UP", "UP", "RANGE", "UP", "RANGE", "RANGE", "RANGE"]
        assert _hysteresis(raw, 2) == ["UP", "UP", "UP", "UP", "UP", "RANGE", "RANGE"]

    def test_compression_after_a_volatile_stretch(self) -> None:
        rng = np.random.default_rng(3)
        wild = 1.1 + rng.normal(0, 0.004, 400).cumsum() * 0.3
        quiet = wild[-1] + rng.normal(0, 0.00005, 150).cumsum()
        candles = frame(np.concatenate([wild, quiet]), wick=0.0)
        candles["high"] = (
            candles[["open", "close"]].max(axis=1) + np.r_[np.full(400, 0.003), np.full(150, 0.00005)]
        )
        candles["low"] = (
            candles[["open", "close"]].min(axis=1) - np.r_[np.full(400, 0.003), np.full(150, 0.00005)]
        )
        compression = state_frame(candles, P)["compression"]
        assert bool(compression.iloc[430])  # early in the quiet stretch
        assert not bool(compression.iloc[300])  # inside the volatile stretch

    def test_efficiency_ratio_of_a_straight_line_is_one(self) -> None:
        er = efficiency_ratio(pd.Series(np.arange(50, dtype=float)), 10)
        assert er.iloc[-1] == pytest.approx(1.0)


class TestNoLookAhead:
    def test_future_bars_never_change_past_states_or_zones(self) -> None:
        a = trend(500)
        b = a.copy()
        b.iloc[400:, :] = b.iloc[400:, :] * 1.07
        sa, sb = state_frame(a, P), state_frame(b, P)
        pd.testing.assert_frame_equal(sa.iloc[:400], sb.iloc[:400])
        assert zones_at(a, sa, 399, P) == zones_at(b, sb, 399, P)


class TestZones:
    def test_a_base_before_a_rally_is_demand_until_a_close_below_it(self) -> None:
        flat = 1.1 + np.random.default_rng(4).normal(0, 0.0003, 257)
        base = np.full(3, flat[-1])  # three tight bars
        rally = flat[-1] + np.linspace(0.002, 0.03, 6)
        hold = rally[-1] + np.random.default_rng(5).normal(0, 0.0005, 40)
        candles = frame(np.concatenate([flat, base, rally, hold]), wick=0.0002)
        tight = slice(257, 260)
        candles.iloc[tight, candles.columns.get_loc("high")] = flat[-1] + 0.00005
        candles.iloc[tight, candles.columns.get_loc("low")] = flat[-1] - 0.00005
        candles.iloc[tight, candles.columns.get_loc("open")] = flat[-1]
        states = state_frame(candles, P)
        zones = zones_at(candles, states, len(candles) - 1, P)
        demand = [z for z in zones if z.source is ZoneSource.BASE and z.kind is ZoneKind.DEMAND]
        assert demand and demand[0].high <= flat[-1] + 0.0001 and demand[0].strength >= 1
        crash = frame(np.full(5, demand[0].low - 0.01), wick=0.0002)
        crash.index = crash.index + (candles.index[-1] - crash.index[0]) + H4
        broken = pd.concat([candles, crash])
        after = zones_at(broken, state_frame(broken, P), len(broken) - 1, P)
        assert all(not (z.source is ZoneSource.BASE and z.low == demand[0].low) for z in after)

    def test_swing_zones_below_are_demand_and_above_supply(self) -> None:
        candles = sideways()
        states = state_frame(candles, P)
        zones = zones_at(candles, states, len(candles) - 1, P)
        close = float(candles["close"].iloc[-1])
        swing = [z for z in zones if z.source is ZoneSource.SWING]
        assert swing and all(z.strength >= P.min_touches for z in swing)
        assert all(z.kind is ZoneKind.DEMAND for z in swing if z.high < close)
        assert all(z.kind is ZoneKind.SUPPLY for z in swing if z.low > close)


def tf_map(state: MapState, zones: tuple[MapZone, ...] = (), box: RangeBox | None = None) -> TimeframeMap:
    return TimeframeMap("H4", T0, state, state, 25.0, 0.4, 0.0050, 1.1000, False, box, zones)


def zone(kind: ZoneKind, low: float, high: float, strength: int = 3) -> MapZone:
    return MapZone(kind, ZoneSource.SWING, low, high, strength, 0, T0)


class TestSignalFeatures:
    def test_trend_sign_follows_the_side(self) -> None:
        up = MarketMap({"H4": tf_map(MapState.UP)})
        buy = signal_features(up, buy=True, entry=1.1, stop=1.09, target=1.13)
        sell = signal_features(up, buy=False, entry=1.1, stop=1.11, target=1.07)
        assert (buy["ctx:h4_trend"], sell["ctx:h4_trend"], buy["ctx:h4_range"]) == (1.0, -1.0, 0.0)

    def test_zone_with_room_and_a_zone_before_the_target(self) -> None:
        zones = (zone(ZoneKind.DEMAND, 1.0990, 1.1005, 4), zone(ZoneKind.SUPPLY, 1.1150, 1.1170))
        m = MarketMap({"H4": tf_map(MapState.RANGE, zones)})
        f = signal_features(m, buy=True, entry=1.1000, stop=1.0950, target=1.1200)
        assert f["ctx:h4_zone_with"] == 1.0 and f["ctx:h4_zone_with_strength"] == 4.0
        assert f["ctx:h4_room_r"] == pytest.approx(0.0150 / 0.0050)
        assert f["ctx:h4_zone_before_tp"] == 1.0
        far = signal_features(m, buy=True, entry=1.1000, stop=1.0950, target=1.1100)
        assert far["ctx:h4_zone_before_tp"] == 0.0

    def test_range_position_is_measured_from_the_favourable_edge(self) -> None:
        box = RangeBox(1.12, 1.10, 4.0, 2, 2)
        m = MarketMap({"H4": tf_map(MapState.RANGE, box=box)})
        assert signal_features(m, buy=True, entry=1.105, stop=1.10, target=1.12)["ctx:h4_range_pos"] == 0.25
        assert signal_features(m, buy=False, entry=1.105, stop=1.11, target=1.10)["ctx:h4_range_pos"] == 0.75

    def test_no_opposing_zone_gives_the_capped_room(self) -> None:
        m = MarketMap({"H4": tf_map(MapState.UP)})
        f = signal_features(m, buy=True, entry=1.1, stop=1.09, target=1.13)
        assert f["ctx:h4_room_r"] == MarketMap().room_cap_r and f["ctx:h4_zone_with"] == 0.0


def test_the_map_round_trips_through_a_dict() -> None:
    zones = (zone(ZoneKind.DEMAND, 1.0990, 1.1005, 4),)
    m = MarketMap({"H4": tf_map(MapState.RANGE, zones, RangeBox(1.12, 1.10, 4.0, 2, 3))}, 0.3, 8.0)
    assert MarketMap.from_dict(m.to_dict()) == m


def test_the_map_carries_the_ema_and_its_slope_at_runtime_only() -> None:
    import numpy as np
    import pandas as pd

    from app.indicators.market_map import MapParams, MarketMap, state_frame, timeframe_map

    idx = pd.date_range("2026-01-01", periods=120, freq="4h", tz="UTC")
    close = pd.Series(np.linspace(100.0, 160.0, 120), index=idx)
    candles = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close})
    p = MapParams()
    states = state_frame(candles, p)
    m = timeframe_map("H4", candles, states, len(candles) - 1, p)
    assert m.ema_mid is not None and m.ema_mid < m.close  # a steady rise: the close above its EMA
    expected = states["ema_mid"].iloc[-1] - states["ema_mid"].iloc[-1 - p.ema_slope_bars]
    assert m.ema_slope is not None and abs(m.ema_slope - expected) < 1e-9 and m.ema_slope > 0
    stored = MarketMap({"H4": m}).to_dict()["frames"]["H4"]
    assert "ema_mid" not in stored and "ema_slope" not in stored  # digests and stored maps unchanged
