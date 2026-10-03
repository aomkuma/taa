"""Simulated broker for backtests and PAPER fills (PLAN §A3, §A17; TAA-501).

- **Account:** balance, equity (positions marked at the last bar's close: bid for BUY, ask for SELL), margin
  in use. Money is in the account currency. A currency's rate comes first from a traded symbol's current
  bid (EURUSD prices EUR), else from a :class:`RateSource` (TAA-503), as known at the time of the price that
  produced it, never later.
- **Orders:** market entries fill at the *next* bar's open (:mod:`app.execution.fill_model`); limit entries
  rest until touched or expired; a requested close fills at the next open. An entry without enough free
  margin at fill time is rejected.
- **Costs:** spread from the bar field (or a fixed model, never below ``min_spread_points``); seeded
  adverse slippage (``none`` / ``fixed`` / ``random``) on market entries, closes and stop exits; commission
  (``commission_per_lot`` is round turn: half on each side); optional swap at each broker-day rollover,
  tripled on ``swap_rollover3days``.
- It implements the :class:`~app.risk.position_sizer.ProfitCalculator` protocol, so the same sizer, exposure
  and decision code runs against it, and it reports positions and deals in the broker's own record types.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

import numpy as np

from app.broker import mt5_constants as c
from app.broker.models import BrokerPosition, Deal
from app.config import BacktestConfig
from app.core.clock import ensure_utc
from app.core.enums import EntryType, ExitReason, Side
from app.core.errors import TaaError
from app.execution.fill_model import Bar, entry_price, excursion, exit_on_bar, limit_fill, mark_price
from app.market_data.data_models import SymbolSpec
from app.risk.position_sizer import AccountFunds


class SimulationError(TaaError):
    """The simulation cannot continue faithfully (e.g. no conversion rate for a currency)."""


class RateSource(Protocol):
    def rate(self, currency: str, at: datetime) -> float | None:
        """Account-currency value of one unit of *currency* at *at* (last known value, no look-ahead)."""


@dataclass(frozen=True)
class AccountCurrencyOnly:
    """The rate source when every symbol's profit and margin currency is the account currency."""

    account_currency: str

    def rate(self, currency: str, at: datetime) -> float | None:
        return 1.0 if currency == self.account_currency else None


@dataclass(frozen=True, slots=True)
class OrderRequest:
    symbol: str
    side: Side
    volume: float
    sl: float | None
    tp: float | None
    entry_type: EntryType = EntryType.MARKET
    price: float | None = None  # limit price
    expires_at: datetime | None = None  # limit orders
    magic: int = 0
    comment: str = ""
    strategy: str = ""
    signal_id: str = ""
    risk_money: float = 0.0  # planned loss at the stop, costs included (for R multiples)


@dataclass(slots=True)
class SimPosition:
    ticket: int
    request: OrderRequest
    entry_time: datetime
    entry_price: float
    sl: float | None
    tp: float | None
    commission: float = 0.0
    swap: float = 0.0
    price_current: float = 0.0
    mae: float = 0.0  # worst adverse excursion, price units
    mfe: float = 0.0
    close_requested: ExitReason | None = None
    stop_kind: ExitReason = ExitReason.STOP_LOSS  # BREAK_EVEN / TRAILING_STOP once management moved the stop
    bars_held: int = 0

    @property
    def side(self) -> Side:
        return self.request.side

    @property
    def symbol(self) -> str:
        return self.request.symbol

    @property
    def volume(self) -> float:
        return self.request.volume


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    ticket: int
    symbol: str
    side: Side
    volume: float
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    exit_reason: ExitReason
    sl_initial: float | None
    tp_initial: float | None
    profit: float  # price P/L in the account currency
    commission: float  # negative
    swap: float
    mae: float
    mfe: float
    risk_money: float
    strategy: str
    signal_id: str
    magic: int

    @property
    def net(self) -> float:
        return self.profit + self.commission + self.swap

    @property
    def r_multiple(self) -> float | None:
        return self.net / self.risk_money if self.risk_money > 0 else None


