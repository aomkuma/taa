"""The signal at the level that confirms an armed AI order (app/strategy/confirm.py; owner 2026-10-26: "wait for a
signal at the level"; "candlestick patterns confirm on 15 minutes to 1 hour; a price structure is read on M1,
bar after bar, until it matches the pattern"). Every bar below is worked by hand: 14 calm bars before the touch
(range 2, volume 100) set the ATR near 2, so the level band (0.1 ATR) is about 0.2."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from app.core.enums import Side
from app.strategy import confirm as cf
from app.strategy.ai_lane import AIOrder, AITrader

T = datetime(2026, 7, 8, 1, 0, tzinfo=UTC)  # 08:00 Thai; the touch bar opens at T (on every frame's boundary)
Row = tuple[float, float, float, float, float]  # open, high, low, close, tick volume
CALM: Row = (4100.0, 4101.0, 4099.0, 4100.0, 100.0)


def bars(rows: list[Row], minutes: int, calm: Row = CALM) -> pd.DataFrame:
    """14 calm bars before T, then ``rows`` from T, ``minutes`` apart."""
    allr = [calm] * 14 + rows
    idx = pd.date_range(T - timedelta(minutes=minutes * 14), periods=len(allr), freq=f"{minutes}min")
    return pd.DataFrame(allr, index=idx, columns=["open", "high", "low", "close", "tick_volume"])


def m1_from(frame: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """M1 bars that aggregate back to ``frame``: open -> high, -> low, -> close, then flat at the close."""
    out = []
    for t, (o, h, lo, c, v) in frame.iterrows():
        path = [(o, h, o, o), (o, o, lo, lo), (lo, c, lo, c)] + [(c, c, c, c)] * (minutes - 3)
        for i, (oo, hh, ll, cc) in enumerate(path):
            out.append((t + timedelta(minutes=i), oo, max(oo, hh, cc), min(oo, ll, cc), cc, v / minutes))
    return pd.DataFrame(out, columns=["t", "open", "high", "low", "close", "tick_volume"]).set_index("t")


# two M5 bars as M1 bars: bar 0 runs past 4105 on volume 150 and closes over it, bar 1 closes back under
SWEEP = m1_from(
    bars([(4104.8, 4105.6, 4104.7, 4105.3, 150.0), (4105.3, 4105.4, 4104.4, 4104.5, 100.0)], 5), 5
)


# --- the price structure on M5 (owner 2026-10-26: "enter on M5 instead of M1") ---


def test_a_sweep_and_close_back_on_m5():
    # bar 0 runs to 4105.6 (past 4105 + 0.2) on volume 150 (> the mean 100) and closes 4105.3, still over the
    # level: not yet; bar 1 closes 4104.5 back under it: the sweep is complete
    b0, b1 = (4104.8, 4105.6, 4104.7, 4105.3, 150.0), (4105.3, 4105.4, 4104.4, 4104.5, 100.0)
    assert cf.structure_signal(bars([b0], 5), T, 4105.0, True, "limit") is None
    assert cf.structure_signal(bars([b0, b1], 5), T, 4105.0, True, "limit") == "sweep"
    quiet = (*b0[:4], 100.0)  # the same path on ordinary volume: not a sweep
    assert cf.structure_signal(bars([quiet, b1], 5), T, 4105.0, True, "limit") is None


def test_a_double_top_on_m5_confirms_when_the_neckline_breaks():
    # push 4105.0 (b0), pullback low 4103.0 (b1), second push 4104.4 (b2: no higher, more than half way back up
    # from 4103 toward 4105), then a close 4102.7 under the 4103.0 neckline (b3)
    b0 = (4103.5, 4105.0, 4103.2, 4104.6, 100.0)
    b1 = (4104.6, 4104.7, 4103.0, 4103.6, 100.0)
    b2 = (4103.6, 4104.4, 4103.5, 4104.2, 100.0)
    b3 = (4104.2, 4104.3, 4102.5, 4102.7, 100.0)
    assert cf.structure_signal(bars([b0, b1, b2], 5), T, 4105.0, True, "limit") is None
    assert cf.structure_signal(bars([b0, b1, b2, b3], 5), T, 4105.0, True, "limit") == "double"
    higher = (4103.6, 4105.3, 4103.5, 4104.2, 100.0)  # a second push over the first: not an M
    assert cf.structure_signal(bars([b0, b1, higher, b3], 5), T, 4105.0, True, "limit") is None
    held = (4104.2, 4104.3, 4103.2, 4103.4, 100.0)  # after the second push a close 4103.4, over the neckline
    assert cf.structure_signal(bars([b0, b1, b2, held], 5), T, 4105.0, True, "limit") is None
    shallow = (4103.6, 4103.8, 4103.5, 4103.7, 100.0)  # back up only 0.8 of 2.0: not a second push
    assert cf.structure_signal(bars([b0, b1, shallow, b3], 5), T, 4105.0, True, "limit") is None


def test_a_break_needs_an_m5_close_through():
    # a sell stop under 4100: b0 trades to 4099.4 but closes 4100.2, over the level - a tick through is not a
    # break; b1 closes 4099.3 under it: the break. (The retest once required missed 2 of 5 winning sell stops.)
    b0, b1 = (4101.0, 4101.2, 4099.4, 4100.2, 100.0), (4100.2, 4100.4, 4099.0, 4099.3, 100.0)
    assert cf.structure_signal(bars([b0], 5), T, 4100.0, True, "stop") is None
    assert cf.structure_signal(bars([b0, b1], 5), T, 4100.0, True, "stop") == "break"
    at = (4100.2, 4100.4, 4099.0, 4100.0, 100.0)  # a close at the level, not through it
    assert cf.structure_signal(bars([b0, at], 5), T, 4100.0, True, "stop") is None


def test_a_buy_structure_is_the_mirror():
    b0, b1 = (4099.0, 4100.6, 4098.8, 4100.4, 100.0), (4100.4, 4101.0, 4100.0, 4100.7, 100.0)
    # a buy stop over 4100: b0 closes 4100.4 over it
    assert cf.structure_signal(bars([b0, b1], 5), T, 4100.0, False, "stop") == "break"
    assert (
        cf.structure_signal(bars([(4099.0, 4100.6, 4098.8, 4099.9, 100.0)], 5), T, 4100.0, False, "stop")
        is None
    )
    s0, s1 = (4095.2, 4095.3, 4094.4, 4094.7, 150.0), (4094.7, 4095.6, 4094.6, 4095.5, 100.0)
    assert (
        cf.structure_signal(bars([s0, s1], 5), T, 4095.0, False, "limit") == "sweep"
    )  # under 4095, back over


# --- candlestick patterns on M15 / M30 / H1 ---

PIN: Row = (4104.0, 4105.5, 4103.5, 4103.8, 100.0)  # at 4105: wick 1.5 of 2.0, a down bar closing under


def test_a_pin_bar_at_the_level():
    assert cf.candle_signal(bars([PIN], 15), T, 15, 4105.0, True) == "pin"
    up = (4103.0, 4105.1, 4102.8, 4104.9, 100.0)  # reached the level, closed up near it: nothing
    assert cf.candle_signal(bars([up], 15), T, 15, 4105.0, True) is None
    wick_up = (4103.5, 4105.5, 4103.4, 4103.9, 100.0)  # a long upper wick (1.6 of 2.1) but an UP bar: no pin
    assert cf.candle_signal(bars([wick_up], 15), T, 15, 4105.0, True) is None
    buy = (4096.0, 4096.5, 4094.5, 4096.2, 100.0)  # at 4095: lower wick 1.5 of 2.0, an up bar closing over
    assert cf.candle_signal(bars([buy], 60), T, 60, 4095.0, False) == "pin"


def test_an_engulfing_bar_at_the_level():
    # bar 1 up to 4105.0 (in the band), bar 2 opens 4104.9 (>= bar 1's close 4104.8) and closes 4102.7 (<= its
    # open 4103): its body covers bar 1's; no pin (upper wick 0.1 of 2.5)
    b1, b2 = (4103.0, 4105.0, 4102.9, 4104.8, 100.0), (4104.9, 4105.0, 4102.5, 4102.7, 100.0)
    assert cf.candle_signal(bars([b1, b2], 30), T, 30, 4105.0, True) == "engulfing"
    assert cf.candle_signal(bars([b1], 30), T, 30, 4105.0, True) is None
    small = (4104.7, 4105.0, 4103.5, 4103.6, 100.0)  # opens under bar 1's close: its body does not cover it
    assert cf.candle_signal(bars([b1, small], 30), T, 30, 4105.0, True) is None


def test_signal_reads_the_m5_structure_first_then_the_candles_on_complete_bars_only():
    m1 = m1_from(bars([PIN], 15), 15)  # the pin as an M15 bar, made of M1 bars that hold no M5 structure
    touched = T + timedelta(minutes=1)
    assert cf.complete(m1, T + timedelta(minutes=14), 15).index[-1] == T - timedelta(minutes=15)  # forming
    assert cf.signal(m1, T + timedelta(minutes=14), touched, 4105.0, True, "limit") is None
    assert cf.signal(m1, T + timedelta(minutes=15), touched, 4105.0, True, "limit") == "M15 pin"
    # a stop order reads no candles: a sell stop at 4103.0 - the pin is there but no M5 bar closed under 4103
    assert cf.signal(m1, T + timedelta(minutes=15), touched, 4103.0, True, "stop") is None
    assert cf.signal(SWEEP, T + timedelta(minutes=10), T, 4105.0, True, "limit") == "M5 sweep"
    assert cf.signal(SWEEP, T + timedelta(minutes=9), T, 4105.0, True, "limit") is None  # bar 1 not closed


# --- the strategy: armed on the touch, filled after the signal ---


def order(**over: object) -> AIOrder:
    base: dict[str, object] = {
        "side": Side.SELL, "entry": 4105.0, "stop": 4112.0, "target": 4090.0, "risk_scale": 0.5, "setup": "plan A",
        "reasons": (), "kb_ids": (), "confidence": 60, "decided_at": T - timedelta(minutes=30),
        "valid_until": T + timedelta(hours=2), "key": "plan-A",
    }  # fmt: skip
    base.update(over)
    return AIOrder(**base)  # type: ignore[arg-type]


def test_the_strategy_arms_on_the_touch_and_fills_after_the_signal():
    s = AITrader()
    s.set_plan_orders("XAUUSD", [order()])
    assert s.on_quote("XAUUSD", T - timedelta(minutes=5), 4100.0, 4100.3) is None  # a limit above the price
    assert s.confirm_orders("XAUUSD", SWEEP, T + timedelta(minutes=10)) == []  # not touched: nothing counts
    # the touch: armed, no fill
    assert s.on_quote("XAUUSD", T + timedelta(seconds=20), 4105.2, 4105.5) is None
    assert s.on_quote("XAUUSD", T + timedelta(seconds=40), 4105.4, 4105.7) is None
    assert s.confirm_orders("XAUUSD", SWEEP, T + timedelta(minutes=5)) == []  # closed 4105.3: not back yet
    assert s.confirm_orders("XAUUSD", SWEEP, T + timedelta(minutes=9)) == []  # M5 bar 1 not closed yet
    assert s.confirm_orders("XAUUSD", SWEEP, T + timedelta(minutes=10)) == [("plan-A", "M5 sweep")]
    assert s.confirmation("plan-A") == "M5 sweep"
    # after the signal: 4,101.0 is 4.0 under the entry, more than half the 7-USD stop distance (3.5) - no chase
    assert s.on_quote("XAUUSD", T + timedelta(minutes=10, seconds=5), 4101.0, 4101.3) is None
    e = s.on_quote("XAUUSD", T + timedelta(minutes=10, seconds=9), 4104.4, 4104.7)  # 0.6 under: fills
    assert e is not None and e.price == 4104.4 and e.order.key == "plan-A"


def test_an_armed_order_whose_stop_is_reached_is_dropped():
    s = AITrader()
    s.accept("XAUUSD", order(key="w"))
    assert s.on_quote("XAUUSD", T, 4105.1, 4105.4) is None  # armed
    assert s.on_quote("XAUUSD", T + timedelta(minutes=2), 4111.8, 4112.1) is None  # the ask reached the stop
    assert s.pending("XAUUSD") is None


def test_only_a_buy_or_sell_decision_may_be_a_market_order():
    # 07-08 13:15: a wait order at 4,132.50 filled 0.95 worse as 'market'; now it is a limit waiting at 4,132.50
    s = AITrader()
    s.accept("XAUUSD", order(key="w", entry=4132.5, stop=4138.7, target=4122.5))
    assert s.on_quote("XAUUSD", T, 4131.55, 4131.85) is None
    assert s.kind_of(s.pending("XAUUSD"), 0.0, 0.0) == "limit"  # type: ignore[arg-type]
    d = AITrader()
    d.accept("XAUUSD", order(key="d", entry=4132.5, stop=4138.7, target=4122.5, direct=True))
    e = d.on_quote("XAUUSD", T, 4131.55, 4131.85)  # the AI's own entry at the bar close: market within 1.0
    assert e is not None and e.price == 4131.55


def test_a_confirmed_fill_keeps_the_5_usd_take_profit_and_the_r_floor():
    # 07-08 07:10: a confirmed fill 2.6 under its 4,102.40 entry left a 3.88 USD target. Entry 4105, stop 4112,
    # target 4099: at 4104.4 the target is 5.4 away (>= 5 and >= 0.2 x 7.6) - fills; at 4103.8 it is 4.8 - waits
    s = AITrader(AITrader.Params(min_take_profit=5.0))
    s.set_plan_orders("XAUUSD", [order(target=4099.0)])
    assert s.on_quote("XAUUSD", T - timedelta(minutes=5), 4100.0, 4100.3) is None
    assert s.on_quote("XAUUSD", T + timedelta(seconds=20), 4105.2, 4105.5) is None  # armed
    assert s.confirm_orders("XAUUSD", SWEEP, T + timedelta(minutes=10)) == [("plan-A", "M5 sweep")]
    assert s.on_quote("XAUUSD", T + timedelta(minutes=10, seconds=1), 4103.8, 4104.1) is None  # 4.8 to target
    e = s.on_quote("XAUUSD", T + timedelta(minutes=10, seconds=2), 4104.4, 4104.7)
    assert e is not None and e.price == 4104.4
