"""Setup OWN, F1 CONF-72 on M1 gold (owner, 2026-10-18; app/strategy/own_setup.py), and the position management
it needs: the break-even at a share of the target (``break_even_target_share``) and a lane's RR floor."""

from __future__ import annotations

import dataclasses
import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.config import PositionManagementConfig, StrategyManagement
from app.core.enums import Action, ExitReason, Side, Timeframe
from app.execution.management import PositionView, manage
from app.indicators.chart_read import LevelRole, Structure
from app.indicators.market_map import MapState, MarketMap, TimeframeMap
from app.strategy import own_setup
from app.strategy.catalog import default_registry
from app.strategy.own_setup import (
    OwnConf72,
    OwnConfParams,
    daily_levels,
    h1_tide,
    hammer,
    in_windows,
    m1_atr,
    m5_votes,
    m15_atr,
    resample,
)
from app.strategy.signal_models import MarketContext, ReasonCode, StrategyContext
from tests.risk_data import XAUUSD_SPEC
from tests.unit.test_setup_chart_read import level, read
from tests.unit.test_strategy_models import state

T = datetime(2026, 9, 30, 8, 30, tzinfo=UTC)  # a Wednesday, inside the London window
N = 4500
SPREAD = 0.30
LEVEL = 4640.0  # the M15 chart-read support the dip touches (a BUY)


def m1_frame(at: datetime = T, n: int = N, *, dip: bool = True) -> pd.DataFrame:
    """A steady rise (0.6 USD an hour) with a gentle wave; with *dip* the last six bars dip to LEVEL + 0.3 and
    the last bar is a hammer closing LEVEL + 2.2."""
    i = np.arange(n)
    close = LEVEL + 2.5 - 0.01 * (n - 1 - i) + 0.8 * np.sin(i / 5)
    open_ = np.r_[close[0], close[:-1]]
    high, low = np.maximum(open_, close) + 0.5, np.minimum(open_, close) - 0.5
    if dip:
        for k, (o, h, lo, c) in enumerate(
            [(1.6, 1.9, 1.0, 1.2), (1.2, 1.4, 0.6, 0.8), (0.8, 1.1, 0.4, 0.9), (0.9, 1.3, 0.5, 1.0)], start=5
        ):
            open_[-k], high[-k], low[-k], close[-k] = LEVEL + o, LEVEL + h, LEVEL + lo, LEVEL + c
        open_[-1], high[-1], low[-1], close[-1] = LEVEL + 2.0, LEVEL + 2.3, LEVEL + 0.3, LEVEL + 2.2
        open_[-2], high[-2], low[-2], close[-2] = LEVEL + 1.0, LEVEL + 2.1, LEVEL + 0.6, LEVEL + 2.0
    closes = pd.date_range(end=at, periods=n, freq="1min")
    return pd.DataFrame(
        {
            "open_time": closes - pd.Timedelta(minutes=1),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "spread": np.full(n, SPREAD / XAUUSD_SPEC.point),
        },
        index=closes,
    )


def h1_frame(m1: pd.DataFrame) -> pd.DataFrame:
    bars = resample(m1, 60, m1.index[-1].to_pydatetime())
    bars.index = bars.index + pd.Timedelta(hours=1)
    return bars


def ctx_for(
    m1: pd.DataFrame, *, levels: tuple[float, ...] = (LEVEL,), at: datetime | None = None
) -> StrategyContext:
    at = at or m1.index[-1].to_pydatetime()
    close = float(m1["close"].iloc[-1])
    lv = tuple(level(p, LevelRole.SUPPORT) for p in levels)
    m15 = TimeframeMap("M15", at, MapState.UP, MapState.UP, 25.0, 0.4, 2.0, close, False, None, (), None)
    maps = {"M15": dataclasses.replace(m15, read=read("M15", Structure.UP, levels=lv))}
    market = MarketContext(
        symbol="XAUUSD",
        decision_time_utc=at,
        entry_timeframe=Timeframe.M1,
        higher_timeframe=Timeframe.H1,
        states=(state(Timeframe.M1, at, close=close), state(Timeframe.H1, at, close=close)),
        bid=close,
        ask=close + SPREAD,
        spread_points=SPREAD / XAUUSD_SPEC.point,
        htf=MarketMap(maps),
    )
    return StrategyContext(market, {Timeframe.M1: m1, Timeframe.H1: h1_frame(m1)}, at, XAUUSD_SPEC)


