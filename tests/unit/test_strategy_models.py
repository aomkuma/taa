from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.core.enums import Action, EntryType, Regime, Session, Side, Timeframe, Trend, VolatilityState
from app.evidence.framework import ActiveEvidence, Direction, Evidence, Family, KeyLevel, Tier
from app.strategy.signal_models import (
    Condition,
    MarketContext,
    Relation,
    Signal,
    SignalError,
    SignalEvidence,
    StrategyContext,
    TimeframeState,
    condition_strength,
    idempotency_key,
)

BAR = datetime(2026, 9, 30, 10, 15, tzinfo=UTC)


def evidence_item(direction: Direction = Direction.BULL) -> ActiveEvidence:
    ev = Evidence(
        detector_id="fib.golden_zone",
        detector_version=1,
        family=Family.FIBONACCI,
        tier=Tier.T1,
        name="Golden zone",
        i18n_key="evidence.fib.golden_zone",
        symbol="EURUSD",
        timeframe=Timeframe.M15,
        direction=direction,
        detected_at=BAR,
        quality=0.8,
        key_levels=(KeyLevel("fib_61.8", 1.1, BAR - timedelta(hours=2)),),
        invalidation=1.09,
        targets=(1.12,),
        details=(("ratio", 0.618),),
    )
    return ActiveEvidence(ev, BAR, 0)


def make_signal(**overrides: object) -> Signal:
    base: dict[str, object] = {
        "signal_id": "sig-1",
        "strategy": "example_trend_pullback",
        "strategy_version": "1.0.0",
        "symbol": "EURUSD",
        "timeframe": Timeframe.M15,
        "action": Action.BUY,
        "data_timestamp_utc": BAR,
        "created_at_utc": BAR + timedelta(seconds=4),
        "expires_at_utc": BAR + timedelta(minutes=15),
        "entry_type": EntryType.MARKET,
        "entry_price": 1.1000,
        "stop_loss": 1.0980,
        "take_profit": 1.1040,
        "score": 72.5,
        "setup_strength": 80.0,
        "conditions": (Condition("htf_bias", True, 2.0, "close > EMA200"), Condition("rsi_cross", False)),
        "evidence": (
            SignalEvidence(evidence_item(), Relation.SUPPORTS),
            SignalEvidence(evidence_item(Direction.BEAR), Relation.CONFLICTS),
        ),
        "reason_codes": ("TREND_PULLBACK",),
        "explanation": "H1 bullish bias; M15 pullback to EMA20",
        "bar_times": ((Timeframe.M15, BAR), (Timeframe.H1, BAR - timedelta(minutes=15))),
    }
    base.update(overrides)
    return Signal(**base)  # type: ignore[arg-type]


def state(tf: Timeframe, close_at: datetime, **kw: object) -> TimeframeState:
    base: dict[str, object] = {
        "timeframe": tf,
        "bar_close_utc": close_at,
        "close": 1.1,
        "trend": Trend.BULLISH,
        "regime": Regime.TRENDING,
        "volatility": VolatilityState.NORMAL,
        "structure": "UP",
        "atr": 0.001,
        "atr_percentile": 55.0,
        "adx": 24.0,
        "plus_di": 30.0,
        "minus_di": 12.0,
        "rsi": 56.0,
        "ema_fast": 1.099,
        "ema_mid": 1.098,
        "ema_slow": 1.095,
    }
    base.update(kw)
    return TimeframeState(**base)  # type: ignore[arg-type]


def make_context(**overrides: object) -> MarketContext:
    base: dict[str, object] = {
        "symbol": "EURUSD",
        "decision_time_utc": BAR,
        "entry_timeframe": Timeframe.M15,
        "higher_timeframe": Timeframe.H1,
        "states": (state(Timeframe.M15, BAR), state(Timeframe.H1, BAR - timedelta(minutes=15))),
        "session": Session.LONDON,
        "bid": 1.1,
        "ask": 1.10008,
        "spread_points": 8.0,
        "quote_time_utc": BAR + timedelta(seconds=3),
        "quality_flags": ("SHORT_HISTORY:390/400",),
        "support_levels": (1.095,),
        "resistance_levels": (1.105, 1.11),
    }
    base.update(overrides)
    return MarketContext(**base)  # type: ignore[arg-type]


class TestCondition:
    def test_strength_is_weighted_share(self) -> None:
        conds = [Condition("a", True, 3.0), Condition("b", False, 1.0)]
        assert condition_strength(conds) == pytest.approx(75.0)
        assert condition_strength([]) == 0.0

    @pytest.mark.parametrize("weight", [0.0, -1.0, float("nan")])
    def test_weight_must_be_positive(self, weight: float) -> None:
        with pytest.raises(SignalError):
            Condition("a", True, weight)


