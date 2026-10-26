"""The AI trader as a lane strategy (PLAN §A37, TAA-1806): its own name, magic number, statistics and Trade
history like any strategy. It never asks the AI itself (strategy code is pure): the engine hands it the AI's
decisions (:meth:`AITrader.accept`, :meth:`AITrader.request_exit`) and feeds it quotes (:meth:`on_quote`), the
path of the release straddle. Every entry it makes is an ordinary signal: the decision engine sizes it by the
owner's profile (the AI's 'half' halves the risk) and runs every check.

An order fills at the quote once price is at the AI's entry (within ``market_tolerance``): a sell when the bid
is at or above it, a buy when the ask is at or below it. It is dropped when its stop is touched first, after
``pending_minutes``, or when a new decision replaces it.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from pydantic import Field

from app.core.clock import ensure_utc
from app.core.enums import Action, ExitReason, Side, Timeframe
from app.strategy import confirm as cf
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.signal_models import (
    Condition,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    StrategyContext,
)

Held = tuple[Side, float, float | None, float | None, datetime]  # side, entry, stop, target, opened


@dataclass(frozen=True)
class AIOrder:
    """One AI decision to enter, as the engine hands it over."""

    side: Side
    entry: float
    stop: float
    target: float | None
    risk_scale: float  # 1.0 for 'full', 0.5 for 'half'
    setup: str
    reasons: tuple[str, ...]
    kb_ids: tuple[str, ...]
    confidence: int
    decided_at: datetime
    valid_until: datetime
    key: str  # the decision's id (its stored prompt and answer)
    watch_above: float | None = None  # the prices the AI asked to be woken at
    watch_below: float | None = None
    # 'market' (fill now, within market_tolerance), 'limit' (a sell above / a buy below the price: fill when
    # price comes to it), 'stop' (a sell below / a buy above the price: fill when price breaks to it); None:
    # read from the entry against the first quote (owner 2026-10-25: "a limit or a stop order, as the
    # situation needs, with an expiry")
    kind: str | None = None
    exit_level: float | None = None  # C6: 3 M5 closes back across it end the trade early (None: the entry)
    # a BUY / SELL decision (the AI read the closed bar and enters now): only such an order may be a market
    # order; a WAIT's order and a plan order are limit / stop orders (07-08 13:15: a wait order at 4,132.50
    # was read as market and filled 0.95 worse)
    direct: bool = False

    def geometry_ok(self, price: float) -> bool:
        """The stop beyond the price on the losing side, the target (if any) on the winning side."""
        if self.side is Side.SELL:
            return self.stop > price and (self.target is None or self.target < price)
        return self.stop < price and (self.target is None or self.target > price)


@dataclass(frozen=True)
class AIEntry:
    order: AIOrder
    at: datetime
    price: float

    @property
    def side(self) -> Side:
        return self.order.side


class AITraderParams(StrategyParams):
    pending_minutes: int = Field(default=30, gt=0, le=240)  # how long an order waits for its price
    market_tolerance: float = Field(
        default=1.0, ge=0, le=50
    )  # price units: this close to the entry fills now
    # the take-profit this share of the way short of the AI's target (owner 2026-10-24: 5-10 % before it; the
    # 2026-07-07 replay's 12:04 sell came within 0.6 of an 11.4 target, then lost)
    target_trim: float = Field(default=0.10, ge=0, lt=1)
    # the trim never brings the take-profit nearer than this to the entry (price units; owner 2026-10-25, C5)
    min_take_profit: float = Field(default=0.0, ge=0)
    # the AI's exit before the stop / take-profit stands only after this many M5 closes back across its level
    # (C6's failed break) or this long held (the scalp's time stop) - 07-07, ISSUES 28
    exit_m5_closes: int = Field(default=3, ge=1, le=12)
    exit_minutes: int = Field(default=60, ge=5, le=480)
    plan_min_rr: float = Field(default=0.2, ge=0)  # a plan order moved out to the map's stop keeps this R
    # C9 (P24): no new trade on a side this long after a trade of that side reached its take-profit
    tp_block_minutes: int = Field(default=30, ge=0, le=240)
    # owner 2026-10-26: "wait for the chart to confirm before entering; never enter at the first moment
    # price gets there"; "a signal at the level - a chart pattern or a candlestick pattern on a larger
    # timeframe") - a limit / stop order whose price is reached is armed, and fills only after a signal
    # at its level on M5 / M15 (app/strategy/confirm.py), at a price no further than chase_share of its
    # stop distance past the entry
    confirm_entries: bool = True
    chase_share: float = Field(default=0.5, gt=0, le=2)


def m5_closes(m1: pd.DataFrame | None, count: int) -> list[float]:
    """The last ``count`` complete M5 closes from closed M1 bars indexed by their close time."""
    if m1 is None or not len(m1):
        return []
    closes = m1["close"].resample("5min", label="right", closed="right").last().dropna()
    last = pd.Timestamp(m1.index[-1])
    if closes.index[-1] > last:  # the bucket still forming
        closes = closes.iloc[:-1]
    return [float(x) for x in closes.iloc[-count:]]


def exit_allowed(
    m1: pd.DataFrame | None,
    pos: OpenPosition,
    now: datetime,
    p: AITraderParams,
    level: float | None = None,
) -> str | None:
    """Why the AI's exit stands, or None: C6 (owner 2026-10-23: "a failed break - 3 M5 closes back inside the
    range") - ``exit_m5_closes`` M5 closes back across ``level``, the level the trade is built on (the range
    edge it broke; None: the entry - 07-08 14:46 used the entry and let out a sell the range kept) - or the
    time stop (``exit_minutes`` held)."""
    held = (ensure_utc(now) - ensure_utc(pos.entry_time)).total_seconds() / 60
    if held >= p.exit_minutes:
        return f"the time stop, {held:.0f} min held"
    mark = pos.entry if level is None else level
    closes = m5_closes(m1, p.exit_m5_closes)
    against = [c > mark if pos.side is Side.SELL else c < mark for c in closes]
    if len(against) == p.exit_m5_closes and all(against):
        return f"{p.exit_m5_closes} M5 closes back across {mark:.2f} (C6)"
    return None


class AITrader(BaseStrategy):
    name = "ai_trader"
    description = (
        "The AI trader (PLAN §A37): the engine hands it the AI's decisions; it enters on quotes. Unproven."
    )
    Params = AITraderParams
    advised = False

    def __init__(self, params: StrategyParams | None = None) -> None:
        super().__init__(params)
        self._orders: dict[str, AIOrder] = {}
        self._plan: dict[str, list[AIOrder]] = {}  # the day plan's orders, placed when the plan is written
        self._kinds: dict[str, str] = {}  # an order's kind read at its first quote (by its key)
        self._levels: dict[str, float | None] = {}  # the open trade's C6 level (from its order)
        self._blocked: dict[tuple[str, Side], datetime] = {}  # no fill on a side until (C9 after a TP)
        self._held: dict[str, list[Held]] = {}  # the positions seen at the last note_positions
        self._touched: dict[str, datetime] = {}  # an order's price first reached (by its key): armed
        self._confirmed: dict[str, str] = {}  # armed orders a signal at the level confirmed (key: signal)
        self._exits: set[str] = set()

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return (Timeframe.M1,)

    def warmup_bars(self) -> int:
        return 50

    def evaluate(self, ctx: StrategyContext) -> Signal:
        return self.hold(ctx, ReasonCode.NO_SETUP, explanation="the AI trader enters on quotes, not on bars")

    # --- the engine's hand-over ---------------------------------------------------------------------------

    def accept(self, symbol: str, order: AIOrder) -> None:
        """A new AI order for ``symbol``; it replaces a waiting one, and an exit asked earlier no longer
        applies (it would close the new position at its first management)."""
        self._orders[symbol] = order
        self._exits.discard(symbol)

    def cancel(self, symbol: str) -> None:
        self._orders.pop(symbol, None)

    def request_exit(self, symbol: str) -> None:
        """The AI asked to close this lane's open position on ``symbol`` (applied at its next management)."""
        self._exits.add(symbol)

    def set_plan_orders(self, symbol: str, orders: list[AIOrder]) -> None:
        """The day plan's orders for ``symbol`` (owner 2026-10-25: a trader places the plan's orders in
        advance); they replace the previous window's. The first to fill withdraws the others."""
        self._plan[symbol] = list(orders)

    def plan_orders(self, symbol: str) -> list[AIOrder]:
        return list(self._plan.get(symbol, []))

    def pending(self, symbol: str, at: datetime | None = None) -> AIOrder | None:
        """The AI's waiting order; with ``at``, an expired one is dropped first (07-06 22:37: an order expired
        at 20:53 still showed as waiting, so the AI was woken outside the windows all night)."""
        order = self._orders.get(symbol)
        if order is not None and at is not None and ensure_utc(at) > order.valid_until:
            self._orders.pop(symbol)
            return None
        return order

    def block_side(self, symbol: str, side: Side, until: datetime) -> None:
        """No new fill on ``side`` until ``until`` (C9 / P24: the cycle that just reached its take-profit is
        over - 07-08 08:16 bought the 08:11 sweep again three minutes after its take-profit)."""
        self._blocked[(symbol, side)] = ensure_utc(until)

    def note_positions(
        self, symbol: str, held: Sequence[Held], m1: pd.DataFrame | None
    ) -> list[tuple[Side, datetime]]:
        """The positions now (side, entry, stop, target, opened) against the last ones: a position gone whose
        target the M1 bars since it opened reached before its stop blocks its side for ``tp_block_minutes``
        from that bar's close (C9). The same path runs in a replay and live (the live engine reads no deal
        history). ``m1``: bar-open index, high / low on bid - a sell's target counted on the bid low, the
        stop on the bid high. Returns the sides blocked now."""
        p: AITraderParams = self.params
        out: list[tuple[Side, datetime]] = []
        now = {(h[0], round(h[1], 5)) for h in held}
        for side, entry, sl, tp, opened in self._held.get(symbol, []):
            if (side, round(entry, 5)) in now or tp is None or m1 is None or not len(m1):
                continue
            bars = m1[m1.index >= pd.Timestamp(opened).floor("1min")]
            buy = side is Side.BUY
            hit_tp = bars.index[(bars["high"] >= tp) if buy else (bars["low"] <= tp)]
            if not len(hit_tp):
                continue
            hit_sl = bars.index[:0]
            if sl:
                hit_sl = bars.index[(bars["low"] <= sl) if buy else (bars["high"] >= sl)]
            if len(hit_sl) and hit_sl[0] < hit_tp[0]:
                continue
            until = (pd.Timestamp(hit_tp[0]) + pd.Timedelta(minutes=1 + p.tp_block_minutes)).to_pydatetime()
            self.block_side(symbol, side, until)
            out.append((side, until))
        self._held[symbol] = list(held)
        return out

    def blocked(self, symbol: str, side: Side, at: datetime) -> bool:
        until = self._blocked.get((symbol, side))
        return until is not None and ensure_utc(at) < until

    def recheck_plan_stops(self, symbol: str, stops: dict[str, float | None]) -> None:
        """The plan's orders against the map's stops now (C4 at the fill, not only when the plan was written -
        07-08 13:16 filled 16 short of the zone): a stop short of the map's is moved out to it; an order whose
        take-profit is then under ``min_take_profit`` or its R under ``plan_min_rr`` is withdrawn."""
        p: AITraderParams = self.params
        keep = []
        for o in self._plan.get(symbol, []):
            m = stops.get(o.side.value)
            if m is None or ((o.stop >= m) if o.side is Side.SELL else (o.stop <= m)):
                keep.append(o)
                continue
            risk, reward = abs(o.entry - m), (abs(o.target - o.entry) if o.target is not None else None)
            if reward is not None and (reward < p.min_take_profit or reward < p.plan_min_rr * risk):
                continue
            keep.append(dataclasses.replace(o, stop=float(m)))
        if symbol in self._plan:
            self._plan[symbol] = keep

    def drop_plan_side(self, symbol: str, side: Side) -> None:
        """Withdraw the plan's orders of ``side`` (a rule in force stops that side now)."""
        if symbol in self._plan:
            self._plan[symbol] = [o for o in self._plan[symbol] if o.side is not side]

    def _waiting(self) -> list[AIOrder]:
        return list(self._orders.values()) + [o for orders in self._plan.values() for o in orders]

    def busy(self, at: datetime) -> bool:
        """An order is waiting for its price: the engine polls quotes faster."""
        return bool(self._waiting())

    def busy_between(self, start: datetime, end: datetime) -> bool:
        """An order is waiting in [start, end) (a backtest replays those quotes, TAA-1807)."""
        return any(start < o.valid_until and o.decided_at < end for o in self._waiting())

    # --- quotes, entries, management ----------------------------------------------------------------------

    def kind_of(self, order: AIOrder, bid: float, ask: float) -> str:
        """The order's kind: its own, else read once from its entry against this quote."""
        if order.kind is not None:
            return order.kind
        if order.key not in self._kinds:
            tol = float(self.params.market_tolerance)
            price = bid if order.side is Side.SELL else ask
            gap = (order.entry - price) * (1 if order.side is Side.SELL else -1)  # > 0: a better price waits
            near = order.direct and abs(order.entry - price) <= tol
            self._kinds[order.key] = "market" if near else "limit" if gap >= 0 else "stop"
        return self._kinds[order.key]

    def confirm_orders(self, symbol: str, m1: pd.DataFrame | None, at: datetime) -> list[tuple[str, str]]:
        """The armed orders a signal at their level now confirms (:mod:`app.strategy.confirm`: a chart pattern
        or a candlestick pattern on M5 / M15 since the touch). ``m1``: bar-open index with open / high / low /
        close / tick_volume. The same path runs in a replay and live, at each M1 close. Returns (key, signal)
        for the orders confirmed now."""
        if m1 is None or not len(m1):
            return []
        mine = ([self._orders[symbol]] if symbol in self._orders else []) + self._plan.get(symbol, [])
        out = []
        for o in mine:
            touched = self._touched.get(o.key)
            if touched is None or o.key in self._confirmed:
                continue
            kind = self._kinds.get(o.key, o.kind or "limit")
            got = cf.signal(m1, at, touched, o.entry, o.side is Side.SELL, kind)
            if got is not None:
                self._confirmed[o.key] = got
                out.append((o.key, got))
        return out

    def confirmation(self, key: str) -> str | None:
        """The signal that confirmed an order (None: not confirmed)."""
        return self._confirmed.get(key)

    def _check(self, order: AIOrder, at: datetime, bid: float, ask: float, symbol: str = "") -> str:
        """'fill', 'drop' (expired, or its stop reached before its entry: the idea is gone) or 'keep'."""
        if at > order.valid_until:
            return "drop"
        if self.blocked(symbol, order.side, at):
            return "keep"  # the side is blocked after a take-profit (C9)
        kind = self.kind_of(order, bid, ask)
        p: AITraderParams = self.params
        tol = float(p.market_tolerance) if kind == "market" else 0.0  # a limit: its price or better
        sell = order.side is Side.SELL
        if (ask >= order.stop) if sell else (bid <= order.stop):
            return "drop"  # the stop reached before the entry: the idea is gone
        price = bid if sell else ask
        if kind == "stop":  # a sell stop: price breaks down to the entry (a buy stop: up to it)
            reached = price <= order.entry if sell else price >= order.entry
        else:
            reached = price >= order.entry - tol if sell else price <= order.entry + tol
        if kind == "market" or not p.confirm_entries:
            return "fill" if reached else "keep"
        if order.key in self._confirmed:  # confirmed by a signal: fill, never chasing far past the entry
            worse = (order.entry - price) if sell else (price - order.entry)
            if worse > p.chase_share * abs(order.stop - order.entry):
                return "keep"
            # the take-profit and R at the fill price, not the order's (07-08 07:10: a confirmed fill 2.6
            # under its 4,102.40 entry left a 3.88 USD target, under C5's 5)
            reward = abs(order.target - price) if order.target is not None else None
            short = reward is not None and reward < max(
                p.min_take_profit, p.plan_min_rr * abs(order.stop - price)
            )
            return "keep" if short else "fill"
        if reached:
            self._touched.setdefault(order.key, at)  # armed: the first touch is not the entry
        return "keep"

    def on_quote(self, symbol: str, at: datetime, bid: float, ask: float) -> AIEntry | None:
        at = ensure_utc(at)
        order = self._orders.get(symbol)
        if order is not None:
            state = self._check(order, at, bid, ask, symbol)
            if state != "keep":
                self._orders.pop(symbol)
            if state == "fill":
                self._exits.discard(symbol)
                self._levels[symbol] = order.exit_level
                self._plan.pop(symbol, None)  # one trade at a time: the plan's orders step aside
                return AIEntry(order, at, bid if order.side is Side.SELL else ask)
        keep = []
        for o in self._plan.get(symbol, []):
            state = self._check(o, at, bid, ask, symbol)
            if state == "fill":
                self._levels[symbol] = o.exit_level if o.exit_level is not None else o.entry
                self._plan.pop(symbol, None)  # the first plan order to fill withdraws the others
                self._orders.pop(symbol, None)
                self._exits.discard(symbol)
                return AIEntry(o, at, bid if o.side is Side.SELL else ask)
            if state == "keep":
                keep.append(o)
        if symbol in self._plan:
            self._plan[symbol] = keep
        return None

    def entry_signal(self, ctx: StrategyContext, entry: AIEntry) -> Signal | None:
        """The market entry at the context's quote, None without one or when the stop / target no longer sit
        on the right sides of it (fail closed)."""
        market = ctx.market
        if market.bid is None or market.ask is None:
            return None
        o = entry.order
        price = market.bid if o.side is Side.SELL else market.ask
        if not o.geometry_ok(price):
            return None
        p: AITraderParams = self.params
        # not rounded here: the order path normalises prices to the symbol's digits (gold 2, EURUSD 5)
        target = None
        if o.target is not None:
            # trimmed short of the AI's target, but never nearer than min_take_profit (C5: the 5 USD floor)
            reach = abs(o.target - price)
            keep = max(reach * (1 - p.target_trim), min(p.min_take_profit, reach))
            target = price + keep if o.target > price else price - keep
        conds = [
            Condition("ai_decision", True, 1.0, f"{o.setup} (confidence {o.confidence}, decision {o.key})"),
            Condition("ai_knowledge", True, 1.0, ", ".join(o.kb_ids)),
            Condition("ai_watch", True, 1.0, f"above {o.watch_above} / below {o.watch_below}"),
        ]
        return self.entry(
            ctx,
            Action.SELL if o.side is Side.SELL else Action.BUY,
            entry_price=price,
            stop_loss=o.stop,
            take_profit=target,
            conditions=conds,
            score=float(o.confidence),
            explanation=" | ".join(o.reasons),
            risk_scale=o.risk_scale,
        )

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        symbol = ctx.market.symbol
        if symbol not in self._exits:
            return None
        self._exits.discard(symbol)
        why = exit_allowed(
            ctx.frames.get(Timeframe.M1), pos, ctx.now_utc, self.params, self._levels.get(symbol)
        )
        if why is None:  # 07-07: three exits of this kind cut sells that then reached their take-profit
            return None
        return PositionAdvice(close=ExitReason.SIGNAL, note=f"the AI trader asked to exit ({why})")
