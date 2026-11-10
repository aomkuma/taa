"""The replay of the run-zone runner against the simulation (eye/ZONE_LIVE.md L11.2).

A replay broker - a test double, not FakeMT5 - serves the runner (``app.zone.trader.ZoneRunner``, unchanged, its
clock / gateway / execution / bar source injected) the stored bars, walks the quote path of every ``exec_tf``
bar tick by tick and works the runner's orders: a limit fills at its price when the path crosses it (BUY:
ask <= P; SELL: bid >= P), a stop-loss and a take-profit exit at their prices on the crossing tick, independently
of the runner's cycles. ``tests/zone_replay_compare.py`` then sets the runner's rows against ``run_zone`` (the
simulation) both ways.

Only the account / terminal / symbol snapshots and the server clock are minted once from FakeMT5's snapshots
(``snapshots_from_fake``); every order, position, deal and history record is this module's."""

from __future__ import annotations

import bisect
import logging
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.broker import mt5_constants as c
from app.broker.execution import CheckResult, SendResult
from app.broker.models import (
    AccountSnapshot,
    BrokerOrder,
    BrokerPosition,
    Deal,
    HistoryOrder,
    TerminalSnapshot,
)
from app.broker.retcodes import classify, describe
from app.core.clock import ManualClock, ServerClock
from app.core.enums import Side, TradingMode
from app.market_data.data_models import SymbolSpec, Tick
from app.risk.kill_switch import KillSwitch
from app.storage.database import Database
from app.zone.core import Bars, cut_bars
from app.zone.params import ZoneParams
from app.zone.trader import DECIDE_SECONDS, RunnerConfig, ZoneRunner

SYMBOL = "XAUUSD"
MAGIC = 7_310_100
CENT = 100
START_LEAD_SECONDS = 5.0  # the runner starts this long before the replay's first H1 open


def utc(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, UTC)


def ts_seconds(t: pd.Timestamp) -> float:
    return t.value / 1e9


# --- the bars the runner is served ----------------------------------------------------------------------------


