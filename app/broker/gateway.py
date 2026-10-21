"""Broker gateway protocols and the read-only MT5 implementation.

Strategy, risk and analytics code depends only on :class:`MarketDataGateway`. Order placement lives in a
separate ``ExecutionGateway`` (Milestone 2), so a PAPER-mode engine has no code path to a broker order.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Protocol

import numpy as np
import pandas as pd

from app.broker import mt5_constants as c
from app.broker.models import AccountSnapshot, BrokerOrder, BrokerPosition, Deal, TerminalSnapshot
from app.broker.mt5_client import MT5Client, account_from_raw, terminal_from_raw
from app.core.clock import ServerClock, ensure_utc
from app.core.enums import Side, Timeframe
from app.core.errors import BrokerError, BrokerUnavailable, SymbolUnavailable
from app.market_data.data_models import SymbolSpec, Tick

RAW_RATE_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
_HISTORY_MARGIN = timedelta(days=1)
# copy_ticks_range on a tick month the terminal has not stored yet blocks about 100 s and answers None
# with (-1, "Terminal: Call failed") while the terminal keeps downloading; the same request succeeds once
# the month is in Bases/<server>/ticks (FBS demo, 2026-10-20: 104.8 s failed, then 13.3 s, then 0.3 s).
# The gateway asks again after a pause (tests/unit/test_ticks_sync.py).
TICK_SYNC_ATTEMPTS = 3
TICK_SYNC_PAUSE_S = 5.0
_TICKS_SYNCING = -1


class MarketDataGateway(Protocol):
    """Read-only broker access."""

    server_clock: ServerClock

    def terminal(self) -> TerminalSnapshot: ...

    def account(self) -> AccountSnapshot: ...

    def symbol_spec(self, symbol: str) -> SymbolSpec: ...

    def symbols(self, group: str | None = None) -> list[SymbolSpec]: ...

    def tick(self, symbol: str) -> Tick | None: ...

    def ticks_range(self, symbol: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame: ...

    def rates_from_pos(self, symbol: str, timeframe: Timeframe, start: int, count: int) -> pd.DataFrame: ...

    def rates_range(
        self, symbol: str, timeframe: Timeframe, start_utc: datetime, end_utc: datetime
    ) -> pd.DataFrame: ...

    def positions(self, symbol: str | None = None) -> list[BrokerPosition]: ...

    def orders(self, symbol: str | None = None) -> list[BrokerOrder]: ...

    def deals(self, start_utc: datetime, end_utc: datetime) -> list[Deal]: ...

    def calc_profit(
        self, side: Side, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None: ...

    def calc_margin(self, side: Side, symbol: str, volume: float, price: float) -> float | None: ...


def spec_from_raw(raw: Any) -> SymbolSpec:
    return SymbolSpec(
        name=str(raw.name),
        description=str(getattr(raw, "description", "")),
        digits=int(raw.digits),
        point=float(raw.point),
        tick_size=float(raw.trade_tick_size),
        tick_value=float(raw.trade_tick_value),
        tick_value_profit=float(getattr(raw, "trade_tick_value_profit", raw.trade_tick_value)),
        tick_value_loss=float(getattr(raw, "trade_tick_value_loss", raw.trade_tick_value)),
        contract_size=float(raw.trade_contract_size),
        volume_min=float(raw.volume_min),
        volume_max=float(raw.volume_max),
        volume_step=float(raw.volume_step),
        volume_limit=float(getattr(raw, "volume_limit", 0.0)),
        stops_level=int(raw.trade_stops_level),
        freeze_level=int(raw.trade_freeze_level),
        filling_mode=int(raw.filling_mode),
        trade_mode=int(raw.trade_mode),
        execution_mode=int(raw.trade_exemode),
        chart_mode=int(getattr(raw, "chart_mode", c.SYMBOL_CHART_MODE_BID)),
        currency_base=str(raw.currency_base),
        currency_profit=str(raw.currency_profit),
        currency_margin=str(raw.currency_margin),
        spread_points=int(raw.spread),
        spread_float=bool(getattr(raw, "spread_float", True)),
        swap_long=float(getattr(raw, "swap_long", 0.0)),
        swap_short=float(getattr(raw, "swap_short", 0.0)),
        swap_rollover3days=int(getattr(raw, "swap_rollover3days", 3)),
        calc_mode=int(getattr(raw, "trade_calc_mode", 0)),
        path=str(getattr(raw, "path", "")),
        swap_mode=int(getattr(raw, "swap_mode", c.SYMBOL_SWAP_MODE_UNKNOWN)),
    )


def rates_to_frame(raw: Any) -> pd.DataFrame:
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=RAW_RATE_COLUMNS)
    arr = np.asarray(raw)
    return pd.DataFrame({col: arr[col] for col in RAW_RATE_COLUMNS})


class ReadOnlyMT5Gateway:
    """MarketDataGateway backed by the MetaTrader5 module (or FakeMT5) through :class:`MT5Client`."""

    def __init__(
        self, client: MT5Client, server_clock: ServerClock, sleep: Callable[[float], None] | None = None
    ) -> None:
        self.client = client
        self.server_clock = server_clock
        self._sleep = sleep if sleep is not None else time.sleep

    # ---------------------------------------------------------------- account/terminal
    def terminal(self) -> TerminalSnapshot:
        raw = self.client.call("terminal_info")
        if raw is None:
            raise BrokerUnavailable(f"terminal_info failed: {self.client.last_error()}")
        return terminal_from_raw(raw)

    def account(self) -> AccountSnapshot:
        raw = self.client.call("account_info")
        if raw is None:
            raise BrokerUnavailable(f"account_info failed: {self.client.last_error()}")
        return account_from_raw(raw, self.client.clock.now_utc())

    # ------------------------------------------------------------------------- symbols
    def symbol_spec(self, symbol: str) -> SymbolSpec:
        if not self.client.call("symbol_select", symbol, True):
            raise SymbolUnavailable(f"symbol {symbol!r} cannot be selected: {self.client.last_error()}")
        raw = self.client.call("symbol_info", symbol)
        if raw is None:
            raise SymbolUnavailable(f"symbol {symbol!r} is not available on this server")
        return spec_from_raw(raw)

    def symbols(self, group: str | None = None) -> list[SymbolSpec]:
        """All symbols on the server matching an MT5 group filter (``*`` wildcards, ``!`` negation)."""
        raw = self.client.call("symbols_get", group=group) if group else self.client.call("symbols_get")
        if raw is None:
            raise BrokerError(f"symbols_get failed: {self.client.last_error()}")
        out: list[SymbolSpec] = []
        for item in raw:
            try:
                out.append(spec_from_raw(item))
            except (AttributeError, TypeError, ValueError):
                continue  # incomplete entries are skipped; they cannot be validated or traded
        return out

    def _copy_ticks(self, symbol: str, start_utc: datetime, end_utc: datetime) -> Any:
        """copy_ticks_range over [start_utc, end_utc) widened by the history margin.

        While the terminal is still downloading a tick month (None with error code -1) the request is
        repeated up to TICK_SYNC_ATTEMPTS times, TICK_SYNC_PAUSE_S apart; any other error raises at once.
        """
        lo = ensure_utc(start_utc) - _HISTORY_MARGIN
        hi = ensure_utc(end_utc) + _HISTORY_MARGIN
        flags = getattr(self.client.mt5, "COPY_TICKS_ALL", c.COPY_TICKS_ALL)
        for attempt in range(1, TICK_SYNC_ATTEMPTS + 1):
            raw = self.client.call(
                "copy_ticks_range", symbol, int(lo.timestamp()), int(hi.timestamp()), flags
            )
            if raw is not None:
                return raw
            err = self.client.last_error()
            if err[0] != _TICKS_SYNCING:
                raise BrokerError(f"copy_ticks_range({symbol}) failed: {err}")
            if attempt < TICK_SYNC_ATTEMPTS:
                self._sleep(TICK_SYNC_PAUSE_S)
        raise BrokerError(
            f"copy_ticks_range({symbol}) failed {TICK_SYNC_ATTEMPTS} times with {err}: the terminal is "
            "probably still downloading this tick month; ask again later"
        )

    def ticks_range(self, symbol: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
        """Ticks with real UTC times in [start_utc, end_utc): columns time_utc, bid, ask.

        Like :meth:`rates_range`, the query window is widened and filtered after converting server time.
        """
        arr = np.asarray(self._copy_ticks(symbol, start_utc, end_utc))
        if len(arr) == 0:
            return pd.DataFrame(columns=["time_utc", "bid", "ask"])
        msc = arr["time_msc"].astype("int64")
        times = self.server_clock.server_epochs_to_utc(msc // 1000) + pd.to_timedelta(msc % 1000, unit="ms")
        df = pd.DataFrame(
            {"time_utc": times, "bid": arr["bid"].astype(float), "ask": arr["ask"].astype(float)}
        )
        mask = (df["time_utc"] >= pd.Timestamp(ensure_utc(start_utc))) & (
            df["time_utc"] < pd.Timestamp(ensure_utc(end_utc))
        )
        return df.loc[mask].reset_index(drop=True)

    def raw_ticks(self, symbol: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
        """Like :meth:`ticks_range`, with every field the broker sends: time_utc, bid, ask, last, volume,
        flags (feed probe, TAA-L001; not part of :class:`MarketDataGateway`)."""
        arr = np.asarray(self._copy_ticks(symbol, start_utc, end_utc))
        columns = ["time_utc", "bid", "ask", "last", "volume", "flags"]
        if len(arr) == 0:
            return pd.DataFrame(columns=columns)
        msc = arr["time_msc"].astype("int64")
        times = self.server_clock.server_epochs_to_utc(msc // 1000) + pd.to_timedelta(msc % 1000, unit="ms")
        df = pd.DataFrame(
            {
                "time_utc": times,
                "bid": arr["bid"].astype(float),
                "ask": arr["ask"].astype(float),
                "last": arr["last"].astype(float),
                "volume": arr["volume"].astype("int64"),
                "flags": arr["flags"].astype("int64"),
            }
        )
        mask = (df["time_utc"] >= pd.Timestamp(ensure_utc(start_utc))) & (
            df["time_utc"] < pd.Timestamp(ensure_utc(end_utc))
        )
        return df.loc[mask, columns].reset_index(drop=True)

    def book_open(self, symbol: str) -> bool:
        """Subscribe to the symbol's depth of market (feed probe, TAA-L001; read-only)."""
        return bool(self.client.call("market_book_add", symbol))

    def book_snapshot(self, symbol: str) -> list[tuple[int, float, float]] | None:
        """The current depth of market as (type, price, volume); None when the terminal refused."""
        raw = self.client.call("market_book_get", symbol)
        if raw is None:
            return None
        return [(int(b.type), float(b.price), float(getattr(b, "volume_dbl", b.volume))) for b in raw]

    def book_close(self, symbol: str) -> None:
        self.client.call("market_book_release", symbol)

    def tick(self, symbol: str) -> Tick | None:
        raw = self.client.call("symbol_info_tick", symbol)
        if raw is None:
            return None
        msc = int(getattr(raw, "time_msc", 0) or int(raw.time) * 1000)
        return Tick(
            symbol=symbol,
            time_server_msc=msc,
            time_utc=self.server_clock.server_epoch_to_utc(msc / 1000),
            bid=float(raw.bid),
            ask=float(raw.ask),
            last=float(getattr(raw, "last", 0.0)),
        )

    # --------------------------------------------------------------------------- rates
    def rates_from_pos(self, symbol: str, timeframe: Timeframe, start: int, count: int) -> pd.DataFrame:
        raw = self.client.call("copy_rates_from_pos", symbol, c.TIMEFRAME[timeframe], start, count)
        if raw is None:
            raise BrokerError(
                f"copy_rates_from_pos({symbol}, {timeframe}) failed: {self.client.last_error()}"
            )
        return rates_to_frame(raw)

    def rates_range(
        self, symbol: str, timeframe: Timeframe, start_utc: datetime, end_utc: datetime
    ) -> pd.DataFrame:
        """Bars whose real UTC open time is in [start_utc, end_utc).

        The query window is widened by one day on both sides because MetaQuotes does not document whether
        the parameters are UTC or server time; results are filtered after converting to UTC.
        """
        lo = ensure_utc(start_utc) - _HISTORY_MARGIN
        hi = ensure_utc(end_utc) + _HISTORY_MARGIN
        raw = self.client.call(
            "copy_rates_range", symbol, c.TIMEFRAME[timeframe], int(lo.timestamp()), int(hi.timestamp())
        )
        if raw is None:
            raise BrokerError(f"copy_rates_range({symbol}, {timeframe}) failed: {self.client.last_error()}")
        frame = rates_to_frame(raw)
        if frame.empty:
            return frame
        open_utc = [self.server_clock.server_epoch_to_utc(t) for t in frame["time"].to_numpy()]
        mask = [(ensure_utc(start_utc) <= t < ensure_utc(end_utc)) for t in open_utc]
        return frame.loc[mask].reset_index(drop=True)

    # ------------------------------------------------------------------- positions/deals
    def positions(self, symbol: str | None = None) -> list[BrokerPosition]:
        raw = (
            self.client.call("positions_get", symbol=symbol) if symbol else self.client.call("positions_get")
        )
        if raw is None:
            raise BrokerError(f"positions_get failed: {self.client.last_error()}")
        out = []
        for p in raw:
            out.append(
                BrokerPosition(
                    ticket=int(p.ticket),
                    symbol=str(p.symbol),
                    side=Side.BUY if int(p.type) == c.POSITION_TYPE_BUY else Side.SELL,
                    volume=float(p.volume),
                    price_open=float(p.price_open),
                    sl=float(p.sl),
                    tp=float(p.tp),
                    price_current=float(p.price_current),
                    profit=float(p.profit),
                    swap=float(getattr(p, "swap", 0.0)),
                    magic=int(p.magic),
                    comment=str(getattr(p, "comment", "")),
                    time_utc=self.server_clock.server_epoch_to_utc(int(p.time)),
                    identifier=int(getattr(p, "identifier", p.ticket)),
                )
            )
        return out

    def orders(self, symbol: str | None = None) -> list[BrokerOrder]:
        """Resting (pending) orders. Buy types are even (BUY_LIMIT, BUY_STOP, BUY_STOP_LIMIT)."""
        raw = self.client.call("orders_get", symbol=symbol) if symbol else self.client.call("orders_get")
        if raw is None:
            raise BrokerError(f"orders_get failed: {self.client.last_error()}")
        out = []
        for o in raw:
            expires = int(getattr(o, "time_expiration", 0) or 0)
            out.append(
                BrokerOrder(
                    ticket=int(o.ticket),
                    symbol=str(o.symbol),
                    side=Side.BUY if int(o.type) % 2 == 0 else Side.SELL,
                    type=int(o.type),
                    volume=float(getattr(o, "volume_current", 0.0)),
                    price_open=float(o.price_open),
                    sl=float(o.sl),
                    tp=float(o.tp),
                    magic=int(o.magic),
                    comment=str(getattr(o, "comment", "")),
                    time_setup_utc=self.server_clock.server_epoch_to_utc(int(o.time_setup)),
                    expiration_utc=self.server_clock.server_epoch_to_utc(expires) if expires else None,
                )
            )
        return out

    def deals(self, start_utc: datetime, end_utc: datetime) -> list[Deal]:
        lo = ensure_utc(start_utc) - _HISTORY_MARGIN
        hi = ensure_utc(end_utc) + _HISTORY_MARGIN
        raw = self.client.call("history_deals_get", int(lo.timestamp()), int(hi.timestamp()))
        if raw is None:
            raise BrokerError(f"history_deals_get failed: {self.client.last_error()}")
        out = []
        for d in raw:
            t = self.server_clock.server_epoch_to_utc(int(d.time))
            if not (ensure_utc(start_utc) <= t < ensure_utc(end_utc)):
                continue
            out.append(
                Deal(
                    ticket=int(d.ticket),
                    order=int(getattr(d, "order", 0)),
                    position_id=int(getattr(d, "position_id", 0)),
                    symbol=str(getattr(d, "symbol", "")),
                    type=int(d.type),
                    entry=int(getattr(d, "entry", 0)),
                    volume=float(getattr(d, "volume", 0.0)),
                    price=float(getattr(d, "price", 0.0)),
                    profit=float(getattr(d, "profit", 0.0)),
                    commission=float(getattr(d, "commission", 0.0)),
                    swap=float(getattr(d, "swap", 0.0)),
                    fee=float(getattr(d, "fee", 0.0)),
                    magic=int(getattr(d, "magic", 0)),
                    comment=str(getattr(d, "comment", "")),
                    time_utc=t,
                    reason=int(getattr(d, "reason", -1)),
                )
            )
        return out

    # ------------------------------------------------------------------- calculators
    def calc_profit(
        self, side: Side, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None:
        order_type = c.ORDER_TYPE_BUY if side is Side.BUY else c.ORDER_TYPE_SELL
        result = self.client.call(
            "order_calc_profit", order_type, symbol, float(volume), float(price_open), float(price_close)
        )
        return None if result is None else float(result)

    def calc_margin(self, side: Side, symbol: str, volume: float, price: float) -> float | None:
        order_type = c.ORDER_TYPE_BUY if side is Side.BUY else c.ORDER_TYPE_SELL
        result = self.client.call("order_calc_margin", order_type, symbol, float(volume), float(price))
        return None if result is None else float(result)
