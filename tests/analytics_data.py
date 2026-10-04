"""Factories for trade-analytics tests: backtest trades, paper rows, shadow rows and decision contexts."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

from app.analytics.trade_builder import Costs, EntryContext, Scope, Trade
from app.core.enums import ExitReason, Regime, Session, Side, Timeframe, Trend, VolatilityState
from app.execution.simulated_broker import ClosedTrade
from app.storage.models import PaperIntentRow, PaperPositionRow, ShadowTradeRow
from app.strategy.signal_models import MarketContext, TimeframeState

T0 = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)  # Wednesday, London session


def closed_trade(**kw: Any) -> ClosedTrade:
    """A BUY EURUSD 0.1 lot: entry 1.1000, initial stop 1.0950 (risk 0.0050), TP 1.1100 hit (+2R gross)."""
    base: dict[str, Any] = {
        "ticket": 7,
        "symbol": "EURUSD",
        "side": Side.BUY,
        "volume": 0.1,
        "entry_time": T0,
        "entry_price": 1.1000,
        "exit_time": T0 + timedelta(hours=5),
        "exit_price": 1.1100,
        "exit_reason": ExitReason.TAKE_PROFIT,
        "sl_initial": 1.0950,
        "tp_initial": 1.1100,
        "profit": 100.0,
        "commission": -0.7,
        "swap": -0.3,
        "mae": 0.0020,
        "mfe": 0.0100,
        "risk_money": 50.0,
        "strategy": "setup_fib_pullback",
        "signal_id": "sig-1",
        "magic": 7_310_000,
    }
    base.update(kw)
    return ClosedTrade(**base)


def intent_row(**kw: Any) -> PaperIntentRow:
    base: dict[str, Any] = {
        "intent_id": "intent-1",
        "account_key": "paper",
        "idempotency_key": "key:0",
        "decision_id": "dec-1",
        "signal_id": "sig-1",
        "strategy": "setup_fib_pullback",
        "symbol": "EURUSD",
        "side": "BUY",
        "volume": 0.1,
        "entry_type": "MARKET",
        "price": None,
        "sl": 1.0950,
        "tp": 1.1100,
        "expires_at": None,
        "magic": 7_310_000,
        "risk_money": 50.0,
        "order_id": 1,
        "ticket": 2,
        "status": "FILLED",
        "detail": "",
        "created_at": T0,
        "updated_at": T0,
    }
    base.update(kw)
    return PaperIntentRow(**base)


def position_row(**kw: Any) -> PaperPositionRow:
    """A closed paper position whose stop was moved to break-even before it was hit."""
    base: dict[str, Any] = {
        "ticket": 2,
        "account_key": "paper",
        "intent_id": "intent-1",
        "symbol": "EURUSD",
        "side": "BUY",
        "volume": 0.1,
        "entry_time": T0,
        "entry_price": 1.1000,
        "sl": 1.1000,
        "tp": 1.1100,
        "stop_kind": "BE",
        "commission": -0.7,
        "swap": 0.0,
        "mae": 0.0010,
        "mfe": 0.0060,
        "price_current": 1.0999,
        "status": "CLOSED",
        "exit_time": T0 + timedelta(hours=3),
        "exit_price": 1.0999,
        "exit_reason": "BE",
        "profit": -1.0,
        "net": -1.7,
        "r_multiple": -1.7 / 50.0,
        "updated_at": T0,
        "bars_held": 12,
    }
    base.update(kw)
    return PaperPositionRow(**base)


def shadow_row(**kw: Any) -> ShadowTradeRow:
    """A CLOSED PLAN shadow BUY: quote 1.1000/1.1002, slippage 0.00001, risk 0.0050, TP at +2R, 0.1 lot."""
    base: dict[str, Any] = {
        "shadow_id": "opp-1:PLAN",
        "opportunity_id": "opp-1",
        "variant": "PLAN",
        "source": "LIVE",
        "server": "FBS-Demo",
        "strategy": "setup_breakout",
        "symbol": "EURUSD",
        "asset_class": "FOREX_MAJOR",
        "timeframe": "M15",
        "side": "BUY",
        "session": "LONDON",
        "setup_strength": 70.0,
        "rr": 2.0,
        "features": {"ctx:regime=TRENDING": 1.0, "ctx:session=LONDON": 1.0, "ctx:htf_aligned": 1.0},
        "atr": 0.0030,
        "alerted": True,
        "followed": False,
        "status": "CLOSED",
        "signal_at": T0,
        "created_at": T0,
        "updated_at": T0,
        "entry_at": T0,
        "entry_price": 1.10021,
        "bid": 1.1000,
        "ask": 1.1002,
        "spread_points": 20.0,
        "slippage_points": 1.0,
        "initial_sl": 1.09521,
        "sl": 1.09521,
        "tp": 1.11021,
        "stop_kind": "SL",
        "deadline": T0 + timedelta(hours=72),
        "cursor": T0 + timedelta(hours=6),
        "lot": 0.1,
        "equity": 10_000.0,
        "currency": "USD",
        "mae": 0.0010,
        "mfe": 0.0100,
        "exit_at": T0 + timedelta(hours=6),
        "exit_price": 1.11021,
        "exit_reason": "TP",
        "win": True,
        "r_multiple": 2.0,
        "r_net": 1.986,
        "mae_r": 0.2,
        "mfe_r": 2.0,
        "gross_pnl": 100.0,
        "commission": -0.7,
        "swap": 0.0,
        "net_pnl": 99.3,
        "risk_money": 50.0,
        "swap_days": 0,
        "flags": [],
        "note": "",
    }
    base.update(kw)
    return ShadowTradeRow(**base)


def market_dict(
    *,
    htf_trend: Trend = Trend.BULLISH,
    regime: Regime = Regime.TRENDING,
    support: tuple[float, ...] = (1.0940, 1.0960),
    resistance: tuple[float, ...] = (1.1060, 1.1090),
) -> dict[str, Any]:
    """A decision record's ``market`` JSON at T0 (entry M15, higher H1)."""
    entry = TimeframeState(
        Timeframe.M15,
        T0,
        1.1000,
        Trend.BULLISH,
        regime,
        VolatilityState.NORMAL,
        atr=0.0020,
        atr_percentile=55.0,
        adx=21.0,
    )
    higher = TimeframeState(
        Timeframe.H1,
        T0,
        1.1000,
        htf_trend,
        Regime.RANGING,
        VolatilityState.HIGH,
        atr=0.0040,
        atr_percentile=80.0,
        adx=27.0,
    )
    ctx = MarketContext(
        symbol="EURUSD",
        decision_time_utc=T0,
        entry_timeframe=Timeframe.M15,
        higher_timeframe=Timeframe.H1,
        states=(entry, higher),
        session=Session.LONDON,
        bid=1.1000,
        ask=1.1002,
        spread_points=20.0,
        support_levels=support,
        resistance_levels=resistance,
    )
    return ctx.to_dict()


def trade(**kw: Any) -> Trade:
    """A BACKTEST trade record built directly (attribution and style tests): +2R TP BUY, risk 0.0050."""
    base = Trade(
        trade_id="BACKTEST:1",
        scope=Scope.BACKTEST,
        symbol="EURUSD",
        side=Side.BUY,
        strategy="setup_fib_pullback",
        signal_id="sig-1",
        volume=0.1,
        entry_time=T0,
        entry_price=1.1000,
        exit_time=T0 + timedelta(hours=5),
        exit_price=1.1100,
        exit_reason=ExitReason.TAKE_PROFIT,
        initial_sl=1.0950,
        initial_tp=1.1100,
        stop_at_exit=None,
        risk_money=50.0,
        gross_pnl=100.0,
        net_pnl=99.0,
        r_multiple=1.98,
        costs=Costs(spread=2.0, slippage=0.0, commission=0.7, swap=0.3),
        cost_r=0.06,
        slippage_price=0.0,
        mae=0.0010,
        mfe=0.0100,
        bars_held=20,
        context=EntryContext(timeframe=Timeframe.M15),
    )
    return dataclasses.replace(base, **kw)