@pytest.fixture
def votes_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """RSI and MACD with the trade, no Stochastic cross (two of three)."""
    monkeypatch.setattr(own_setup, "m5_votes", lambda m5, sign: (True, True, False, "patched"))


def run(ctx: StrategyContext, **params: object) -> object:
    return OwnConf72(OwnConfParams(**params)).evaluate(ctx)  # type: ignore[arg-type]


class TestHelpers:
    def test_windows_are_start_inclusive_end_exclusive_weekdays(self) -> None:
        w = OwnConfParams().windows
        assert in_windows(datetime(2026, 9, 30, 7, 0, tzinfo=UTC), w, "UTC")
        assert in_windows(datetime(2026, 9, 30, 16, 59, tzinfo=UTC), w, "UTC")
        assert not in_windows(datetime(2026, 9, 30, 17, 0, tzinfo=UTC), w, "UTC")
        assert not in_windows(datetime(2026, 9, 30, 2, 0, tzinfo=UTC), w, "UTC")
        assert not in_windows(datetime(2026, 10, 3, 8, 0, tzinfo=UTC), w, "UTC")  # Saturday

    def test_params_reject_bad_windows_zones_and_stop_ranges(self) -> None:
        with pytest.raises(ValidationError):
            OwnConfParams(windows=("12:00-07:00",))
        with pytest.raises(ValidationError):
            OwnConfParams(window_zone="Mars/Olympus")
        with pytest.raises(ValidationError):
            OwnConfParams(stop_min_u=10.0, stop_max_u=3.0)

    def test_m1_atr_is_the_researched_range(self) -> None:
        h = np.array([10.0, 11.0, 12.0] * 6)
        lo = h - 1.0
        c = h - 0.5
        atr = m1_atr(h, lo, c)
        assert np.isnan(atr[12]) and not np.isnan(atr[13])
        # bar range 1.0; |previous close - high| is 1.5 after a step up, 0.5 / 2.5 otherwise
        rng = np.fmax(h - lo, np.abs(np.r_[np.nan, c[:-1]] - h))
        assert atr[-1] == pytest.approx(rng[-14:].mean())

    def test_hammer_both_ways(self) -> None:
        assert hammer(2.0, 2.3, 0.3, 2.2, 1) and not hammer(2.0, 2.3, 0.3, 2.2, -1)
        assert hammer(1.0, 2.7, 0.7, 0.8, -1) and not hammer(1.0, 2.7, 0.7, 0.8, 1)

    def test_resample_keeps_only_closed_bins(self) -> None:
        m1 = m1_frame(T + timedelta(minutes=3), n=30, dip=False)  # the last bin 08:30-08:35 is still open
        m5 = resample(m1, 5, T + timedelta(minutes=3))
        assert m5.index[-1] == pd.Timestamp(T - timedelta(minutes=5))
        first = m1[(m1["open_time"] >= m5.index[-1]) & (m1["open_time"] < pd.Timestamp(T))]
        assert m5["high"].iloc[-1] == first["high"].max() and m5["close"].iloc[-1] == first["close"].iloc[-1]

    def test_m15_atr_is_the_mean_true_range(self) -> None:
        bars = pd.DataFrame({"high": np.full(20, 3.0), "low": np.full(20, 1.0), "close": np.full(20, 2.0)})
        assert m15_atr(bars) == pytest.approx(2.0)
        assert m15_atr(bars.iloc[:10]) is None

    def test_tide_follows_the_h1_emas(self) -> None:
        up = h1_frame(m1_frame(dip=False))
        assert h1_tide(up) == 1
        down = up.assign(**{k: 2 * 4600 - up[k] for k in ("open", "close")}).assign(
            high=lambda d: 2 * 4600 - up["low"], low=lambda d: 2 * 4600 - up["high"]
        )
        assert h1_tide(down) == -1
        assert h1_tide(up.iloc[:30]) == 0

    def test_m5_votes_after_a_dip_that_turned(self) -> None:
        c = np.r_[np.linspace(100, 110, 40), np.linspace(110, 104, 12), [104.6]]
        m5 = pd.DataFrame({"open": c, "high": c + 0.3, "low": c - 0.3, "close": c})
        votes = m5_votes(m5, 1)
        assert votes is not None and votes[0] and votes[1]  # RSI turning up under 50, histogram rising
        assert m5_votes(m5.iloc[:20], 1) is None

    def test_daily_levels_today_yesterday_and_asia(self) -> None:
        m1 = m1_frame(dip=False)
        opens = pd.DatetimeIndex(m1["open_time"])
        lo, hi = m1["low"].to_numpy(), m1["high"].to_numpy()
        p = OwnConfParams()
        got = daily_levels(opens, lo, hi, p, 1)
        q = len(m1) - 1 - p.level_lag_bars
        today = opens >= pd.Timestamp("2026-09-29 21:00", tz="UTC")  # Athens midnight (EEST)
        yesterday = (opens >= pd.Timestamp("2026-09-28 21:00", tz="UTC")) & ~today
        asia = (opens >= pd.Timestamp("2026-09-30", tz="UTC")) & (
            opens < pd.Timestamp("2026-09-30 07:00", tz="UTC")
        )
        assert got["today"] == lo[: q + 1][today[: q + 1]].min()
        assert got["yesterday"] == lo[yesterday].min()
        assert got["asia"] == lo[asia].min()
        assert daily_levels(opens, lo, hi, p, -1)["yesterday"] == hi[yesterday].max()


