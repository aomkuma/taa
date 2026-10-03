"""Bar-based fill rules for the simulated broker (PLAN §A17 "Costs and fills", "Intrabar SL/TP rules").

Bars are **Bid** OHLC (FX/CFD chart mode). The ask is the bid plus the spread, so:

- a BUY enters at ``ask = bid + spread`` and exits (SL/TP/close) at the bid;
- a SELL enters at the bid and exits at the ask.

Entries happen at the **next bar's open** after the decision. Adverse slippage applies to market entries and
to stop exits; take-profits and limit entries never fill better than their price, except that a limit order
gapped through at the open fills at that open.

Intrabar order is unknown, so: if the SL and the TP are both inside one bar, the **SL is assumed first**; an
open already beyond the SL fills at that open (a gap through the stop). These are pessimistic bar
approximations, documented as limitations: no requotes, partial fills or tick-level paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.enums import ExitReason, Side


@dataclass(frozen=True, slots=True)
class Bar:
    open_time: datetime
    close_time: datetime
    open: float  # bid
    high: float
    low: float
    close: float
    spread: float  # in price units (spread points × point)


def entry_price(side: Side, bar: Bar, slippage: float) -> float:
    """Market entry at the bar's open: BUY pays the spread; slippage is always adverse."""
    if side is Side.BUY:
        return bar.open + bar.spread + slippage
    return bar.open - slippage


def mark_price(side: Side, bid: float, spread: float) -> float:
    """The price a position would close at now: the bid for a BUY, the ask for a SELL."""
    return bid if side is Side.BUY else bid + spread


@dataclass(frozen=True, slots=True)
class ExitFill:
    reason: ExitReason
    price: float


def exit_on_bar(side: Side, sl: float | None, tp: float | None, bar: Bar, slippage: float) -> ExitFill | None:
    """SL/TP touched during *bar* (SL first when both are), or None."""
    s = bar.spread
    if side is Side.BUY:  # exits sell at the bid
        open_, high, low = bar.open, bar.high, bar.low
        if sl is not None and open_ <= sl:
            return ExitFill(ExitReason.STOP_LOSS, open_ - slippage)
        if sl is not None and low <= sl:
            return ExitFill(ExitReason.STOP_LOSS, sl - slippage)
        if tp is not None and high >= tp:
            return ExitFill(ExitReason.TAKE_PROFIT, tp)
        return None
    open_, high, low = bar.open + s, bar.high + s, bar.low + s  # exits buy at the ask
    if sl is not None and open_ >= sl:
        return ExitFill(ExitReason.STOP_LOSS, open_ + slippage)
    if sl is not None and high >= sl:
        return ExitFill(ExitReason.STOP_LOSS, sl + slippage)
    if tp is not None and low <= tp:
        return ExitFill(ExitReason.TAKE_PROFIT, tp)
    return None


def limit_fill(side: Side, limit: float, bar: Bar) -> float | None:
    """Fill price of a resting limit entry during *bar*, or None (BUY limits fill on the ask)."""
    if side is Side.BUY:
        ask_open, ask_low = bar.open + bar.spread, bar.low + bar.spread
        if ask_open <= limit:
            return ask_open  # gapped through: the open is better than the limit
        return limit if ask_low <= limit else None
    if bar.open >= limit:
        return bar.open
    return limit if bar.high >= limit else None


def excursion(side: Side, entry: float, bar: Bar) -> tuple[float, float]:
    """(adverse, favourable) price excursion of a position during *bar*, both ≥ 0."""
    if side is Side.BUY:
        return max(0.0, entry - bar.low), max(0.0, bar.high - entry)
    ask_high, ask_low = bar.high + bar.spread, bar.low + bar.spread
    return max(0.0, ask_high - entry), max(0.0, entry - ask_low)
