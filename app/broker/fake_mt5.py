"""In-memory emulation of the subset of the ``MetaTrader5`` module that TAA uses.

Used by tests (Linux CI has no MT5) and for local development without a terminal. Behaviour mirrors
the real module where it matters for safety:

* times are **broker-server wall-clock epochs** (EET), not UTC;
* ``copy_rates_from_pos`` position 0 is the bar still forming;
* functions return ``None`` and set ``last_error()`` on failure;
* markets close per asset type (FX week, US stock hours, crypto 24/7) and ticks stop advancing;
* ``initialize()`` without a login uses the "last" account;
* optional FBS-style equity-tiered Forex leverage and fixed per-instrument leverage.

Every call is counted in :attr:`FakeMT5.calls`, so tests can assert that ``order_send`` was never
invoked in read-only modes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from app.broker import mt5_constants as c
from app.broker.fake_trading import FakeTradeDesk
from app.broker.symbol_groups import match_group
from app.core.clock import Clock, ServerClock

RATE_DTYPE = np.dtype(
    [
        ("time", "<i8"),
        ("open", "<f8"),
        ("high", "<f8"),
        ("low", "<f8"),
        ("close", "<f8"),
        ("tick_volume", "<u8"),
        ("spread", "<i4"),
        ("real_volume", "<u8"),
    ]
)

TICK_DTYPE = np.dtype(
    [
        ("time", "<i8"),
        ("bid", "<f8"),
        ("ask", "<f8"),
        ("last", "<f8"),
        ("volume", "<u8"),
        ("time_msc", "<i8"),
        ("flags", "<u4"),
        ("volume_real", "<f8"),
    ]
)

_TF_SECONDS = {1: 60, 5: 300, 15: 900, 30: 1800, 16385: 3600, 16388: 14_400, 16408: 86_400}

SCHEDULE_FX = "FX"  # closed Friday 21:00 UTC .. Sunday 21:00 UTC
SCHEDULE_CRYPTO = "CRYPTO"  # 24/7
SCHEDULE_US_STOCK = "US_STOCK"  # Monday-Friday 09:30-16:00 America/New_York


@dataclass
class FakeSymbol:
    name: str
    base_price: float
    vol_per_min: float  # stdev of 1-minute moves in price units
    digits: int
    contract_size: float
    currency_base: str
    currency_profit: str
    spread_points: int = 12
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    stops_level: int = 0
    freeze_level: int = 0
    filling_mode: int = c.SYMBOL_FILLING_FOK | c.SYMBOL_FILLING_IOC
    trade_mode: int = c.SYMBOL_TRADE_MODE_FULL
    execution_mode: int = c.SYMBOL_TRADE_EXECUTION_MARKET
    chart_mode: int = c.SYMBOL_CHART_MODE_BID
    description: str = ""
    path: str = ""
    calc_mode: int = c.SYMBOL_CALC_MODE_FOREX
    schedule: str = SCHEDULE_FX
    fixed_leverage: int | None = None  # instrument leverage independent of the account (metals, indices, ...)

    @property
    def point(self) -> float:
        return 10.0**-self.digits


DEFAULT_SYMBOLS: dict[str, FakeSymbol] = {
    "EURUSD": FakeSymbol(
        "EURUSD",
        1.1000,
        0.00012,
        5,
        100_000,
        "EUR",
        "USD",
        10,
        description="Euro vs US Dollar",
        path="Forex\\Majors\\EURUSD",
    ),
    "GBPUSD": FakeSymbol(
        "GBPUSD", 1.2700, 0.00015, 5, 100_000, "GBP", "USD", 14, path="Forex\\Majors\\GBPUSD"
    ),
    "USDJPY": FakeSymbol("USDJPY", 150.00, 0.015, 3, 100_000, "USD", "JPY", 12, path="Forex\\Majors\\USDJPY"),
    "XAUUSD": FakeSymbol(
        "XAUUSD",
        2400.0,
        0.35,
        2,
        100,
        "XAU",
        "USD",
        25,
        volume_max=50.0,
        path="Metals\\XAUUSD",
        fixed_leverage=500,
    ),
}

# Additional instruments covering every asset class (used by universe/ranking tests and the dev runner).
EXTRA_SYMBOLS: dict[str, FakeSymbol] = {
    "AUDUSD": FakeSymbol(
        "AUDUSD", 0.6600, 0.00010, 5, 100_000, "AUD", "USD", 12, path="Forex\\Majors\\AUDUSD"
    ),
    "EURGBP": FakeSymbol(
        "EURGBP", 0.8600, 0.00008, 5, 100_000, "EUR", "GBP", 15, path="Forex\\Minors\\EURGBP"
    ),
    "USDZAR": FakeSymbol(
        "USDZAR", 18.200, 0.004, 5, 100_000, "USD", "ZAR", 150, path="Forex\\Exotics\\USDZAR"
    ),
    "XAGUSD": FakeSymbol(
        "XAGUSD", 30.000, 0.008, 3, 5_000, "XAG", "USD", 30, path="Metals\\XAGUSD", fixed_leverage=500
    ),
    "US30": FakeSymbol(
        "US30",
        42_000.0,
        6.0,
        2,
        1,
        "USD",
        "USD",
        200,
        volume_min=0.1,
        volume_step=0.1,
        path="Indices\\US30",
        calc_mode=c.SYMBOL_CALC_MODE_CFDINDEX,
        fixed_leverage=500,
    ),
    "USOIL": FakeSymbol(
        "USOIL",
        75.00,
        0.03,
        2,
        1_000,
        "USD",
        "USD",
        4,
        path="Energies\\USOIL",
        calc_mode=c.SYMBOL_CALC_MODE_CFD,
        fixed_leverage=200,
    ),
    "BTCUSD": FakeSymbol(
        "BTCUSD",
        65_000.0,
        25.0,
        2,
        1,
        "BTC",
        "USD",
        2500,
        path="Crypto\\BTCUSD",
        calc_mode=c.SYMBOL_CALC_MODE_CFD,
        schedule=SCHEDULE_CRYPTO,
        fixed_leverage=500,
    ),
    "AAPL": FakeSymbol(
        "AAPL",
        230.00,
        0.08,
        2,
        1,
        "USD",
        "USD",
        10,
        volume_min=1.0,
        volume_step=1.0,
        volume_max=1000.0,
        path="Stocks\\US\\AAPL",
        calc_mode=c.SYMBOL_CALC_MODE_CFD,
        schedule=SCHEDULE_US_STOCK,
        fixed_leverage=100,
    ),
}

ALL_SYMBOLS: dict[str, FakeSymbol] = {**DEFAULT_SYMBOLS, **EXTRA_SYMBOLS}


def fbs_forex_leverage_for_equity(equity: float) -> int:
    """FBS equity tiers for Forex leverage (fbs.com/trading/margin-and-leverage)."""
    if equity < 200:
        return 3000
    if equity < 5_000:
        return 2000
    if equity < 30_000:
        return 1000
    if equity < 150_000:
        return 500
    return 200


@dataclass
class _Series:
    utc: np.ndarray  # minute start, UTC epoch seconds (int64)
    server: np.ndarray  # minute start, server wall-clock epoch
    o: np.ndarray
    h: np.ndarray
    lo: np.ndarray
    cl: np.ndarray
    vol: np.ndarray
    spread: np.ndarray


@dataclass
class _Failure:
    times: int
    error: tuple[int, str]


@dataclass
class FakeAccount:
    login: int = 12345678
    password: str = "investor-pass"  # noqa: S105 - test fixture value
    server: str = "FBS-Demo"
    investor: bool = True  # investor password => trade_allowed False
    trade_mode: int = c.ACCOUNT_TRADE_MODE_DEMO
    margin_mode: int = c.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING
    currency: str = "USD"
    leverage: int = 500
    tiered_leverage: bool = False  # emulate FBS equity tiers instead of the fixed value above
    balance: float = 10_000.0
    name: str = "Fake Trader"
    company: str = "FBS Markets Inc."
    trade_expert: bool = True
    margin_so_call: float = 40.0
    margin_so_so: float = 20.0


@dataclass
class FakeTerminal:
    connected: bool = True
    trade_allowed: bool = True
    tradeapi_disabled: bool = False
    dlls_allowed: bool = False
    build: int = 6230
    maxbars: int = 100_000
    ping_last: int = 35_000
    path: str = r"C:\MT5\taa-bot"
    data_path: str = r"C:\MT5\taa-bot"


def market_open_mask(utc_minutes: np.ndarray, schedule: str) -> np.ndarray:
    """Which minute starts (UTC epoch seconds) are inside the instrument's trading schedule."""
    if schedule == SCHEDULE_CRYPTO:
        return np.ones(len(utc_minutes), dtype=bool)
    dt = pd.to_datetime(utc_minutes, unit="s", utc=True)
    if schedule == SCHEDULE_US_STOCK:
        local = dt.tz_convert("America/New_York")
        minutes_of_day = local.hour.to_numpy() * 60 + local.minute.to_numpy()
        weekday = local.dayofweek.to_numpy() < 5
        return weekday & (minutes_of_day >= 9 * 60 + 30) & (minutes_of_day < 16 * 60)
    dow = dt.dayofweek.to_numpy()
    hour = dt.hour.to_numpy()
    closed = (dow == 5) | ((dow == 4) & (hour >= 21)) | ((dow == 6) & (hour < 21))
    return ~closed


