from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.config import AppConfig, load_settings
from app.core.enums import Action, Regime, Timeframe, Trend
from app.core.errors import ConfigError
from app.strategy.catalog import default_registry
from app.strategy.context_builder import context_at
from app.strategy.example_strategy import TrendPullback, TrendPullbackParams
from app.strategy.signal_models import MarketContext, Signal, StrategyContext
from tests.strategy_data import EURUSD_SPEC, analyzed, resample, sawtooth_m15
from tests.unit.test_strategy_models import state

T = datetime(2026, 9, 30, 10, 15, tzinfo=UTC)  # Wednesday, inside the session window
ATR = 0.0010
EMA = 1.1000


def buy_frame(n: int = 30) -> pd.DataFrame:
    """A pullback BUY setup: rising closes, a confirmed swing low at bar 20, then a dip to EMA(fast) and an
    RSI cross back above 50 on the last bar."""
    close = np.linspace(1.1000, 1.1030, n)
    close[-3:] = [1.1008, 1.1004, 1.1012]
    low = close - 0.0005
    low[20] = 1.0990  # swing low, confirmed at bar 23 (k = 3)
    low[-2] = 1.0998  # touches EMA 1.1000
    high = close + 0.0005
    rsi = np.full(n, 60.0)
    rsi[-3:] = [45.0, 47.0, 55.0]
    idx = pd.date_range(end=T, periods=n, freq="15min")
    return pd.DataFrame(
        {
            "high": high,
            "low": low,
            "close": close,
            "ema_fast": np.full(n, EMA),
            "rsi": rsi,
            "atr": np.full(n, ATR),
            "spread": np.full(n, 8.0),
        },
        index=idx,
    )


def mirror(frame: pd.DataFrame) -> pd.DataFrame:
    """The same setup reflected around 1.1 (a SELL)."""
    out = frame.copy()
    out["high"], out["low"] = 2.2 - frame["low"], 2.2 - frame["high"]
    out["close"] = 2.2 - frame["close"]
    out["ema_fast"] = 2.2 - frame["ema_fast"]
    out["rsi"] = 100.0 - frame["rsi"]
    return out


def ctx(
    frame: pd.DataFrame | None = None,
    *,
    at: datetime = T,
    trend: Trend = Trend.BULLISH,
    regime: Regime = Regime.TRENDING,
    adx: float = 25.0,
    spread: float | None = 8.0,
    resistance: tuple[float, ...] = (1.1060,),
    support: tuple[float, ...] = (1.0940,),
    ask: float | None = None,
    spec: object = EURUSD_SPEC,
) -> StrategyContext:
    frame = buy_frame() if frame is None else frame
    frame = frame.set_axis(pd.date_range(end=at, periods=len(frame), freq="15min"))
    close = float(frame["close"].iloc[-1])
    market = MarketContext(
        symbol="EURUSD",
        decision_time_utc=at,
        entry_timeframe=Timeframe.M15,
        higher_timeframe=Timeframe.H1,
        states=(
            state(Timeframe.M15, at, close=close),
            state(Timeframe.H1, at - timedelta(minutes=15), trend=trend, regime=regime, adx=adx),
        ),
        bid=None if ask is None else ask - 0.00008,
        ask=ask,
        spread_points=spread,
        support_levels=support,
        resistance_levels=resistance,
    )
    return StrategyContext(market, {Timeframe.M15: frame}, at + timedelta(seconds=4), spec)  # type: ignore[arg-type]


def evaluate(context: StrategyContext, **params: object) -> Signal:
    return TrendPullback(TrendPullbackParams(**params)).evaluate(context)  # type: ignore[arg-type]


