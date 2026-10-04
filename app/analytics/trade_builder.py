"""Trade builder (PLAN §A16 "Trade record", §A27 "Feedback loops"; TAA-1001).

Turns closed fills of every scope into one :class:`Trade` record, the input of style tagging
(:mod:`app.analytics.styles`) and P/L attribution (:mod:`app.analytics.attribution`). Pure and deterministic:
no database, clock or broker access; callers load the rows and pass them in.

**Scopes:** ``BACKTEST`` (:class:`~app.execution.simulated_broker.ClosedTrade`), ``PAPER`` (closed
``paper_positions`` with their intents), ``SHADOW`` (CLOSED ``shadow_trades``; OPEN and VOID rows are not
trades). ``DEMO`` and ``LIVE`` are reserved for broker deals. Backtest, paper and shadow results are
**hypothetical** (no real broker fill); shadow rows keep their ``source`` (LIVE/REPLAY) and ``variant``
(PLAN/MANAGED) in :class:`ShadowInfo` and are never mixed into another scope.

**Conventions:**

- R multiples are net of costs: ``net / risk_money`` (planned loss at the stop, costs included) for backtest
  and paper, the tracker's ``r_net`` for shadow trades. Without a planned risk the R fields are None.
- MAE/MFE are price excursions from the fill (>= 0); in R they divide by the distance from the fill to the
  initial stop, like the backtest metrics.
- Costs are money paid in the account currency (a swap credit is a negative cost); a component the source
  does not record is None and the total covers the known ones, so ``cost_r`` is a lower bound then. The spread
  is the decision quote's ``ask - bid``, valued with the trade's own money per price unit
  (``|profit / (exit - entry)|``). Slippage is known when the venue's per-fill slippage is fixed (PAPER, a
  ``fixed`` backtest model) or recorded (shadow): it applies to market entries and to every exit except a
  take-profit and an end-of-data mark.
- Entry context (trend, regime, session, S/R, news) is not stored with fills: callers pass an
  :class:`EntryContext` per signal id, built from the decision record with :func:`context_from_decision`.
  Shadow rows carry their own facts (session, regime and HTF alignment from the stored features, ATR).
- A row that cannot be turned into a faithful record (missing exit, unknown side or exit reason, no valid
  stop distance for a shadow trade) is skipped and listed in :attr:`TradeSet.skipped`, never guessed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, TypeVar

from app.core.clock import ensure_utc
from app.core.enums import ExitReason, Regime, Session, Side, Timeframe, Trend, VolatilityState
from app.core.errors import TaaError
from app.execution.simulated_broker import ClosedTrade
from app.storage.models import PaperIntentRow, PaperPositionRow, ShadowTradeRow
from app.strategy.signal_models import MarketContext, SignalError


class AnalyticsError(TaaError):
    """Analytics input cannot be interpreted faithfully (e.g. a malformed decision record)."""


class Scope(StrEnum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    DEMO = "DEMO"
    LIVE = "LIVE"
    SHADOW = "SHADOW"

    @property
    def hypothetical(self) -> bool:
        """No real broker fill behind the result."""
        return self in (Scope.BACKTEST, Scope.PAPER, Scope.SHADOW)


class Outcome(StrEnum):
    WIN = "WIN"
    LOSS = "LOSS"
    SCRATCH = "SCRATCH"


class Alignment(StrEnum):
    """The entry side against the higher timeframe's trend."""

    WITH = "WITH"
    AGAINST = "AGAINST"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


SCRATCH_R = 0.2  # |R| below this is a scratch (break-even after costs)
STOP_EXITS = frozenset({ExitReason.STOP_LOSS, ExitReason.BREAK_EVEN, ExitReason.TRAILING_STOP})
UNSLIPPED_EXITS = frozenset({ExitReason.TAKE_PROFIT, ExitReason.END_OF_DATA})


@dataclass(frozen=True, slots=True)
class EntryContext:
    """Market facts at the entry decision (all optional: unknown facts disable the rules that need them)."""

    timeframe: Timeframe | None = None  # entry timeframe
    htf_trend: Trend | None = None
    regime: Regime | None = None  # entry timeframe (what shadow rows record)
    volatility: VolatilityState | None = None
    atr: float | None = None  # entry timeframe, price units
    atr_percentile: float | None = None
    adx: float | None = None  # higher timeframe
    session: Session | None = None
    spread: float | None = None  # price units at the decision (ask - bid)
    support: float | None = None  # nearest support zone below / resistance above the decision close
    resistance: float | None = None
    news_window: bool | None = None  # a news blackout window overlapped the trade
    reason_codes: tuple[str, ...] = ()
    # observed at the exit (optional; LOSS_REGIME_SHIFT and LOSS_VOLATILITY_SPIKE need them)
    htf_trend_at_exit: Trend | None = None
    atr_at_exit: float | None = None