class ReplayBars:
    """``BarSource``: the stored bars closed by the replay clock; the forming H1 bar's open."""

    def __init__(self, full: Bars, clock: ManualClock) -> None:
        self.clock = clock
        self.frames = {tf: full.frame(tf) for tf in ("D1", "H4", "H1", "M15", "M5")}
        self.close_ns = {
            tf: f["close_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
            for tf, f in self.frames.items()
        }
        self.open_ns = {
            tf: f["open_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
            for tf, f in self.frames.items()
        }
        self.open_idx = {tf: pd.DatetimeIndex(f["open_time"]) for tf, f in self.frames.items()}
        self.empty = {tf: f.iloc[0:0] for tf, f in self.frames.items()}
        self.h1_open = self.frames["H1"]["open"].to_numpy(float)

    def _now_ns(self) -> int:
        return int(pd.Timestamp(self.clock.now_utc()).value)

    def _closed(self, tf: str) -> int:
        return int(np.searchsorted(self.close_ns[tf], self._now_ns(), side="right"))

    def closed_bars(self, tf: str, after: pd.Timestamp | None) -> pd.DataFrame:
        k = self._closed(tf)
        start = 0 if after is None else int(np.searchsorted(self.open_ns[tf], after.value, side="right"))
        if start >= k:
            return self.empty[tf]
        return self.frames[tf].iloc[start:k].reset_index(drop=True)

    def last_closed_open(self, tf: str) -> pd.Timestamp | None:
        k = self._closed(tf)
        return None if k == 0 else pd.Timestamp(self.open_idx[tf][k - 1])

    def forming_h1(self) -> tuple[pd.Timestamp, float] | None:
        now = self._now_ns()
        k = int(np.searchsorted(self.open_ns["H1"], now, side="right")) - 1
        if k < 0 or now >= self.close_ns["H1"][k]:
            return None
        return pd.Timestamp(self.open_idx["H1"][k]), float(self.h1_open[k])


# --- the broker -----------------------------------------------------------------------------------------------


@dataclass
class _Order:
    ticket: int
    buy: bool
    volume: float
    price: float
    price_c: int
    sl: float
    tp: float
    magic: int
    comment: str
    setup_s: float
    exp_s: float | None
    exp_epoch: int | None


@dataclass
class _Pos:
    ticket: int
    buy: bool
    volume: float
    price_open: float
    sl: float
    tp: float
    magic: int
    comment: str
    time_s: float
    order: int


@dataclass
class Event:
    """What the broker did, with the replay time (for the explanations of the comparison)."""

    t: float
    kind: str  # place | fill | market | exit | expire | cancel | modify | sltp | close
    comment: str
    price: float
    detail: str = ""


_SNAPSHOTS: dict[tuple[Any, ...], tuple[AccountSnapshot, TerminalSnapshot, SymbolSpec]] = {}


def snapshots_from_fake(
    settings: Any, clock: ManualClock
) -> tuple[AccountSnapshot, TerminalSnapshot, SymbolSpec, ServerClock]:
    """The account / terminal / symbol snapshots and the server clock, taken from FakeMT5's gateway. Building a
    FakeMT5 allocates ~66 MB and takes ~2 s, and many tests ask for the same one, so the three FROZEN snapshots are
    cached per process, keyed on everything they depend on (mode, server, login, broker timezone, clock time).
    Without the cache, parallel pytest processes exhausted the machine's commit limit and failed with numpy's
    ArrayMemoryError in whichever test built the next FakeMT5. The ``ServerClock`` is mutable (it holds the caller's
    clock): it is built fresh from the caller's own clock on every call and never shared."""
    from app.broker.factory import build_trading

    env = settings.env
    key = (
        str(env.TRADING_MODE),
        str(env.MT5_SERVER),
        env.MT5_LOGIN,
        str(env.BROKER_TIMEZONE),
        clock.now_utc(),
    )
    if key not in _SNAPSHOTS:
        bundle = build_trading(settings, fake=True, clock=clock)
        bundle.client.connect()
        spec = bundle.gateway.symbol_spec(SYMBOL)
        _SNAPSHOTS[key] = (bundle.gateway.account(), bundle.gateway.terminal(), spec)
        del bundle
    account, terminal, spec = _SNAPSHOTS[key]
    return account, terminal, spec, ServerClock(env.BROKER_TIMEZONE, clock)


class ReplayBroker:
    """The replay broker: ``ZoneGateway`` + ``ZoneExecution`` for the runner, and the market engine the replay
    driver feeds one tick at a time (``on_tick``)."""

    def __init__(
        self,
        clock: ManualClock,
        account: AccountSnapshot,
        terminal: TerminalSnapshot,
        spec: SymbolSpec,
        server_clock: ServerClock,
    ) -> None:
        if abs(spec.tick_size - 0.01) > 1e-12 or abs(spec.point - 0.01) > 1e-12:
            raise ValueError("the replay walks the quote in steps of 0.01: tick size and point must be 0.01")
        self.clock = clock
        self._account, self._terminal, self._spec = account, terminal, spec
        self.server_clock = server_clock
        self.orders_: dict[int, _Order] = {}
        self.positions_: dict[int, _Pos] = {}
        self.deals_: list[Deal] = []
        self._deal_t: list[float] = []
        self.history_: list[HistoryOrder] = []
        self._hist_t: list[float] = []
        self.events: list[Event] = []
        self.requests: list[tuple[float, dict[str, Any], int | None]] = []
        self._next = 9_000_000
        self.bid_c = 0
        self.ask_c = 0
        self.spread_c = 0
        self.t_s = 0.0
        self.tick_s = 0.0  # the time of the latest tick: the quote is stamped with it
        self.have_tick = False
        self.version = 0  # bumped on every change a cycle could see

    def _id(self) -> int:
        self._next += 1
        return self._next

    # --- the market engine: one tick ---
    def on_tick(self, bid_c: int, spread_c: int, t_s: float) -> None:
        self.bid_c, self.spread_c, self.ask_c, self.t_s = bid_c, spread_c, bid_c + spread_c, t_s
        self.have_tick = True
        self.tick_s = t_s
        if self.orders_:
            for o in [o for o in self.orders_.values() if o.exp_s is not None and o.exp_s <= t_s]:
                self._expire(o, o.exp_s if o.exp_s is not None else t_s)
            for o in list(self.orders_.values()):
                if (o.buy and self.ask_c <= o.price_c) or (not o.buy and self.bid_c >= o.price_c):
                    self._fill_order(o, t_s)
        if self.positions_:
            for p in list(self.positions_.values()):
                self._check_exit(p, t_s)

    def expire_until(self, t_s: float) -> None:
        if self.orders_:
            for o in [o for o in self.orders_.values() if o.exp_s is not None and o.exp_s <= t_s]:
                self._expire(o, o.exp_s if o.exp_s is not None else t_s)

    def _expire(self, o: _Order, when: float) -> None:
        del self.orders_[o.ticket]
        self._history(o, c.ORDER_STATE_EXPIRED, when, 0)
        self.events.append(Event(when, "expire", o.comment, o.price))
        self.version += 1

    def _history(self, o: _Order, state: int, when: float, position_id: int) -> None:
        self.history_.append(
            HistoryOrder(
                o.ticket,
                position_id,
                SYMBOL,
                c.ORDER_TYPE_BUY_LIMIT if o.buy else c.ORDER_TYPE_SELL_LIMIT,
                state,
                o.volume,
                0.0 if state == c.ORDER_STATE_FILLED else o.volume,
                o.price,
                o.sl,
                o.tp,
                o.magic,
                o.comment,
                utc(o.setup_s),
                utc(when),
                None if o.exp_s is None else utc(o.exp_s),
            )
        )
        self._hist_t.append(when)

    def _deal(
        self,
        buy: bool,
        entry: int,
        volume: float,
        price: float,
        pos: int,
        order: int,
        magic: int,
        comment: str,
        when: float,
        reason: int,
        profit: float = 0.0,
    ) -> Deal:
        d = Deal(
            self._id(),
            order,
            pos,
            SYMBOL,
            c.DEAL_TYPE_BUY if buy else c.DEAL_TYPE_SELL,
            entry,
            volume,
            price,
            profit,
            0.0,
            0.0,
            0.0,
            magic,
            comment,
            utc(when),
            reason,
        )
        self.deals_.append(d)
        self._deal_t.append(when)
        return d

    def _open_position(
        self,
        buy: bool,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        magic: int,
        comment: str,
        order: int,
        when: float,
    ) -> _Pos:
        p = _Pos(self._id(), buy, volume, price, sl, tp, magic, comment, when, order)
        self.positions_[p.ticket] = p
        self._deal(
            buy, c.DEAL_ENTRY_IN, volume, price, p.ticket, order, magic, comment, when, c.DEAL_REASON_EXPERT
        )
        self.version += 1
        return p

    def _fill_order(self, o: _Order, when: float) -> None:
        del self.orders_[o.ticket]
        p = self._open_position(o.buy, o.volume, o.price, o.sl, o.tp, o.magic, o.comment, o.ticket, when)
        self._history(o, c.ORDER_STATE_FILLED, when, p.ticket)
        self.events.append(Event(when, "fill", o.comment, o.price))

    def _close_position(
        self, p: _Pos, price: float, when: float, reason: int, kind: str, volume: float | None = None
    ) -> None:
        """Close ``volume`` of the position (all of it by default); a partial close leaves the rest open."""
        vol = p.volume if volume is None else volume
        if vol < p.volume - 1e-9:
            p.volume = round(p.volume - vol, 8)
        else:
            del self.positions_[p.ticket]
        sgn = 1 if p.buy else -1
        self._deal(
            not p.buy,
            c.DEAL_ENTRY_OUT,
            vol,
            price,
            p.ticket,
            0,
            p.magic,
            "",
            when,
            reason,
            profit=sgn * (price - p.price_open) * vol * 100.0,
        )
        self.events.append(Event(when, kind, p.comment, price, f"reason {reason}"))
        self.version += 1

    def _check_exit(self, p: _Pos, when: float) -> None:
        sl_c = round(p.sl * CENT) if p.sl else None
        tp_c = round(p.tp * CENT) if p.tp else None
        if p.buy:
            if sl_c is not None and self.bid_c <= sl_c:
                self._close_position(p, p.sl, when, c.DEAL_REASON_SL, "exit")
            elif tp_c is not None and self.bid_c >= tp_c:
                self._close_position(p, p.tp, when, c.DEAL_REASON_TP, "exit")
        else:
            if sl_c is not None and self.ask_c >= sl_c:
                self._close_position(p, p.sl, when, c.DEAL_REASON_SL, "exit")
            elif tp_c is not None and self.ask_c <= tp_c:
                self._close_position(p, p.tp, when, c.DEAL_REASON_TP, "exit")

    # --- ZoneGateway ---
    def terminal(self) -> TerminalSnapshot:
        return self._terminal

    def account(self) -> AccountSnapshot:
        return self._account

    def symbol_spec(self, symbol: str) -> SymbolSpec:
        return self._spec

    def tick(self, symbol: str) -> Tick | None:
        """The latest quote, stamped with the time of its own tick (a flat bar with ticks far apart is stale)."""
        if not self.have_tick:
            return None
        when = utc(self.tick_s)
        return Tick(SYMBOL, int(self.tick_s * 1000), when, self.bid_c / CENT, self.ask_c / CENT)

    def positions(self, symbol: str | None = None) -> list[BrokerPosition]:
        return [
            BrokerPosition(
                p.ticket,
                SYMBOL,
                Side.BUY if p.buy else Side.SELL,
                p.volume,
                p.price_open,
                p.sl,
                p.tp,
                self.bid_c / CENT,
                0.0,
                0.0,
                p.magic,
                p.comment,
                utc(p.time_s),
                p.ticket,
            )
            for p in self.positions_.values()
        ]

    def orders(self, symbol: str | None = None) -> list[BrokerOrder]:
        self.expire_until(ts_seconds(pd.Timestamp(self.clock.now_utc())))
        return [
            BrokerOrder(
                o.ticket,
                SYMBOL,
                Side.BUY if o.buy else Side.SELL,
                c.ORDER_TYPE_BUY_LIMIT if o.buy else c.ORDER_TYPE_SELL_LIMIT,
                o.volume,
                o.price,
                o.sl,
                o.tp,
                o.magic,
                o.comment,
                utc(o.setup_s),
                None if o.exp_s is None else utc(o.exp_s),
            )
            for o in self.orders_.values()
        ]

    def deals(self, start_utc: datetime, end_utc: datetime) -> list[Deal]:
        a = bisect.bisect_left(self._deal_t, start_utc.timestamp())
        b = bisect.bisect_left(self._deal_t, end_utc.timestamp())
        return self.deals_[a:b]

    def history_orders(self, start_utc: datetime, end_utc: datetime) -> list[HistoryOrder]:
        a = bisect.bisect_left(self._hist_t, start_utc.timestamp())
        b = bisect.bisect_left(self._hist_t, end_utc.timestamp())
        return self.history_[a:b]

    # --- ZoneExecution ---
    def check(self, request: dict[str, Any]) -> CheckResult:
        return CheckResult(0, "Done")

    def _result(self, code: int, **kw: Any) -> SendResult:
        return SendResult(code, classify(code), describe(code), **kw)

    def send(self, request: dict[str, Any]) -> SendResult:
        now_s = ts_seconds(pd.Timestamp(self.clock.now_utc()))
        res = self._send(request, now_s)
        # the ticket the broker gave an order is kept with the request: the gate ties a modify to its order
        rec_req = {**request, "_order": res.order}
        if request.get("expiration"):  # the expiry in UTC seconds, as the double understood it
            rec_req["_exp_s"] = self.server_clock.server_epoch_to_utc(int(request["expiration"])).timestamp()
        self.requests.append((now_s, rec_req, res.retcode))
        return res

    def _send(self, req: dict[str, Any], now_s: float) -> SendResult:
        action = int(req["action"])
        if action == c.TRADE_ACTION_PENDING:
            return self._pending(req, now_s)
        if action == c.TRADE_ACTION_DEAL:
            return self._deal_request(req, now_s)
        if action == c.TRADE_ACTION_REMOVE:
            o = self.orders_.get(int(req["order"]))
            if o is None:
                return self._result(10013)
            del self.orders_[o.ticket]
            self._history(o, c.ORDER_STATE_CANCELED, now_s, 0)
            self.events.append(Event(now_s, "cancel", o.comment, o.price))
            self.version += 1
            return self._result(10009, order=o.ticket)
        if action == c.TRADE_ACTION_MODIFY:
            return self._modify(req, now_s)
        if action == c.TRADE_ACTION_SLTP:
            p = self.positions_.get(int(req["position"]))
            if p is None:
                return self._result(10036)
            sl, tp = float(req.get("sl", 0.0)), float(req.get("tp", 0.0))
            if sl and (
                (p.buy and round(sl * CENT) >= self.bid_c) or (not p.buy and round(sl * CENT) <= self.ask_c)
            ):
                return self._result(10016)
            if tp and (
                (p.buy and round(tp * CENT) <= self.bid_c) or (not p.buy and round(tp * CENT) >= self.ask_c)
            ):
                return self._result(10016)
            if sl == p.sl and tp == p.tp:
                return self._result(10025)
            p.sl, p.tp = sl, tp
            self.events.append(Event(now_s, "sltp", p.comment, sl, f"tp {tp}"))
            self.version += 1
            return self._result(10009)
        return self._result(10013)

    def _modify(self, req: dict[str, Any], now_s: float) -> SendResult:
        """As MT5: the order takes the request's price, SL, TP and time type (and expiration)."""
        o = self.orders_.get(int(req["order"]))
        if o is None:
            return self._result(10013)
        price = float(req.get("price", o.price))
        price_c = round(price * CENT)
        sl, tp = float(req.get("sl", o.sl)), float(req.get("tp", o.tp))
        if (o.buy and price_c >= self.ask_c) or (not o.buy and price_c <= self.bid_c) or price_c <= 0:
            return self._result(10015)
        exp_s: float | None = None
        epoch: int | None = None
        if int(req.get("type_time", c.ORDER_TIME_GTC)) == c.ORDER_TIME_SPECIFIED:
            epoch = int(req.get("expiration", 0) or 0)
            if epoch <= 0:
                return self._result(10022)
            exp_s = self.server_clock.server_epoch_to_utc(epoch).timestamp()
            if exp_s <= now_s:
                return self._result(10022)
        if (price_c, sl, tp, epoch) == (o.price_c, o.sl, o.tp, o.exp_epoch):
            return self._result(10025)
        o.price, o.price_c, o.sl, o.tp, o.exp_epoch, o.exp_s = price, price_c, sl, tp, epoch, exp_s
        self.events.append(Event(now_s, "modify", o.comment, price, f"sl {sl} tp {tp} expires {exp_s}"))
        self.version += 1
        return self._result(10009, order=o.ticket)

    def _pending(self, req: dict[str, Any], now_s: float) -> SendResult:
        buy = int(req["type"]) == c.ORDER_TYPE_BUY_LIMIT
        price = float(req["price"])
        price_c = round(price * CENT)
        if (buy and price_c >= self.ask_c) or (not buy and price_c <= self.bid_c) or price_c <= 0:
            return self._result(10015)
        exp_s: float | None = None
        epoch: int | None = None
        if int(req.get("type_time", c.ORDER_TIME_GTC)) == c.ORDER_TIME_SPECIFIED:
            epoch = int(req.get("expiration", 0) or 0)
            exp_s = self.server_clock.server_epoch_to_utc(epoch).timestamp()
            if exp_s <= now_s:
                return self._result(10022)
        o = _Order(
            self._id(),
            buy,
            float(req["volume"]),
            price,
            price_c,
            float(req.get("sl", 0.0)),
            float(req.get("tp", 0.0)),
            int(req.get("magic", 0)),
            str(req.get("comment", "")),
            now_s,
            exp_s,
            epoch,
        )
        self.orders_[o.ticket] = o
        self.events.append(Event(now_s, "place", o.comment, price))
        self.version += 1
        return self._result(10008, order=o.ticket, volume=o.volume, price=price)

    def _deal_request(self, req: dict[str, Any], now_s: float) -> SendResult:
        position = int(req.get("position", 0) or 0)
        if position:
            p = self.positions_.get(position)
            if p is None:
                return self._result(10036)
            # as MT5: the close names the symbol, the OPPOSITE side and a volume not above the position's
            if req.get("symbol") != SYMBOL:
                return self._result(10013)
            if int(req.get("type", -1)) != (c.ORDER_TYPE_SELL if p.buy else c.ORDER_TYPE_BUY):
                return self._result(10013)
            vol = float(req.get("volume", 0.0))
            if vol <= 0 or vol > p.volume + 1e-9:
                return self._result(10014)
            price = self.bid_c / CENT if p.buy else self.ask_c / CENT
            self._close_position(p, price, now_s, c.DEAL_REASON_EXPERT, "close", vol)
            return self._result(10009, deal=self.deals_[-1].ticket, volume=vol, price=price)
        buy = int(req["type"]) == c.ORDER_TYPE_BUY
        price = self.ask_c / CENT if buy else self.bid_c / CENT
        order = self._id()
        p = self._open_position(
            buy,
            float(req["volume"]),
            price,
            float(req.get("sl", 0.0)),
            float(req.get("tp", 0.0)),
            int(req.get("magic", 0)),
            str(req.get("comment", "")),
            order,
            now_s,
        )
        self.events.append(Event(now_s, "market", p.comment, price))
        return self._result(10009, order=order, deal=self.deals_[-1].ticket, volume=p.volume, price=price)


# --- the quote path of a bar -------------------------------------------------------------------------------


def bar_path(
    o: float, h: float, low: float, c_: float, open_s: float, close_s: float, preclose: float
) -> tuple[np.ndarray, np.ndarray]:
    """The bid ticks (in cents) and their times (seconds) of one ``exec_tf`` bar: the open, the extreme nearer
    the open, the other extreme, the close, in steps of one cent; evenly over the bar's period, the first tick at
    its open, the last ``preclose / 2`` before its close."""
    oc, hc, lc, cc = round(o * CENT), round(h * CENT), round(low * CENT), round(c_ * CENT)
    hc, lc = max(hc, oc, cc), min(lc, oc, cc)
    first, second = (hc, lc) if hc - oc < oc - lc else (lc, hc)
    pts = [oc, first, second, cc]
    legs = [np.arange(a, b, 1 if b > a else -1, dtype=np.int64) for a, b in pairwise(pts)]
    arr = np.concatenate([*legs, np.array([cc], dtype=np.int64)])
    arr = arr[np.concatenate([[True], np.diff(arr) != 0])]
    if len(arr) < 2:
        arr = np.array([oc, cc], dtype=np.int64)
    last_s = close_s - preclose / 2
    times = open_s + (last_s - open_s) * np.arange(len(arr)) / (len(arr) - 1)
    return arr, times


# --- the replay driver -----------------------------------------------------------------------------------------


@dataclass
class ReplayConfig:
    tf: str = "M15"
    mode: str = "tick"  # tick: a cycle after every tick; poll: a cycle every cycle_seconds
    cycle_seconds: float = 2.0
    preclose_seconds: float = 15.0
    epoch: pd.Timestamp = field(default_factory=lambda: pd.Timestamp("2023-10-01", tz="UTC"))
    gate: bool = True  # skip a cycle that cannot change a decision (see ``Replay._maybe_cycle``)


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.lines: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append((record.levelname, record.getMessage()))


class Replay:
    """One replay: the runner on the replay broker from ``start`` (an H1 open) to ``end``."""

    def __init__(
        self,
        full: Bars,
        params: ZoneParams,
        settings: Any,
        cfg: ReplayConfig,
        start: pd.Timestamp,
        end: pd.Timestamp,
        lock_dir: Path | None = None,
    ) -> None:
        self.full, self.params, self.cfg = full, params, cfg
        self.start, self.end = start, end
        # L11.2: the replay starts a few seconds before an H1 open (L8: the first decision is the first H1 open
        # after the start), with the stored bars cut there
        self.boot = start - pd.Timedelta(seconds=START_LEAD_SECONDS)
        self.clock = ManualClock(self.boot.to_pydatetime())
        account, terminal, spec, server_clock = snapshots_from_fake(settings, self.clock)
        self.spec = spec
        self.broker = ReplayBroker(self.clock, account, terminal, spec, server_clock)
        self.src = ReplayBars(full, self.clock)
        self.db = Database("sqlite://")
        self.db.create_all()
        kill = KillSwitch((lock_dir or Path(".")) / "NO_KILL_SWITCH_FILE_FOR_THE_REPLAY", clock=self.clock)
        rc = RunnerConfig(
            lot=0.01,
            cycle_seconds=cfg.cycle_seconds,
            stale_quote_seconds=30.0,
            preclose_seconds=cfg.preclose_seconds,
            epoch=cfg.epoch,
            symbol=SYMBOL,
            market=SYMBOL,
            set_name="default",
            set_version=1,
            mode=TradingMode.DEMO,
            env=settings.env,
        )
        self.runner = ZoneRunner(
            cfg=rc,
            params=params,
            clock=self.clock,
            gateway=self.broker,
            execution=self.broker,
            bar_source=self.src,
            db=self.db,
            bars=cut_bars(full, self.boot),
            kill_switch=kill,
            magic=MAGIC,
        )
        self.collect = _Collect()
        logging.getLogger("app.zone").addHandler(self.collect)
        logging.getLogger("app.zone").setLevel(logging.WARNING)
        self.cycles = 0
        self.skipped = 0
        self.progress = False
        self.cycle_log: list[
            tuple[float, int, int]
        ] = []  # (time, bid cents, ask cents) of every cycle that ran
        self._last_bid_c: int | None = None
        self._last_version = -1
        self._last_cycle_s = -1.0
        self._last_tick_s = -1.0
        self._last_stale = False
        self._seen_s = -1.0  # the latest time a cycle was run or considered (the gap fill starts after it)
        self._open_intent = False
        # L11.2: the facts the gate reads of the runner's hours and stale data (``gate_failures``)
        self.decided_first: float | None = None  # the open of the runner's first decided hour
        self.undecided_hours: dict[float, str] = {}  # hour open -> why it was not decided
        self.stale_events: list[float] = []  # the cycles at which a stale-data removal fell due
        self._stale_latched = False
        self.stale_seconds = 30.0
        self._levels: list[float] = []
        self._ext_at: float | None = None

    def close(self) -> None:
        logging.getLogger("app.zone").removeHandler(self.collect)
        self.db.dispose()

    # --- the levels the runner compares the quote to: used only to skip a cycle that cannot change a decision ---
    def _refresh_levels(self) -> None:
        lv: set[float] = set()
        for cd in self.runner.cands.values():
            if cd.dropped:
                continue
            v, pl, sp = cd.visit, cd.plan, cd.sent
            lv.update(
                (v.line, v.line + v.z, v.line - v.z, pl.p1, pl.p2, pl.sl, pl.tp, sp.p1, sp.p2, sp.sl, sp.tp)
            )
            lv.update((v.line + pl.away, v.line - pl.away, v.line + pl.cancel, v.line - pl.cancel))
            for x in (cd.be_sent, cd.be_sl):
                if x is not None:
                    lv.add(x)
            if cd.fills:
                avg = float(np.mean([f.price for f in cd.fill_list()]))
                lv.update((avg, avg + pl.be_frac * (pl.tp - avg)))
        for p in self.broker.positions_.values():
            lv.update((p.sl, p.tp))
        for o in self.broker.orders_.values():
            lv.update((o.price, o.sl, o.tp))
        self._levels = sorted(x for x in lv if x)
        exp = [o.exp_s for o in self.broker.orders_.values() if o.exp_s is not None]
        self._ext_at = (min(exp) - 600.0) if exp else None

    def _crossed(self, bid_c: int, spread_c: int) -> bool:
        if self._last_bid_c is None:
            return True
        lo, hi = sorted((self._last_bid_c, bid_c))
        margin = spread_c + 3
        i = bisect.bisect_left(self._levels, (lo - margin) / CENT - 1e-9)
        return i < len(self._levels) and self._levels[i] <= (hi + margin) / CENT + 1e-9

    def _run_cycle(self, t_s: float) -> None:
        version0 = self.broker.version
        self.clock.set(utc(t_s))
        self.runner.cycle()
        self.cycles += 1
        self._last_bid_c = self.broker.bid_c
        self._last_version = self.broker.version if self.broker.version == version0 else -1
        self._last_cycle_s = t_s
        self._seen_s = max(self._seen_s, t_s)
        self._last_tick_s = self.broker.tick_s
        self._last_stale = t_s - self.broker.tick_s >= self.stale_seconds
        self.cycle_log.append((t_s, self.broker.bid_c, self.broker.ask_c))
        self._note_hours_and_stale(t_s)
        store = self.runner.store
        # a place request still "intent" (outcome unknown) is searched by the runner every cycle
        self._open_intent = store is not None and bool(
            store.requests(kinds=("place",), states=("intent",), limit=1)
        )
        self._refresh_levels()

    def _note_hours_and_stale(self, t_s: float) -> None:
        """The facts of this cycle the gate needs: the hour decided or not, a stale-data removal falling due
        (the stale debt or a stale interruption latched)."""
        r = self.runner
        h = r.hour
        if h is not None:
            if h.decided and self.decided_first is None:
                self.decided_first = h.open.timestamp()
            elif h.undecided:
                self.undecided_hours.setdefault(h.open.timestamp(), str(h.undecided))
        latched = bool(r.stale_owed or r.interrupt_owed == "stale")
        if latched and not self._stale_latched:
            self.stale_events.append(t_s)
        self._stale_latched = latched

    def _decision_pending(self, t_s: float) -> bool:
        """L2: inside an hour's 60 s decision window, the hour not yet decided - a cycle may decide it."""
        r = self.runner
        h = r.hour
        if h is None or h.decided or h.undecided or h.reserved:
            return False
        first = r._hour_first_quote(h.open)
        return t_s - first.timestamp() <= DECIDE_SECONDS

    def _retry_pending(self) -> bool:
        """A request the runner retries every cycle (a refused modify / remove / stops / close, a refused P2 or
        P1) changes no broker version, so while one is pending no cycle is skipped."""
        r = self.runner  # direct attribute access: a rename in the runner must fail loudly, not silently gate
        return bool(
            r.pending
            or r.close_wanted
            or r.stale_owed  # the latch is released by a cycle (L7): the next cycle can place again
            # every latch and L8 timer the runner holds: a cycle can act on it whatever the broker does
            or r.interrupt_owed is not None
            or r.unwanted
            or r.unknown_since
            or r.gone_since
            or r.entries
            or r.exit_since
            or r.remove_since
            or r.close_since
            or r.market_since
            or any(cd.refusals for cd in r.cands.values())
            or self._open_intent
        )

    def _quote_aging(self, t_s: float) -> bool:
        """The quote is old enough to turn stale (or the last cycle saw it stale and a new tick came): the
        runner's stale-quote handling depends on time alone."""
        stale = self.stale_seconds
        if t_s - self.broker.tick_s >= stale - 2 * self.cfg.cycle_seconds:
            # the quote turns stale: a cycle at the crossing; while it stays stale the runner's state changes
            # with time only through its stale timer (removals after one bar of staleness, L7)
            if not self._last_stale:
                return True
            since = self.runner.stale_since
            if since is not None:
                due = since.timestamp() + self.runner.period_s
                return self._last_cycle_s < due <= t_s
            return False
        return self._last_stale and self.broker.tick_s != self._last_tick_s

    def _maybe_cycle(self, t_s: float, close_s: float, force: bool = False) -> None:
        """Run a cycle, unless (``gate``) nothing a decision depends on has happened since the last one: the
        broker unchanged, outside the pre-close window, no expiry extension due, and no level the runner
        compares the quote to lies between the last cycle's bid and this one (a cycle with the same inputs does
        nothing: the inputs of a cycle are the quote, the broker's state, the bars and the time)."""
        self._seen_s = max(self._seen_s, t_s)
        if not self.cfg.gate or force:
            self._run_cycle(t_s)
            return
        if (
            self.broker.version != self._last_version
            or self._retry_pending()
            or self._decision_pending(t_s)
            or self._quote_aging(t_s)
            or close_s - t_s <= self.cfg.preclose_seconds + self.cfg.cycle_seconds
            or (self._ext_at is not None and t_s >= self._ext_at and self._last_cycle_s < self._ext_at)
            or self._crossed(self.broker.bid_c, self.broker.spread_c)
        ):
            self._run_cycle(t_s)
        else:
            self.skipped += 1

    def run(self) -> None:
        cfg = self.cfg
        fr = self.full.frame(cfg.tf)
        open_ns = fr["open_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
        close_ns = fr["close_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
        j0 = int(np.searchsorted(open_ns, self.start.value, side="left"))
        j1 = int(np.searchsorted(close_ns, self.end.value, side="right"))
        o, h, low, c_ = (fr[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        spread = fr["spread"].to_numpy(int)
        if j0 > 0:
            # as live: the broker's quote at the runner's start is the last tick before the span (stamped before
            # its first hour - Friday's last when the span opens the week), so the runner's reads before the hour
            # are quote reads with an old stamp (L2's last pre-hour read); the gap to the span's first tick is
            # cycled by ``_fill_gap``
            pb, pt = bar_path(
                o[j0 - 1],
                h[j0 - 1],
                low[j0 - 1],
                c_[j0 - 1],
                open_ns[j0 - 1] / 1e9,
                close_ns[j0 - 1] / 1e9,
                cfg.preclose_seconds,
            )
            self.broker.on_tick(int(pb[-1]), int(spread[j0 - 1]), float(pt[-1]))
        self.runner.start()
        self._run_cycle(ts_seconds(self.start))
        t_start, day = time.time(), -1
        for j in range(j0, j1):
            open_s, close_s = open_ns[j] / 1e9, close_ns[j] / 1e9
            if self.progress and int(open_s // 86400) != day:
                day = int(open_s // 86400)
                print(
                    f"  {utc(open_s):%Y-%m-%d} cycles {self.cycles} skipped {self.skipped} "
                    f"events {len(self.broker.events)} {time.time() - t_start:.0f} s",
                    file=sys.stderr,
                    flush=True,
                )
            bids, times = bar_path(o[j], h[j], low[j], c_[j], open_s, close_s, cfg.preclose_seconds)
            sp = int(spread[j])
            if cfg.mode == "tick":
                self._bar_ticks(bids, times, sp, close_s)
            else:
                self._bar_poll(bids, times, sp, open_s, close_s)
            if (
                j + 1 >= j1 or open_ns[j + 1] > close_ns[j]
            ):  # the bar's close is seen even when no tick follows
                self.broker.expire_until(close_s)
                self._maybe_cycle(close_s, close_s + 1e9, force=True)

    def _fill_gap(self, t_next: float, close_s: float) -> None:
        """L11.2 - through any gap between two ticks longer than ``stale_quote_seconds`` (the daily break, the
        weekend, a quiet market) the runner keeps cycling, every ``cycle_seconds`` of replay time with the
        quote unchanged (the cycles the gate can skip are skipped; the last one before the next tick is run:
        it is the read the next tick's hour counts its first quote from, L2)."""
        prev = self.broker.tick_s
        if prev <= 0.0 or t_next - prev <= self.stale_seconds:
            return
        cs = self.cfg.cycle_seconds
        slot = (math.floor(max(self._seen_s, prev) / cs) + 1) * cs
        while slot < t_next - 1e-9:
            self._maybe_cycle(slot, close_s, force=slot + cs >= t_next - 1e-9)
            slot += cs

    def _bar_ticks(self, bids: np.ndarray, times: np.ndarray, sp: int, close_s: float) -> None:
        br = self.broker
        for k in range(len(bids)):
            t = float(times[k])
            self._fill_gap(t, close_s)
            br.on_tick(int(bids[k]), sp, t)
            self._maybe_cycle(t, close_s, force=k == 0)

    def _bar_poll(self, bids: np.ndarray, times: np.ndarray, sp: int, open_s: float, close_s: float) -> None:
        br, cs = self.broker, self.cfg.cycle_seconds
        n, k = len(bids), 0
        self._fill_gap(float(times[0]), close_s)
        slot = math.ceil(open_s / cs) * cs
        first = True
        while slot < close_s - 1e-9:
            while k < n and times[k] <= slot + 1e-9:
                br.on_tick(int(bids[k]), sp, float(times[k]))
                k += 1
            self._maybe_cycle(slot, close_s, force=first)
            first = False
            slot += cs
        while k < n:  # ticks after the last slot of the bar (before its close)
            br.on_tick(int(bids[k]), sp, float(times[k]))
            k += 1
