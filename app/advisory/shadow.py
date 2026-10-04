"""Shadow trades (PLAN §A27; TAA-6C1): the hypothetical result of every opportunity, alerted or not.

Pure functions, shared by the live tracker (:mod:`app.advisory.shadow_tracker`) and historical replay.

**Entry** at signal time at the recorded ask (BUY) or bid (SELL) plus the configured adverse slippage. The
spread is recorded with it. Bars are bid OHLC (:class:`~app.execution.fill_model.Bar`): a BUY exits at the
bid, a SELL at the ask (bid + the bar's spread).

**Variants:** ``PLAN`` keeps the signal's SL/TP. ``MANAGED`` applies the A11 rules
(:func:`app.execution.management.manage`: break-even, trailing, ``time_stop_bars``) at every M1 close, with
the ATR recorded at signal time; a stop-out after a move is labelled ``BE`` or ``TRAIL``.

**Resolution on closed M1 bars**, in order, each bar once (``cursor``):

1. The bar holding the entry instant is partial: its ticks after the entry decide. Without ticks only a stop
   touch counts (``PARTIAL_BAR``), because the bar's range includes prices from before the entry.
2. An open beyond the stop fills at the open (``GAP``, adverse slippage). An open at or after the time stop
   (default 72 h) closes there; an open beyond the TP fills at the TP (never better).
3. A bar touching only the SL fills at the SL with slippage; only the TP fills at the TP.
4. A bar touching both: its ticks (``copy_ticks_range``) decide (``TICK_RESOLVED``); without usable ticks
   the SL is assumed first (``AMBIGUOUS``).

**Result:** win = TP first. R multiple from the fill price (``r_multiple``, gross) and after costs
(``r_net``); commission is round turn per lot, swap is the per-lot nightly swap times the rollover days
(weekends free, triple on ``swap_rollover3days``). P/L in account currency uses the broker's
``order_calc_profit`` for the snapshotted lot. Without a lot ("not tradable at your capital") the trade is
tracked in R only; its costs in R use a 1-lot reference.

These are hypothetical results: no requotes, partial fills or real slippage.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, tzinfo
from enum import StrEnum

import pandas as pd

from app.config import PositionManagementConfig
from app.core.enums import ExitReason, Side
from app.execution.fill_model import Bar
from app.execution.management import PositionView, manage


class Variant(StrEnum):
    PLAN = "PLAN"
    MANAGED = "MANAGED"


class ShadowStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    VOID = "VOID"  # no valid geometry at the fill (the stop was already reached): excluded from statistics


class Flag(StrEnum):
    AMBIGUOUS = "AMBIGUOUS"  # SL and TP in one M1 bar without usable ticks: SL assumed first
    TICK_RESOLVED = "TICK_RESOLVED"
    PARTIAL_BAR = "PARTIAL_BAR"  # the entry minute had no ticks: only a stop touch counted
    GAP = "GAP"  # filled at an open beyond the stop
    NOT_TRADABLE = "NOT_TRADABLE"  # no lot at the owner's capital: R only
    ENTRY_FALLBACK = "ENTRY_FALLBACK"  # no recorded quote: the signal's entry price was used
    SWAP_UNKNOWN = "SWAP_UNKNOWN"
    PNL_UNAVAILABLE = "PNL_UNAVAILABLE"  # the broker could not value the trade: r_net = r_multiple


TickRow = tuple[datetime, float, float]  # time (UTC), bid, ask
TickSource = Callable[[datetime, datetime], Sequence[TickRow] | None]  # [start, end); None = unavailable

STOP_KINDS = (ExitReason.STOP_LOSS, ExitReason.BREAK_EVEN, ExitReason.TRAILING_STOP)


@dataclass(slots=True)
class ShadowState:
    side: Side
    entry: float  # fill price
    entry_at: datetime
    initial_sl: float
    sl: float
    tp: float | None
    deadline: datetime  # time stop
    cursor: datetime  # open time of the next bar to resolve
    stop_kind: ExitReason = ExitReason.STOP_LOSS
    mae: float = 0.0  # price units, >= 0
    mfe: float = 0.0
    flags: set[Flag] = field(default_factory=set)

    @property
    def risk(self) -> float:
        """Price distance from the fill to the initial stop (> 0 for valid geometry)."""
        return (self.entry - self.initial_sl) * self.side.sign

    def excursion(self, adverse: float, favourable: float) -> None:
        sign = self.side.sign
        self.mae = max(self.mae, (self.entry - adverse) * sign)
        self.mfe = max(self.mfe, (favourable - self.entry) * sign)


@dataclass(frozen=True, slots=True)
class ShadowExit:
    reason: ExitReason
    price: float
    at: datetime


@dataclass(frozen=True, slots=True)
class Management:
    """What the MANAGED variant needs for the A11 rules."""

    config: PositionManagementConfig
    atr: float | None
    point: float
    bar_seconds: int  # the entry timeframe, for ``time_stop_bars``


def bars_from_frame(df: pd.DataFrame, point: float) -> list[Bar]:
    """Candle frame rows (``normalize_rates`` columns, spread in points) → bid :class:`Bar` objects."""
    columns = ("open_time", "close_time", "open", "high", "low", "close", "spread")
    if df.empty:
        return []
    return [
        Bar(
            pd.Timestamp(o_t).to_pydatetime(),
            pd.Timestamp(c_t).to_pydatetime(),
            float(o),
            float(h),
            float(lo),
            float(c),
            float(s) * point,
        )
        for o_t, c_t, o, h, lo, c, s in zip(*(df[col].tolist() for col in columns), strict=True)
    ]


def entry_fill(side: Side, bid: float, ask: float, slippage: float) -> float:
    """Market entry at the quote: BUY at the ask, SELL at the bid, slippage always adverse."""
    return ask + slippage if side is Side.BUY else bid - slippage


def new_state(
    *,
    side: Side,
    entry: float,
    entry_at: datetime,
    sl: float,
    tp: float | None,
    time_stop: timedelta,
) -> ShadowState:
    minute = entry_at.replace(second=0, microsecond=0)
    return ShadowState(side, entry, entry_at, sl, sl, tp, entry_at + time_stop, minute)


# --- resolution ---------------------------------------------------------------------------------------------


def advance(
    state: ShadowState,
    bars: Iterable[Bar],
    *,
    slippage: float,
    ticks: TickSource | None = None,
    management: Management | None = None,
) -> ShadowExit | None:
    """Resolve *state* over closed *bars* (oldest first); bars before ``state.cursor`` are skipped.

    Mutates the state (cursor, stop, excursions, flags) and returns the exit, or None while still open.
    """
    for bar in bars:
        if bar.open_time < state.cursor:
            continue
        result = _step(state, bar, slippage, ticks, management)
        state.cursor = bar.close_time
        if result is not None:
            return result
    return None


def _exit(state: ShadowState, reason: ExitReason, price: float, at: datetime) -> ShadowExit:
    sign = state.side.sign
    if reason in STOP_KINDS:
        state.mae = max(state.mae, (state.entry - price) * sign)
    elif reason is ExitReason.TAKE_PROFIT:
        state.mfe = max(state.mfe, (price - state.entry) * sign)
    return ShadowExit(reason, price, at)


def _step(
    state: ShadowState, bar: Bar, slip: float, ticks: TickSource | None, management: Management | None
) -> ShadowExit | None:
    side = state.side
    sign = side.sign
    offset = 0.0 if side is Side.BUY else bar.spread  # exit-side prices: bid for BUY, ask for SELL
    open_, close = bar.open + offset, bar.close + offset
    adverse = (bar.low if side is Side.BUY else bar.high) + offset
    favourable = (bar.high if side is Side.BUY else bar.low) + offset
    tp = state.tp

    if bar.open_time < state.entry_at:  # the entry minute: only what happened after the entry counts
        rows = ticks(state.entry_at, bar.close_time) if ticks is not None else None
        if rows:
            done = _walk(state, rows, slip)
            if done is not None:
                return done
        else:
            state.flags.add(Flag.PARTIAL_BAR)
            if (adverse - state.sl) * sign <= 0:
                return _exit(state, state.stop_kind, state.sl - sign * slip, state.entry_at)
        return _manage(state, close, bar, slip, management)

    if (open_ - state.sl) * sign < 0:
        state.flags.add(Flag.GAP)
        return _exit(state, state.stop_kind, open_ - sign * slip, bar.open_time)
    if bar.open_time >= state.deadline:
        return _exit(state, ExitReason.TIME_STOP, open_ - sign * slip, bar.open_time)
    if tp is not None and (open_ - tp) * sign >= 0:
        return _exit(state, ExitReason.TAKE_PROFIT, tp, bar.open_time)

    sl_hit = (adverse - state.sl) * sign <= 0
    tp_hit = tp is not None and (favourable - tp) * sign >= 0
    if sl_hit and tp_hit:
        rows = ticks(bar.open_time, bar.close_time) if ticks is not None else None
        done = _walk(state, rows, slip) if rows else None
        if done is not None:
            state.flags.add(Flag.TICK_RESOLVED)
            return done
        state.flags.add(Flag.AMBIGUOUS)
        return _exit(state, state.stop_kind, state.sl - sign * slip, bar.open_time)
    if sl_hit:
        return _exit(state, state.stop_kind, state.sl - sign * slip, bar.open_time)
    if tp_hit and tp is not None:
        state.excursion(adverse, state.entry)  # the bar's low/high came before or after; count it (MAE)
        return _exit(state, ExitReason.TAKE_PROFIT, tp, bar.open_time)
    state.excursion(adverse, favourable)
    return _manage(state, close, bar, slip, management)


def _walk(state: ShadowState, rows: Sequence[TickRow], slip: float) -> ShadowExit | None:
    """First stop or TP crossing in tick order (exit side: bid for BUY, ask for SELL)."""
    sign = state.side.sign
    for at, bid, ask in rows:
        if at < state.entry_at:
            continue
        price = bid if state.side is Side.BUY else ask
        if (price - state.sl) * sign <= 0:
            return _exit(state, state.stop_kind, price - sign * slip, at)
        if state.tp is not None and (price - state.tp) * sign >= 0:
            return _exit(state, ExitReason.TAKE_PROFIT, state.tp, at)
        state.excursion(price, price)
    return None


def _manage(
    state: ShadowState, mark: float, bar: Bar, slip: float, management: Management | None
) -> ShadowExit | None:
    if management is None:
        return None
    held = int((bar.close_time - state.entry_at).total_seconds() // management.bar_seconds)
    view = PositionView(state.side, state.entry, state.initial_sl, state.sl, held)
    adj = manage(view, mark=mark, atr=management.atr, point=management.point, cfg=management.config)
    if adj.close is not None:
        return _exit(state, adj.close, mark - state.side.sign * slip, bar.close_time)
    if adj.new_sl is not None and adj.stop_kind is not None:
        state.sl = adj.new_sl
        state.stop_kind = adj.stop_kind
    return None


# --- costs and result ---------------------------------------------------------------------------------------


def rollover_days(entry_at: datetime, exit_at: datetime, *, tz: tzinfo, triple_weekday: int) -> int:
    """Swap days charged between two instants: each broker midnight passed charges the day that ended.

    Saturdays and Sundays charge nothing; the day whose MT5 weekday (Sunday = 0) equals *triple_weekday*
    charges three (it covers the weekend), like the simulated broker.
    """
    day = entry_at.astimezone(tz).date()
    last = exit_at.astimezone(tz).date()
    total = 0
    while day < last:
        if day.weekday() <= 4:
            total += 3 if (day.weekday() + 1) % 7 == triple_weekday else 1
        day += timedelta(days=1)
    return total


ProfitFn = Callable[[float, float], float | None]  # (volume, close price) -> money from the fill, or None


@dataclass(frozen=True, slots=True)
class ShadowResult:
    win: bool
    r_multiple: float
    r_net: float
    mae_r: float
    mfe_r: float
    swap_days: int
    gross_pnl: float | None  # money fields: None without a lot
    commission: float | None
    swap: float | None
    net_pnl: float | None
    risk_money: float | None
    flags: frozenset[Flag]


def settle(
    state: ShadowState,
    exit_: ShadowExit,
    *,
    lot: float | None,
    profit: ProfitFn,
    commission_per_lot: float,
    swap_per_lot_night: float | None,
    swap_days: int,
) -> ShadowResult:
    """Costs, P/L and R of a closed shadow trade (*profit* values a close for a volume from the fill)."""
    flags = set(state.flags)
    risk = state.risk
    r = (exit_.price - state.entry) * state.side.sign / risk
    volume = lot if lot is not None else 1.0
    gross = profit(volume, exit_.price)
    loss = profit(volume, state.initial_sl)
    commission = -commission_per_lot * volume
    if swap_per_lot_night is None:
        swap = 0.0
        if swap_days:
            flags.add(Flag.SWAP_UNKNOWN)
    else:
        swap = swap_per_lot_night * volume * swap_days
    risk_money = None if loss is None or loss >= 0 else -loss
    if gross is None or risk_money is None:
        flags.add(Flag.PNL_UNAVAILABLE)
        net = None
        r_net = r
    else:
        net = gross + commission + swap
        r_net = net / risk_money
    if lot is None:
        flags.add(Flag.NOT_TRADABLE)

    def money(value: float | None) -> float | None:
        return None if lot is None or value is None else round(value, 2)

    return ShadowResult(
        win=exit_.reason is ExitReason.TAKE_PROFIT,
        r_multiple=r,
        r_net=r_net,
        mae_r=state.mae / risk,
        mfe_r=state.mfe / risk,
        swap_days=swap_days,
        gross_pnl=money(gross),
        commission=money(commission),
        swap=money(swap),
        net_pnl=money(net),
        risk_money=money(risk_money),
        flags=frozenset(flags),
    )
