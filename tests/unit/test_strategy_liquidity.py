"""The liquidity map (app/strategy/liquidity.py, TAA-1807; owner 2026-10-24: "find the liquidation zones").
Every number below is worked by hand on small frames."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.strategy import liquidity as lq
from app.strategy.liquidity import Pool


def frame(start: str, minutes: int, highs: list[float], lows: list[float], vol: float = 10.0) -> pd.DataFrame:
    t = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=len(highs), freq=f"{minutes}min")
    h, lo = np.array(highs), np.array(lows)
    return pd.DataFrame(
        {"open": (h + lo) / 2, "high": h, "low": lo, "close": (h + lo) / 2, "tick_volume": vol}, index=t
    )


def test_atr_is_the_mean_true_range():
    h, lo, c = np.array([10.0, 12.0, 11.0]), np.array([9.0, 10.0, 8.0]), np.array([9.5, 11.0, 9.0])
    # true ranges: 1 (first bar), max(2, |12-9.5|, |10-9.5|) = 2.5, max(3, |11-11|, |8-11|) = 3
    assert lq.atr(h, lo, c, n=3) == pytest.approx((1 + 2.5 + 3) / 3)


def test_closed_keeps_only_bars_closed_by_the_time():
    m5 = frame("2026-07-08T07:00", 5, [1, 2, 3], [0, 1, 2])
    assert len(lq.closed(m5, 5, pd.Timestamp("2026-07-08T07:10", tz="UTC"))) == 2  # 07:10 bar still forming
    assert len(lq.closed(m5, 5, pd.Timestamp("2026-07-08T07:15", tz="UTC"))) == 3


def test_taken_after_looks_only_from_the_start_bar():
    h, lo = np.array([5.0, 4.0, 6.0]), np.array([1.0, 2.0, 0.5])
    assert lq.taken_after(5.5, True, h, lo, 1) is True  # bar 2 traded over 5.5
    assert lq.taken_after(6.5, True, h, lo, 0) is False
    assert lq.taken_after(0.8, False, h, lo, 2) is True and lq.taken_after(0.8, False, h, lo, 3) is False


def test_round_numbers_around_the_price():
    assert [p.price for p in lq.rounds(4120.63)] == [4100.0, 4150.0]
    assert [p.price for p in lq.rounds(4150.0)] == [4150.0, 4200.0]


def test_volume_nodes_spread_each_bar_over_its_steps():
    as_of = pd.Timestamp("2026-07-08T07:03", tz="UTC")
    # bar 1 (4120-4124, 10 ticks) covers the 5-USD step 4120 only; bar 2 (4123-4127, 30) the steps 4120 and
    # 4125, 15 each; bar 3 (4126-4128, 20) step 4125: 4120 -> 25, 4125 -> 35 of 60
    m1 = frame("2026-07-08T07:00", 1, [4124, 4127, 4128], [4120, 4123, 4126])
    m1["tick_volume"] = [10.0, 30.0, 20.0]
    assert lq.volume_nodes(m1, as_of, bucket=5.0) == [
        (4125.0, pytest.approx(35 / 60)),
        (4120.0, pytest.approx(25 / 60)),
    ]
    assert lq.volume_nodes(m1, as_of - pd.Timedelta(minutes=3), bucket=5.0) == []  # nothing closed yet


def test_a_stop_goes_past_the_structure_and_a_pool_just_beyond_it():
    a = 4.0  # reach 0.5 x 4 = 2, buffer 1.0 x 4 = 4
    pools = [Pool(4135.5, "tops", False), Pool(4140.0, "round", False), Pool(4118.0, "bottoms", False)]
    # price well under the top 4134: the pool 4135.5 is within 2 beyond it -> past it; 4140 is 4.5 past that
    assert lq.beyond(4134.0, 4120.0, pools, a, up=True) == pytest.approx(4139.5)
    # no pool within reach under the bottom 4121 (4118 is 3 away): just the buffer
    assert lq.beyond(4121.0, 4130.0, pools, a, up=False) == pytest.approx(4117.0)


def test_at_the_edge_the_stop_goes_past_the_next_untaken_pool():
    # 2026-07-08 18:44: price 4058.34 at the 2-hour top 4058.38; the M15 equal tops 4061.08 beyond (2.70 > the
    # 2.53 reach): the stop goes past them too; a taken pool does not count
    a = 5.05
    pools = [
        Pool(4061.08, "M15 equal tops x2", False),
        Pool(4060.0, "taken", True),
        Pool(4092.2, "far", False),
    ]
    assert lq.beyond(4058.38, 4058.34, pools, a, up=True) == pytest.approx(4061.08 + 5.05, abs=0.006)
    far = lq.beyond(4058.38, 4040.0, pools, a, up=True)  # price far from the edge: the buffer only
    assert far == pytest.approx(4058.38 + 5.05, abs=0.006)


def test_structure_is_two_hours_of_m5():
    highs = [4100.0 + i for i in range(30)]  # rising tops 4100 .. 4129
    lows = [h - 3 for h in highs]
    m5 = frame("2026-07-08T05:00", 5, highs, lows)
    as_of = pd.Timestamp("2026-07-08T07:30", tz="UTC")  # 30 bars closed
    st = lq.structure(m5, as_of, 4128.0, [])
    assert st is not None
    # the last 24 bars: highs 4106 .. 4129, lows 4103 .. 4126; the close mid-bar (high - 1.5), so the true
    # range is max(3, |high - (high - 2.5)|, |low - (high - 2.5)|) = 3; price 4128 is within 1.5 (0.5 ATR) of
    # the top but no pool lies beyond it: the buffer 3 (1.0 ATR) only
    assert (st.top, st.bottom) == (4129.0, 4103.0)
    assert st.atr_m5 == pytest.approx(3.0)
    assert st.sell_stop == pytest.approx(4132.0) and st.buy_stop == pytest.approx(4100.0)
    # an hour of bars is enough (Monday 07:00 Thai has 23 since the open, ISSUES 15); 11 are not
    assert lq.structure(m5, pd.Timestamp("2026-07-08T06:00", tz="UTC"), 4110.0, []) is not None  # 12 bars
    assert lq.structure(m5, pd.Timestamp("2026-07-08T05:55", tz="UTC"), 4110.0, []) is None  # 11 bars


def test_pools_list_the_days_levels_and_yesterday():
    # the Thai day starts 05:00 Thai = 22:00 UTC; M15 bars from 22:00: a swing high 4110 at 22:15, a swing low
    # 4090 at 22:45, later a bar over 4110 (the swing high taken)
    m15 = frame(
        "2026-07-07T22:00", 15, [4100, 4110, 4100, 4095, 4105, 4112], [4095, 4100, 4096, 4090, 4097, 4104]
    )
    d1 = frame("2026-07-06T00:00", 1440, [4150.0], [4080.0])
    got = {p.kind: p for p in lq.pools(m15.iloc[:0], m15, d1, pd.Timestamp("2026-07-08T00:00", tz="UTC"))}
    assert got["M15 swing high 05:15"].price == 4110.0 and got["M15 swing high 05:15"].taken is True
    assert got["M15 swing low 05:45"].price == 4090.0 and got["M15 swing low 05:45"].taken is False
    assert (got["the day's high"].price, got["the day's low"].price) == (4112.0, 4090.0)
    assert (got["yesterday's high"].price, got["yesterday's low"].price) == (4150.0, 4080.0)
    assert not any("Asia" in k for k in got)  # 07:00 Thai: London has not opened yet


def test_the_map_reads_like_the_ai_gets_it():
    as_of = pd.Timestamp("2026-07-08T07:00", tz="UTC")
    m1 = frame("2026-07-08T06:00", 1, [4101.0] * 60, [4099.0] * 60)
    m5 = frame("2026-07-08T05:00", 5, [4102.0] * 24, [4098.0] * 24)
    h1 = frame("2026-07-07T16:00", 60, [4105.0] * 15, [4095.0] * 15)  # ATR 10: pools within 30 listed
    d1 = frame("2026-07-06T00:00", 1440, [4140.0], [4060.0])
    lines = lq.liquidity_lines(m1, m5, h1.iloc[:0], h1, d1, as_of)
    assert lines[0] == "price 4100.00"
    # flat M5 bars make equal tops 4102 / bottoms 4098 (22 touches); yesterday's 4140 / 4060 are 40 away (> 30)
    assert lines[1] == "above (a SELL's stop side, not targets): 4102.00 M5 equal tops x22 +2.00"
    assert lines[2] == (
        "below (a BUY's stop side, not targets): 4100.00 round number +0.00 | 4098.00 M5 equal bottoms x22 -2.00"
    )
    assert lines[3] == "volume nodes (24 h, tick volume by price): 4095-4100 50%, 4100-4105 50%"
    # M5 ATR 4 (reach 2, buffer 4); price 4100 stands 2 from the top 4102 and the bottom 4098 - at both edges:
    # each stop goes through the volume bands (4100-4105 above, 4095-4100 below) and 4 past them
    assert lines[4] == (
        "the structure (2 h of M5): top 4102.00, bottom 4098.00; a SELL's stop beyond it 4109.00, "
        "a BUY's stop beyond it 4091.00 (M5 ATR 4.00)"
    )
    # ISSUES 31: the zones the stops pass are named (the band ends 4105 / 4095, inside the 2-ATR cap of 8)
    assert lines[5] == (
        "the liquidate zones those stops pass: above 4102.00 up to 4105.00, below 4098.00 down to 4095.00, "
        "then 1 M5 ATR"
    )
    # no take-profit line: the liquidate zones are for the stop; the take-profit follows P09 / C5 (owner 10-25)
    assert len(lines) == 6
    st = lq.structure_now(m1, m5, h1.iloc[:0], d1, h1, as_of)
    assert st is not None and (st.sell_stop, st.buy_stop) == (4109.0, 4091.0)  # the same as the map's line
    assert (st.sell_zone, st.buy_zone) == (4105.0, 4095.0)
    assert lq.liquidity_lines(m1.iloc[:0], m5, h1, h1, d1, as_of) == [
        "(not enough bars for the liquidity map)"
    ]


def test_the_stop_goes_through_a_volume_band_and_along_a_chain_of_pools():
    # 2026-07-08 14:05 shape: the busiest step 4125-4130 starts 1 over a top of 4124 (reach 2): the stop goes
    # through the whole band, 4130 + 4 (1.0 ATR) - past the liquidation zone, not into it
    a = 4.0

    def up(bands: list[tuple[float, float]]) -> float:
        return lq.beyond(4124.0, 4115.0, [], a, up=True, bands=bands)

    assert up([(4125.0, 4130.0)]) == pytest.approx(4134.0)
    assert up([(4127.0, 4132.0)]) == pytest.approx(4128.0)  # starts 3 away: out of reach
    assert up([(4120.0, 4125.0)]) == pytest.approx(4129.0)  # the band holds the top
    # pools chain: 4125.5 is 1.5 past the top, 4127 is 1.5 past that one; 4130 is 3 past 4127: not taken in
    chain = [Pool(4125.5, "tops", False), Pool(4127.0, "swing", False), Pool(4130.0, "round", False)]
    assert lq.beyond(4124.0, 4115.0, chain, a, up=True) == pytest.approx(4131.0)
    # a buy's stop through a band under the bottom
    assert lq.beyond(4100.0, 4110.0, [], a, up=False, bands=[(4095.0, 4099.0)]) == pytest.approx(4091.0)


def test_off_the_bar_marks_a_forming_bar_is_left_out():
    m5 = frame("2026-07-08T07:00", 5, [1, 2, 3], [0, 1, 2])
    # 07:12: the 07:00 and 07:05 bars have closed (07:05 closed at 07:10); the 07:10 bar is still forming
    assert len(lq.closed(m5, 5, pd.Timestamp("2026-07-08T07:12", tz="UTC"))) == 2


def test_yesterday_is_the_last_closed_d1_bar_not_todays():
    m15 = frame("2026-07-07T22:00", 15, [4100, 4110, 4100], [4095, 4100, 4096])
    # the D1 bar of 07-07 closed at 07-08 00:00; the 07-08 bar is forming at 07-08 01:00
    d1 = frame("2026-07-07T00:00", 1440, [4150.0, 4199.0], [4080.0, 4001.0])
    got = {p.kind: p for p in lq.pools(m15.iloc[:0], m15, d1, pd.Timestamp("2026-07-08T01:00", tz="UTC"))}
    assert (got["yesterday's high"].price, got["yesterday's low"].price) == (4150.0, 4080.0)


def test_a_swing_is_taken_by_the_first_bar_that_trades_through_it():
    # a swing high 4110 at 05:15 (bar 1); bar 3 (05:45) trades 4111 - the first bar that can (bar 2 makes the swing)
    m15 = frame("2026-07-07T22:00", 15, [4100, 4110, 4105, 4111, 4101], [4095, 4100, 4096, 4100, 4096])
    d1 = frame("2026-07-06T00:00", 1440, [4150.0], [4080.0])
    got = {p.kind: p for p in lq.pools(m15.iloc[:0], m15, d1, pd.Timestamp("2026-07-08T00:00", tz="UTC"))}
    assert got["M15 swing high 05:15"].taken is True


def test_at_the_edge_only_a_near_pool_joins_the_zone():
    # ISSUES 33 (07-08 07:25): price at the 2-hour top; the code jumped to the first untaken pool beyond however
    # far it was and chained on, to a stop 48 USD over a 4,105.84 sell. Now the next pool joins only within
    # EDGE_JUMP_ATR (1.0 ATR). M5 ATR 4: jump 4, reach 2, buffer 4, cap 8
    a = 4.0

    def up(pool: float) -> tuple[float, float]:
        return lq.beyond_zone(4110.0, 4109.5, [Pool(pool, "tops", False)], a, up=True)

    assert up(4118.0) == (4114.0, 4110.0)  # 8 away (2 ATR): not part of the zone; the buffer past the edge
    assert up(4114.0) == (4118.0, 4114.0)  # exactly 1 ATR: joins
    assert up(4114.01) == (4114.0, 4110.0)  # just over 1 ATR: does not
    # a buy at the bottom 4000 (price 4000.5): 3997 is 3 under (0.75 ATR) - joins; 3994 is 6 - does not
    assert lq.beyond_zone(4000.0, 4000.5, [Pool(3997.0, "bottoms", False)], a, up=False) == (3993.0, 3997.0)
    assert lq.beyond_zone(4000.0, 4000.5, [Pool(3994.0, "bottoms", False)], a, up=False) == (3996.0, 4000.0)


def test_the_zone_ends_two_atr_past_the_structure():
    # a chain of pools 1.5 apart (each within the 2 reach of the last) runs 10.5 past the top 4100; the zone
    # stops at 4100 + 2 x 4 = 4108 and the stop is 4 past that: 4112 (not 4114.5)
    a = 4.0
    chain = [Pool(4100.0 + 1.5 * k, f"p{k}", False) for k in range(1, 8)]  # 4101.5 .. 4110.5
    assert lq.beyond_zone(4100.0, 4090.0, chain, a, up=True) == (4112.0, 4108.0)
    down = [Pool(4000.0 - 1.5 * k, f"p{k}", False) for k in range(1, 8)]  # 3998.5 .. 3989.5
    assert lq.beyond_zone(4000.0, 4010.0, down, a, up=False) == (3988.0, 3992.0)
    # a volume band 4101-4130 starts within reach: through it, but the zone still ends at 4108
    assert lq.beyond_zone(4100.0, 4090.0, [], a, up=True, bands=[(4101.0, 4130.0)]) == (4112.0, 4108.0)
    # beyond() is the stop of beyond_zone()
    assert lq.beyond(4100.0, 4090.0, chain, a, up=True) == 4112.0


def test_the_forming_m5_bar_is_part_of_the_structure():
    # 07-07 19:09: a sell at 4,166.48 after price broke over the 2-hour top 4,159.85 inside the M5 bar not yet
    # closed; the 'stop past the top' (4,164.46) sat under the entry. The closed M1 bars of that bar count.
    m5 = frame("2026-07-08T05:00", 5, [4102.0] * 24, [4098.0] * 24)  # closed by 07:00
    m1 = frame(
        "2026-07-08T06:57",
        1,
        [4101.0, 4101.0, 4101.0, 4103.0, 4107.0, 4105.0],
        [4099.0] * 3 + [4100.0, 4104.0, 4097.0],
    )
    as_of = pd.Timestamp("2026-07-08T07:03", tz="UTC")
    # 06:57-06:59 belong to the closed 06:55 M5 bar; 07:00, 07:01, 07:02 are closed by 07:03: high 4107, low 4097
    assert lq.forming(m1, m5, as_of) == (4107.0, 4097.0)
    assert (
        lq.forming(m1, m5, pd.Timestamp("2026-07-08T07:00", tz="UTC")) is None
    )  # no M1 bar of it closed yet
    st = lq.structure(m5, as_of, 4106.0, [], (), lq.forming(m1, m5, as_of))
    assert st is not None and (st.top, st.bottom) == (4107.0, 4097.0)
    # M5 ATR 4: price 4106 within 2 of the top - no pool beyond; the sell's stop 4107 + 4, never under price
    assert st.sell_stop == pytest.approx(4111.0) and st.buy_stop == pytest.approx(4093.0)
    plain = lq.structure(m5, as_of, 4106.0, [])
    assert plain is not None and plain.sell_stop == pytest.approx(4106.0)  # the old reading: at the price
