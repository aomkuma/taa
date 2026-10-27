"""Hand-worked H4 box break cases for the range strategy."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.core.enums import Action, Side, Timeframe
from app.strategy import range_break as module
from app.strategy.range_break import RangeBreak
from app.strategy.signal_models import MarketContext, OpenPosition, StrategyContext
from app.strategy.zigzag import Swing
from tests.unit.test_strategy_models import state

AT = datetime(2026, 10, 27, 0, 5, tzinfo=UTC)


def context(*, prev: float = 100.0, price: float = 101.0, high: float = 101.0, low: float = 99.0):
    m5idx = pd.date_range(end=AT, periods=2, freq="5min", tz="UTC")
    m5 = pd.DataFrame(
        {"open": [prev, price], "high": [prev, high], "low": [prev, low], "close": [prev, price]},
        index=m5idx,
    )
    h1idx = pd.date_range(end=datetime(2026, 10, 27, 0, 0, tzinfo=UTC), periods=1200, freq="1h")
    h1 = pd.DataFrame({"open": 90.0, "high": 100.0, "low": 80.0, "close": 90.0}, index=h1idx)
    m1idx = pd.date_range(AT - timedelta(minutes=60), AT, freq="1min", tz="UTC")
    m1 = pd.DataFrame({"open": 100.0, "high": high, "low": low, "close": price}, index=m1idx)
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


def flat_swings() -> list[Swing]:
    return [Swing(1, 105, 1), Swing(2, 75, -1), Swing(3, 100, 1), Swing(4, 80, -1)]


def test_break_plan_matches_the_calculated_h4_box(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (flat_swings(), Swing(5, 110, 1)))
    got = RangeBreak().evaluate(context())
    # H4 top/floor = 100/80, so rng=20, stop=100 - .3*20*.25=98.5, TP=101 + .5*20=111.
    assert (got.action, got.entry_price, got.stop_loss, got.take_profit) == (Action.BUY, 101.0, 98.5, 111.0)


def test_h4_flat_box_needs_only_one_confirmed_swing_per_side(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: ([Swing(1, 100, 1), Swing(2, 80, -1)], None))
    assert RangeBreak().evaluate(context()).action is Action.BUY


def test_trigger_needs_the_close_to_leave_the_box(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (flat_swings(), None))
    assert RangeBreak().evaluate(context(price=99.5, high=101, low=98)).action is Action.HOLD
    assert RangeBreak().evaluate(context(prev=101, price=101)).action is Action.HOLD


def test_h4_stepping_and_run_gate_reject(monkeypatch: pytest.MonkeyPatch):
    up = [Swing(1, 90, 1), Swing(2, 70, -1), Swing(3, 100, 1), Swing(4, 80, -1)]
    monkeypatch.setattr(module, "zigzag", lambda *_args: (up, None))
    assert RangeBreak().evaluate(context()).action is Action.HOLD
    monkeypatch.setattr(module, "zigzag", lambda *_args: (flat_swings(), None))
    assert RangeBreak().evaluate(context(high=120)).action is Action.HOLD


def test_range_strategy_uses_only_m1_m5_and_h1_frames():
    assert RangeBreak().required_timeframes() == (Timeframe.M1, Timeframe.M5, Timeframe.H1)


def test_range_reward_must_cover_minimum_risk_multiple(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "zigzag", lambda *_args: (flat_swings(), None))
    # Close at 120 after crossing 100: reward=10 but risk=21.5, below the required 0.8 R.
    assert RangeBreak().evaluate(context(price=120, high=120, low=119)).action is Action.HOLD


def test_sell_break_plan_is_the_mirror_and_reward_floor_is_enforced(monkeypatch: pytest.MonkeyPatch):
    down = [Swing(1, 95, 1), Swing(2, 65, -1), Swing(3, 90, 1), Swing(4, 78, -1)]
    monkeypatch.setattr(module, "zigzag", lambda *_args: (down, None))
    got = RangeBreak().evaluate(context(prev=78, price=77, high=78, low=76))
    # The box is 90/78 (range 12): stop 78 + .3*12*.25 = 78.9; target 77 - .5*12 = 71.
    assert (got.action, got.entry_price, got.stop_loss, got.take_profit) == (Action.SELL, 77.0, 78.9, 71.0)
    small_box = [Swing(1, 95, 1), Swing(2, 75, -1), Swing(3, 90, 1), Swing(4, 82, -1)]
    monkeypatch.setattr(module, "zigzag", lambda *_args: (small_box, None))
    # the box is 90/82: a BUY at 91 targets 95, so a reward of 4.00 USD. It passes with the floor off
    # (the default since 2026-10-27) and is refused by a lane that sets one.
    bars = context(prev=90, price=91, high=91, low=90)
    assert RangeBreak().evaluate(bars).action is Action.BUY
    floored = RangeBreak(RangeBreak.Params(min_take_profit=5.0)).evaluate(bars)
    assert floored.action is Action.HOLD


def test_break_even_requires_half_r_touch_then_returns_entry_stop():
    strat = RangeBreak()
    pos = OpenPosition(Side.BUY, 100, 90, 90, 120, AT - timedelta(minutes=10))
    ctx = context(high=104.9, low=101)
    assert strat.manage_position(ctx, pos) is None
    reached = context(high=105, low=101)
    advice = strat.manage_position(reached, pos)
    assert advice is not None and advice.new_sl == 100


def test_h4_resampling_uses_the_h1_four_hour_boundaries():
    idx = pd.DatetimeIndex(
        [
            "2026-10-26 17:00Z",
            "2026-10-26 18:00Z",
            "2026-10-26 19:00Z",
            "2026-10-27 01:00Z",
            "2026-10-27 02:00Z",
        ]
    )
    frame = pd.DataFrame({"open": 1, "high": 2, "low": 0, "close": 1}, index=idx)
    h4 = RangeBreak._h4_from_h1(frame)
    # Shift close times to H1 opens: 20:00 has no H1 data and drops; nonempty partial H4 bins remain.
    assert list(h4.index) == list(pd.to_datetime(["2026-10-26 16:00Z", "2026-10-27 00:00Z"]))


def test_h4_is_built_from_h1_open_times_and_only_from_closed_bars(monkeypatch: pytest.MonkeyPatch):
    # Found in review 2026-10-27: dropping the close-to-open shift, or letting an unclosed H4 bar in, left
    # every test green. App H1 frames are stamped at the close, so an H1 bar stamped 04:00 covers 03:00-04:00
    # and belongs to the 00:00-04:00 H4 bar, not to 04:00-08:00.
    idx = pd.date_range("2026-10-26 01:00", periods=8, freq="1h", tz="UTC")  # closes 01:00 .. 08:00
    h1 = pd.DataFrame({"open": 100.0, "high": [101.0, 102, 103, 104, 105, 106, 107, 108],
                       "low": 99.0, "close": 100.0}, index=idx)  # fmt: skip
    h4 = RangeBreak._h4_from_h1(h1)
    # the shift puts the closes 01:00-04:00 into the 00:00 bar (high 104) and 05:00-08:00 into 04:00 (high 108)
    assert list(h4.index) == [
        pd.Timestamp("2026-10-26 00:00", tz="UTC"),
        pd.Timestamp("2026-10-26 04:00", tz="UTC"),
    ]
    assert list(h4.high) == [104.0, 108.0]


def h4_highs_seen(monkeypatch: pytest.MonkeyPatch, at: datetime, highs: list[float]) -> list[float]:
    """Run evaluate() with 1,200 H1 bars closing at ``at``'s hour and capture what the ZigZag is given."""
    ctx = context()
    closes = pd.date_range(end=at.replace(minute=0), periods=1200, freq="1h")
    h1 = pd.DataFrame({"open": 90.0, "high": highs, "low": 80.0, "close": 90.0}, index=closes)
    m5 = ctx.frame(Timeframe.M5).copy()
    m5.index = pd.DatetimeIndex([at - timedelta(minutes=5), at])
    m1 = ctx.frame(Timeframe.M1).copy()
    m1.index = pd.date_range(at - timedelta(minutes=60), at, freq="1min", tz="UTC")
    later = StrategyContext(
        replace(ctx.market, decision_time_utc=at),
        {Timeframe.M1: m1, Timeframe.M5: m5, Timeframe.H1: h1},
        at + timedelta(seconds=3),
    )
    seen: list[float] = []

    def capture(high, _low):
        seen.extend(float(x) for x in high)
        return flat_swings(), None

    monkeypatch.setattr(module, "zigzag", capture)
    RangeBreak().evaluate(later)
    return seen


