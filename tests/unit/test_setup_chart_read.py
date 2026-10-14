"""Chart read gates of the setups (TAA-L813 CR-5, docs/CHART_READ.md §7): all off by default, each one on its
own, relative to the trade actually taken (the fade's side for a fade)."""

from __future__ import annotations

import dataclasses

import pytest

from app.core.enums import Action
from app.indicators.chart_read import ChartRead, Level, LevelRole, Pivot, Structure
from app.indicators.market_map import MapState, MarketMap, TimeframeMap
from app.indicators.price_action import SwingKind
from app.strategy.setups import RangeBreakout
from app.strategy.signal_models import StrategyContext
from tests.unit.test_strategy_setups import ATR, BO_RISK, CLOSE, DONCHIAN, ENTRY, SPREAD, T, run, sctx

FADE = {"screen_h4": "with", "screen_h1": "with", "fade_counter_trend": True}


def read(
    tf: str,
    structure: Structure,
    *,
    levels: tuple[Level, ...] = (),
    pivots: tuple[Pivot, ...] = (),
) -> ChartRead:
    return ChartRead(tf, T, CLOSE, ATR, 5, structure, None, False, 1, pivots=pivots, levels=levels)


def level(price: float, role: LevelRole = LevelRole.SUPPORT) -> Level:
    return Level(price, role, price > CLOSE, 2, T, T, 0, abs(price - CLOSE) / ATR)


def pivot(kind: SwingKind, price: float) -> Pivot:
    return Pivot(kind, price, T, T, None)


def ctx_with(
    *, h4: MapState = MapState.UP, h1: MapState = MapState.UP, **reads: ChartRead | None
) -> StrategyContext:
    """DONCHIAN (a BUY break) with H4/H1 maps in *h4* / *h1* and the given reads (keys: H1, H4)."""
    ctx = sctx(DONCHIAN)
    states = {"H4": h4, "H1": h1}
    maps = {
        tf: TimeframeMap(tf, T, st, st, 25.0, 0.4, 0.004, CLOSE, False, None, (), None, reads.get(tf))
        for tf, st in states.items()
    }
    return dataclasses.replace(ctx, market=dataclasses.replace(ctx.market, htf=MarketMap(maps)))


class TestOffByDefault:
    def test_reads_change_nothing_until_a_param_opts_in(self) -> None:
        plain = run(RangeBreakout, ctx_with())
        with_reads = run(
            RangeBreakout, ctx_with(H1=read("H1", Structure.DOWN), H4=read("H4", Structure.BROADENING))
        )
        assert with_reads.action is plain.action is Action.BUY
        assert (with_reads.stop_loss, with_reads.take_profit) == (plain.stop_loss, plain.take_profit)
        assert [c.name for c in with_reads.conditions] == [c.name for c in plain.conditions]


class TestScreenSource:
    def test_the_screens_read_the_swings_instead_of_the_map(self) -> None:
        swings_down = ctx_with(H1=read("H1", Structure.DOWN), H4=read("H4", Structure.DOWN))
        assert run(RangeBreakout, swings_down, screen_h4="with", screen_h1="with").action is Action.BUY
        sig = run(RangeBreakout, swings_down, screen_h4="with", screen_h1="with", screen_source="swings")
        assert sig.action is Action.HOLD

    def test_a_mixed_phase_counts_as_a_range(self) -> None:
        tri = ctx_with(H1=read("H1", Structure.CONTRACTING), H4=read("H4", Structure.UP))
        assert run(RangeBreakout, tri, screen_h1="with_or_range", screen_source="swings").action is Action.BUY
        assert run(RangeBreakout, tri, screen_h1="with", screen_source="swings").action is Action.HOLD

    def test_the_fade_reads_against_both_from_the_swings(self) -> None:
        ctx = ctx_with(H1=read("H1", Structure.DOWN), H4=read("H4", Structure.DOWN))  # maps UP, swings DOWN
        sig = run(RangeBreakout, ctx, screen_source="swings", **FADE)
        assert sig.action is Action.SELL and "FADE" in sig.reason_codes

    def test_no_read_holds(self) -> None:
        assert run(RangeBreakout, ctx_with(), screen_h4="with", screen_source="swings").action is Action.HOLD


class TestStructureGate:
    @pytest.mark.parametrize(
        ("gate", "structure", "fires"),
        [
            ("not_against", Structure.UP, True),
            ("not_against", Structure.CONTRACTING, True),
            ("not_against", Structure.DOWN, False),
            ("with", Structure.UP, True),
            ("with", Structure.BROADENING, False),
            ("with", Structure.NONE, False),
        ],
    )
    def test_the_h1_swings_against_a_buy(self, gate: str, structure: Structure, fires: bool) -> None:
        sig = run(RangeBreakout, ctx_with(H1=read("H1", structure)), structure_gate=gate)
        assert (sig.action is Action.BUY) is fires

    def test_the_gate_judges_the_fade_s_side(self) -> None:
        ctx = ctx_with(h4=MapState.DOWN, h1=MapState.DOWN, H1=read("H1", Structure.DOWN))
        assert run(RangeBreakout, ctx, structure_gate="with", **FADE).action is Action.SELL
        up = ctx_with(h4=MapState.DOWN, h1=MapState.DOWN, H1=read("H1", Structure.UP))
        assert run(RangeBreakout, up, structure_gate="with", **FADE).action is Action.HOLD

    def test_the_timeframe_is_chosen(self) -> None:
        ctx = ctx_with(H1=read("H1", Structure.DOWN), H4=read("H4", Structure.UP))
        assert run(RangeBreakout, ctx, structure_gate="with").action is Action.HOLD
        assert run(RangeBreakout, ctx, structure_gate="with", structure_tf="H4").action is Action.BUY

    def test_a_missing_read_holds(self) -> None:
        sig = run(RangeBreakout, ctx_with(), structure_gate="not_against")
        assert sig.action is Action.HOLD
        assert any(c.name == "chart_read" and not c.passed for c in sig.conditions)


