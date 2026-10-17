"""The owner's triple screen setup TS (2026-10-17, docs/OWNER_TRADING.md "Setup TS"): with the H4 tide, a
pullback that turned at an H1/H4 chart-read level, entered on the entry timeframe's structure break."""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from app.core.enums import Action, Timeframe
from app.evidence.framework import ActiveEvidence, Direction, Family
from app.indicators.chart_read import Level, LevelRole, Structure
from app.indicators.market_map import MapState, MarketMap, TimeframeMap
from app.strategy.setups import SETUPS, TripleScreen
from app.strategy.signal_models import StrategyContext
from tests.unit.test_setup_chart_read import level, read
from tests.unit.test_strategy_setups import ATR, CLOSE, ENTRY, SPREAD, T, ev, run, sctx

LOW = 1.0995  # the pullback's low (a BUY): the bos/choch trigger's invalidation
HIGH = 1.1030  # the pullback's high (a SELL)
TARGET_UP, TARGET_DOWN = 1.1060, 1.0960  # the next H4 levels


def trigger(direction: Direction = Direction.BULL, pivot: float | None = None) -> ActiveEvidence:
    inv = pivot if pivot is not None else (LOW if direction is Direction.BULL else HIGH)
    return ev("structure.bos_choch", direction, family=Family.TREND, invalidation=inv, var="choch")


def ts_ctx(
    item: ActiveEvidence,
    *,
    h4: MapState = MapState.UP,
    h4_swings: Structure = Structure.UP,
    h1_levels: tuple[Level, ...] = (level(LOW),),
    h4_levels: tuple[Level, ...] = (level(TARGET_UP, LevelRole.RESISTANCE),),
) -> StrategyContext:
    ctx = sctx(item)
    reads = {"H1": read("H1", Structure.UP, levels=h1_levels), "H4": read("H4", h4_swings, levels=h4_levels)}
    maps = {
        tf: TimeframeMap(tf, T, st, st, 25.0, 0.4, 0.004, CLOSE, False, None, (), None, reads[tf])
        for tf, st in (("H4", h4), ("H1", MapState.UP))
    }
    return dataclasses.replace(ctx, market=dataclasses.replace(ctx.market, htf=MarketMap(maps)))


def sell_ctx() -> StrategyContext:
    return ts_ctx(
        trigger(Direction.BEAR),
        h4=MapState.DOWN,
        h4_swings=Structure.DOWN,
        h1_levels=(level(HIGH, LevelRole.RESISTANCE),),
        h4_levels=(level(TARGET_DOWN),),
    )


def failed(sig: object) -> list[str]:
    return [c.name for c in sig.conditions if not c.passed]  # type: ignore[attr-defined]


class TestPlan:
    def test_a_buy_after_a_pullback_that_turned_at_a_level(self) -> None:
        sig = run(TripleScreen, ts_ctx(trigger()))
        assert sig.action is Action.BUY
        assert sig.reason_codes[0] == "TRIPLE_SCREEN_PULLBACK"
        assert sig.stop_loss == pytest.approx(LOW - 0.5 * ATR - SPREAD)  # beyond the low, half an ATR
        assert sig.take_profit == pytest.approx(TARGET_UP - 0.25 * ATR)  # before the next H4 level
        assert sig.entry_price == pytest.approx(ENTRY)

    def test_a_sell_is_the_mirror(self) -> None:
        sig = run(TripleScreen, sell_ctx())
        assert sig.action is Action.SELL
        assert sig.stop_loss == pytest.approx(HIGH + 0.5 * ATR + SPREAD)
        assert sig.take_profit == pytest.approx(TARGET_DOWN + 0.25 * ATR)

    def test_no_front_puts_the_target_on_the_level(self) -> None:
        assert run(TripleScreen, ts_ctx(trigger()), target_front_atr=0).take_profit == pytest.approx(
            TARGET_UP
        )

    def test_a_far_level_caps_the_target_at_rr_target(self) -> None:
        far = ts_ctx(trigger(), h4_levels=(level(1.1300, LevelRole.RESISTANCE),))
        sig = run(TripleScreen, far)
        assert sig.action is Action.BUY and sig.stop_loss is not None
        risk = ENTRY - sig.stop_loss
        assert sig.take_profit == pytest.approx(ENTRY + 3.0 * risk)

    def test_a_near_level_leaves_too_little_room(self) -> None:
        near = ts_ctx(trigger(), h4_levels=(level(1.1030, LevelRole.RESISTANCE),))
        sig = run(TripleScreen, near)
        assert sig.action is Action.HOLD and "rr_ok" in failed(sig)


