"""The AI trader lane strategy (app/strategy/ai_lane.py, TAA-1806): an AI order waits for its price on quotes,
is dropped when its stop comes first or its time runs out, becomes an ordinary signal with the AI's reasons, and an
EXIT closes the lane's position. Hand-worked cases on gold-like prices."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.core.enums import Action, ExitReason, Side, Timeframe
from app.strategy import ai_lane as lane
from app.strategy.ai_lane import AIEntry, AIOrder, AITrader
from app.strategy.signal_models import OpenPosition, StrategyContext
from tests.unit.test_strategy_models import make_context

T0 = datetime(2026, 10, 23, 14, 48, tzinfo=UTC)
# the touch mechanics, read without the signal at the level (tested in its own tests below)
NOCONF = AITrader.Params(confirm_entries=False)


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
    s = AITrader(NOCONF)
    s.accept("XAUUSD", order())
    assert s.busy(T0) is True
    # the first bid 4,003.9 is 1.1 under the entry (beyond the 1.0 tolerance): a sell LIMIT, it fills at its
    # price or better - the bid at or above 4,005.0, not within the tolerance (owner 2026-10-25, ISSUES 14)
    assert s.on_quote("XAUUSD", T0 + timedelta(minutes=1), 4003.9, 4004.3) is None
    assert s.on_quote("XAUUSD", T0 + timedelta(minutes=2), 4004.9, 4005.3) is None
    got = s.on_quote("XAUUSD", T0 + timedelta(minutes=3), 4005.0, 4005.4)
    assert got is not None
    assert (got.price, got.side, got.at) == (4005.0, Side.SELL, T0 + timedelta(minutes=3))
    assert s.pending("XAUUSD") is None  # filled once
    assert s.busy(T0) is False


def test_a_buy_waits_until_the_ask_reaches_the_entry():
    s = AITrader(NOCONF)
    s.accept("XAUUSD", order(side=Side.BUY, entry=3995.0, stop=3987.0, target=4020.0))
    assert s.on_quote("XAUUSD", T0, 3995.8, 3996.1) is None  # 1.1 above: a buy limit at 3,995.0
    assert s.on_quote("XAUUSD", T0, 3995.6, 3996.0) is None  # within the tolerance is not at the limit
    got = s.on_quote("XAUUSD", T0, 3994.6, 3995.0)
    assert got is not None
    assert got.price == 3995.0


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
    # the take-profit 10 % short of the AI's 3,977.00 from the fill 4,004.20: 3,977.00 + 27.20 x 0.10
    assert (sig.entry_price, sig.stop_loss) == (4004.2, 4013.0)
    assert sig.take_profit == pytest.approx(3979.72)
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
    pos = OpenPosition(Side.SELL, 4004.2, 4013.0, 4013.0, 3977.0, T0 - timedelta(minutes=61))  # time stop
    assert s.manage_position(ctx(4000.0, 4000.4), pos) is None
    s.request_exit("XAUUSD")
    advice = s.manage_position(ctx(4000.0, 4000.4), pos)
    assert advice is not None
    assert advice.close is ExitReason.SIGNAL
    assert s.manage_position(ctx(4000.0, 4000.4), pos) is None


def test_an_exit_asked_with_nothing_open_does_not_close_the_next_trade():
    # 2026-07-07 replay: EXIT at 13:26 with nothing open; the 16:36 sell was closed at its first management
    s = AITrader(NOCONF)
    s.request_exit("XAUUSD")
    s.accept("XAUUSD", order())  # a new order: the old exit no longer applies
    pos = OpenPosition(Side.SELL, 4004.2, 4013.0, 4013.0, 3977.0, T0)
    assert s.manage_position(ctx(4000.0, 4000.4), pos) is None
    b = AITrader(NOCONF)
    b.accept("XAUUSD", order(direct=True))  # a BUY / SELL decision near price: a market order
    b.request_exit("XAUUSD")  # an exit while the order still waits
    assert b.on_quote("XAUUSD", T0, 4004.5, 4004.9) is not None  # it fills
    assert b.manage_position(ctx(4000.0, 4000.4), pos) is None  # the fill cleared the exit


def test_the_take_profit_sits_short_of_the_target_on_both_sides():
    b = order(side=Side.BUY, entry=3995.0, stop=3987.0, target=4020.0)
    sig = AITrader().entry_signal(ctx(3995.6, 3996.0), AIEntry(b, T0, 3996.0))
    assert sig is not None and sig.take_profit == pytest.approx(
        4017.6
    )  # 4020.00 - (4020.00 - 3996.00) x 0.10
    untrimmed = AITrader(AITrader.Params(target_trim=0.0)).entry_signal(
        ctx(3995.6, 3996.0), AIEntry(b, T0, 3996.0)
    )
    assert untrimmed is not None and untrimmed.take_profit == 4020.0
    no_target = AITrader().entry_signal(ctx(4004.2, 4004.6), AIEntry(order(target=None), T0, 4004.2))
    assert no_target is not None and no_target.take_profit is None


def test_the_trim_never_brings_the_take_profit_under_the_floor():
    # owner 2026-10-25 (C5): a 5.4 USD target trimmed 10 % would be 4.86 away; the floor keeps 5.00
    b = order(side=Side.BUY, entry=3995.0, stop=3987.0, target=4001.4)
    p = AITrader.Params(min_take_profit=5.0)
    sig = AITrader(p).entry_signal(ctx(3995.6, 3996.0), AIEntry(b, T0, 3996.0))
    assert sig is not None and sig.take_profit == pytest.approx(4001.0)  # 3996.00 + 5.00
    far = order(side=Side.BUY, entry=3995.0, stop=3987.0, target=4020.0)
    sig = AITrader(p).entry_signal(ctx(3995.6, 3996.0), AIEntry(far, T0, 3996.0))
    assert sig is not None and sig.take_profit == pytest.approx(4017.6)  # 21.6 > 5: the plain trim
    near = order(side=Side.SELL, entry=4004.0, stop=4012.0, target=4000.0)  # 4.2 away: the target itself
    sig = AITrader(p).entry_signal(ctx(4004.2, 4004.6), AIEntry(near, T0, 4004.2))
    assert sig is not None and sig.take_profit == pytest.approx(4000.0)


class TestOrderKinds:
    """Owner 2026-10-25: 'a limit order or a stop order, as the situation needs, with an expiry'."""

    def test_a_sell_above_the_price_is_a_limit_it_fills_when_price_rises_to_it(self) -> None:
        s = AITrader(NOCONF)
        s.accept("XAUUSD", order(entry=4005.0, stop=4013.0, key="k1"))
        assert s.on_quote("XAUUSD", T0, 4000.0, 4000.4) is None  # 5 under: waits
        assert s.kind_of(order(key="k1"), 4000.0, 4000.4) == "limit"
        assert s.on_quote("XAUUSD", T0 + timedelta(minutes=2), 4004.2, 4004.6) is None  # within 1.0: not yet
        e = s.on_quote("XAUUSD", T0 + timedelta(minutes=3), 4005.0, 4005.4)  # at the limit
        assert e is not None and e.price == 4005.0

    def test_a_sell_below_the_price_is_a_stop_it_fills_when_price_breaks_down_to_it(self) -> None:
        s = AITrader(NOCONF)
        s.accept("XAUUSD", order(entry=3995.0, stop=4004.0, target=3980.0, key="k2"))
        assert s.on_quote("XAUUSD", T0, 4000.0, 4000.4) is None  # 5 above the entry: a stop, not a fill
        assert s.on_quote("XAUUSD", T0 + timedelta(minutes=1), 3995.5, 3995.9) is None  # not broken yet
        e = s.on_quote("XAUUSD", T0 + timedelta(minutes=2), 3994.9, 3995.3)
        assert e is not None and e.price == 3994.9

    def test_a_buy_above_the_price_is_a_stop_and_a_buy_below_a_limit(self) -> None:
        s = AITrader(NOCONF)
        s.accept("XAUUSD", order(side=Side.BUY, entry=4006.0, stop=3998.0, target=4020.0, key="k3"))
        assert s.on_quote("XAUUSD", T0, 4000.0, 4000.4) is None
        e = s.on_quote("XAUUSD", T0 + timedelta(minutes=1), 4005.8, 4006.2)  # the ask breaks up to 4,006
        assert e is not None and e.price == 4006.2
        b = AITrader(NOCONF)
        b.accept("XAUUSD", order(side=Side.BUY, entry=3995.0, stop=3988.0, target=4010.0, key="k4"))
        assert b.on_quote("XAUUSD", T0, 4000.0, 4000.4) is None
        assert b.on_quote("XAUUSD", T0 + timedelta(minutes=1), 3995.5, 3995.9) is None  # within 1.0: not yet
        assert b.on_quote("XAUUSD", T0 + timedelta(minutes=2), 3994.6, 3995.0) is not None  # at the limit

    def test_an_order_expires_and_its_stop_first_drops_it(self) -> None:
        s = AITrader()
        s.accept("XAUUSD", order(entry=4005.0, key="k5", valid_until=T0 + timedelta(minutes=10)))
        assert s.on_quote("XAUUSD", T0 + timedelta(minutes=11), 4005.0, 4005.4) is None  # expired
        assert s.pending("XAUUSD") is None


def test_the_plan_s_orders_wait_and_the_first_fill_withdraws_the_others() -> None:
    s = AITrader(NOCONF)
    sell = order(entry=4005.0, stop=4013.0, key="plan-A")
    buy = order(side=Side.BUY, entry=3990.0, stop=3982.0, target=4000.0, key="plan-B")
    s.set_plan_orders("XAUUSD", [sell, buy])
    assert s.on_quote("XAUUSD", T0, 3998.0, 3998.4) is None and len(s.plan_orders("XAUUSD")) == 2
    assert s.busy(T0)
    e = s.on_quote("XAUUSD", T0 + timedelta(minutes=5), 3989.6, 3990.0)  # the buy limit fills at 3,990
    assert e is not None and e.order.key == "plan-B"
    assert s.plan_orders("XAUUSD") == []  # the sell withdrawn: one trade at a time


def test_an_expired_order_is_not_waiting_any_more() -> None:
    # ISSUES 25: the 07-06 sell expired at 20:53 still showed as waiting at 22:37 (no quote had dropped it)
    s = AITrader()
    s.accept("XAUUSD", order(valid_until=T0 + timedelta(minutes=30)))
    assert s.pending("XAUUSD", T0 + timedelta(minutes=10)) is not None
    assert s.pending("XAUUSD", T0 + timedelta(minutes=31)) is None
    assert s.pending("XAUUSD") is None  # dropped for good


def test_a_side_the_rules_stop_is_withdrawn_from_the_plan() -> None:
    s = AITrader()
    sell = order(key="plan-A")
    buy = order(side=Side.BUY, entry=3990.0, stop=3982.0, target=4000.0, key="plan-B")
    s.set_plan_orders("XAUUSD", [sell, buy])
    s.drop_plan_side("XAUUSD", Side.BUY)
    assert [o.key for o in s.plan_orders("XAUUSD")] == ["plan-A"]


def m1_frame(closes: list[float], end: datetime) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=len(closes), freq="1min", tz="UTC")  # bar close times
    return pd.DataFrame({"close": closes}, index=idx)


def test_an_early_exit_needs_three_m5_closes_back_across_the_entry():
    # ISSUES 28 (07-07): three AI exits cut sells that then reached their take-profit; C6 decides
    pos = OpenPosition(Side.SELL, 4004.2, 4013.0, 4013.0, 3977.0, T0 - timedelta(minutes=20))
    p = AITrader.Params()
    under = m1_frame([4003.0] * 15, T0)  # every M5 close under the entry: the sell holds
    assert lane.exit_allowed(under, pos, T0, p) is None
    two = m1_frame([4003.0] * 5 + [4005.0] * 10, T0)  # only two M5 closes over it
    assert lane.exit_allowed(two, pos, T0, p) is None
    three = m1_frame([4005.0] * 15, T0)  # three M5 closes over the entry: the failed break
    assert lane.exit_allowed(three, pos, T0, p) == "3 M5 closes back across 4004.20 (C6)"
    assert lane.exit_allowed(None, pos, T0 + timedelta(minutes=40), p) == "the time stop, 60 min held"
    # M1 closes 14:42 .. 14:48 = 1 .. 7: the M5 bar to 14:45 closes at 4; the one to 14:50 is still forming
    assert lane.m5_closes(m1_frame([1.0, 2, 3, 4, 5, 6, 7], T0), 2) == [4.0]


def test_c6_counts_closes_back_across_the_level_the_trade_is_built_on():
    # ISSUES 32 (07-08 14:46): the sell broke the range bottom 4,010 at 4,004.2; three M5 closes at 4,005 are
    # over the entry but still under the broken bottom - the break has not failed; closes at 4,011 are back in
    pos = OpenPosition(Side.SELL, 4004.2, 4013.0, 4013.0, 3977.0, T0 - timedelta(minutes=20))
    p = AITrader.Params()
    back_over_entry = m1_frame([4005.0] * 15, T0)
    assert lane.exit_allowed(back_over_entry, pos, T0, p, 4010.0) is None
    assert lane.exit_allowed(back_over_entry, pos, T0, p) == "3 M5 closes back across 4004.20 (C6)"
    back_in = m1_frame([4011.0] * 15, T0)
    assert lane.exit_allowed(back_in, pos, T0, p, 4010.0) == "3 M5 closes back across 4010.00 (C6)"
    # a buy broke a range top 3,990 at 3,995: closes at 3,992 hold; at 3,989 the break failed
    buy = OpenPosition(Side.BUY, 3995.0, 3986.0, 3986.0, 4010.0, T0 - timedelta(minutes=20))
    assert lane.exit_allowed(m1_frame([3992.0] * 15, T0), buy, T0, p, 3990.0) is None
    assert lane.exit_allowed(m1_frame([3989.0] * 15, T0), buy, T0, p, 3990.0) is not None


def test_the_filled_order_s_level_is_the_one_c6_uses():
    s = AITrader(NOCONF)
    s.accept("XAUUSD", order(exit_level=4010.0))
    assert s.on_quote("XAUUSD", T0, 4005.0, 4005.4) is not None
    assert s._levels["XAUUSD"] == 4010.0
    s.set_plan_orders("XAUUSD", [order(key="plan-A", entry=4006.0)])  # a plan order: its entry (no level)
    assert s.on_quote("XAUUSD", T0, 4006.0, 4006.4) is not None
    assert s._levels["XAUUSD"] == 4006.0
    # the strategy hands the level to C6: closes at 4,007 over it end the plan sell
    pos = OpenPosition(Side.SELL, 4006.0, 4013.0, 4013.0, 3977.0, T0 - timedelta(minutes=20))
    c = StrategyContext(
        market=make_context(symbol="XAUUSD", bid=4005.0, ask=4005.4, decision_time_utc=T0),
        frames={Timeframe.M1: m1_frame([4007.0] * 15, T0 - timedelta(minutes=1))},
        now_utc=T0,
    )
    s.request_exit("XAUUSD")
    advice = s.manage_position(c, pos)
    assert advice is not None and "across 4006.00" in advice.note


def test_the_plan_s_stops_are_rechecked_against_the_map_now():
    # ISSUES 33 (07-08 13:16): a plan order checked only when the plan was written filled 16 short of the zone
    s = AITrader(AITrader.Params(min_take_profit=5.0))
    sell = order(key="plan-A", entry=4005.0, stop=4013.0, target=3977.0)  # reward 28
    buy = order(key="plan-B", side=Side.BUY, entry=3990.0, stop=3982.0, target=4000.0)  # reward 10
    s.set_plan_orders("XAUUSD", [sell, buy])
    s.recheck_plan_stops("XAUUSD", {"SELL": 4010.0, "BUY": None})  # already past / no map stop: unchanged
    assert [(o.key, o.stop) for o in s.plan_orders("XAUUSD")] == [("plan-A", 4013.0), ("plan-B", 3982.0)]
    # the sell's map stop 4,020: moved out (risk 15, 28 >= 0.2 x 15); the buy's 3,975: risk 15, 10 >= 3
    s.recheck_plan_stops("XAUUSD", {"SELL": 4020.0, "BUY": 3975.0})
    assert [(o.key, o.stop) for o in s.plan_orders("XAUUSD")] == [("plan-A", 4020.0), ("plan-B", 3975.0)]
    # a map stop 4,145: risk 140, 0.2 x 140 = 28 <= 28 - kept; 4,145.5: 28.1 > 28 - withdrawn
    s.set_plan_orders("XAUUSD", [sell])
    s.recheck_plan_stops("XAUUSD", {"SELL": 4145.0})
    assert [o.stop for o in s.plan_orders("XAUUSD")] == [4145.0]
    s.set_plan_orders("XAUUSD", [sell])
    s.recheck_plan_stops("XAUUSD", {"SELL": 4145.5})
    assert s.plan_orders("XAUUSD") == []
    # a take-profit under 5 is withdrawn when its stop must move (a buy with a 4-USD target)
    s.set_plan_orders(
        "XAUUSD", [order(key="plan-C", side=Side.BUY, entry=3990.0, stop=3982.0, target=3994.0)]
    )
    s.recheck_plan_stops("XAUUSD", {"BUY": 3980.0})
    assert s.plan_orders("XAUUSD") == []


def m1_bars(start: datetime, highs: list[float], lows: list[float]) -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=len(highs), freq="1min", tz="UTC")  # bar-open times
    return pd.DataFrame({"high": highs, "low": lows}, index=idx)


def test_a_side_is_blocked_after_its_take_profit():
    # ISSUES 30 (07-08): the 08:13 take-profit, then a buy of the same sweep at 08:16. A position gone whose
    # target the bars reached before its stop blocks its side for tp_block_minutes (30) from that bar's close
    t8 = datetime(2026, 7, 8, 1, 0, tzinfo=UTC)
    s = AITrader(NOCONF)
    sell = (Side.SELL, 4005.0, 4013.0, 3995.0, t8)
    bars = m1_bars(t8, [4006.0, 4004.0, 4001.0, 3998.0], [4003.0, 4000.0, 3994.9, 3996.0])
    assert s.note_positions("XAUUSD", [sell], bars) == []  # held: nothing to judge
    until = t8 + timedelta(minutes=33)  # the 01:02 bar (low 3,994.9) closes 01:03, + 30
    assert s.note_positions("XAUUSD", [], bars) == [(Side.SELL, until)]
    assert s.blocked("XAUUSD", Side.SELL, until - timedelta(seconds=1))
    assert not s.blocked("XAUUSD", Side.SELL, until) and not s.blocked("XAUUSD", Side.BUY, t8)
    # a sell order in the block does not fill (it keeps waiting); after it, it does
    at = t8 + timedelta(minutes=10)
    s.accept("XAUUSD", order(entry=4005.0, decided_at=at, valid_until=at + timedelta(minutes=60)))
    assert s.on_quote("XAUUSD", at, 4005.0, 4005.4) is None and s.pending("XAUUSD") is not None
    assert s.on_quote("XAUUSD", until, 4005.0, 4005.4) is not None
    assert s.note_positions("XAUUSD", [], bars) == []  # nothing held last time: nothing new


def test_no_block_when_the_stop_came_first_or_there_was_no_target():
    t8 = datetime(2026, 7, 8, 1, 0, tzinfo=UTC)
    s = AITrader()
    stopped = m1_bars(t8, [4013.0, 4004.0, 4001.0], [4003.0, 4000.0, 3994.0])  # 4,013 at 01:00, 3,994 later
    s.note_positions("XAUUSD", [(Side.SELL, 4005.0, 4013.0, 3995.0, t8)], stopped)
    assert s.note_positions("XAUUSD", [], stopped) == []
    s.note_positions("XAUUSD", [(Side.BUY, 4005.0, 3995.0, None, t8)], stopped)  # no target
    assert s.note_positions("XAUUSD", [], stopped) == []
    early = m1_bars(t8 - timedelta(minutes=2), [4013.0, 4006.0, 4006.0], [3990.0, 4003.0, 4003.0])
    s.note_positions(
        "XAUUSD", [(Side.SELL, 4005.0, 4013.0, 3995.0, t8)], early
    )  # the low came before the fill
    assert s.note_positions("XAUUSD", [], early) == []
    # a buy: 4,015 reached at 01:01 (before its stop 3,990 at 01:02)
    buy = m1_bars(t8, [4006.0, 4015.0, 4000.0], [4003.0, 4004.0, 3990.0])
    s.note_positions("XAUUSD", [(Side.BUY, 4005.0, 3990.0, 4015.0, t8)], buy)
    assert s.note_positions("XAUUSD", [], buy) == [(Side.BUY, t8 + timedelta(minutes=32))]
