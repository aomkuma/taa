from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from app.broker import mt5_constants as c
from app.config import BacktestConfig, RiskConfig
from app.core.enums import EntryType, ExitReason, Side
from app.execution.fill_model import Bar, entry_price, exit_on_bar, limit_fill
from app.execution.simulated_broker import (
    AccountCurrencyOnly,
    EventKind,
    OrderRequest,
    SimulatedBroker,
    SimulationError,
)
from app.risk.position_sizer import PositionSizer
from tests.strategy_data import EURUSD_SPEC

T = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
SPREAD = 0.0001  # 10 points
H = timedelta(hours=1)


def bar(i: int, o: float, h: float, low: float, cl: float, spread: float = SPREAD) -> Bar:
    return Bar(T + i * H, T + (i + 1) * H, o, h, low, cl, spread)


def broker(**cfg: object) -> SimulatedBroker:
    config = BacktestConfig.model_validate({"slippage_model": "none", **cfg})
    return SimulatedBroker({"EURUSD": EURUSD_SPEC}, config, AccountCurrencyOnly("USD"))


def buy(
    volume: float = 1.0, sl: float | None = 1.0980, tp: float | None = 1.1040, **kw: object
) -> OrderRequest:
    return OrderRequest("EURUSD", Side.BUY, volume, sl, tp, risk_money=200.0, **kw)  # type: ignore[arg-type]


def sell(
    volume: float = 1.0, sl: float | None = 1.1020, tp: float | None = 1.0960, **kw: object
) -> OrderRequest:
    return OrderRequest("EURUSD", Side.SELL, volume, sl, tp, risk_money=200.0, **kw)  # type: ignore[arg-type]


class TestFillRules:
    def test_entries_at_the_open_buy_pays_the_spread(self) -> None:
        b = bar(0, 1.1000, 1.1010, 1.0990, 1.1005)
        assert entry_price(Side.BUY, b, 0.0) == pytest.approx(1.1001)
        assert entry_price(Side.SELL, b, 0.0) == pytest.approx(1.1000)
        assert entry_price(Side.BUY, b, 0.00002) == pytest.approx(1.10012)
        assert entry_price(Side.SELL, b, 0.00002) == pytest.approx(1.09998)

    def test_sl_first_when_both_are_hit(self) -> None:
        wide = bar(0, 1.1000, 1.1050, 1.0970, 1.1000)
        fill = exit_on_bar(Side.BUY, 1.0980, 1.1040, wide, 0.0)
        assert fill is not None and fill.reason is ExitReason.STOP_LOSS and fill.price == 1.0980

    def test_gap_through_the_stop_fills_at_the_open(self) -> None:
        gap = bar(0, 1.0950, 1.0960, 1.0940, 1.0955)
        fill = exit_on_bar(Side.BUY, 1.0980, 1.1040, gap, 0.0)
        assert fill is not None and fill.price == 1.0950
        up_gap = bar(0, 1.1050, 1.1060, 1.1045, 1.1055)
        short = exit_on_bar(Side.SELL, 1.1020, 1.0960, up_gap, 0.0)
        assert short is not None and short.price == pytest.approx(1.1051)  # the ask at the open

    def test_sell_exits_on_the_ask(self) -> None:
        # bid high 1.1015 + spread 0.0001 = ask 1.1016 does not reach the SL at 1.1020
        assert exit_on_bar(Side.SELL, 1.1020, 1.0960, bar(0, 1.1000, 1.1015, 1.0990, 1.1000), 0.0) is None
        hit = exit_on_bar(Side.SELL, 1.1020, 1.0960, bar(0, 1.1000, 1.1019, 1.0990, 1.1000), 0.0)
        assert hit is not None and hit.reason is ExitReason.STOP_LOSS
        # TP needs the ask low (bid low + spread) at the TP
        assert exit_on_bar(Side.SELL, 1.1020, 1.0960, bar(0, 1.1000, 1.1001, 1.0960, 1.0970), 0.0) is None
        tp = exit_on_bar(Side.SELL, 1.1020, 1.0960, bar(0, 1.1000, 1.1001, 1.0959, 1.0970), 0.0)
        assert tp is not None and tp.reason is ExitReason.TAKE_PROFIT and tp.price == 1.0960

    def test_stop_slippage_is_adverse_tp_has_none(self) -> None:
        sl = exit_on_bar(Side.BUY, 1.0980, None, bar(0, 1.1000, 1.1001, 1.0970, 1.0975), 0.00003)
        assert sl is not None and sl.price == pytest.approx(1.09797)
        tp = exit_on_bar(Side.BUY, None, 1.1040, bar(0, 1.1000, 1.1050, 1.0999, 1.1045), 0.00003)
        assert tp is not None and tp.price == 1.1040

    def test_limits(self) -> None:
        b = bar(0, 1.1000, 1.1010, 1.0980, 1.1005)
        assert limit_fill(Side.BUY, 1.0985, b) == 1.0985  # ask low 1.0981 reaches it
        assert limit_fill(Side.BUY, 1.0980, b) is None  # ask low 1.0981 does not
        assert limit_fill(Side.BUY, 1.1005, b) == pytest.approx(1.1001)  # gapped: ask open is better
        assert limit_fill(Side.SELL, 1.1008, b) == 1.1008
        assert limit_fill(Side.SELL, 1.0990, b) == 1.1000


