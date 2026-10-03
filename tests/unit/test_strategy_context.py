from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.config import AppConfig, RegimeConfig
from app.core.clock import ManualClock
from app.core.enums import Regime, Session, Timeframe, Trend, VolatilityState
from app.core.errors import DataQualityError, InsufficientDataError
from app.market_data.data_models import Quote
from app.strategy.context_builder import (
    FRAME_COLUMNS,
    ContextBuilder,
    analyze_frame,
    context_at,
    trading_session,
)
from app.strategy.regime_detector import (
    classify_regime,
    classify_trend,
    classify_volatility,
    regime_series,
    trend_series,
    volatility_series,
)
from tests.strategy_data import StubCandles, analyzed, random_m15, resample, upto

CFG = AppConfig()
P = RegimeConfig()
NAN = float("nan")


@pytest.fixture(scope="module")
def m15() -> pd.DataFrame:
    return random_m15(1600)


@pytest.fixture(scope="module")
def frames(m15: pd.DataFrame) -> dict[Timeframe, pd.DataFrame]:
    return {Timeframe.M15: m15, Timeframe.H1: resample(m15, Timeframe.H1)}


def build_at(frames: dict[Timeframe, pd.DataFrame], t: datetime):  # type: ignore[no-untyped-def]
    return context_at(
        analyzed(frames, CFG),
        symbol="EURUSD",
        entry_timeframe=Timeframe.M15,
        higher_timeframe=Timeframe.H1,
        decision_time=t,
        now_utc=t + timedelta(seconds=5),
        params=CFG.indicators,
    )


class TestRegimeDetector:
    @pytest.mark.parametrize(
        ("adx", "pct", "expected"),
        [
            (25.0, 50.0, Regime.TRENDING),
            (20.0, 50.0, Regime.TRENDING),
            (19.0, 50.0, Regime.UNCLEAR),
            (17.9, 50.0, Regime.RANGING),
            (30.0, 95.0, Regime.VOLATILE),  # volatility wins over trend strength
            (NAN, 50.0, Regime.UNCLEAR),
            (25.0, NAN, Regime.UNCLEAR),
            (None, 50.0, Regime.UNCLEAR),
        ],
    )
    def test_regime(self, adx: float | None, pct: float, expected: Regime) -> None:
        assert classify_regime(adx, pct, P) is expected

    @pytest.mark.parametrize(
        ("pct", "expected"),
        [
            (10.0, VolatilityState.LOW),
            (50.0, VolatilityState.NORMAL),
            (80.0, VolatilityState.HIGH),
            (95.0, VolatilityState.EXTREME),
            (NAN, VolatilityState.NORMAL),
        ],
    )
    def test_volatility(self, pct: float, expected: VolatilityState) -> None:
        assert classify_volatility(pct, P) is expected

    @pytest.mark.parametrize(
        ("close", "mid", "slow", "expected"),
        [
            (1.2, 1.15, 1.1, Trend.BULLISH),
            (1.0, 1.05, 1.1, Trend.BEARISH),
            (1.2, 1.05, 1.1, Trend.NEUTRAL),  # close above, mid below: no alignment
            (NAN, 1.15, 1.1, Trend.NEUTRAL),
        ],
    )
    def test_trend(self, close: float, mid: float, slow: float, expected: Trend) -> None:
        assert classify_trend(close, mid, slow) is expected

    def test_vectorized_matches_scalar(self) -> None:
        rng = np.random.default_rng(1)
        n = 400
        adx_v = np.where(rng.random(n) < 0.1, np.nan, rng.uniform(5, 40, n))
        pct = np.where(rng.random(n) < 0.1, np.nan, rng.uniform(0, 100, n))
        close, mid, slow = rng.uniform(1, 2, (3, n))
        close[::17] = np.nan
        reg, vol = regime_series(adx_v, pct, P), volatility_series(pct, P)
        tr = trend_series(close, mid, slow)
        for i in range(n):
            assert reg[i] == classify_regime(adx_v[i], pct[i], P).value
            assert vol[i] == classify_volatility(pct[i], P).value
            assert tr[i] == classify_trend(close[i], mid[i], slow[i]).value

    def test_config_ordering_is_validated(self) -> None:
        with pytest.raises(ValueError, match="range_adx"):
            RegimeConfig(trend_adx=18, range_adx=20)
        with pytest.raises(ValueError, match="percentile"):
            RegimeConfig(low_atr_percentile=80, high_atr_percentile=75)


class TestAnalyzeFrame:
    def test_columns_and_index(self, m15: pd.DataFrame) -> None:
        a = analyze_frame(m15, Timeframe.M15, CFG.indicators, CFG.regime)
        assert tuple(a.df.columns) == FRAME_COLUMNS
        assert str(a.df.index.tz) == "UTC"
        assert a.df.index[0] == m15["close_time"].iloc[0]
        assert all(s.confirm_pos < len(a.df) for s in a.swings)

    def test_naive_times_are_rejected(self, m15: pd.DataFrame) -> None:
        bad = m15.assign(close_time=m15["close_time"].dt.tz_localize(None))
        with pytest.raises(DataQualityError):
            analyze_frame(bad, Timeframe.M15, CFG.indicators, CFG.regime)

    def test_unsorted_rows_are_rejected(self, m15: pd.DataFrame) -> None:
        with pytest.raises(DataQualityError):
            analyze_frame(m15.iloc[::-1], Timeframe.M15, CFG.indicators, CFG.regime)