class TestLocation:
    def test_the_pullback_must_turn_at_a_level(self) -> None:
        sig = run(TripleScreen, ts_ctx(trigger(), h1_levels=()))
        assert sig.action is Action.HOLD and failed(sig) == ["pivot_at_level"]

    def test_within_the_read_s_tolerance(self) -> None:
        near = ts_ctx(trigger(), h1_levels=(level(LOW + 0.2 * ATR),))  # the read's tolerance: 0.25 ATR
        assert run(TripleScreen, near).action is Action.BUY
        off = ts_ctx(trigger(), h1_levels=(level(LOW + 0.4 * ATR),))
        assert run(TripleScreen, off).action is Action.HOLD
        assert run(TripleScreen, off, pivot_tol_atr=0.5).action is Action.BUY

    def test_a_flipped_or_swept_level_counts(self) -> None:
        flipped = ts_ctx(trigger(), h1_levels=(level(LOW, LevelRole.FLIPPED),))
        assert run(TripleScreen, flipped).action is Action.BUY
        swept = ts_ctx(trigger(), h1_levels=(level(LOW + 0.1 * ATR, LevelRole.RESISTANCE),))
        assert run(TripleScreen, swept).action is Action.BUY

    def test_the_h4_levels_count_too_and_the_frames_are_chosen(self) -> None:
        h4_only = ts_ctx(
            trigger(), h1_levels=(), h4_levels=(level(LOW), level(TARGET_UP, LevelRole.RESISTANCE))
        )
        assert run(TripleScreen, h4_only).action is Action.BUY
        assert run(TripleScreen, h4_only, pivot_level_tfs=("H1",)).action is Action.HOLD

    def test_no_frames_switch_the_gate_off(self) -> None:
        sig = run(TripleScreen, ts_ctx(trigger(), h1_levels=()), pivot_level_tfs=())
        assert sig.action is Action.BUY and "pivot_at_level" not in [c.name for c in sig.conditions]

    def test_a_missing_read_holds(self) -> None:
        sig = run(TripleScreen, sctx(trigger()), screen_h4="any", structure_gate="off", target_mode="rr")
        assert sig.action is Action.HOLD and failed(sig) == ["pivot_at_level"]


class TestContext:
    @pytest.mark.parametrize(
        ("gate", "h4", "fires"),
        [
            ("with", MapState.UP, True),
            ("with", MapState.RANGE, False),
            ("with_or_range", MapState.RANGE, True),
            ("with_or_range", MapState.DOWN, False),
        ],
    )
    def test_the_tide_is_the_h4_map(self, gate: str, h4: MapState, fires: bool) -> None:
        sig = run(TripleScreen, ts_ctx(trigger(), h4=h4), screen_h4=gate)
        assert (sig.action is Action.BUY) is fires

    def test_the_h4_swings_must_not_be_against(self) -> None:
        assert run(TripleScreen, ts_ctx(trigger(), h4_swings=Structure.CONTRACTING)).action is Action.BUY
        sig = run(TripleScreen, ts_ctx(trigger(), h4_swings=Structure.DOWN))
        assert sig.action is Action.HOLD and failed(sig) == ["structure_gate"]

    def test_only_the_structure_break_triggers(self) -> None:
        donchian = ev("volatility.donchian", invalidation=LOW)
        assert run(TripleScreen, ts_ctx(donchian)).action is Action.HOLD


class TestCatalog:
    def test_registered_lane_only(self) -> None:
        assert TripleScreen in SETUPS
        assert TripleScreen.advised is False  # the scanner does not offer it
        assert TripleScreen.name == "setup_triple_screen"


