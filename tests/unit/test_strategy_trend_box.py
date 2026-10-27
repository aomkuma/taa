"""Hand-worked tests for trend boxes: prices are deliberately small and all bar closes are UTC-aware."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.core.enums import Action, Side, Timeframe
from app.strategy import trend_box as module
from app.strategy.signal_models import MarketContext, OpenPosition, StrategyContext
from app.strategy.trend_box import TrendBoxDown, TrendBoxUp, running_push_exceeded, stepped
from app.strategy.zigzag import Swing
from tests.unit.test_strategy_models import state

AT = datetime(2026, 10, 27, 0, 5, tzinfo=UTC)  # 07:05 Bangkok, inside Asia window


def context(*, low: float = 99.5) -> StrategyContext:
    m5idx = pd.date_range(AT - timedelta(minutes=120), AT, freq="5min", tz="UTC")
    m5 = pd.DataFrame({"open": 105.0, "high": 110.0, "low": 100.0, "close": 105.0}, index=m5idx)
    m5.iloc[-1, m5.columns.get_loc("high")] = 111.0
    m5.iloc[-1, m5.columns.get_loc("low")] = 98.0
    m5.iloc[-1, m5.columns.get_loc("close")] = 99.0
    m1idx = pd.date_range(AT - timedelta(minutes=60), AT, freq="1min", tz="UTC")
    m1 = pd.DataFrame({"high": 100.0, "low": low, "close": 99.5, "open": 99.5}, index=m1idx)
    h1idx = pd.date_range(end=AT, periods=1200, freq="1h", tz="UTC")
    h1 = pd.DataFrame({"high": 150.0, "low": 50.0, "close": 100.0, "open": 100.0}, index=h1idx)
    market = MarketContext(
        symbol="XAUUSD",
        decision_time_utc=AT,
        entry_timeframe=Timeframe.M5,
        higher_timeframe=Timeframe.H1,
        states=(state(Timeframe.M5, AT), state(Timeframe.H1, AT)),
    )
    return StrategyContext(
        market,
        {Timeframe.M1: m1, Timeframe.M5: m5, Timeframe.H1: h1},
        AT + timedelta(seconds=3),
    )


def down_swings() -> list[Swing]:
    return [Swing(10, 140.0, 1), Swing(20, 90.0, -1), Swing(30, 130.0, 1), Swing(40, 70.0, -1)]


def up_swings(retr: float = 0.5) -> list[Swing]:
    b = 2048 + retr * 2048
    return [Swing(10, 400, -1), Swing(20, b - 5, 1), Swing(30, b - 2048, -1), Swing(40, b, 1)]


def up_context() -> StrategyContext:
    ctx = context()
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[:-1, m5.columns.get_loc("high")] = 2080.0
    m5.iloc[:-1, m5.columns.get_loc("low")] = 2016.0
    m5.iloc[-1, m5.columns.get_loc("high")] = 2081.0
    m5.iloc[-1, m5.columns.get_loc("low")] = 2079.0
    m5.iloc[-1, m5.columns.get_loc("close")] = 2080.1
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["high"] = 2080.1
    return StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5, Timeframe.M1: m1}, ctx.now_utc)


def test_stepping_requires_both_swing_kinds_to_agree():
    assert stepped(down_swings()) == "DOWN"
    assert stepped([Swing(1, 100, 1), Swing(2, 70, -1), Swing(3, 110, 1), Swing(4, 80, -1)]) == "UP"
    assert stepped([Swing(1, 100, 1), Swing(2, 90, -1), Swing(3, 110, 1), Swing(4, 80, -1)]) == "FLAT"
    assert stepped([Swing(1, 140, 1), Swing(2, 70, -1), Swing(3, 130, 1), Swing(4, 80, -1)]) == "FLAT"


def test_windows_follow_bangkok_and_new_york_local_time():
    assert module.in_window(pd.Timestamp(AT))  # 07:05 Bangkok
    assert module.in_window(pd.Timestamp("2026-10-27 06:05Z"))  # 13:05 Bangkok
    assert module.in_window(pd.Timestamp("2026-10-27 12:05Z"))  # 08:05 New York, still daylight time
    assert module.in_window(pd.Timestamp("2026-11-03 13:05Z"))  # 08:05 New York after daylight time ends
    assert not module.in_window(pd.Timestamp("2026-10-27 04:00Z"))


def test_strategy_frames_are_only_m1_m5_and_h1():
    assert TrendBoxDown().required_timeframes() == (Timeframe.M1, Timeframe.M5, Timeframe.H1)
    assert TrendBoxUp().required_timeframes() == (Timeframe.M1, Timeframe.M5, Timeframe.H1)


def test_down_entry_uses_box_before_decision_bar_and_exact_plan(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (down_swings(), Swing(41, 151, 1)))
    got = TrendBoxDown().evaluate(context())
    # The 24 prior M5 bars have top 110 / floor 100; the decision bar's 111 / 98 wick is excluded.
    assert (got.action, got.entry_price, got.stop_loss, got.take_profit) == (Action.SELL, 99.0, 112.0, 70.0)
    assert "24 bars" in next(c.detail for c in got.conditions if c.name == "box")


def test_up_entry_mirrors_trend_leg_and_stop_plan(monkeypatch: pytest.MonkeyPatch):
    up = [Swing(10, 50.0, -1), Swing(20, 120.0, 1), Swing(30, 60.0, -1), Swing(40, 130.0, 1)]
    monkeypatch.setattr(module, "zigzag", lambda *_args: (up, None))
    ctx = context()
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[:-1, m5.columns.get_loc("high")] = 100.0
    m5.iloc[:-1, m5.columns.get_loc("low")] = 90.0
    m5.iloc[-1, m5.columns.get_loc("high")] = 102.0
    m5.iloc[-1, m5.columns.get_loc("low")] = 99.0
    m5.iloc[-1, m5.columns.get_loc("close")] = 101.0
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["high"] = 101.0
    ctx = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5, Timeframe.M1: m1}, ctx.now_utc)
    got = TrendBoxUp().evaluate(ctx)
    # Leg 60->130 (70 USD), box 100/90, entry 101; SL=90-2=88 and target=130.
    assert (got.action, got.entry_price, got.stop_loss, got.take_profit) == (Action.BUY, 101.0, 88.0, 130.0)


@pytest.mark.parametrize(
    ("retr", "should_enter"),
    [(0.382, True), (0.786, True), (0.381, False), (0.787, False)],
)
def test_up_retrace_bounds_are_inclusive(retr: float, should_enter: bool, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (up_swings(retr), None))
    assert TrendBoxUp().evaluate(up_context()).action.is_entry is should_enter


def test_up_box_and_close_trigger_gates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (up_swings(), None))
    ctx = up_context()
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[-1, m5.columns.get_loc("close")] = 2079.9  # The wick is above top; the close is not.
    wick_only = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5}, ctx.now_utc)
    assert TrendBoxUp().evaluate(wick_only).action is Action.HOLD
    m5.iloc[:-1, m5.columns.get_loc("high")] = 2800.0  # 784 USD > .33 x 2,048 USD leg.
    too_tall = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5}, ctx.now_utc)
    assert TrendBoxUp().evaluate(too_tall).action is Action.HOLD


def test_up_run_and_reward_risk_gates_reject(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (up_swings(), None))
    ctx = up_context()
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["high"] = 2180.0  # Run 99.9 USD > 1.2 x the 76.9 USD initial risk.
    running = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M1: m1}, ctx.now_utc)
    assert TrendBoxUp().evaluate(running).action is Action.HOLD
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[-1, m5.columns.get_loc("close")] = 3071.0  # Reward 1, risk 1,067.8: below 1.2 R.
    m1["high"] = 3071.0
    weak = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5, Timeframe.M1: m1}, ctx.now_utc)
    assert TrendBoxUp().evaluate(weak).action is Action.HOLD


@pytest.mark.parametrize(
    ("retr", "should_enter"),
    [(0.382, True), (0.786, True), (0.381, False), (0.787, False)],
)
def test_retrace_bounds_are_inclusive(retr: float, should_enter: bool, monkeypatch: pytest.MonkeyPatch):
    # For top/floor 105/104, choose B so (104.5-B)/(120-B) equals the tested retrace.
    b = (104.5 - 120 * retr) / (1 - retr)
    swings = [Swing(10, 140, 1), Swing(20, b + 5, -1), Swing(30, 120, 1), Swing(40, b, -1)]
    monkeypatch.setattr(module, "zigzag", lambda *_args: (swings, None))
    ctx = context()
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[:-1, m5.columns.get_loc("high")] = 105.0
    m5.iloc[:-1, m5.columns.get_loc("low")] = 104.0
    m5.iloc[-1, m5.columns.get_loc("close")] = 103.9
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["low"] = 103.9
    ctx = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5, Timeframe.M1: m1}, ctx.now_utc)
    got = TrendBoxDown().evaluate(ctx)
    assert got.action.is_entry is should_enter


def test_wick_only_break_and_running_push_hold(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (down_swings(), None))
    ctx = context()
    frame = ctx.frame(Timeframe.M5).copy()
    frame.iloc[-1, frame.columns.get_loc("close")] = 101.0  # wick low remains 98, close is inside box
    no_close = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: frame}, ctx.now_utc)
    assert TrendBoxDown().evaluate(no_close).action is Action.HOLD
    assert TrendBoxDown().evaluate(context(low=80.0)).action is Action.HOLD  # 19 USD run > 1.2 x 13 risk


def test_run_threshold_is_strict_and_uses_the_preceding_sixty_minutes(monkeypatch: pytest.MonkeyPatch):
    assert not running_push_exceeded(6.0, 5.0)
    assert running_push_exceeded(6.01, 5.0)
    monkeypatch.setattr(module, "zigzag", lambda *_args: (down_swings(), None))
    ctx = context()
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["low"] = 83.4  # 99 - 83.4 = 15.6 = 1.2 x the 13 USD risk: equality passes.
    m1.iloc[-1, m1.columns.get_loc("low")] = 1.0  # at the decision timestamp; excluded from the run window
    ctx = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M1: m1}, ctx.now_utc)
    assert TrendBoxDown().evaluate(ctx).action.is_entry
    m1.iloc[0, m1.columns.get_loc("low")] = 83.39  # exactly 60 minutes old; included
    just_over = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M1: m1}, ctx.now_utc)
    assert TrendBoxDown().evaluate(just_over).action is Action.HOLD


def test_too_tall_box_and_close_equal_to_floor_hold(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (down_swings(), None))
    ctx = context()
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[:-1, m5.columns.get_loc("high")] = 120.0  # 20 USD > .2 x 60 USD leg
    tall = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5}, ctx.now_utc)
    assert TrendBoxDown().evaluate(tall).action is Action.HOLD
    m5.iloc[:-1, m5.columns.get_loc("high")] = 110.0
    m5.iloc[-1, m5.columns.get_loc("close")] = 100.0  # close is at, not below, floor
    equal_floor = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5}, ctx.now_utc)
    assert TrendBoxDown().evaluate(equal_floor).action is Action.HOLD


def test_weak_reward_to_risk_holds(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (down_swings(), None))
    ctx = context()
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[-1, m5.columns.get_loc("close")] = 80.0
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["low"] = 80.0  # No running push; only the reward/risk gate can reject this candidate.
    rejected = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5, Timeframe.M1: m1}, ctx.now_utc)
    assert TrendBoxDown().evaluate(rejected).action is Action.HOLD


def test_longest_fitting_box_is_not_replaced_after_retrace_failure(monkeypatch: pytest.MonkeyPatch):
    # The 24-bar box is 117/105, exactly 12 USD tall; its retrace is .85 and must stop the search.
    # Removing its oldest bar leaves a 106/105 box with a valid .758 retrace that must not be tried.
    swings = [Swing(10, 140, 1), Swing(20, 90, -1), Swing(30, 120, 1), Swing(40, 60, -1)]
    monkeypatch.setattr(module, "zigzag", lambda *_args: (swings, None))
    ctx = context()
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[:-1, m5.columns.get_loc("high")] = 106.0
    m5.iloc[:-1, m5.columns.get_loc("low")] = 105.0
    m5.iloc[0, m5.columns.get_loc("high")] = 117.0
    m5.iloc[0, m5.columns.get_loc("low")] = 105.0
    m5.iloc[-1, m5.columns.get_loc("close")] = 104.0
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["low"] = 104.0
    ctx = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5, Timeframe.M1: m1}, ctx.now_utc)
    assert TrendBoxDown().evaluate(ctx).action is Action.HOLD


def test_up_break_even_waits_for_touch_then_moves_to_entry():
    strat = TrendBoxUp()
    pos = OpenPosition(Side.BUY, 100, 90, 90, 120, AT - timedelta(minutes=10))
    ctx = context()
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["high"] = 104.9
    before = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M1: m1}, ctx.now_utc)
    assert strat.manage_position(before, pos) is None
    m1.iloc[-1, m1.columns.get_loc("high")] = 105.0
    reached = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M1: m1}, ctx.now_utc)
    advice = strat.manage_position(reached, pos)
    assert advice is not None and advice.new_sl == 100


def test_original_stop_is_checked_before_same_bar_break_even_touch():
    strat = TrendBoxUp()
    pos = OpenPosition(Side.BUY, 100, 90, 90, 120, AT - timedelta(minutes=10))
    ctx = context()
    m1 = ctx.frame(Timeframe.M1).copy()
    m1.iloc[-1, m1.columns.get_loc("high")] = 105.0
    m1.iloc[-1, m1.columns.get_loc("low")] = 90.0
    same_bar = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M1: m1}, ctx.now_utc)
    assert strat.manage_position(same_bar, pos) is None


def test_break_even_never_replaces_a_better_stop():
    strat = TrendBoxUp()
    pos = OpenPosition(Side.BUY, 100, 90, 101, 120, AT - timedelta(minutes=10))
    ctx = context()
    m1 = ctx.frame(Timeframe.M1).copy()
    m1["high"], m1["low"] = 105.0, 102.0
    advanced = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M1: m1}, ctx.now_utc)
    assert strat.manage_position(advanced, pos) is None


def test_daily_flat_is_at_seven_thai():
    strat = TrendBoxDown()
    at = datetime(2026, 10, 27, 0, 0, tzinfo=UTC)
    market = MarketContext(
        symbol="XAUUSD",
        decision_time_utc=at,
        entry_timeframe=Timeframe.M5,
        higher_timeframe=Timeframe.H1,
        states=(state(Timeframe.M5, at), state(Timeframe.H1, at)),
    )
    ctx = StrategyContext(market, {}, at + timedelta(seconds=3))
    assert strat.should_close(ctx, Side.SELL)


def test_a_box_taller_than_the_cap_is_not_a_box(monkeypatch: pytest.MonkeyPatch):
    # Found in review 2026-10-27: removing the `box * leg` cap left every test green. The leg is 130 -> 70, so
    # 60; the cap is 0.2 x 60 = 12. Widen the 24 bars before the decision to 110 - 97 = 13 and no window fits,
    # while the decision bar still closes under the floor - so only the cap can be refusing.
    monkeypatch.setattr(module, "zigzag", lambda *_args: (down_swings(), Swing(41, 151, 1)))
    ctx = context()
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.iloc[:-1, m5.columns.get_loc("low")] = 97.0
    m5.iloc[-1, m5.columns.get_loc("close")] = 96.0  # through the 97 floor: the trigger is satisfied
    m5.iloc[-1, m5.columns.get_loc("low")] = 95.0
    wide = StrategyContext(ctx.market, {**ctx.frames, Timeframe.M5: m5}, ctx.now_utc)
    assert TrendBoxDown().evaluate(wide).action is Action.HOLD
    # the same bars with the cap raised to 0.3 x 60 = 18 do enter, so it was the cap that refused
    got = TrendBoxDown(TrendBoxDown.Params(box=0.3)).evaluate(wide)
    assert (got.action, got.entry_price, got.take_profit) == (Action.SELL, 96.0, 70.0)
    assert got.stop_loss == pytest.approx(110 + 0.2 * 13)