@dataclass(frozen=True, slots=True)
class ShadowInfo:
    source: str  # LIVE / REPLAY
    variant: str  # PLAN / MANAGED
    opportunity_id: str
    alerted: bool
    followed: bool
    tradable: bool  # False: no lot at the owner's capital, results in R only
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Costs:
    """Money paid by one trade (account currency); None = not recorded by the source."""

    spread: float | None = None
    slippage: float | None = None
    commission: float | None = None
    swap: float | None = None  # negative: a swap credit

    @property
    def total(self) -> float:
        """The sum of the known components."""
        return sum(v for v in (self.spread, self.slippage, self.commission, self.swap) if v is not None)

    @property
    def complete(self) -> bool:
        return None not in (self.spread, self.slippage, self.commission, self.swap)


@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: str  # <scope>:<source key>
    scope: Scope
    symbol: str
    side: Side
    strategy: str
    signal_id: str
    volume: float | None  # None: a shadow trade without a lot
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    exit_reason: ExitReason
    initial_sl: float | None
    initial_tp: float | None
    stop_at_exit: float | None  # the stop in force at the exit (moved by break-even/trailing), if known
    risk_money: float | None
    gross_pnl: float | None  # price P/L in money; None without a lot
    net_pnl: float | None
    r_multiple: float | None  # net of costs
    costs: Costs
    cost_r: float | None  # known costs in R (a lower bound when ``costs`` is incomplete)
    slippage_price: float | None  # total adverse slippage of the fills, price units
    mae: float  # price units from the fill, >= 0
    mfe: float
    bars_held: int | None  # entry-timeframe bars
    context: EntryContext = field(default_factory=EntryContext)
    shadow: ShadowInfo | None = None

    @property
    def hypothetical(self) -> bool:
        return self.scope.hypothetical

    @property
    def holding(self) -> timedelta:
        return self.exit_time - self.entry_time

    @property
    def risk_distance(self) -> float | None:
        """Price distance from the fill to the initial stop; None without valid geometry."""
        if self.initial_sl is None:
            return None
        dist = (self.entry_price - self.initial_sl) * self.side.sign
        return dist if dist > 0 else None

    def _in_r(self, value: float | None) -> float | None:
        dist = self.risk_distance
        return None if value is None or dist is None else value / dist

    @property
    def mae_r(self) -> float | None:
        return self._in_r(self.mae)

    @property
    def mfe_r(self) -> float | None:
        return self._in_r(self.mfe)

    @property
    def slippage_r(self) -> float | None:
        return self._in_r(self.slippage_price)

    @property
    def gap_r(self) -> float | None:
        """For a stop exit: how far beyond the stop the fill was, in R (> 0 = worse than the stop)."""
        if self.exit_reason not in STOP_EXITS or self.stop_at_exit is None:
            return None
        return self._in_r((self.stop_at_exit - self.exit_price) * self.side.sign)

    @property
    def spread_to_sl(self) -> float | None:
        return self._in_r(self.context.spread)

    @property
    def sr_distance_atr(self) -> float | None:
        """Fill to the nearest level ahead (resistance for a BUY, support for a SELL), in ATR."""
        level = self.context.resistance if self.side is Side.BUY else self.context.support
        atr = self.context.atr
        if level is None or atr is None or atr <= 0:
            return None
        return (level - self.entry_price) * self.side.sign / atr

    @property
    def pre_cost_r(self) -> float | None:
        """The R result had the known costs been zero."""
        if self.r_multiple is None or self.cost_r is None:
            return None
        return self.r_multiple + self.cost_r

    @property
    def outcome(self) -> Outcome:
        """By R (scratch band ±``SCRATCH_R``); by the sign of the net P/L when no R is known."""
        r = self.r_multiple
        if r is not None:
            if r >= SCRATCH_R:
                return Outcome.WIN
            return Outcome.LOSS if r <= -SCRATCH_R else Outcome.SCRATCH
        net = self.net_pnl or 0.0
        if net > 0:
            return Outcome.WIN
        return Outcome.LOSS if net < 0 else Outcome.SCRATCH

    @property
    def alignment(self) -> Alignment:
        return _alignment(self.side, self.context.htf_trend)

    @property
    def alignment_at_exit(self) -> Alignment:
        return _alignment(self.side, self.context.htf_trend_at_exit)