class TestBroker:
    def test_market_order_fills_at_the_next_open(self) -> None:
        br = broker()
        br.submit(buy(), T + H)  # decided at the close of bar 0
        assert br.on_bar("EURUSD", bar(0, 1.0990, 1.0995, 1.0985, 1.0992)) == []  # the decision bar itself
        events = br.on_bar("EURUSD", bar(1, 1.1000, 1.1010, 1.0995, 1.1005))
        assert [e.kind for e in events] == [EventKind.ENTRY]
        pos = next(iter(br.positions.values()))
        assert pos.entry_price == pytest.approx(1.1001)
        assert pos.price_current == 1.1005  # BUY marked at the bid close
        assert br.equity == pytest.approx(10_000 + 0.0004 * 100_000)

    def test_full_round_trip_with_costs(self) -> None:
        br = broker(commission_per_lot=7.0)
        br.submit(buy(), T)
        br.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005))
        events = br.on_bar("EURUSD", bar(1, 1.1005, 1.1045, 1.1000, 1.1040))
        trade = events[0].trade
        assert trade is not None and trade.exit_reason is ExitReason.TAKE_PROFIT
        assert trade.profit == pytest.approx((1.1040 - 1.1001) * 100_000)
        assert trade.commission == pytest.approx(-7.0)
        assert trade.r_multiple == pytest.approx((390 - 7) / 200)
        assert br.balance == pytest.approx(10_000 + 390 - 7)
        assert br.positions == {}
        assert [(d.entry, d.type) for d in br.deals] == [
            (c.DEAL_ENTRY_IN, c.DEAL_TYPE_BUY),
            (c.DEAL_ENTRY_OUT, c.DEAL_TYPE_SELL),
        ]
        assert br.deals[1].profit == pytest.approx(390)

    def test_exit_on_the_entry_bar(self) -> None:
        br = broker()
        br.submit(sell(), T)
        events = br.on_bar("EURUSD", bar(0, 1.1000, 1.1030, 1.0995, 1.1025))
        assert [e.kind for e in events] == [EventKind.ENTRY, EventKind.EXIT]
        trade = events[1].trade
        assert trade is not None and trade.exit_reason is ExitReason.STOP_LOSS
        assert trade.mae == pytest.approx(1.1031 - 1.1000)

    def test_requested_close_fills_at_the_next_open(self) -> None:
        br = broker()
        br.submit(buy(sl=None, tp=None), T)
        br.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005))
        ticket = next(iter(br.positions))
        br.request_close(ticket)
        events = br.on_bar("EURUSD", bar(1, 1.1007, 1.1010, 1.0995, 1.1005))
        trade = events[0].trade
        assert trade is not None and trade.exit_reason is ExitReason.SIGNAL and trade.exit_price == 1.1007

    def test_limit_order_and_expiry(self) -> None:
        br = broker()
        br.submit(buy(entry_type=EntryType.LIMIT, price=1.0990, expires_at=T + 2 * H), T)
        assert br.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005)) == []
        assert [e.kind for e in br.on_bar("EURUSD", bar(1, 1.1000, 1.1005, 1.0985, 1.0995))] == [
            EventKind.ENTRY
        ]
        br2 = broker()
        br2.submit(buy(entry_type=EntryType.LIMIT, price=1.0900, expires_at=T + H), T)
        br2.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005))
        assert [e.kind for e in br2.on_bar("EURUSD", bar(1, 1.1000, 1.1005, 1.0985, 1.0995))] == [
            EventKind.EXPIRED
        ]
        assert br2.pending == {}

    def test_seeded_slippage_is_reproducible(self) -> None:
        def run() -> float:
            br = broker(slippage_model="random", slippage_points=5.0, seed=7)
            br.submit(buy(), T)
            br.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005))
            return next(iter(br.positions.values())).entry_price

        first, second = run(), run()
        assert first == second
        assert 1.1001 <= first <= 1.1001 + 5 * EURUSD_SPEC.point
        other = broker(slippage_model="random", slippage_points=5.0, seed=8)
        other.submit(buy(), T)
        other.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005))
        assert next(iter(other.positions.values())).entry_price != first

    def test_spread_models(self) -> None:
        assert broker().spread_price("EURUSD", 12) == pytest.approx(0.00012)
        assert broker(spread_model="fixed", fixed_spread_points=20).spread_price(
            "EURUSD", 12
        ) == pytest.approx(0.0002)
        assert broker(min_spread_points=15).spread_price("EURUSD", 3) == pytest.approx(0.00015)

    def test_swap_with_triple_wednesday(self) -> None:
        spec = dataclasses.replace(EURUSD_SPEC, swap_long=-10.0, swap_rollover3days=3)
        config = BacktestConfig(slippage_model="none", swap_enabled=True)
        br = SimulatedBroker({"EURUSD": spec}, config, AccountCurrencyOnly("USD"))
        start = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)  # Tuesday
        br.submit(buy(sl=None, tp=None), start)
        for day in range(3):  # Tue -> Wed -> Thu
            when = start + timedelta(days=day)
            br.on_bar("EURUSD", Bar(when, when + H, 1.1, 1.1, 1.1, 1.1, SPREAD))
        pos = next(iter(br.positions.values()))
        # Tuesday's rollover x1, Wednesday's x3: -10 points * 1e-5 * 100k * (1 + 3)
        assert pos.swap == pytest.approx(-10 * 4)

    def test_margin_rejection(self) -> None:
        br = broker(initial_balance=100.0)
        br.submit(buy(volume=10.0), T)
        events = br.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005))
        assert [e.kind for e in events] == [EventKind.REJECTED]

    def test_missing_conversion_fails_loudly(self) -> None:
        jpy = dataclasses.replace(
            EURUSD_SPEC, name="USDJPY", currency_profit="JPY", currency_base="USD", currency_margin="USD"
        )
        br = SimulatedBroker({"USDJPY": jpy}, BacktestConfig(), AccountCurrencyOnly("USD"))
        br.submit(OrderRequest("USDJPY", Side.BUY, 1.0, None, None), T)
        assert br.calc_profit(Side.BUY, "USDJPY", 1.0, 150.0, 151.0) is None
        with pytest.raises(SimulationError):
            br.spec_at("USDJPY")

    def test_is_a_profit_calculator_for_the_sizer(self) -> None:
        br = broker()
        br.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005))
        r = PositionSizer(RiskConfig(), br).size(
            br.spec_at("EURUSD"), Side.BUY, 1.1, 1.098, br.funds(), lot_limit=1.0
        )
        assert r.ok, r.detail

    def test_end_of_data_closes_everything(self) -> None:
        br = broker()
        br.submit(buy(sl=None, tp=None), T)
        br.on_bar("EURUSD", bar(0, 1.1000, 1.1010, 1.0995, 1.1005))
        events = br.close_all(T + H)
        assert events[0].trade is not None and events[0].trade.exit_reason is ExitReason.END_OF_DATA
        assert br.equity == br.balance