def test_an_unclosed_h4_bar_never_reaches_the_zigzag(monkeypatch: pytest.MonkeyPatch):
    # The partner of the resampling test above, through evaluate() instead of a copy of the filter: 1,200 H1
    # bars whose closes end at 01:00 leave the 00:00-04:00 H4 bar still forming at the 01:05 decision
    # (08:05 Bangkok, inside the Asia window). Its one H1 bar carries a high of 999.
    seen = h4_highs_seen(monkeypatch, datetime(2026, 10, 27, 1, 5, tzinfo=UTC), [100.0] * 1199 + [999.0])
    assert seen and 999.0 not in seen
    assert len(seen) == 300


def test_the_newest_closed_h4_bar_does_reach_the_zigzag(monkeypatch: pytest.MonkeyPatch):
    # The other half, and the one the review caught missing (developer session, 2026-10-27): excluding a bar
    # that HAS closed passed the first version, because the tail slice refilled the count from older data.
    # Here the closes end at 00:00, so the 20:00-00:00 bar closed 5 minutes before the 00:05 decision
    # (07:05 Bangkok). Its four H1 bars carry a high of 500; a cutoff one bar too late drops it.
    seen = h4_highs_seen(monkeypatch, datetime(2026, 10, 27, 0, 5, tzinfo=UTC), [100.0] * 1196 + [500.0] * 4)
    assert len(seen) == 300
    assert seen[-1] == 500.0