class TestSignals:
    def test_a_buy_at_the_level_with_the_tide(self, votes_ok: None) -> None:
        sig = run(ctx_for(m1_frame()))
        assert sig.action is Action.BUY  # type: ignore[attr-defined]
        entry = LEVEL + 2.2 + SPREAD
        unit = (LEVEL + 2.2) / 4100
        atr1 = float(m1_atr(*(m1_frame()[k].to_numpy() for k in ("high", "low", "close")))[-1])
        assert sig.entry_price == pytest.approx(entry)  # type: ignore[attr-defined]
        assert sig.stop_loss == pytest.approx(LEVEL - atr1)  # type: ignore[attr-defined]
        assert sig.take_profit == pytest.approx(entry + 8 * unit)  # type: ignore[attr-defined]
        names = [c.name for c in sig.conditions]  # type: ignore[attr-defined]
        assert names == [
            "h1_tide",
            "not_fast_tape",
            "room72",
            "at_level",
            "price_action",
            "m5_indicators",
            "stop_range",
        ]

    def test_the_stop_floor_widens_a_tight_stop(self, votes_ok: None) -> None:
        ctx = ctx_for(m1_frame())
        a15 = m15_atr(resample(ctx.frame(Timeframe.M1), 15, T))
        assert a15 is not None
        sig = run(ctx, stop_floor_m15_atr=3.0)
        entry = LEVEL + 2.2 + SPREAD
        assert sig.stop_loss == pytest.approx(entry - 3.0 * a15)  # type: ignore[attr-defined]

    def test_holds_outside_the_windows(self) -> None:
        at = T.replace(hour=5)
        sig = run(ctx_for(m1_frame(at), at=at))
        assert sig.action is Action.HOLD and ReasonCode.OUTSIDE_SESSION in sig.reason_codes  # type: ignore[attr-defined]

    def test_holds_without_enough_m1_history(self) -> None:
        sig = run(ctx_for(m1_frame(n=3000)))
        assert sig.action is Action.HOLD and ReasonCode.INSUFFICIENT_DATA in sig.reason_codes  # type: ignore[attr-defined]

    def test_no_level_near_holds(self, votes_ok: None) -> None:
        sig = run(ctx_for(m1_frame(), levels=()))
        assert sig.action is Action.HOLD  # type: ignore[attr-defined]
        failed = [c.name for c in sig.conditions if not c.passed]  # type: ignore[attr-defined]
        assert failed == ["at_level"]

    def test_a_stop_beyond_ten_units_is_no_trade(self, votes_ok: None) -> None:
        sig = run(ctx_for(m1_frame()), stop_max_u=3.1)
        assert sig.action is Action.HOLD and ReasonCode.SL_TOO_FAR in sig.reason_codes  # type: ignore[attr-defined]

    def test_far_from_the_72_hour_extreme_holds(self, votes_ok: None) -> None:
        m1 = m1_frame()
        m1.iloc[-1000, m1.columns.get_loc("high")] = LEVEL + 40  # a spike two days ago: the extreme is far
        sig = run(ctx_for(m1))
        failed = [c.name for c in sig.conditions if not c.passed]  # type: ignore[attr-defined]
        assert sig.action is Action.HOLD and failed == ["room72"]  # type: ignore[attr-defined]

    def test_a_shorter_window_gives_the_same_plan(self, votes_ok: None) -> None:
        """The values settle within the warm-up: where the window starts does not change the decision."""
        full = m1_frame()
        a, b = run(ctx_for(full)), run(ctx_for(full.iloc[-4400:]))
        assert a.action is b.action is Action.BUY  # type: ignore[attr-defined]
        assert a.stop_loss == pytest.approx(b.stop_loss)  # type: ignore[attr-defined]

    def test_off_the_round_50_half_size_or_skip(self, votes_ok: None) -> None:
        """The nearest level here is the M15 support at 4640, not a round 50."""
        assert run(ctx_for(m1_frame())).risk_scale == 1.0  # type: ignore[attr-defined]
        half = run(ctx_for(m1_frame()), off_round="half")
        assert half.action is Action.BUY and half.risk_scale == 0.5  # type: ignore[attr-defined]
        skip = run(ctx_for(m1_frame()), off_round="skip")
        failed = [c.name for c in skip.conditions if not c.passed]  # type: ignore[attr-defined]
        assert skip.action is Action.HOLD and failed == ["round_level"]  # type: ignore[attr-defined]

    def test_at_the_round_50_full_size_in_every_mode(self, votes_ok: None) -> None:
        m1 = m1_frame()
        m1[["open", "high", "low", "close"]] += 10.0  # the dip now touches 4650
        for mode in ("half", "skip"):
            sig = run(ctx_for(m1, levels=()), off_round=mode)
            assert sig.action is Action.BUY and sig.risk_scale == 1.0  # type: ignore[attr-defined]
            assert "round 4650.00" in next(c.detail for c in sig.conditions if c.name == "at_level")  # type: ignore[attr-defined]

    def test_registered_for_lanes_only(self) -> None:
        cls = default_registry().get("setup_own_conf72")
        assert cls is OwnConf72 and not cls.advised
        assert OwnConf72().warmup_bars() == 4322
        assert OwnConf72().required_timeframes() == (Timeframe.M1, Timeframe.H1)