class EventKind(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class BrokerEvent:
    kind: EventKind
    at: datetime
    symbol: str
    ticket: int | None = None
    detail: str = ""
    trade: ClosedTrade | None = None


@dataclass(slots=True)
class _Pending:
    order_id: int
    request: OrderRequest
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EquityPoint:
    at: datetime
    balance: float
    equity: float
    margin: float
    open_positions: int


@dataclass
class SimulatedBroker:
    specs: Mapping[str, SymbolSpec]
    config: BacktestConfig
    rates: RateSource
    account_currency: str = "USD"
    leverage: float = 100.0
    broker_tz: str = "Europe/Athens"
    commission_overrides: Mapping[str, float] = field(default_factory=dict)  # round turn per lot

    def __post_init__(self) -> None:
        self.balance = float(self.config.initial_balance)
        self.positions: dict[int, SimPosition] = {}
        self.pending: dict[int, _Pending] = {}
        self.trades: list[ClosedTrade] = []
        self.deals: list[Deal] = []
        self.equity_curve: list[EquityPoint] = []
        self._rng = np.random.default_rng(self.config.seed)
        self._next_id = 1
        self._now: datetime | None = None
        self._last_bid: dict[str, float] = {}
        self._last_spread: dict[str, float] = {}
        self._last_day: dict[str, str] = {}
        self._tz = ZoneInfo(self.broker_tz)

    # --- conversion and calculators (ProfitCalculator protocol) --------------------------------------------

    def _own_rate(self, currency: str) -> float | None:
        """A rate implied by a traded symbol's current bid (EURUSD prices EUR, USDJPY prices JPY)."""
        for name, spec in self.specs.items():
            bid = self._last_bid.get(name)
            if bid is None or bid <= 0:
                continue
            if spec.currency_base == currency and spec.currency_profit == self.account_currency:
                return bid
            if spec.currency_base == self.account_currency and spec.currency_profit == currency:
                return 1.0 / bid
        return None

    def _rate(self, currency: str, at: datetime | None) -> float:
        if currency == self.account_currency:
            return 1.0
        own = self._own_rate(currency)
        if own is not None:
            return own
        when = at or self._now
        value = None if when is None else self.rates.rate(currency, when)
        if value is None or value <= 0:
            raise SimulationError(f"no {currency}->{self.account_currency} conversion rate at {when}")
        return value

    def calc_profit(
        self, side: Side, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None:
        spec = self.specs.get(symbol)
        if spec is None:
            return None
        try:
            rate = self._rate(spec.currency_profit, None)
        except SimulationError:
            return None
        return (price_close - price_open) * side.sign * volume * spec.contract_size * rate

    def calc_margin(self, side: Side, symbol: str, volume: float, price: float) -> float | None:
        spec = self.specs.get(symbol)
        if spec is None:
            return None
        try:
            if spec.currency_margin != spec.currency_profit:  # FX: margin on the base-currency notional
                notional = volume * spec.contract_size * self._rate(spec.currency_margin, None)
            else:  # CFDs and metals priced in the margin currency; |price|: a negative print is not a credit
                notional = volume * spec.contract_size * abs(price) * self._rate(spec.currency_profit, None)
        except SimulationError:
            return None
        return notional / self.leverage

    def spec_at(self, symbol: str) -> SymbolSpec:
        """The symbol's spec with tick values re-derived at the current conversion rate.

        A stored spec snapshot holds the tick value of the day it was saved; for a JPY or cross pair it moves
        with the rate, and the sizer's tick-value cross-check needs the value *at the bar*.
        """
        spec = self.specs[symbol]
        tick_value = spec.tick_size * spec.contract_size * self._rate(spec.currency_profit, None)
        return dataclasses.replace(
            spec, tick_value=tick_value, tick_value_profit=tick_value, tick_value_loss=tick_value
        )

    # --- account ------------------------------------------------------------------------------------------

    def _floating(self, pos: SimPosition) -> float:
        profit = self.calc_profit(pos.side, pos.symbol, pos.volume, pos.entry_price, pos.price_current)
        return (profit or 0.0) + pos.swap

    @property
    def margin(self) -> float:
        total = 0.0
        for pos in self.positions.values():
            total += self.calc_margin(pos.side, pos.symbol, pos.volume, pos.entry_price) or 0.0
        return total

    @property
    def equity(self) -> float:
        return self.balance + sum(self._floating(p) for p in self.positions.values())

    def funds(self) -> AccountFunds:
        equity, margin = self.equity, self.margin
        return AccountFunds(equity=equity, balance=self.balance, margin=margin, margin_free=equity - margin)

    def broker_positions(self) -> list[BrokerPosition]:
        return [
            BrokerPosition(
                ticket=p.ticket,
                symbol=p.symbol,
                side=p.side,
                volume=p.volume,
                price_open=p.entry_price,
                sl=p.sl or 0.0,
                tp=p.tp or 0.0,
                price_current=p.price_current,
                profit=self._floating(p) - p.swap,
                swap=p.swap,
                magic=p.request.magic,
                comment=p.request.comment,
                time_utc=p.entry_time,
                identifier=p.ticket,
            )
            for p in self.positions.values()
        ]

    def record_equity(self, at: datetime) -> EquityPoint:
        point = EquityPoint(ensure_utc(at), self.balance, self.equity, self.margin, len(self.positions))
        self.equity_curve.append(point)
        return point

    # --- orders -------------------------------------------------------------------------------------------

    def submit(self, request: OrderRequest, at: datetime) -> int:
        """Queue an order; it can fill from the next bar on."""
        if request.symbol not in self.specs:
            raise SimulationError(f"unknown symbol {request.symbol}")
        if request.volume <= 0:
            raise SimulationError("order volume must be positive")
        if request.entry_type is EntryType.LIMIT and request.price is None:
            raise SimulationError("a limit order needs a price")
        order_id = self._new_id()
        self.pending[order_id] = _Pending(order_id, request, ensure_utc(at))
        return order_id

    def cancel(self, order_id: int) -> None:
        self.pending.pop(order_id, None)

    def modify(
        self,
        ticket: int,
        *,
        sl: float | None = None,
        tp: float | None = None,
        stop_kind: ExitReason | None = None,
    ) -> None:
        pos = self.positions[ticket]
        if sl is not None:
            pos.sl = sl
            if stop_kind is not None:
                pos.stop_kind = stop_kind
        if tp is not None:
            pos.tp = tp

    def request_close(self, ticket: int, reason: ExitReason = ExitReason.SIGNAL) -> None:
        """Close at the next bar's open."""
        self.positions[ticket].close_requested = reason

    # --- bar processing -----------------------------------------------------------------------------------

    def spread_price(self, symbol: str, bar_spread_points: float | None) -> float:
        spec = self.specs[symbol]
        cfg = self.config
        points = (
            cfg.fixed_spread_points
            if cfg.spread_model == "fixed" or bar_spread_points is None
            else bar_spread_points
        )
        return max(points, cfg.min_spread_points) * spec.point

    def slippage(self, symbol: str) -> float:
        cfg = self.config
        point = self.specs[symbol].point
        if cfg.slippage_model == "none":
            return 0.0
        if cfg.slippage_model == "fixed":
            return cfg.slippage_points * point
        return float(self._rng.uniform(0.0, cfg.slippage_points)) * point

    def on_bar(self, symbol: str, bar: Bar) -> list[BrokerEvent]:
        """Advance *symbol* through one closed bar: rollover, fills at the open, intrabar exits, marking."""
        self._now = ensure_utc(bar.open_time)
        self._last_bid[symbol] = bar.open  # the price known at the open: fills and margin use it
        events: list[BrokerEvent] = []
        self._rollover(symbol, bar)
        events += self._fill_closes(symbol, bar)
        events += self._fill_entries(symbol, bar)
        for pos in [p for p in self.positions.values() if p.symbol == symbol]:
            adverse, favourable = excursion(pos.side, pos.entry_price, bar)
            pos.mae, pos.mfe = max(pos.mae, adverse), max(pos.mfe, favourable)
            fill = exit_on_bar(pos.side, pos.sl, pos.tp, bar, self.slippage(symbol))
            if fill is not None:
                self._now = ensure_utc(bar.close_time)
                reason = pos.stop_kind if fill.reason is ExitReason.STOP_LOSS else fill.reason
                events.append(self._close(pos, fill.price, bar.close_time, reason))
            else:
                pos.bars_held += 1
        self._now = ensure_utc(bar.close_time)
        self._last_bid[symbol], self._last_spread[symbol] = bar.close, bar.spread
        for pos in self.positions.values():
            if pos.symbol == symbol:
                pos.price_current = mark_price(pos.side, bar.close, bar.spread)
        return events

    def close_all(self, at: datetime, reason: ExitReason = ExitReason.END_OF_DATA) -> list[BrokerEvent]:
        """Close every position at its last mark (end of data)."""
        self._now = ensure_utc(at)
        return [self._close(p, p.price_current, at, reason) for p in list(self.positions.values())]

    # --- internals ----------------------------------------------------------------------------------------

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    def _commission_side(self, symbol: str, volume: float) -> float:
        round_turn = self.commission_overrides.get(symbol, self.config.commission_per_lot)
        return -round_turn / 2 * volume

    def _fill_closes(self, symbol: str, bar: Bar) -> list[BrokerEvent]:
        out = []
        for pos in [p for p in self.positions.values() if p.symbol == symbol and p.close_requested]:
            slip = self.slippage(symbol)
            price = bar.open - slip if pos.side is Side.BUY else bar.open + bar.spread + slip
            out.append(self._close(pos, price, bar.open_time, pos.close_requested or ExitReason.SIGNAL))
        return out

    def _fill_entries(self, symbol: str, bar: Bar) -> list[BrokerEvent]:
        out = []
        for pending in [p for p in self.pending.values() if p.request.symbol == symbol]:
            req = pending.request
            if pending.created_at >= ensure_utc(bar.close_time):
                continue  # submitted at or after this bar's close: not yet
            if req.entry_type is EntryType.MARKET:
                price: float | None = entry_price(req.side, bar, self.slippage(symbol))
            else:
                if req.expires_at is not None and ensure_utc(bar.open_time) >= ensure_utc(req.expires_at):
                    del self.pending[pending.order_id]
                    out.append(
                        BrokerEvent(
                            EventKind.EXPIRED, bar.open_time, symbol, detail=f"order {pending.order_id}"
                        )
                    )
                    continue
                price = limit_fill(req.side, req.price or 0.0, bar)
            if price is None:
                continue
            del self.pending[pending.order_id]
            out.append(self._open(req, price, bar.open_time))
        return out

    def _open(self, req: OrderRequest, price: float, at: datetime) -> BrokerEvent:
        margin = self.calc_margin(req.side, req.symbol, req.volume, price)
        if margin is None or margin > self.funds().margin_free:
            return BrokerEvent(EventKind.REJECTED, at, req.symbol, detail="not enough free margin")
        ticket = self._new_id()
        commission = self._commission_side(req.symbol, req.volume)
        self.balance += commission
        pos = SimPosition(
            ticket, req, ensure_utc(at), price, req.sl, req.tp, commission=commission, price_current=price
        )
        self.positions[ticket] = pos
        self.deals.append(self._deal(pos, c.DEAL_ENTRY_IN, req.side, price, at, 0.0, commission, 0.0))
        return BrokerEvent(EventKind.ENTRY, at, req.symbol, ticket)

    def _close(self, pos: SimPosition, price: float, at: datetime, reason: ExitReason) -> BrokerEvent:
        profit = self.calc_profit(pos.side, pos.symbol, pos.volume, pos.entry_price, price)
        if profit is None:
            raise SimulationError(f"cannot value the close of {pos.symbol}")
        commission = self._commission_side(pos.symbol, pos.volume)
        self.balance += profit + commission + pos.swap
        del self.positions[pos.ticket]
        trade = ClosedTrade(
            ticket=pos.ticket,
            symbol=pos.symbol,
            side=pos.side,
            volume=pos.volume,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=ensure_utc(at),
            exit_price=price,
            exit_reason=reason,
            sl_initial=pos.request.sl,
            tp_initial=pos.request.tp,
            profit=profit,
            commission=pos.commission + commission,
            swap=pos.swap,
            mae=pos.mae,
            mfe=pos.mfe,
            risk_money=pos.request.risk_money,
            strategy=pos.request.strategy,
            signal_id=pos.request.signal_id,
            magic=pos.request.magic,
        )
        self.trades.append(trade)
        self.deals.append(
            self._deal(pos, c.DEAL_ENTRY_OUT, pos.side.opposite, price, at, profit, commission, pos.swap)
        )
        return BrokerEvent(EventKind.EXIT, at, pos.symbol, pos.ticket, reason.value, trade)

    def _deal(
        self,
        pos: SimPosition,
        entry: int,
        side: Side,
        price: float,
        at: datetime,
        profit: float,
        commission: float,
        swap: float,
    ) -> Deal:
        return Deal(
            ticket=self._new_id(),
            order=pos.ticket,
            position_id=pos.ticket,
            symbol=pos.symbol,
            type=c.DEAL_TYPE_BUY if side is Side.BUY else c.DEAL_TYPE_SELL,
            entry=entry,
            volume=pos.volume,
            price=price,
            profit=profit,
            commission=commission,
            swap=swap,
            fee=0.0,
            magic=pos.request.magic,
            comment=pos.request.comment,
            time_utc=ensure_utc(at),
        )

    def _rollover(self, symbol: str, bar: Bar) -> None:
        """Charge one day's swap when the broker day changes between two bars of *symbol*."""
        local = ensure_utc(bar.open_time).astimezone(self._tz)
        day = local.date().isoformat()
        previous = self._last_day.get(symbol)
        self._last_day[symbol] = day
        if previous is None or previous == day or not self.config.swap_enabled:
            return
        prev_date = datetime.fromisoformat(previous)
        if prev_date.weekday() > 4:
            return  # no rollover is charged for weekend days (Wednesday's triple covers them)
        spec = self.specs[symbol]
        mt5_weekday = (prev_date.weekday() + 1) % 7  # MT5 numbers days from Sunday = 0
        days = 3 if mt5_weekday == spec.swap_rollover3days else 1
        for pos in self.positions.values():
            if pos.symbol != symbol:
                continue
            points = spec.swap_long if pos.side is Side.BUY else spec.swap_short
            pos.swap += (
                points
                * spec.point
                * spec.contract_size
                * pos.volume
                * self._rate(spec.currency_profit, None)
                * days
            )
