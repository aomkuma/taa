"""Entry-mode shadow variants (TAA-L702): geometry, sizing and waiting limits (pure)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.advisory.shadow import Flag, Variant, advance, new_state
from app.config import EntryModesConfig
from app.core.enums import ExitReason, Side
from app.execution.fill_model import Bar
from app.learning.entry_modes import await_fill, configured, geometry

T0 = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
SPREAD = 0.0002
CFG = EntryModesConfig(variants=["PULLBACK", "WIDE_STOP", "PULLBACK_WIDE"])


def bar(minute: int, o: float, h: float, lo: float, c: float, spread: float = SPREAD) -> Bar:
    start = T0 + timedelta(minutes=minute)
    return Bar(start, start + timedelta(minutes=1), o, h, lo, c, spread)


def geo(variant: Variant, side: Side = Side.BUY, *, lot: float | None = 0.1, **kw: object):  # type: ignore[no-untyped-def]
    sign = side.sign
    args: dict[str, object] = {
        "side": side,
        "fill": 1.1000,
        "plan_sl": 1.1000 - sign * 0.0010,
        "tp": 1.1000 + sign * 0.0020,
        "lot": lot,
        "entry_at": T0,
        "bar_seconds": 900,
        "cfg": CFG,
        "volume_step": 0.01,
        "volume_min": 0.01,
    } | kw
    return geometry(variant, **args)  # type: ignore[arg-type]


class TestGeometry:
    def test_configured_in_order(self) -> None:
        assert configured(CFG) == [Variant.PULLBACK, Variant.WIDE_STOP, Variant.PULLBACK_WIDE]
        assert configured(EntryModesConfig()) == []

    @pytest.mark.parametrize("side", [Side.BUY, Side.SELL])
    def test_wide_stop_keeps_the_entry_tp_and_money_at_risk(self, side: Side) -> None:
        g = geo(Variant.WIDE_STOP, side)
        assert g.entry == pytest.approx(1.1000)
        assert g.sl == pytest.approx(1.1000 - side.sign * 0.0020)
        assert g.tp == pytest.approx(1.1000 + side.sign * 0.0020)
        assert g.lot == pytest.approx(0.05) and g.window_end is None

    @pytest.mark.parametrize("side", [Side.BUY, Side.SELL])
    def test_pullback_waits_at_a_limit_with_the_plan_stop(self, side: Side) -> None:
        g = geo(Variant.PULLBACK, side)
        assert g.entry == pytest.approx(1.1000 - side.sign * 0.0005)
        assert g.sl == pytest.approx(1.1000 - side.sign * 0.0010)
        assert g.lot == pytest.approx(0.2)  # half the distance: twice the lot, same money at risk
        assert g.window_end == T0 + timedelta(minutes=60)  # 4 entry bars of M15

    def test_pullback_wide_stop_from_the_signal_entry(self) -> None:
        g = geo(Variant.PULLBACK_WIDE)
        assert (g.entry, g.sl) == (pytest.approx(1.0995), pytest.approx(1.0980))
        assert g.lot == pytest.approx(0.06)  # 0.1 x 1.0 / 1.5, floored to the step

    def test_lot_below_the_minimum_is_tracked_in_r_only(self) -> None:
        assert geo(Variant.WIDE_STOP, lot=0.01).lot is None
        assert geo(Variant.WIDE_STOP, lot=None).lot is None

    def test_invalid_plan_geometry_passes_through(self) -> None:
        g = geo(Variant.WIDE_STOP, plan_sl=1.1005)
        assert (g.entry, g.sl) == (1.1000, 1.1005)

    def test_config_bounds(self) -> None:
        with pytest.raises(ValueError, match="beyond"):
            EntryModesConfig(pullback_depth_r=0.8, pullback_wide_stop_r=0.6)
        with pytest.raises(ValueError, match="duplicates"):
            EntryModesConfig(variants=["PULLBACK", "PULLBACK"])
        with pytest.raises(ValueError):
            EntryModesConfig(entry_window_bars=7)


def pending(side: Side = Side.BUY, limit: float = 1.0995, sl: float = 1.0990, tp: float = 1.1020):  # type: ignore[no-untyped-def]
    return new_state(side=side, entry=limit, entry_at=T0, sl=sl, tp=tp, time_stop=timedelta(hours=72))


class TestAwaitFill:
    def test_a_buy_limit_fills_when_the_ask_reaches_it(self) -> None:
        state = pending()
        bars = [bar(0, 1.1000, 1.1002, 1.0994, 1.1000), bar(1, 1.1000, 1.1001, 1.0992, 1.0996)]
        w = await_fill(state, bars, window_end=T0 + timedelta(minutes=10), slippage=0.0)
        # bar 0: ask low 1.0994 + 0.0002 = 1.0996 > 1.0995; bar 1: 1.0994 <= 1.0995
        assert (w.filled, w.missed, w.exit) == (True, False, None)
        assert state.entry_at == bars[1].open_time and state.cursor == bars[1].close_time
        assert state.entry == 1.0995 and Flag.PARTIAL_BAR in state.flags

    def test_a_sell_limit_fills_on_the_bid(self) -> None:
        state = pending(Side.SELL, limit=1.1005, sl=1.1010, tp=1.0980)
        w = await_fill(
            state, [bar(0, 1.1000, 1.1005, 1.0999, 1.1003)], window_end=T0 + timedelta(minutes=5), slippage=0
        )
        assert w.filled

    def test_only_a_stop_counts_on_the_fill_bar(self) -> None:
        state = pending()
        w = await_fill(
            state,
            [bar(0, 1.1000, 1.1030, 1.0985, 1.1000)],
            window_end=T0 + timedelta(minutes=5),
            slippage=0.00001,
        )
        assert w.filled and w.exit is not None
        assert w.exit.reason is ExitReason.STOP_LOSS and w.exit.price == pytest.approx(1.0990 - 0.00001)

    def test_resolution_continues_after_the_fill_bar(self) -> None:
        state = pending()
        bars = [bar(0, 1.1000, 1.1025, 1.0993, 1.1000), bar(1, 1.1000, 1.1025, 1.0999, 1.1020)]
        w = await_fill(state, bars, window_end=T0 + timedelta(minutes=5), slippage=0)
        assert w.filled and w.exit is None  # the TP on the fill bar may have come before the fill
        exit_ = advance(state, bars, slippage=0)
        assert exit_ is not None and exit_.reason is ExitReason.TAKE_PROFIT and exit_.at == bars[1].open_time

    def test_missed_at_the_end_of_the_window(self) -> None:
        state = pending()
        bars = [bar(i, 1.1000, 1.1002, 1.0998, 1.1000) for i in range(6)]
        w = await_fill(state, bars, window_end=T0 + timedelta(minutes=4), slippage=0)
        assert (w.filled, w.missed) == (False, True) and state.cursor == bars[4].open_time

    def test_still_waiting_when_the_bars_end(self) -> None:
        state = pending()
        w = await_fill(
            state, [bar(0, 1.1000, 1.1002, 1.0998, 1.1000)], window_end=T0 + timedelta(minutes=4), slippage=0
        )
        assert (w.filled, w.missed) == (False, False) and state.cursor == T0 + timedelta(minutes=1)
        # a later pass resumes from the cursor (bars before it are skipped)
        again = await_fill(
            state,
            [bar(0, 1.0, 1.0, 0.9, 1.0), bar(1, 1.1, 1.1, 1.0991, 1.1)],
            window_end=T0 + timedelta(minutes=4),
            slippage=0,
        )
        assert again.filled and state.entry_at == T0 + timedelta(minutes=1)