def view(tp: float | None = 108.0) -> PositionView:
    return PositionView(Side.BUY, 100.0, 95.0, 95.0, 3, tp)


class TestBreakEvenAtATargetShare:
    CFG = PositionManagementConfig(by_strategy={"own": StrategyManagement(break_even_target_share=0.6)})

    def test_the_bar_reach_arms_it_and_the_r_trigger_is_off(self) -> None:
        cfg = self.CFG.for_strategy("own")
        assert math.isinf(cfg.break_even_trigger_r) and cfg.break_even_target_share == 0.6
        adj = manage(view(), mark=103.0, atr=1.0, point=0.01, cfg=cfg, reach=104.81)
        assert adj.new_sl == pytest.approx(100.02) and adj.stop_kind is ExitReason.BREAK_EVEN
        assert manage(view(), mark=103.0, atr=1.0, point=0.01, cfg=cfg, reach=104.7).new_sl is None
        assert manage(view(), mark=104.81, atr=1.0, point=0.01, cfg=cfg).new_sl == pytest.approx(100.02)

    def test_needs_a_target_and_a_live_switch(self) -> None:
        cfg = self.CFG.for_strategy("own")
        assert manage(view(None), mark=104.9, atr=1.0, point=0.01, cfg=cfg, reach=110.0).new_sl is None
        off = PositionManagementConfig(
            by_strategy={"own": StrategyManagement(break_even=False, break_even_target_share=0.6)}
        ).for_strategy("own")
        assert off.break_even_target_share is None and math.isinf(off.break_even_trigger_r)

    def test_a_sell_mirrors(self) -> None:
        cfg = self.CFG.for_strategy("own")
        pos = PositionView(Side.SELL, 100.0, 105.0, 105.0, 3, 92.0)
        assert manage(pos, mark=97.0, atr=1.0, point=0.01, cfg=cfg, reach=95.19).new_sl == pytest.approx(
            99.98
        )

    def test_bounds(self) -> None:
        with pytest.raises(ValidationError):
            StrategyManagement(break_even_target_share=1.0)


