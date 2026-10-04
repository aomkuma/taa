"""Shadow-trade resolution, costs and results (pure core; TAA-6C1)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.advisory.shadow import (
    Flag,
    Management,
    ShadowState,
    TickRow,
    advance,
    bars_from_frame,
    entry_fill,
    new_state,
    rollover_days,
    settle,
)
from app.config import PositionManagementConfig
from app.core.enums import ExitReason, Side
from app.execution.fill_model import Bar

T0 = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)  # Wednesday
SPREAD = 0.0002
SLIP = 0.00001
ATHENS = ZoneInfo("Europe/Athens")


def bar(minute: int, o: float, h: float, lo: float, c: float, spread: float = SPREAD) -> Bar:
    start = T0 + timedelta(minutes=minute)
    return Bar(start, start + timedelta(minutes=1), o, h, lo, c, spread)


def flat(minute: int, price: float = 1.1000) -> Bar:
    return bar(minute, price, price + 0.0001, price - 0.0001, price)


def buy(entry: float = 1.1000, sl: float = 1.0950, tp: float | None = 1.1100, **kw: object) -> ShadowState:
    at = kw.pop("at", T0)
    assert isinstance(at, datetime)
    return new_state(side=Side.BUY, entry=entry, entry_at=at, sl=sl, tp=tp, time_stop=timedelta(hours=72))


def sell(entry: float = 1.1000, sl: float = 1.1050, tp: float | None = 1.0900) -> ShadowState:
    return new_state(side=Side.SELL, entry=entry, entry_at=T0, sl=sl, tp=tp, time_stop=timedelta(hours=72))


def ticks_of(rows: Sequence[TickRow]):  # type: ignore[no-untyped-def]
    calls: list[tuple[datetime, datetime]] = []

    def source(start: datetime, end: datetime) -> list[TickRow]:
        calls.append((start, end))
        return [r for r in rows if start <= r[0] < end]

    source.calls = calls  # type: ignore[attr-defined]
    return source


class TestEntry:
    def test_buy_at_the_ask_sell_at_the_bid_slippage_adverse(self) -> None:
        assert entry_fill(Side.BUY, 1.1000, 1.1002, SLIP) == pytest.approx(1.10021)
        assert entry_fill(Side.SELL, 1.1000, 1.1002, SLIP) == pytest.approx(1.09999)

    def test_new_state_starts_at_the_entry_minute(self) -> None:
        s = buy(at=T0 + timedelta(seconds=30))
        assert s.cursor == T0 and s.deadline == T0 + timedelta(hours=72, seconds=30)
        assert s.risk == pytest.approx(0.0050) and s.sl == s.initial_sl


class TestPlan:
    def test_take_profit(self) -> None:
        s = buy()
        bars = [flat(0), bar(1, 1.1000, 1.1101, 1.0990, 1.1090)]
        ex = advance(s, bars, slippage=SLIP)
        assert ex is not None and ex.reason is ExitReason.TAKE_PROFIT and ex.price == 1.1100
        assert ex.at == T0 + timedelta(minutes=1)
        assert s.mfe == pytest.approx(0.0100) and s.mae == pytest.approx(0.0010)  # the TP bar's low counts

    def test_stop_loss_with_slippage(self) -> None:
        s = buy()
        ex = advance(s, [flat(0), bar(1, 1.0990, 1.0995, 1.0949, 1.0960)], slippage=SLIP)
        assert ex is not None and ex.reason is ExitReason.STOP_LOSS
        assert ex.price == pytest.approx(1.0950 - SLIP) and s.mae == pytest.approx(0.0050 + SLIP)

    def test_sell_exits_on_the_ask(self) -> None:
        s = sell()
        # bid high 1.1049 + spread 0.0002 = ask 1.1051 >= SL 1.1050
        ex = advance(s, [bar(0, 1.1000, 1.1049, 1.0995, 1.1000)], slippage=SLIP)
        assert (
            ex is not None and ex.reason is ExitReason.STOP_LOSS and ex.price == pytest.approx(1.1050 + SLIP)
        )
        s = sell()
        # bid low 1.0899 + spread = ask 1.0901 > TP 1.0900: not reached
        assert advance(s, [bar(0, 1.1000, 1.1001, 1.0899, 1.0950)], slippage=SLIP) is None
        ex = advance(s, [bar(1, 1.0950, 1.0951, 1.0897, 1.0900)], slippage=SLIP)
        assert ex is not None and ex.reason is ExitReason.TAKE_PROFIT and ex.price == 1.0900

    def test_gap_through_the_stop_fills_at_the_open(self) -> None:
        s = buy()
        ex = advance(s, [flat(0), bar(1, 1.0900, 1.0910, 1.0890, 1.0905)], slippage=SLIP)
        assert ex is not None and ex.reason is ExitReason.STOP_LOSS
        assert ex.price == pytest.approx(1.0900 - SLIP) and Flag.GAP in s.flags

    def test_gap_beyond_the_take_profit_never_fills_better(self) -> None:
        s = buy()
        ex = advance(s, [flat(0), bar(1, 1.1150, 1.1160, 1.1140, 1.1155)], slippage=SLIP)
        assert ex is not None and ex.reason is ExitReason.TAKE_PROFIT and ex.price == 1.1100

    def test_time_stop_at_the_first_open_after_the_deadline(self) -> None:
        s = new_state(
            side=Side.BUY, entry=1.1, entry_at=T0, sl=1.095, tp=1.11, time_stop=timedelta(minutes=3)
        )
        bars = [flat(0), flat(1), flat(2), bar(3, 1.1010, 1.1011, 1.1009, 1.1010)]
        ex = advance(s, bars, slippage=SLIP)
        assert ex is not None and ex.reason is ExitReason.TIME_STOP
        assert ex.at == T0 + timedelta(minutes=3) and ex.price == pytest.approx(1.1010 - SLIP)

    def test_weekend_gap_closes_at_monday_open(self) -> None:
        s = new_state(side=Side.BUY, entry=1.1, entry_at=T0, sl=1.095, tp=1.11, time_stop=timedelta(hours=1))
        monday = T0 + timedelta(days=5)
        late = Bar(monday, monday + timedelta(minutes=1), 1.1020, 1.1030, 1.1010, 1.1025, SPREAD)
        ex = advance(s, [flat(0), late], slippage=SLIP)
        assert ex is not None and ex.reason is ExitReason.TIME_STOP and ex.at == monday

    def test_no_take_profit_runs_to_stop_or_time(self) -> None:
        s = buy(tp=None)
        assert advance(s, [bar(0, 1.1, 1.2, 1.099, 1.15)], slippage=SLIP) is None
        assert s.mfe == pytest.approx(0.1)


class TestTieBreak:
    BOTH = bar(1, 1.1000, 1.1105, 1.0945, 1.1000)

    def test_ticks_decide(self) -> None:
        t = T0 + timedelta(minutes=1)
        rows = [
            (t, 1.1000, 1.1002),
            (t + timedelta(seconds=10), 1.1101, 1.1103),
            (t + timedelta(seconds=20), 1.0940, 1.0942),
        ]
        s = buy()
        ex = advance(s, [flat(0), self.BOTH], slippage=SLIP, ticks=ticks_of(rows))
        assert ex is not None and ex.reason is ExitReason.TAKE_PROFIT and Flag.TICK_RESOLVED in s.flags
        assert ex.at == t + timedelta(seconds=10)

    def test_without_ticks_the_stop_is_assumed_first(self) -> None:
        s = buy()
        ex = advance(s, [flat(0), self.BOTH], slippage=SLIP, ticks=lambda a, b: None)
        assert ex is not None and ex.reason is ExitReason.STOP_LOSS and Flag.AMBIGUOUS in s.flags
        s = buy()
        ex = advance(s, [flat(0), self.BOTH], slippage=SLIP)  # no tick source configured
        assert ex is not None and ex.reason is ExitReason.STOP_LOSS and Flag.AMBIGUOUS in s.flags

    def test_ticks_that_cross_neither_fall_back_to_the_stop(self) -> None:
        t = T0 + timedelta(minutes=1)
        s = buy()
        ex = advance(s, [flat(0), self.BOTH], slippage=SLIP, ticks=ticks_of([(t, 1.1, 1.1002)]))
        assert ex is not None and ex.reason is ExitReason.STOP_LOSS and Flag.AMBIGUOUS in s.flags

    def test_a_stop_tick_fills_at_its_price(self) -> None:
        t = T0 + timedelta(minutes=1)
        s = buy()
        ex = advance(s, [flat(0), self.BOTH], slippage=SLIP, ticks=ticks_of([(t, 1.0945, 1.0947)]))
        assert (
            ex is not None and ex.reason is ExitReason.STOP_LOSS and ex.price == pytest.approx(1.0945 - SLIP)
        )


class TestEntryMinute:
    AT = T0 + timedelta(seconds=30)

    def test_ticks_after_the_entry_decide(self) -> None:
        # the bar reached the TP at :10, before the entry at :30, then fell
        rows = [(T0 + timedelta(seconds=10), 1.1101, 1.1103), (T0 + timedelta(seconds=40), 1.0990, 1.0992)]
        s = buy(at=self.AT)
        source = ticks_of(rows)
        assert advance(s, [bar(0, 1.1000, 1.1101, 1.0990, 1.0995)], slippage=SLIP, ticks=source) is None
        assert source.calls == [(self.AT, T0 + timedelta(minutes=1))]
        assert s.mae == pytest.approx(0.0010) and s.mfe == 0.0 and s.cursor == T0 + timedelta(minutes=1)

    def test_without_ticks_only_a_stop_counts(self) -> None:
        s = buy(at=self.AT)
        assert advance(s, [bar(0, 1.1000, 1.1101, 1.0990, 1.0995)], slippage=SLIP) is None
        assert Flag.PARTIAL_BAR in s.flags
        s = buy(at=self.AT)
        ex = advance(s, [bar(0, 1.1000, 1.1101, 1.0940, 1.0995)], slippage=SLIP)
        assert ex is not None and ex.reason is ExitReason.STOP_LOSS and ex.at == self.AT


class TestResume:
    def test_resuming_from_the_cursor_equals_one_pass(self) -> None:
        bars = [
            bar(
                i,
                1.1 + i * 0.0002,
                1.1 + i * 0.0002 + 0.0003,
                1.1 + i * 0.0002 - 0.0003,
                1.1 + (i + 1) * 0.0002,
            )
            for i in range(60)
        ]
        one = buy()
        whole = advance(one, bars, slippage=SLIP)
        two = buy()
        assert advance(two, bars[:20], slippage=SLIP) is None
        again = advance(two, bars, slippage=SLIP)  # overlapping bars are skipped by the cursor
        assert whole == again and (one.mae, one.mfe, one.cursor) == (two.mae, two.mfe, two.cursor)


class TestManaged:
    CFG = PositionManagementConfig(
        break_even_trigger_r=1.0, break_even_buffer_points=2.0, trailing_start_r=1.5, trailing_atr_multiple=2.0,
        min_sl_step_points=5.0,
    )  # fmt: skip

    def mgmt(self, cfg: PositionManagementConfig | None = None, atr: float | None = 0.0010) -> Management:
        return Management(cfg or self.CFG, atr, 0.00001, 900)

    def test_break_even_then_stopped_at_break_even(self) -> None:
        s = buy(tp=1.1200)
        bars = [flat(0), bar(1, 1.1000, 1.1055, 1.0999, 1.1052), bar(2, 1.1050, 1.1051, 1.0990, 1.0995)]
        ex = advance(s, bars, slippage=SLIP, management=self.mgmt())
        assert ex is not None and ex.reason is ExitReason.BREAK_EVEN
        assert ex.price == pytest.approx(1.10002 - SLIP) and s.sl == pytest.approx(1.10002)

    def test_trailing(self) -> None:
        s = buy(tp=1.1300)
        bars = [flat(0), bar(1, 1.1000, 1.1081, 1.0999, 1.1080), bar(2, 1.1080, 1.1081, 1.1050, 1.1055)]
        ex = advance(s, bars, slippage=SLIP, management=self.mgmt())
        assert s.sl == pytest.approx(1.1060)  # 1.6R: trail 2 ATR behind the close 1.1080
        assert (
            ex is not None
            and ex.reason is ExitReason.TRAILING_STOP
            and ex.price == pytest.approx(1.1060 - SLIP)
        )

    def test_plan_ignores_management(self) -> None:
        s = buy(tp=1.1200)
        bars = [flat(0), bar(1, 1.1000, 1.1055, 1.0999, 1.1052), bar(2, 1.1050, 1.1051, 1.0990, 1.0995)]
        assert advance(s, bars, slippage=SLIP) is None and s.sl == 1.0950

    def test_time_stop_bars_close_at_the_mark(self) -> None:
        cfg = self.CFG.model_copy(update={"time_stop_bars": 1})
        s = buy()
        ex = advance(s, [flat(i) for i in range(16)], slippage=SLIP, management=self.mgmt(cfg))
        assert ex is not None and ex.reason is ExitReason.TIME_STOP and ex.at == T0 + timedelta(minutes=15)


class TestCosts:
    def test_rollover_days(self) -> None:
        wed = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
        assert rollover_days(wed, wed + timedelta(hours=5), tz=ATHENS, triple_weekday=3) == 0
        assert (
            rollover_days(wed, wed + timedelta(days=1), tz=ATHENS, triple_weekday=3) == 3
        )  # Wednesday triple
        thu = wed + timedelta(days=1)
        assert rollover_days(thu, thu + timedelta(days=1), tz=ATHENS, triple_weekday=3) == 1
        fri = wed + timedelta(days=2)
        assert rollover_days(fri, fri + timedelta(days=3), tz=ATHENS, triple_weekday=3) == 1  # Fri only
        # 21:30 UTC is 00:30 in Athens (EEST): a broker midnight has passed
        assert rollover_days(thu, thu.replace(hour=21, minute=30), tz=ATHENS, triple_weekday=3) == 1

    def profit(self, volume: float, price: float) -> float:
        return (price - 1.1000) * 100_000 * volume

    def test_money_r_and_costs(self) -> None:
        s = buy()
        ex = advance(s, [flat(0), bar(1, 1.1000, 1.1101, 1.0990, 1.1090)], slippage=SLIP)
        assert ex is not None
        r = settle(
            s, ex, lot=0.5, profit=self.profit, commission_per_lot=7.0, swap_per_lot_night=-2.0, swap_days=3
        )
        assert r.win and r.r_multiple == pytest.approx(2.0)
        assert r.gross_pnl == pytest.approx(500.0) and r.commission == pytest.approx(-3.5)
        assert r.swap == pytest.approx(-3.0) and r.net_pnl == pytest.approx(493.5)
        assert r.risk_money == pytest.approx(250.0) and r.r_net == pytest.approx(493.5 / 250)
        assert r.mfe_r == pytest.approx(2.0) and r.mae_r == pytest.approx(0.2) and r.swap_days == 3

    def test_not_tradable_is_tracked_in_r(self) -> None:
        s = buy()
        ex = advance(s, [flat(0), bar(1, 1.0990, 1.0995, 1.0949, 1.0960)], slippage=0.0)
        assert ex is not None
        r = settle(
            s, ex, lot=None, profit=self.profit, commission_per_lot=7.0, swap_per_lot_night=0.0, swap_days=0
        )
        assert not r.win and r.r_multiple == pytest.approx(-1.0)
        assert r.r_net == pytest.approx((-500 - 7) / 500)  # 1-lot reference
        assert r.gross_pnl is r.net_pnl is r.risk_money is None and Flag.NOT_TRADABLE in r.flags

    def test_unvalued_and_unknown_swap(self) -> None:
        s = buy()
        ex = advance(s, [flat(0), bar(1, 1.0990, 1.0995, 1.0949, 1.0960)], slippage=0.0)
        assert ex is not None
        r = settle(
            s,
            ex,
            lot=0.1,
            profit=lambda v, p: None,
            commission_per_lot=0,
            swap_per_lot_night=None,
            swap_days=1,
        )
        assert {Flag.PNL_UNAVAILABLE, Flag.SWAP_UNKNOWN} <= r.flags and r.r_net == r.r_multiple
        assert r.net_pnl is None


def test_bars_from_frame() -> None:
    df = pd.DataFrame(
        {
            "open_time": [pd.Timestamp(T0)],
            "close_time": [pd.Timestamp(T0 + timedelta(minutes=1))],
            "open": [1.1],
            "high": [1.2],
            "low": [1.0],
            "close": [1.15],
            "spread": [12],
        }
    )
    [b] = bars_from_frame(df, 0.00001)
    assert b.open_time == T0 and b.spread == pytest.approx(0.00012) and b.close == 1.15
    assert bars_from_frame(df.iloc[0:0], 0.00001) == []