def _alignment(side: Side, trend: Trend | None) -> Alignment:
    if trend is None:
        return Alignment.UNKNOWN
    if trend is Trend.NEUTRAL:
        return Alignment.NEUTRAL
    with_trend = Trend.BULLISH if side is Side.BUY else Trend.BEARISH
    return Alignment.WITH if trend is with_trend else Alignment.AGAINST


@dataclass(frozen=True, slots=True)
class Skipped:
    source_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class TradeSet:
    trades: tuple[Trade, ...]
    skipped: tuple[Skipped, ...] = ()


# --- context ------------------------------------------------------------------------------------------------


def context_from_decision(
    signal: Mapping[str, Any],
    market: Mapping[str, Any],
    *,
    news_window: bool | None = None,
    htf_trend_at_exit: Trend | None = None,
    atr_at_exit: float | None = None,
) -> EntryContext:
    """The entry context from a decision record's ``signal`` and ``market`` JSON."""
    try:
        ctx = MarketContext.from_dict(market)
        codes = tuple(str(c) for c in signal.get("reason_codes", ()))
    except (KeyError, TypeError, ValueError, SignalError) as exc:
        raise AnalyticsError(f"malformed decision record: {exc}") from exc
    spread = None if ctx.bid is None or ctx.ask is None else ctx.ask - ctx.bid
    return EntryContext(
        timeframe=ctx.entry_timeframe,
        htf_trend=ctx.trend,
        regime=ctx.entry.regime,
        volatility=ctx.volatility,
        atr=ctx.atr,
        atr_percentile=ctx.entry.atr_percentile,
        adx=ctx.adx,
        session=ctx.session,
        spread=spread if spread is not None and spread >= 0 else None,
        support=max(ctx.support_levels) if ctx.support_levels else None,
        resistance=min(ctx.resistance_levels) if ctx.resistance_levels else None,
        news_window=news_window,
        reason_codes=codes,
        htf_trend_at_exit=htf_trend_at_exit,
        atr_at_exit=atr_at_exit,
    )


# --- backtest and paper -------------------------------------------------------------------------------------


def _money_per_price(profit: float, entry: float, exit_: float) -> float | None:
    move = exit_ - entry
    return abs(profit / move) if move != 0 else None


def _slipped_fills(reason: ExitReason, market_entry: bool) -> int:
    return int(market_entry) + int(reason not in UNSLIPPED_EXITS)