class TestRules:
    def test_buy_setup(self) -> None:
        sig = evaluate(ctx())
        assert sig.action is Action.BUY, sig.explanation
        entry = 1.1012 + 0.00008  # bid-based close plus the spread
        stop = 1.0990 - 0.00008  # swing low (farther than 1.5 ATR) minus the spread buffer
        assert sig.entry_price == pytest.approx(entry)
        assert sig.stop_loss == pytest.approx(stop)
        assert sig.take_profit == pytest.approx(entry + 2 * (entry - stop))
        assert sig.risk_reward == pytest.approx(2.0)
        assert sig.setup_strength == 100.0
        assert 75.0 <= sig.score <= 100.0
        assert sig.reason_codes == ("TREND_PULLBACK", "DEMO_UNPROVEN")
        assert "[x] htf_bias" in sig.explanation
        assert all(c.passed for c in sig.conditions)

    def test_sell_setup_is_the_mirror(self) -> None:
        sell = evaluate(
            ctx(mirror(buy_frame()), trend=Trend.BEARISH, resistance=(1.1060,), support=(1.0940,))
        )
        assert sell.action is Action.SELL, sell.explanation
        assert sell.entry_price == pytest.approx(2.2 - 1.1012)  # SELL enters at the bid (the close)
        assert sell.stop_loss == pytest.approx(2.2 - 1.0990 + 0.00008)
        assert sell.risk_reward == pytest.approx(2.0)

    def test_quote_is_the_entry_when_available(self) -> None:
        assert evaluate(ctx(ask=1.10125)).entry_price == pytest.approx(1.10125)

    def test_atr_stop_when_the_swing_is_closer(self) -> None:
        frame = buy_frame()
        frame.loc[frame.index[20], "low"] = 1.1003  # swing low only 0.9 ATR below the entry
        sig = evaluate(ctx(frame))
        entry = 1.1012 + 0.00008
        assert sig.stop_loss == pytest.approx(entry - 1.5 * ATR - 0.00008)

    @pytest.mark.parametrize(
        ("kw", "params", "reason"),
        [
            ({"trend": Trend.NEUTRAL}, {}, "NO_BIAS"),
            ({"adx": 19.0}, {}, "NO_BIAS"),
            ({"regime": Regime.RANGING}, {}, "REGIME_NOT_TRENDING"),
            ({"regime": Regime.VOLATILE}, {}, "REGIME_NOT_TRENDING"),
            ({"resistance": (1.1018,)}, {}, "NEAR_OPPOSING_LEVEL"),
            ({"spread": 400.0}, {}, "SPREAD_TOO_HIGH"),
            ({"at": datetime(2026, 9, 30, 21, 0, tzinfo=UTC)}, {}, "OUTSIDE_SESSION"),
            (
                {"at": datetime(2026, 10, 2, 19, 0, tzinfo=UTC)},
                {"friday_cutoff_utc": "18:00"},
                "FRIDAY_CUTOFF",
            ),
            ({"at": datetime(2026, 10, 3, 10, 0, tzinfo=UTC)}, {}, "FRIDAY_CUTOFF"),  # Saturday
            ({}, {"max_sl_atr": 2.0}, "SL_TOO_FAR"),
            ({"spec": None}, {}, "INSUFFICIENT_DATA"),
        ],
    )
    def test_filters_hold_with_reason(
        self, kw: dict[str, object], params: dict[str, object], reason: str
    ) -> None:
        sig = evaluate(ctx(**kw), **params)  # type: ignore[arg-type]
        assert sig.action is Action.HOLD
        assert reason in sig.reason_codes, sig.reason_codes

    def test_no_pullback_no_setup(self) -> None:
        frame = buy_frame()
        frame.loc[frame.index[-2], "low"] = 1.1003
        sig = evaluate(ctx(frame))
        assert sig.reason_codes == ("NO_SETUP",)
        assert [c.name for c in sig.conditions if not c.passed] == ["pullback_to_ema"]
        assert sig.setup_strength == pytest.approx(100 * 12 / 13)

    def test_rsi_must_cross_50(self) -> None:
        frame = buy_frame()
        frame.loc[frame.index[-3:-1], "rsi"] = 52.0
        assert evaluate(ctx(frame)).reason_codes == ("NO_SETUP",)

    def test_close_must_be_back_beyond_ema(self) -> None:
        frame = buy_frame()
        frame.loc[frame.index[-1], "close"] = 1.0999
        assert evaluate(ctx(frame)).action is Action.HOLD

    def test_warmup_nan_holds(self) -> None:
        frame = buy_frame()
        frame.loc[frame.index[-1], "atr"] = np.nan
        sig = evaluate(ctx(frame))
        assert sig.reason_codes == ("INSUFFICIENT_DATA",)

    def test_bias_is_exposed_for_management(self) -> None:
        strat = TrendPullback()
        assert strat.bias(ctx()) is Trend.BULLISH
        assert strat.bias(ctx(adx=10.0)) is Trend.NEUTRAL

    def test_signals_round_trip(self) -> None:
        sig = evaluate(ctx())
        assert Signal.from_json(sig.to_json()) == sig

    @pytest.mark.parametrize(
        "params",
        [
            {"rr_target": 1.2},
            {"sl_atr_multiple": 4.0},
            {"session_start_utc": "21:00"},
            {"session_end_utc": "25:00"},
        ],
    )
    def test_incoherent_params_are_rejected(self, params: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            TrendPullbackParams(**params)  # type: ignore[arg-type]


class TestCatalog:
    def test_config_yaml_builds_the_example(self) -> None:
        settings = load_settings(
            env_file=None, config_file="config.yaml", environ={"TRADING_MODE": "BACKTEST"}
        )
        built = default_registry().from_config(settings.config.strategies, settings.config.timeframes)
        assert built.names[0] == "example_trend_pullback" and len(built.names) == 9  # with the 8 setups
        assert built.strategies[0].demo_only

    def test_unknown_param_is_a_config_error(self) -> None:
        cfg = AppConfig.model_validate(
            {"strategies": {"items": [{"name": "example_trend_pullback", "params": {"adx": 5}}]}}
        )
        with pytest.raises(ConfigError):
            default_registry().from_config(cfg.strategies, cfg.timeframes)


def scan(sign: int, **kw: object) -> list[Signal]:
    """Run the strategy bar by bar over a synthetic trend, through the real context builder."""
    cfg = AppConfig()
    m15 = sawtooth_m15(sign=sign, **kw)  # type: ignore[arg-type]
    frames = analyzed({Timeframe.M15: m15, Timeframe.H1: resample(m15, Timeframe.H1)}, cfg)
    strat = TrendPullback()
    out = []
    for t in m15["close_time"].iloc[1000:1450]:
        c = context_at(
            frames,
            symbol="EURUSD",
            entry_timeframe=Timeframe.M15,
            higher_timeframe=Timeframe.H1,
            decision_time=t.to_pydatetime(),
            now_utc=t.to_pydatetime(),
            params=cfg.indicators,
            spec=EURUSD_SPEC,
        )
        out.append(strat.evaluate(c))
    return out


class TestScenarios:
    @pytest.mark.parametrize(("sign", "action"), [(1, Action.BUY), (-1, Action.SELL)])
    def test_trend_with_pullbacks_signals_only_with_the_trend(self, sign: int, action: Action) -> None:
        signals = scan(sign)
        entries = [s for s in signals if s.is_entry]
        assert entries, "the scenario should produce at least one setup"
        assert {s.action for s in entries} == {action}
        for s in entries:
            assert s.stop_loss is not None and s.entry_price is not None and s.take_profit is not None
            assert (s.entry_price - s.stop_loss) * sign > 0
            assert (s.take_profit - s.entry_price) * sign > 0
            assert s.risk_reward == pytest.approx(2.0)
            assert s.data_timestamp_utc.weekday() < 5

    def test_flat_market_never_signals(self) -> None:
        signals = scan(1, up=6, down=6, flat=0, step_up=0.0007, step_down=0.0007)
        assert not [s for s in signals if s.is_entry]
        assert {"NO_BIAS", "REGIME_NOT_TRENDING"} & {r for s in signals for r in s.reason_codes}


def test_signal_fields_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        evaluate(ctx()).stop_loss = None  # type: ignore[misc]