def own_pos(
    m1: pd.DataFrame, *, bars_in: int, tp_u: float, entry: float = LEVEL + 2.5, sl: float | None = None
):
    """A BUY opened *bars_in* bars before the end of *m1* (its entry bar included)."""
    unit = entry / 4100
    t = pd.Timestamp(m1["open_time"].iloc[-bars_in]).to_pydatetime()
    stop = entry - 4.0 if sl is None else sl
    return own_setup.OpenPosition(Side.BUY, entry, entry - 4.0, stop, entry + tp_u * unit, t, "sig")


def v2(**kw: object) -> OwnConf72:
    return OwnConf72(OwnConfParams(exit_mode="regime", scratch_bars=10, **kw))  # type: ignore[arg-type]


class TestV2Exits:
    def test_v1_leaves_it_to_the_lane(self) -> None:
        ctx = ctx_for(m1_frame(dip=False))
        assert OwnConf72().manage_position(ctx, own_pos(ctx.frame(Timeframe.M1), bars_in=10, tp_u=8)) is None

    def test_a_fixed_trade_is_scratched_at_ten_bars_and_timed_out_at_sixty(self) -> None:
        m1 = m1_frame(dip=False)
        ctx = ctx_for(m1)
        close = float(m1["close"].iloc[-1])
        high10 = float(m1["high"].iloc[-10:].max())
        # an entry above every high of the last ten bars: never 2 U ahead, the close against it
        losing = own_pos(m1, bars_in=10, tp_u=8, entry=high10 + 0.5)
        advice = v2().manage_position(ctx, losing)
        assert advice is not None and advice.close is ExitReason.SIGNAL
        assert v2().manage_position(ctx, own_pos(m1, bars_in=9, tp_u=8, entry=high10 + 0.5)) is None
        timed = v2().manage_position(ctx, own_pos(m1, bars_in=60, tp_u=8, entry=close))
        assert timed is not None and timed.close is ExitReason.TIME_STOP

    def test_a_runner_locks_behind_the_level_it_closed_beyond_then_trails(self) -> None:
        m1 = m1_frame(dip=False)
        ctx = ctx_for(m1)
        entry = (
            float(m1["close"].iloc[-30]) - 3.0
        )  # 30 bars ago, 3 USD lower: the level 1 USD above the entry
        unit = entry / 4100
        level = entry + 1.0
        pos = own_setup.OpenPosition(
            Side.BUY,
            entry,
            entry - 5,
            entry - 5,
            level + 40 * unit,
            m1["open_time"].iloc[-30].to_pydatetime(),
        )
        advice = v2().manage_position(ctx, pos)
        assert advice is not None and advice.stop_kind is ExitReason.TRAILING_STOP
        before = m1.iloc[: len(m1) - 30]
        a15 = m15_atr(resample(before, 15, before.index[-1].to_pydatetime()))
        assert a15 is not None
        tail = m1["close"].to_numpy()[-30:]
        top = tail[np.flatnonzero(tail > level)[0] :].max()
        assert advice.new_sl == pytest.approx(
            max(
                top - a15,
                level - 0.5 * m1_atr(*(before[k].to_numpy() for k in ("high", "low", "close")))[-1],
                entry,
            )
        )

    def test_a_runner_without_a_level_only_breaks_even(self) -> None:
        m1 = m1_frame(dip=False)
        ctx = ctx_for(m1)
        entry = float(m1["close"].iloc[-30]) - 6.0
        pos = own_setup.OpenPosition(
            Side.BUY,
            entry,
            entry - 5,
            entry - 5,
            entry + 40 * entry / 4100,
            m1["open_time"].iloc[-30].to_pydatetime(),
        )
        advice = v2().manage_position(ctx, pos)
        assert advice is not None and advice.stop_kind is ExitReason.BREAK_EVEN and advice.new_sl == entry

    def test_strong_phase_needs_a_hundred_atrs(self) -> None:
        assert own_setup.strong_phase(np.r_[np.ones(150), 2.0], 288, 1.3) is True
        assert own_setup.strong_phase(np.r_[np.ones(150), 1.2], 288, 1.3) is False
        assert own_setup.strong_phase(np.ones(50), 288, 1.3) is None

    def test_regime_entries_mark_runners_by_their_target(
        self, votes_ok: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(own_setup, "strong_phase", lambda atrs, bars, ratio: True)
        ctx = ctx_for(m1_frame(n=4700))
        sig = v2().evaluate(ctx)
        entry = LEVEL + 2.2 + SPREAD
        assert sig.action is Action.BUY
        assert (sig.take_profit - entry) > 30 * entry / 4100  # past the level in front by 40 U
        monkeypatch.setattr(own_setup, "strong_phase", lambda atrs, bars, ratio: False)
        assert v2().evaluate(ctx).take_profit == pytest.approx(entry + 8 * (LEVEL + 2.2) / 4100)

    def test_v2_needs_more_warm_up(self) -> None:
        assert v2().warmup_bars() == (288 + 15) * 15
        with pytest.raises(ValidationError):
            OwnConfParams(runner_cap_u=8.0)


class TestAdvice:
    def test_a_stop_through_the_price_closes(self) -> None:
        from app.execution.management import Adjustment, from_advice, with_advice
        from app.strategy.signal_models import PositionAdvice

        move = PositionAdvice(new_sl=101.0, stop_kind=ExitReason.TRAILING_STOP)
        assert from_advice(move, Side.BUY, mark=102.0, sl=99.0) == Adjustment(
            101.0, ExitReason.TRAILING_STOP, None, ""
        )
        assert from_advice(move, Side.BUY, mark=100.5, sl=99.0).close is ExitReason.TRAILING_STOP  # type: ignore[union-attr]
        assert from_advice(move, Side.BUY, mark=102.0, sl=101.5) is None  # not favourable
        rules = Adjustment(100.0, ExitReason.BREAK_EVEN)
        assert with_advice(Side.BUY, rules, Adjustment(101.0, ExitReason.TRAILING_STOP)).new_sl == 101.0
        assert with_advice(Side.BUY, rules, Adjustment(close=ExitReason.SIGNAL)).close is ExitReason.SIGNAL
        assert (
            with_advice(Side.BUY, Adjustment(close=ExitReason.TIME_STOP), None).close is ExitReason.TIME_STOP
        )