class FakeMT5:
    # --- constants mirrored from the real module -------------------------------------------------
    TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15, TIMEFRAME_M30 = 1, 5, 15, 30
    TIMEFRAME_H1, TIMEFRAME_H4, TIMEFRAME_D1 = 16385, 16388, 16408
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = c.ORDER_TYPE_BUY, c.ORDER_TYPE_SELL
    TRADE_ACTION_DEAL, TRADE_ACTION_SLTP = c.TRADE_ACTION_DEAL, c.TRADE_ACTION_SLTP
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    ORDER_TIME_GTC = 0
    COPY_TICKS_ALL, COPY_TICKS_INFO, COPY_TICKS_TRADE = (
        c.COPY_TICKS_ALL,
        c.COPY_TICKS_INFO,
        c.COPY_TICKS_TRADE,
    )
    __version__ = "fake-5.0.6231"

    def __init__(
        self,
        clock: Clock,
        *,
        account: FakeAccount | None = None,
        terminal: FakeTerminal | None = None,
        symbols: dict[str, FakeSymbol] | None = None,
        history_days: int = 60,
        future_days: int = 14,
        seed: int = 7,
        tz: str = "Europe/Athens",
    ) -> None:
        self.clock = clock
        self.account = account or FakeAccount()
        self.terminal = terminal or FakeTerminal()
        self.symbols = dict(symbols or DEFAULT_SYMBOLS)
        self.server_clock = ServerClock(tz, clock)
        self.initialized = False
        self.init_kwargs: dict[str, Any] = {}
        self.calls: Counter[str] = Counter()
        self.positions: list[SimpleNamespace] = []
        self.deals: list[SimpleNamespace] = []
        self.selected: set[str] = set()
        self._failures: dict[str, _Failure] = {}
        self._last_error: tuple[int, str] = (1, "Success")
        self._seed = seed
        self.desk = FakeTradeDesk(self)
        start = clock.now_utc() - timedelta(days=history_days)
        end = clock.now_utc() + timedelta(days=future_days)
        self._series = {
            name: self._generate(sym, start, end, seed + i)
            for i, (name, sym) in enumerate(sorted(self.symbols.items()))
        }

    # ======================================================================== test controls
    def fail_next(self, name: str, times: int = 1, error: tuple[int, str] = (-1, "injected failure")) -> None:
        self._failures[name] = _Failure(times, error)

    def disconnect(self) -> None:
        self.terminal.connected = False

    def reconnect(self) -> None:
        self.terminal.connected = True

    def add_deal(self, **fields: Any) -> None:
        self.deals.append(SimpleNamespace(**fields))

    def add_position(self, **fields: Any) -> None:
        self.positions.append(SimpleNamespace(**fields))

    # ============================================================================ internals
    def _generate(self, sym: FakeSymbol, start: datetime, end: datetime, seed: int) -> _Series:
        rng = np.random.default_rng(seed)
        first = int(start.timestamp()) // 60 * 60
        last = int(end.timestamp()) // 60 * 60
        minutes = np.arange(first, last + 60, 60, dtype=np.int64)
        minutes = minutes[market_open_mask(minutes, sym.schedule)]
        n = len(minutes)
        # mild mean reversion keeps prices in a plausible band over long horizons
        steps = rng.normal(0, sym.vol_per_min, n)
        drift = np.sin(np.arange(n) / 2_000.0) * sym.vol_per_min * 0.15
        closes = sym.base_price + np.cumsum(steps + drift)
        closes = np.maximum(closes, sym.base_price * 0.5)
        opens = np.concatenate([[sym.base_price], closes[:-1]])
        wick = np.abs(rng.normal(0, sym.vol_per_min * 0.6, (2, n)))
        highs = np.maximum(opens, closes) + wick[0]
        lows = np.minimum(opens, closes) - wick[1]
        digits = sym.digits
        local = pd.to_datetime(minutes, unit="s", utc=True).tz_convert(self.server_clock.tz_name)
        offsets = (local.tz_localize(None) - local.tz_convert(None)).total_seconds().to_numpy()
        server = minutes + offsets.astype(np.int64)
        return _Series(
            utc=minutes,
            server=server.astype(np.int64),
            o=np.round(opens, digits),
            h=np.round(highs, digits),
            lo=np.round(lows, digits),
            cl=np.round(closes, digits),
            vol=rng.integers(20, 400, n).astype(np.uint64),
            spread=np.maximum(1, rng.normal(sym.spread_points, sym.spread_points * 0.2, n)).astype(np.int32),
        )

    def _enter(self, name: str) -> bool:
        """Count the call and apply injected failures / disconnection. False means 'return None'."""
        self.calls[name] += 1
        failure = self._failures.get(name)
        if failure and failure.times > 0:
            failure.times -= 1
            self._last_error = failure.error
            return False
        if name not in ("initialize", "last_error", "shutdown", "version") and not self.initialized:
            self._last_error = (-10004, "No IPC connection")
            return False
        if (
            name not in ("initialize", "last_error", "shutdown", "version", "terminal_info")
            and not self.terminal.connected
        ):
            self._last_error = (-10004, "No IPC connection")
            return False
        self._last_error = (1, "Success")
        return True

    def _visible_upto(self, series: _Series) -> int:
        now = int(self.clock.now_utc().timestamp())
        return int(np.searchsorted(series.utc, now, side="right"))

    def _bars(self, symbol: str, timeframe: int) -> np.ndarray | None:
        series = self._series.get(symbol)
        if series is None or timeframe not in _TF_SECONDS:
            return None
        k = self._visible_upto(series)
        if k == 0:
            return np.empty(0, dtype=RATE_DTYPE)
        tf = _TF_SECONDS[timeframe]
        server = series.server[:k]
        bucket = server // tf * tf
        df = pd.DataFrame(
            {
                "b": bucket,
                "o": series.o[:k],
                "h": series.h[:k],
                "l": series.lo[:k],
                "c": series.cl[:k],
                "v": series.vol[:k],
                "s": series.spread[:k],
            }
        )
        g = df.groupby("b", sort=True)
        agg = g.agg(
            o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), v=("v", "sum"), s=("s", "min")
        )
        out = np.empty(len(agg), dtype=RATE_DTYPE)
        out["time"] = agg.index.to_numpy()
        out["open"], out["high"], out["low"], out["close"] = agg["o"], agg["h"], agg["l"], agg["c"]
        out["tick_volume"], out["spread"], out["real_volume"] = agg["v"], agg["s"], 0
        return out

    def _current_price(self, symbol: str) -> tuple[float, int, int] | None:
        series = self._series.get(symbol)
        if series is None:
            return None
        k = self._visible_upto(series)
        if k == 0:
            return None
        return float(series.cl[k - 1]), int(series.spread[k - 1]), int(series.utc[k - 1])

    def _conversion_to_account(self, currency: str) -> float | None:
        """Price of 1 unit of ``currency`` in the account currency, from available symbols."""
        acct = self.account.currency
        if currency == acct:
            return 1.0
        for name, sym in self.symbols.items():
            price = self._current_price(name)
            if price is None:
                continue
            if sym.currency_base == currency and sym.currency_profit == acct:
                return price[0]
            if sym.currency_base == acct and sym.currency_profit == currency:
                return 1.0 / price[0]
        return None

    def _equity(self) -> float:
        return self.account.balance + sum(float(getattr(p, "profit", 0.0)) for p in self.positions)

    def _account_leverage(self) -> int:
        if self.account.tiered_leverage:
            return fbs_forex_leverage_for_equity(self._equity())
        return self.account.leverage

    def _symbol_namespace(self, symbol: str) -> SimpleNamespace:
        sym = self.symbols[symbol]
        price = self._current_price(symbol)
        bid = price[0] if price else sym.base_price
        spread = price[1] if price else sym.spread_points
        conv = self._conversion_to_account(sym.currency_profit) or 0.0
        tick_value = sym.point * sym.contract_size * conv
        return SimpleNamespace(
            custom=False,
            chart_mode=sym.chart_mode,
            select=symbol in self.selected,
            visible=symbol in self.selected,
            digits=sym.digits,
            spread=spread,
            spread_float=True,
            trade_calc_mode=sym.calc_mode,
            trade_mode=sym.trade_mode,
            trade_stops_level=sym.stops_level,
            trade_freeze_level=sym.freeze_level,
            trade_exemode=sym.execution_mode,
            swap_mode=1,
            swap_rollover3days=3,
            filling_mode=sym.filling_mode,
            order_mode=127,
            bid=bid,
            ask=round(bid + spread * sym.point, sym.digits),
            point=sym.point,
            trade_tick_value=tick_value,
            trade_tick_value_profit=tick_value,
            trade_tick_value_loss=tick_value,
            trade_tick_size=sym.point,
            trade_contract_size=sym.contract_size,
            volume_min=sym.volume_min,
            volume_max=sym.volume_max,
            volume_step=sym.volume_step,
            volume_limit=0.0,
            swap_long=-5.0,
            swap_short=1.0,
            currency_base=sym.currency_base,
            currency_profit=sym.currency_profit,
            currency_margin=sym.currency_base,
            description=sym.description or symbol,
            name=symbol,
            path=sym.path or f"Forex\\{symbol}",
        )

    # ==================================================================== module functions
    def initialize(
        self,
        path: str | None = None,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        portable: bool = False,
    ) -> bool:
        if not self._enter("initialize"):
            return False
        self.init_kwargs = {
            "path": path,
            "login": login,
            "server": server,
            "timeout": timeout,
            "portable": portable,
            "password_given": password is not None,
        }
        if login is not None and (
            login != self.account.login or server != self.account.server or password != self.account.password
        ):
            self._last_error = (-6, "Terminal: Authorization failed")
            return False
        self.initialized = True
        return True

    def login(
        self, login: int, password: str | None = None, server: str | None = None, timeout: int | None = None
    ) -> bool:
        if not self._enter("login"):
            return False
        return (
            login == self.account.login
            and password == self.account.password
            and server == self.account.server
        )

    def shutdown(self) -> None:
        self.calls["shutdown"] += 1
        self.initialized = False

    def version(self) -> tuple[int, int, str]:
        self.calls["version"] += 1
        return (500, self.terminal.build, "03 Oct 2026")

    def last_error(self) -> tuple[int, str]:
        self.calls["last_error"] += 1
        return self._last_error

    def terminal_info(self) -> SimpleNamespace | None:
        if not self._enter("terminal_info"):
            return None
        t = self.terminal
        return SimpleNamespace(
            community_account=False,
            community_connection=False,
            connected=t.connected,
            dlls_allowed=t.dlls_allowed,
            trade_allowed=t.trade_allowed,
            tradeapi_disabled=t.tradeapi_disabled,
            email_enabled=False,
            ftp_enabled=False,
            notifications_enabled=False,
            mqid=False,
            build=t.build,
            maxbars=t.maxbars,
            codepage=0,
            ping_last=t.ping_last,
            community_balance=0.0,
            retransmission=0.0,
            company=self.account.company,
            name="FBS MetaTrader 5",
            language="English",
            path=t.path,
            data_path=t.data_path,
            commondata_path=t.data_path,
        )

    def account_info(self) -> SimpleNamespace | None:
        if not self._enter("account_info"):
            return None
        self.desk.refresh()
        a = self.account
        floating = sum(float(getattr(p, "profit", 0.0)) for p in self.positions)
        equity = a.balance + floating
        margin = sum(float(getattr(p, "margin", 0.0)) for p in self.positions)
        return SimpleNamespace(
            login=a.login,
            trade_mode=a.trade_mode,
            leverage=self._account_leverage(),
            limit_orders=200,
            margin_so_mode=c.ACCOUNT_STOPOUT_MODE_PERCENT,
            trade_allowed=not a.investor,
            trade_expert=a.trade_expert,
            margin_mode=a.margin_mode,
            currency_digits=2,
            fifo_close=False,
            balance=a.balance,
            credit=0.0,
            profit=floating,
            equity=equity,
            margin=margin,
            margin_free=equity - margin,
            margin_level=(equity / margin * 100) if margin else 0.0,
            margin_so_call=a.margin_so_call,
            margin_so_so=a.margin_so_so,
            margin_initial=0.0,
            margin_maintenance=0.0,
            assets=0.0,
            liabilities=0.0,
            commission_blocked=0.0,
            name=a.name,
            server=a.server,
            currency=a.currency,
            company=a.company,
        )

    def symbols_get(self, group: str | None = None) -> tuple[SimpleNamespace, ...] | None:
        if not self._enter("symbols_get"):
            return None
        return tuple(self._symbol_namespace(n) for n in self.symbols if match_group(n, group))

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        if not self._enter("symbol_select"):
            return False
        if symbol not in self.symbols:
            self._last_error = (-1, f"symbol {symbol} not found")
            return False
        (self.selected.add if enable else self.selected.discard)(symbol)
        return True

    def symbol_info(self, symbol: str) -> SimpleNamespace | None:
        if not self._enter("symbol_info"):
            return None
        if symbol not in self.symbols:
            return None
        return self._symbol_namespace(symbol)

    def symbol_info_tick(self, symbol: str) -> SimpleNamespace | None:
        if not self._enter("symbol_info_tick"):
            return None
        sym = self.symbols.get(symbol)
        price = self._current_price(symbol)
        if sym is None or price is None:
            return None
        bid, spread, last_minute_utc = price
        now = self.clock.now_utc()
        market_open = bool(market_open_mask(np.array([int(now.timestamp()) // 60 * 60]), sym.schedule)[0])
        tick_utc = now if market_open else datetime.fromtimestamp(last_minute_utc + 59, UTC)
        server_epoch = self.server_clock.utc_to_server_epoch(tick_utc)
        msc = server_epoch * 1000 + (tick_utc.microsecond // 1000)
        return SimpleNamespace(
            time=server_epoch,
            bid=bid,
            ask=round(bid + spread * sym.point, sym.digits),
            last=0.0,
            volume=0,
            time_msc=msc,
            flags=6,
            volume_real=0.0,
        )

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> np.ndarray | None:
        if not self._enter("copy_rates_from_pos"):
            return None
        bars = self._bars(symbol, timeframe)
        if bars is None:
            self._last_error = (-2, "Invalid arguments")
            return None
        end = len(bars) - start_pos
        if end <= 0:
            return np.empty(0, dtype=RATE_DTYPE)
        count = min(count, self.terminal.maxbars)
        return bars[max(0, end - count) : end].copy()

    def copy_rates_range(
        self, symbol: str, timeframe: int, date_from: Any, date_to: Any
    ) -> np.ndarray | None:
        if not self._enter("copy_rates_range"):
            return None
        bars = self._bars(symbol, timeframe)
        if bars is None:
            self._last_error = (-2, "Invalid arguments")
            return None
        lo = _as_epoch(date_from)
        hi = _as_epoch(date_to)
        # Interpret parameters as UTC (per MQL5 moderator guidance) and compare in server time.
        lo_s = self.server_clock.utc_to_server_epoch(datetime.fromtimestamp(lo, UTC))
        hi_s = self.server_clock.utc_to_server_epoch(datetime.fromtimestamp(hi, UTC))
        mask = (bars["time"] >= lo_s) & (bars["time"] <= hi_s)
        return bars[mask].copy()

    def copy_ticks_range(self, symbol: str, date_from: Any, date_to: Any, flags: int) -> np.ndarray | None:
        """Four synthetic ticks per M1 bar (open, first extreme, second extreme, close) consistent with OHLC.

        Up bars visit the low before the high; down bars visit the high first. Times are server epochs.
        """
        if not self._enter("copy_ticks_range"):
            return None
        series = self._series.get(symbol)
        sym = self.symbols.get(symbol)
        if series is None or sym is None:
            self._last_error = (-2, "Invalid arguments")
            return None
        lo, hi = _as_epoch(date_from), _as_epoch(date_to)
        now = int(self.clock.now_utc().timestamp())
        mask = (series.utc >= lo) & (series.utc < min(hi, now + 1))
        idx = np.nonzero(mask)[0]
        n = len(idx)
        out = np.zeros(4 * n, dtype=TICK_DTYPE)
        if n == 0:
            return out
        o, h, lo_p, cl = series.o[idx], series.h[idx], series.lo[idx], series.cl[idx]
        up = cl >= o
        first = np.where(up, lo_p, h)
        second = np.where(up, h, lo_p)
        prices = np.stack([o, first, second, cl], axis=1).reshape(-1)
        offsets_ms = np.tile(np.array([0, 15_000, 30_000, 59_000], dtype=np.int64), n)
        base_ms = np.repeat(series.server[idx] * 1000, 4)
        spreads = np.repeat(series.spread[idx], 4) * sym.point
        out["time_msc"] = base_ms + offsets_ms
        out["time"] = out["time_msc"] // 1000
        out["bid"] = prices
        out["ask"] = np.round(prices + spreads, sym.digits)
        out["flags"] = 6
        return out

    def positions_get(self, symbol: str | None = None, ticket: int | None = None) -> tuple[Any, ...] | None:
        if not self._enter("positions_get"):
            return None
        self.desk.refresh()
        out = [
            p
            for p in self.positions
            if (symbol is None or p.symbol == symbol) and (ticket is None or p.ticket == ticket)
        ]
        return tuple(out)

    def orders_get(self, symbol: str | None = None) -> tuple[Any, ...] | None:
        if not self._enter("orders_get"):
            return None
        return ()

    def history_deals_get(self, date_from: Any, date_to: Any) -> tuple[Any, ...] | None:
        if not self._enter("history_deals_get"):
            return None
        self.desk.refresh()
        lo = _as_epoch(date_from) + self.server_clock.expected_offset_seconds()
        hi = _as_epoch(date_to) + self.server_clock.expected_offset_seconds()
        return tuple(d for d in self.deals if lo <= d.time <= hi)

    def order_calc_profit(
        self, action: int, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None:
        if not self._enter("order_calc_profit"):
            return None
        sym = self.symbols.get(symbol)
        if sym is None:
            return None
        direction = 1 if action == c.ORDER_TYPE_BUY else -1
        profit_ccy = (price_close - price_open) * direction * sym.contract_size * volume
        if sym.currency_base == self.account.currency and sym.currency_profit != self.account.currency:
            return round(profit_ccy / price_close, 2)
        conv = self._conversion_to_account(sym.currency_profit)
        return None if conv is None else round(profit_ccy * conv, 2)

    def order_calc_margin(self, action: int, symbol: str, volume: float, price: float) -> float | None:
        if not self._enter("order_calc_margin"):
            return None
        sym = self.symbols.get(symbol)
        if sym is None:
            return None
        leverage = sym.fixed_leverage or self._account_leverage()
        if sym.calc_mode == c.SYMBOL_CALC_MODE_FOREX:
            conv = self._conversion_to_account(sym.currency_base)
            if conv is not None:
                return round(sym.contract_size * volume * conv / leverage, 2)
        # CFD-style (and metals without a base-currency quote): notional = price x contract x volume
        conv_profit = self._conversion_to_account(sym.currency_profit)
        if conv_profit is None:
            return None
        return round(price * sym.contract_size * volume * conv_profit / leverage, 2)

    def order_check(self, request: dict[str, Any]) -> SimpleNamespace | None:
        if not self._enter("order_check"):
            return None
        self.desk.refresh()
        return self.desk.order_check(request)

    def order_send(self, request: dict[str, Any]) -> SimpleNamespace | None:
        """Emulated trade server (``app/broker/fake_trading.py``); ``calls`` counts every attempt."""
        if not self._enter("order_send"):
            return None
        self.desk.refresh()
        return self.desk.order_send(request)


def _as_epoch(value: Any) -> int:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime passed to FakeMT5")
        return int(value.timestamp())
    return int(value)