def with_d1(ctx: StrategyContext, ema: tuple[float, float], close: float) -> StrategyContext:
    """A D1 frame (the tide) whose EMA moves linearly from ema[0] to ema[1] over 10 bars."""
    idx = pd.date_range(end=T, periods=10, freq="1D")
    frame = pd.DataFrame({"close": np.full(10, close), "ema_mid": np.linspace(*ema, 10)}, index=idx)
    return dataclasses.replace(ctx, frames={**ctx.frames, Timeframe.D1: frame})


class TestTide:
    def test_a_buy_needs_the_d1_close_above_a_rising_ema(self) -> None:
        up = with_d1(ts_ctx(trigger()), (1.0950, 1.0990), 1.1000)
        sig = run(TripleScreen, up, tide_ema_tf="D1")
        assert sig.action is Action.BUY and "ema_tide" in [c.name for c in sig.conditions]
        below = with_d1(ts_ctx(trigger()), (1.0950, 1.0990), 1.0980)
        assert failed(run(TripleScreen, below, tide_ema_tf="D1")) == ["ema_tide"]
        falling = with_d1(ts_ctx(trigger()), (1.0990, 1.0950), 1.1000)
        assert failed(run(TripleScreen, falling, tide_ema_tf="D1")) == ["ema_tide"]

    def test_a_sell_is_the_mirror(self) -> None:
        down = with_d1(sell_ctx(), (1.1060, 1.1020), 1.1000)
        assert run(TripleScreen, down, tide_ema_tf="D1").action is Action.SELL
        up = with_d1(sell_ctx(), (1.0950, 1.0990), 1.1000)
        assert run(TripleScreen, up, tide_ema_tf="D1").action is Action.HOLD

    def test_a_missing_frame_holds_and_the_default_is_off(self) -> None:
        assert failed(run(TripleScreen, ts_ctx(trigger()), tide_ema_tf="D1")) == ["ema_tide"]
        sig = run(TripleScreen, ts_ctx(trigger()))
        assert sig.action is Action.BUY and "ema_tide" not in [c.name for c in sig.conditions]


def with_map_ema(ctx: StrategyContext, tf: str, ema: float | None, slope: float | None) -> StrategyContext:
    assert ctx.market.htf is not None
    frames = dict(ctx.market.htf.frames)
    m = frames.get(tf) or TimeframeMap(tf, T, MapState.UP, MapState.UP, 25.0, 0.4, 0.004, CLOSE, False, None)
    frames[tf] = dataclasses.replace(m, ema_mid=ema, ema_slope=slope)
    return dataclasses.replace(ctx, market=dataclasses.replace(ctx.market, htf=MarketMap(frames)))


class TestMapTide:
    def test_every_listed_timeframe_must_agree(self) -> None:
        both = with_map_ema(
            with_map_ema(ts_ctx(trigger()), "H4", CLOSE - ATR, 0.0002), "D1", CLOSE - ATR, 0.001
        )
        sig = run(TripleScreen, both, tide_ema_tfs=("D1", "H4"))
        assert sig.action is Action.BUY and {"tide_d1", "tide_h4"} <= {c.name for c in sig.conditions}
        h4_down = with_map_ema(both, "H4", CLOSE - ATR, -0.0002)
        assert failed(run(TripleScreen, h4_down, tide_ema_tfs=("D1", "H4"))) == ["tide_h4"]
        below = with_map_ema(both, "D1", CLOSE + ATR, 0.001)
        assert failed(run(TripleScreen, below, tide_ema_tfs=("D1", "H4"))) == ["tide_d1"]

    def test_a_sell_is_the_mirror_and_a_missing_value_holds(self) -> None:
        down = with_map_ema(sell_ctx(), "H4", CLOSE + ATR, -0.0002)
        assert run(TripleScreen, down, tide_ema_tfs=("H4",)).action is Action.SELL
        assert failed(run(TripleScreen, sell_ctx(), tide_ema_tfs=("H4",))) == ["tide_h4"]