def from_closed_trade(
    t: ClosedTrade,
    *,
    scope: Scope,
    trade_id: str,
    context: EntryContext | None = None,
    slippage: float | None = None,
    market_entry: bool = True,
    stop_at_exit: float | None = None,
    bars_held: int | None = None,
) -> Trade:
    """One simulated-broker trade. *slippage*: the venue's adverse slippage per fill (price), if fixed."""
    ctx = context or EntryContext()
    risk_money = t.risk_money if t.risk_money > 0 else None
    per_price = _money_per_price(t.profit, t.entry_price, t.exit_price)
    slip_price = None if slippage is None else slippage * _slipped_fills(t.exit_reason, market_entry)
    costs = Costs(
        spread=None if ctx.spread is None or per_price is None else ctx.spread * per_price,
        slippage=None if slip_price is None or per_price is None else slip_price * per_price,
        commission=-t.commission,
        swap=-t.swap,
    )
    if stop_at_exit is None and t.exit_reason is ExitReason.STOP_LOSS:
        stop_at_exit = t.sl_initial  # a stop still labelled SL was never moved
    if bars_held is None and ctx.timeframe is not None:
        bars_held = int((t.exit_time - t.entry_time).total_seconds() // ctx.timeframe.seconds)
    return Trade(
        trade_id=trade_id,
        scope=scope,
        symbol=t.symbol,
        side=t.side,
        strategy=t.strategy,
        signal_id=t.signal_id,
        volume=t.volume,
        entry_time=ensure_utc(t.entry_time),
        entry_price=t.entry_price,
        exit_time=ensure_utc(t.exit_time),
        exit_price=t.exit_price,
        exit_reason=t.exit_reason,
        initial_sl=t.sl_initial,
        initial_tp=t.tp_initial,
        stop_at_exit=stop_at_exit,
        risk_money=risk_money,
        gross_pnl=t.profit,
        net_pnl=t.net,
        r_multiple=None if risk_money is None else t.net / risk_money,
        costs=costs,
        cost_r=None if risk_money is None else costs.total / risk_money,
        slippage_price=slip_price,
        mae=t.mae,
        mfe=t.mfe,
        bars_held=bars_held,
        context=ctx,
    )


def trades_from_backtest(
    trades: Iterable[ClosedTrade],
    *,
    run_id: str = "",
    contexts: Mapping[str, EntryContext] | None = None,
    slippage: Mapping[str, float] | None = None,
) -> TradeSet:
    """Backtest trades; *contexts* by signal id, *slippage* per fill by symbol (a ``fixed`` model only)."""
    contexts = contexts or {}
    prefix = f"{Scope.BACKTEST.value}:{run_id}:" if run_id else f"{Scope.BACKTEST.value}:"
    out = [
        from_closed_trade(
            t,
            scope=Scope.BACKTEST,
            trade_id=f"{prefix}{t.ticket}",
            context=contexts.get(t.signal_id),
            slippage=None if slippage is None else slippage.get(t.symbol),
        )
        for t in trades
    ]
    return TradeSet(tuple(out))


def trades_from_paper(
    positions: Iterable[PaperPositionRow],
    intents: Mapping[str, PaperIntentRow],
    *,
    contexts: Mapping[str, EntryContext] | None = None,
    slippage: Mapping[str, float] | None = None,
) -> TradeSet:
    """Closed PAPER positions; *intents* by intent id supply the initial stop, planned risk and strategy.

    Without its intent a position's initial stop is known only while its stop was never moved.
    """
    contexts = contexts or {}
    trades: list[Trade] = []
    skipped: list[Skipped] = []
    for row in positions:
        if row.status != "CLOSED":
            continue
        source_id = f"{Scope.PAPER.value}:{row.account_key}:{row.ticket}"
        if row.exit_time is None or row.exit_price is None or row.exit_reason is None or row.profit is None:
            skipped.append(Skipped(source_id, "closed without exit time, price, reason or profit"))
            continue
        try:
            side, reason = Side(row.side), ExitReason(row.exit_reason)
        except ValueError as exc:
            skipped.append(Skipped(source_id, str(exc)))
            continue
        intent = intents.get(row.intent_id)
        if intent is not None:
            initial_sl, initial_tp, risk_money = intent.sl, intent.tp, intent.risk_money
            strategy, signal_id, magic = intent.strategy, intent.signal_id, int(intent.magic)
            market_entry = intent.entry_type == "MARKET"
        else:
            initial_sl = row.sl if row.stop_kind == ExitReason.STOP_LOSS.value else None
            initial_tp, risk_money, strategy, signal_id, magic = row.tp, 0.0, "", "", 0
            market_entry = True
        closed = ClosedTrade(
            ticket=int(row.ticket),
            symbol=row.symbol,
            side=side,
            volume=row.volume,
            entry_time=row.entry_time,
            entry_price=row.entry_price,
            exit_time=row.exit_time,
            exit_price=row.exit_price,
            exit_reason=reason,
            sl_initial=initial_sl,
            tp_initial=initial_tp,
            profit=row.profit,
            commission=row.commission,
            swap=row.swap,
            mae=row.mae,
            mfe=row.mfe,
            risk_money=risk_money,
            strategy=strategy,
            signal_id=signal_id,
            magic=magic,
        )
        trades.append(
            from_closed_trade(
                closed,
                scope=Scope.PAPER,
                trade_id=source_id,
                context=contexts.get(signal_id),
                slippage=None if slippage is None else slippage.get(row.symbol),
                market_entry=market_entry,
                stop_at_exit=row.sl,
                bars_held=row.bars_held,
            )
        )
    return TradeSet(tuple(trades), tuple(skipped))


# --- shadow -------------------------------------------------------------------------------------------------


E = TypeVar("E", bound=StrEnum)


def _enum_or_none(cls: type[E], value: str | None) -> E | None:
    try:
        return None if value is None else cls(value)
    except ValueError:
        return None


def _feature_value(features: Mapping[str, float], prefix: str) -> str | None:
    """The value of a one-hot context feature such as ``ctx:regime=TRENDING``."""
    for key, weight in sorted(features.items()):
        if key.startswith(prefix) and weight:
            return key[len(prefix) :]
    return None


def _shadow_context(row: ShadowTradeRow, side: Side) -> EntryContext:
    features = row.features or {}
    aligned = features.get("ctx:htf_aligned")
    # aligned = 0 is either a neutral or an opposite trend: unknown, so no counter-trend claim is made
    trend = (Trend.BULLISH if side is Side.BUY else Trend.BEARISH) if aligned == 1.0 else None
    spread = None if row.bid is None or row.ask is None else row.ask - row.bid
    return EntryContext(
        timeframe=_enum_or_none(Timeframe, row.timeframe),
        htf_trend=trend,
        regime=_enum_or_none(Regime, _feature_value(features, "ctx:regime=")),
        atr=row.atr,
        session=_enum_or_none(Session, row.session),
        spread=spread if spread is not None and spread >= 0 else None,
    )


def _shadow_slippage(row: ShadowTradeRow, side: Side) -> float | None:
    """Adverse slippage of the entry fill against the recorded quote (None without a quote)."""
    if "ENTRY_FALLBACK" in (row.flags or []) or row.bid is None or row.ask is None:
        return None
    slip = row.entry_price - row.ask if side is Side.BUY else row.bid - row.entry_price
    return max(0.0, slip)


def trade_from_shadow(row: ShadowTradeRow) -> Trade | Skipped:
    source_id = f"{Scope.SHADOW.value}:{row.shadow_id}"
    if row.exit_at is None or row.exit_price is None or row.exit_reason is None or row.r_net is None:
        return Skipped(source_id, "closed without exit time, price, reason or R")
    try:
        side, reason = Side(row.side), ExitReason(row.exit_reason)
    except ValueError as exc:
        return Skipped(source_id, str(exc))
    risk = (row.entry_price - row.initial_sl) * side.sign
    if risk <= 0:
        return Skipped(source_id, "no valid stop distance at the fill")
    ctx = _shadow_context(row, side)
    per_fill = _shadow_slippage(row, side)
    slip_price = None if per_fill is None else per_fill * _slipped_fills(reason, True)
    tradable = row.lot is not None
    per_price = (
        _money_per_price(row.gross_pnl, row.entry_price, row.exit_price)
        if tradable and row.gross_pnl is not None
        else None
    )
    costs = Costs(
        spread=None if ctx.spread is None or per_price is None else ctx.spread * per_price,
        slippage=None if slip_price is None or per_price is None else slip_price * per_price,
        commission=None if row.commission is None else -row.commission,
        swap=None if row.swap is None else -row.swap,
    )
    # in R from prices, so trades without a lot have it too: spread and slippage over the stop distance,
    # commission and swap as the tracker's gross-to-net R difference
    parts = [p / risk for p in (ctx.spread, slip_price) if p is not None]
    if row.r_multiple is not None:
        parts.append(row.r_multiple - row.r_net)
    cost_r = sum(parts) if parts else None
    entry_at, exit_at = ensure_utc(row.entry_at), ensure_utc(row.exit_at)
    bars = (
        None if ctx.timeframe is None else int((exit_at - entry_at).total_seconds() // ctx.timeframe.seconds)
    )
    return Trade(
        trade_id=source_id,
        scope=Scope.SHADOW,
        symbol=row.symbol,
        side=side,
        strategy=row.strategy,
        signal_id=row.opportunity_id,
        volume=row.lot,
        entry_time=entry_at,
        entry_price=row.entry_price,
        exit_time=exit_at,
        exit_price=row.exit_price,
        exit_reason=reason,
        initial_sl=row.initial_sl,
        initial_tp=row.tp,
        stop_at_exit=row.sl,
        risk_money=row.risk_money,
        gross_pnl=row.gross_pnl,
        net_pnl=row.net_pnl,
        r_multiple=row.r_net,
        costs=costs,
        cost_r=cost_r,
        slippage_price=slip_price,
        mae=row.mae,
        mfe=row.mfe,
        bars_held=bars,
        context=ctx,
        shadow=ShadowInfo(
            source=row.source,
            variant=row.variant,
            opportunity_id=row.opportunity_id,
            alerted=bool(row.alerted),
            followed=bool(row.followed),
            tradable=tradable,
            flags=tuple(sorted(row.flags or [])),
        ),
    )


def trades_from_shadow(rows: Iterable[ShadowTradeRow]) -> TradeSet:
    """CLOSED shadow trades (OPEN and VOID rows are ignored); hypothetical, scope SHADOW."""
    trades: list[Trade] = []
    skipped: list[Skipped] = []
    for row in rows:
        if row.status != "CLOSED":
            continue
        built = trade_from_shadow(row)
        if isinstance(built, Skipped):
            skipped.append(built)
        else:
            trades.append(built)
    return TradeSet(tuple(trades), tuple(skipped))
