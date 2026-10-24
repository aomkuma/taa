"""The AI trader lane strategy (app/strategy/ai_lane.py, TAA-1806): an AI order waits for its price on quotes,
is dropped when its stop comes first or its time runs out, becomes an ordinary signal with the AI's reasons, and an
EXIT closes the lane's position. Hand-worked cases on gold-like prices."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from app.core.enums import Action, ExitReason, Side, Timeframe
from app.strategy.ai_lane import AIEntry, AIOrder, AITrader
from app.strategy.signal_models import OpenPosition, StrategyContext
from tests.unit.test_strategy_models import make_context

T0 = datetime(2026, 10, 23, 14, 48, tzinfo=UTC)


def order(**over: object) -> AIOrder:
    base: dict[str, object] = {
        "side": Side.SELL,
        "entry": 4005.0,
        "stop": 4013.0,
        "target": 3977.0,
        "risk_scale": 0.5,
        "setup": "a lower high under the broken midday support",
        "reasons": ("every frame down", "the bounce stalled under 4,005.6"),
        "kb_ids": ("P19", "L15"),
        "confidence": 66,
        "decided_at": T0,
        "valid_until": T0 + timedelta(minutes=30),
        "key": "step-202610231448",
        "watch_above": 4013.0,
        "watch_below": 3990.0,
    }
    base.update(over)
    return AIOrder(**base)  # type: ignore[arg-type]


def ctx(bid: float, ask: float) -> StrategyContext:
    market = make_context(symbol="XAUUSD", bid=bid, ask=ask)  # the helper's M15 / H1 states
    return StrategyContext(market=market, frames={Timeframe.M15: pd.DataFrame()}, now_utc=T0)


def test_a_sell_waits_until_the_bid_reaches_the_entry():
    s = AITrader()
    s.accept("XAUUSD", order())
    assert s.busy(T0) is True
    # tolerance 1.0: the bid must be at or above 4,004.0
    assert s.on_quote("XAUUSD", T0 + timedelta(minutes=1), 4003.9, 4004.3) is None
    got = s.on_quote("XAUUSD", T0 + timedelta(minutes=2), 4004.0, 4004.4)
    assert got is not None
    assert (got.price, got.side, got.at) == (4004.0, Side.SELL, T0 + timedelta(minutes=2))
    assert s.pending("XAUUSD") is None  # filled once
    assert s.busy(T0) is False


def test_a_buy_waits_until_the_ask_reaches_the_entry():
    s = AITrader()
    s.accept("XAUUSD", order(side=Side.BUY, entry=3995.0, stop=3987.0, target=4020.0))
    assert s.on_quote("XAUUSD", T0, 3995.8, 3996.1) is None  # the ask must be at or under 3,996.0
    got = s.on_quote("XAUUSD", T0, 3995.6, 3996.0)
    assert got is not None
    assert got.price == 3996.0


def test_the_stop_first_drops_the_order():
    s = AITrader()
    s.accept("XAUUSD", order(entry=4010.0))
    assert s.on_quote("XAUUSD", T0, 4012.6, 4013.0) is None  # the ask touched the stop 4,013 before any fill
    assert s.pending("XAUUSD") is None
    b = AITrader()
    b.accept("XAUUSD", order(side=Side.BUY, entry=3990.0, stop=3987.0, target=4010.0))
    assert b.on_quote("XAUUSD", T0, 3987.0, 3987.4) is None  # the bid touched the buy's stop
    assert b.pending("XAUUSD") is None


def test_the_order_expires_and_a_new_one_replaces_it():
    s = AITrader()
    s.accept("XAUUSD", order())
    assert s.on_quote("XAUUSD", T0 + timedelta(minutes=31), 4006.0, 4006.4) is None  # 30 minutes passed
    assert s.pending("XAUUSD") is None
    s.accept("XAUUSD", order(entry=4004.0))
    s.accept("XAUUSD", order(entry=4008.0))
    assert s.pending("XAUUSD").entry == 4008.0  # type: ignore[union-attr]
    s.cancel("XAUUSD")
    assert s.pending("XAUUSD") is None
    assert s.on_quote("XAUUSD", T0, 4008.0, 4008.4) is None


def test_the_signal_carries_the_ais_stop_target_risk_and_reasons():
    s = AITrader()
    o = order()
    sig = s.entry_signal(ctx(4004.2, 4004.6), AIEntry(o, T0, 4004.2))
    assert sig is not None
    assert sig.action is Action.SELL
    assert (sig.entry_price, sig.stop_loss, sig.take_profit) == (4004.2, 4013.0, 3977.0)
    assert sig.risk_scale == 0.5
    assert sig.score == 66.0
    assert sig.strategy == "ai_trader"
    assert sig.explanation == "every frame down | the bounce stalled under 4,005.6"
    assert [(c.name, c.passed, c.detail) for c in sig.conditions] == [
        (
            "ai_decision",
            True,
            "a lower high under the broken midday support (confidence 66, decision step-202610231448)",
        ),
        ("ai_knowledge", True, "P19, L15"),
        ("ai_watch", True, "above 4013.0 / below 3990.0"),
    ]


def test_no_signal_when_the_geometry_broke_or_there_is_no_quote():
    s = AITrader()
    o = order()  # a sell, stop 4,013, target 3,977
    assert s.entry_signal(ctx(4013.5, 4013.9), AIEntry(o, T0, 4013.5)) is None  # price above the stop now
    assert s.entry_signal(ctx(3976.0, 3976.4), AIEntry(o, T0, 3976.0)) is None  # the target already passed
    no_quote = StrategyContext(
        market=make_context(symbol="XAUUSD", bid=None, ask=None), frames={}, now_utc=T0
    )
    assert s.entry_signal(no_quote, AIEntry(o, T0, 4004.0)) is None


def test_geometry_for_both_sides():
    assert order().geometry_ok(4004.0) is True
    assert order(target=None).geometry_ok(4004.0) is True
    b = order(side=Side.BUY, entry=3995.0, stop=3987.0, target=4020.0)
    assert b.geometry_ok(3996.0) is True
    assert b.geometry_ok(3986.0) is False
    assert b.geometry_ok(4021.0) is False


def test_an_exit_closes_the_lanes_position_once():
    s = AITrader()
    pos = OpenPosition(Side.SELL, 4004.2, 4013.0, 4013.0, 3977.0, T0)
    assert s.manage_position(ctx(4000.0, 4000.4), pos) is None
    s.request_exit("XAUUSD")
    advice = s.manage_position(ctx(4000.0, 4000.4), pos)
    assert advice is not None
    assert advice.close is ExitReason.SIGNAL
    assert s.manage_position(ctx(4000.0, 4000.4), pos) is None