class TestAlignment:
    def test_forming_htf_bar_is_not_used(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        t = datetime(2026, 9, 15, 10, 15, tzinfo=UTC)  # the 10:00-11:00 H1 bar is still forming
        ctx = build_at(frames, t)
        assert ctx.market.bar_times[Timeframe.M15] == t
        assert ctx.market.bar_times[Timeframe.H1] == datetime(2026, 9, 15, 10, 0, tzinfo=UTC)
        assert ctx.frame(Timeframe.H1).index[-1] == pd.Timestamp("2026-09-15 10:00", tz="UTC")

    def test_htf_bar_closing_at_decision_time_is_used(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        t = datetime(2026, 9, 15, 11, 0, tzinfo=UTC)
        assert build_at(frames, t).market.bar_times[Timeframe.H1] == t

    def test_decision_time_must_be_an_entry_bar_close(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        with pytest.raises(DataQualityError):
            build_at(frames, datetime(2026, 9, 15, 10, 20, tzinfo=UTC))

    def test_missing_htf_history_is_insufficient(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        early = datetime(2026, 9, 1, 0, 30, tzinfo=UTC)  # before the first H1 bar closes
        with pytest.raises(InsufficientDataError):
            build_at(frames, early)

    def test_stale_htf_is_flagged(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        t = datetime(2026, 9, 15, 10, 15, tzinfo=UTC)
        stale = {**frames, Timeframe.H1: upto(frames[Timeframe.H1], t - timedelta(hours=3))}
        flags = build_at(stale, t).market.quality_flags
        assert "H1:ALIGNMENT_LAG:3" in flags

    def test_states_and_levels(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        ctx = build_at(frames, datetime(2026, 9, 15, 10, 15, tzinfo=UTC))
        m = ctx.market
        assert m.entry.atr is not None and m.entry.atr > 0
        assert m.higher.adx is not None
        assert all(lv < m.entry.close for lv in m.support_levels)
        assert all(lv > m.entry.close for lv in m.resistance_levels)
        assert list(m.support_levels) == sorted(m.support_levels, reverse=True)
        assert m.session is Session.LONDON


class TestNoLookAhead:
    @pytest.mark.parametrize("hours", [80, 150, 251, 333])
    def test_future_bars_never_change_the_context(
        self, frames: dict[Timeframe, pd.DataFrame], m15: pd.DataFrame, hours: int
    ) -> None:
        t = datetime(2026, 9, 1, tzinfo=UTC) + timedelta(hours=hours, minutes=15 * (hours % 4))
        full = build_at(frames, t)
        # what a live fetch at t would have returned
        cut = build_at({tf: upto(df, t) for tf, df in frames.items()}, t)
        # an unrelated future
        future = m15.copy()
        later = future["close_time"] > pd.Timestamp(t)
        future.loc[later, ["open", "high", "low", "close"]] *= 1.3
        mutated = build_at({Timeframe.M15: future, Timeframe.H1: resample(future, Timeframe.H1)}, t)
        assert full.market.to_json() == cut.market.to_json() == mutated.market.to_json()
        for tf in (Timeframe.M15, Timeframe.H1):
            pd.testing.assert_frame_equal(full.frame(tf), cut.frame(tf))
            pd.testing.assert_frame_equal(full.frame(tf), mutated.frame(tf))


class TestTradingSession:
    @pytest.mark.parametrize(
        ("at", "expected"),
        [
            (datetime(2026, 9, 30, 2, 0, tzinfo=UTC), Session.ASIA),  # Tokyo 11:00
            (datetime(2026, 9, 30, 9, 0, tzinfo=UTC), Session.LONDON),  # London 10:00 BST
            (datetime(2026, 9, 30, 13, 0, tzinfo=UTC), Session.LONDON_NY_OVERLAP),  # NY 09:00 EDT
            (datetime(2026, 9, 30, 18, 0, tzinfo=UTC), Session.NEW_YORK),
            (datetime(2026, 9, 30, 22, 0, tzinfo=UTC), Session.OFF),
            (datetime(2026, 10, 3, 12, 0, tzinfo=UTC), Session.OFF),  # Saturday
            (datetime(2026, 11, 4, 7, 30, tzinfo=UTC), Session.ASIA),  # London opens 08:00 GMT in winter
        ],
    )
    def test_sessions_follow_local_hours(self, at: datetime, expected: Session) -> None:
        assert trading_session(at) is expected


class TestContextBuilder:
    def test_build_fetches_each_timeframe_and_logs(
        self, frames: dict[Timeframe, pd.DataFrame], caplog: pytest.LogCaptureFixture
    ) -> None:
        now = datetime(2026, 9, 15, 10, 20, tzinfo=UTC)
        source = StubCandles(frames, now)

        class Quotes:
            def quote(self, spec: object) -> Quote:
                return Quote("EURUSD", 1.1, 1.10008, 8.0, now, 1.0, True)

        builder = ContextBuilder(source, CFG, ManualClock(now), Quotes())
        with caplog.at_level(logging.INFO, logger="app.strategy.context_builder"):
            ctx = builder.build("EURUSD", spec=object())  # type: ignore[arg-type]
        assert {(tf, count) for _, tf, count in source.calls} == {
            (Timeframe.H1, CFG.timeframes.warmup_bars),
            (Timeframe.M15, CFG.timeframes.warmup_bars),
        }
        assert ctx.decision_time_utc == datetime(2026, 9, 15, 10, 15, tzinfo=UTC)
        assert ctx.now_utc == now
        assert ctx.market.spread_points == 8.0
        lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("analysis")]
        assert any("tf=H1" in line for line in lines)
        assert any("tf=M15" in line for line in lines)

    def test_no_entry_bars_is_insufficient(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        now = datetime(2026, 8, 1, tzinfo=UTC)
        builder = ContextBuilder(StubCandles(frames, now), CFG, ManualClock(now))
        with pytest.raises(InsufficientDataError):
            builder.build("EURUSD")