class TestSignal:
    def test_round_trip_is_exact(self) -> None:
        sig = make_signal()
        text = sig.to_json()
        back = Signal.from_json(text)
        assert back == sig
        assert back.to_json() == text

    def test_json_is_canonical(self) -> None:
        text = make_signal().to_json()
        assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))

    def test_idempotency_key_ignores_ids_and_prices(self) -> None:
        a = make_signal()
        b = make_signal(signal_id="other", entry_price=1.2, created_at_utc=BAR + timedelta(minutes=1))
        assert a.idempotency_key == b.idempotency_key
        assert a.idempotency_key == idempotency_key(a.strategy, "EURUSD", Timeframe.M15, BAR, Action.BUY)
        assert make_signal(action=Action.SELL).idempotency_key != a.idempotency_key
        later = make_signal(
            data_timestamp_utc=BAR + timedelta(minutes=15), expires_at_utc=BAR + timedelta(hours=1)
        )
        assert later.idempotency_key != a.idempotency_key

    def test_tampered_record_is_rejected(self) -> None:
        d = make_signal().to_dict()
        d["action"] = "SELL"
        with pytest.raises(SignalError, match="altered"):
            Signal.from_dict(d)

    def test_derived_values(self) -> None:
        sig = make_signal()
        assert sig.side is Side.BUY
        assert sig.risk_reward == pytest.approx(2.0)
        assert len(sig.supporting) == 1
        assert len(sig.conflicting) == 1
        assert not sig.is_expired(BAR + timedelta(minutes=14))
        assert sig.is_expired(BAR + timedelta(minutes=15))
        assert sig.bar_times[0][0] is Timeframe.H1  # longest timeframe first

    def test_hold_has_no_side_or_rr(self) -> None:
        hold = make_signal(action=Action.HOLD, entry_price=None, stop_loss=None, take_profit=None)
        assert hold.side is None
        assert hold.risk_reward is None
        assert Signal.from_json(hold.to_json()) == hold

    def test_geometry_is_left_to_the_decision_engine(self) -> None:
        # a stop on the wrong side is a market outcome reported as SL_WRONG_SIDE, not a model error
        sig = make_signal(stop_loss=1.2)
        assert sig.risk_distance == pytest.approx(0.1)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"score": 101.0},
            {"setup_strength": -1.0},
            {"entry_price": float("nan")},
            {"expires_at_utc": BAR},
            {"action": Action.CLOSE},
            {"signal_id": ""},
            {"data_timestamp_utc": datetime(2026, 9, 30, 10, 15)},
        ],
    )
    def test_malformed_values_are_rejected(self, overrides: dict[str, object]) -> None:
        with pytest.raises((SignalError, ValueError)):
            make_signal(**overrides)

    def test_is_immutable(self) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            make_signal().score = 1.0  # type: ignore[misc]


class TestMarketContext:
    def test_round_trip_is_exact(self) -> None:
        ctx = make_context()
        back = MarketContext.from_json(ctx.to_json())
        assert back == ctx
        assert back.digest == ctx.digest

    def test_derived_views(self) -> None:
        ctx = make_context()
        assert ctx.trend is Trend.BULLISH
        assert ctx.regime is Regime.TRENDING
        assert ctx.adx == 24.0
        assert ctx.atr == 0.001
        assert ctx.states[0].timeframe is Timeframe.H1
        assert ctx.bar_times == {Timeframe.H1: BAR - timedelta(minutes=15), Timeframe.M15: BAR}

    def test_future_bar_is_rejected(self) -> None:
        with pytest.raises(SignalError, match="look-ahead"):
            make_context(states=(state(Timeframe.M15, BAR), state(Timeframe.H1, BAR + timedelta(minutes=45))))

    def test_missing_timeframe_is_rejected(self) -> None:
        with pytest.raises(SignalError, match="lacks"):
            make_context(states=(state(Timeframe.M15, BAR),))

    def test_nan_indicator_is_rejected(self) -> None:
        with pytest.raises(SignalError):
            state(Timeframe.M15, BAR, adx=float("nan"))


class TestStrategyContext:
    def frame(self, end: datetime) -> pd.DataFrame:
        idx = pd.date_range(end=end, periods=3, freq="15min")
        return pd.DataFrame({"close": [1.0, 1.1, 1.2]}, index=idx)

    def test_frames_are_read_only_mapping(self) -> None:
        sctx = StrategyContext(make_context(), {Timeframe.M15: self.frame(BAR)}, BAR + timedelta(seconds=4))
        assert sctx.symbol == "EURUSD"
        with pytest.raises(TypeError):
            sctx.frames[Timeframe.H1] = self.frame(BAR)  # type: ignore[index]
        with pytest.raises(SignalError):
            sctx.frame(Timeframe.H1)

    def test_frame_past_decision_time_is_rejected(self) -> None:
        with pytest.raises(SignalError, match="look-ahead"):
            StrategyContext(make_context(), {Timeframe.M15: self.frame(BAR + timedelta(minutes=15))}, BAR)