class TestMixedRule:
    def test_skip_takes_nothing_in_a_triangle_and_trades_a_trend(self) -> None:
        tri = ctx_with(H1=read("H1", Structure.CONTRACTING))
        assert run(RangeBreakout, tri, mixed_rule="skip").action is Action.HOLD
        assert (
            run(RangeBreakout, ctx_with(H1=read("H1", Structure.UP)), mixed_rule="skip").action is Action.BUY
        )

    def test_surest_needs_the_higher_trend_and_a_supportive_level(self) -> None:
        at_support = (level(ENTRY - 0.0001),)
        both = ctx_with(H1=read("H1", Structure.BROADENING, levels=at_support), H4=read("H4", Structure.UP))
        assert run(RangeBreakout, both, mixed_rule="surest").action is Action.BUY
        no_level = ctx_with(H1=read("H1", Structure.BROADENING), H4=read("H4", Structure.UP))
        assert run(RangeBreakout, no_level, mixed_rule="surest").action is Action.HOLD
        h4_down = ctx_with(
            H1=read("H1", Structure.BROADENING, levels=at_support), H4=read("H4", Structure.DOWN)
        )
        assert run(RangeBreakout, h4_down, mixed_rule="surest").action is Action.HOLD


class TestLevels:
    def test_at_level_needs_a_supportive_level_near_the_entry(self) -> None:
        near = ctx_with(H1=read("H1", Structure.UP, levels=(level(ENTRY - 0.0002, LevelRole.FLIPPED),)))
        far = ctx_with(H1=read("H1", Structure.UP, levels=(level(ENTRY - 0.0010),)))
        above = ctx_with(H1=read("H1", Structure.UP, levels=(level(CLOSE + 0.0001, LevelRole.RESISTANCE),)))
        assert run(RangeBreakout, near, level_gate="at_level").action is Action.BUY
        assert run(RangeBreakout, far, level_gate="at_level").action is Action.HOLD
        assert run(RangeBreakout, above, level_gate="at_level").action is Action.HOLD  # resists a buy

    def test_room_to_the_next_opposing_level(self) -> None:
        close_by = ctx_with(
            H1=read("H1", Structure.UP, levels=(level(ENTRY + 0.5 * BO_RISK, LevelRole.RESISTANCE),))
        )
        roomy = ctx_with(
            H1=read("H1", Structure.UP, levels=(level(ENTRY + 3 * BO_RISK, LevelRole.RESISTANCE),))
        )
        assert run(RangeBreakout, close_by, room_min_r=1.0).action is Action.HOLD
        assert run(RangeBreakout, roomy, room_min_r=1.0).action is Action.BUY
        assert run(RangeBreakout, ctx_with(H1=read("H1", Structure.UP)), room_min_r=1.0).action is Action.BUY


class TestStructureStop:
    def test_a_buy_s_stop_goes_beyond_the_last_low_and_the_target_keeps_its_r(self) -> None:
        plain = run(RangeBreakout, ctx_with())
        low = ENTRY - 0.0012
        sig = run(
            RangeBreakout,
            ctx_with(H1=read("H1", Structure.UP, pivots=(pivot(SwingKind.LOW, low),))),
            structure_stop=True,
        )
        dist = 0.0012 + 0.1 * ATR + SPREAD
        assert sig.action is Action.BUY
        assert sig.stop_loss == pytest.approx(ENTRY - dist)
        r_plain = (plain.take_profit - ENTRY) / (ENTRY - plain.stop_loss)
        assert (sig.take_profit - ENTRY) / dist == pytest.approx(r_plain)

    def test_the_stop_is_capped_at_max_sl_atr(self) -> None:
        far = ctx_with(H1=read("H1", Structure.UP, pivots=(pivot(SwingKind.LOW, ENTRY - 0.0100),)))
        sig = run(RangeBreakout, far, structure_stop=True)
        assert sig.stop_loss == pytest.approx(ENTRY - 3.0 * ATR)

    def test_no_swing_behind_the_entry_keeps_the_plan(self) -> None:
        plain = run(RangeBreakout, ctx_with())
        above = ctx_with(H1=read("H1", Structure.UP, pivots=(pivot(SwingKind.LOW, ENTRY + 0.0005),)))
        sig = run(RangeBreakout, above, structure_stop=True)
        assert (sig.stop_loss, sig.take_profit) == (plain.stop_loss, plain.take_profit)

    def test_a_fade_s_stop_goes_beyond_the_last_high(self) -> None:
        high = ENTRY + 0.0020
        ctx = ctx_with(
            h4=MapState.DOWN,
            h1=MapState.DOWN,
            H1=read("H1", Structure.DOWN, pivots=(pivot(SwingKind.HIGH, high),)),
        )
        sig = run(RangeBreakout, ctx, structure_stop=True, **FADE)
        dist = 0.0020 + 0.1 * ATR + SPREAD
        assert sig.action is Action.SELL
        assert sig.stop_loss == pytest.approx(ENTRY + dist)
        # the fade's target keeps its R multiple: the plain fade risks 2 R of the plan for 1 R of it
        assert (ENTRY - sig.take_profit) / dist == pytest.approx(BO_RISK / (2 * BO_RISK))
