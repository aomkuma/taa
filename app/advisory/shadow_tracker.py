"""Live shadow-trade tracker (PLAN §A27; TAA-6C1). Runs inside the engine; never trades.

Every ``advisory.shadow.poll_seconds``:

1. **Open:** every opportunity of this server without shadow rows gets a ``PLAN`` and a ``MANAGED`` row
   (:mod:`app.advisory.shadow`), entered at the quote the decision used. The same query catches up
   opportunities recorded just before a crash or restart.
2. **Flags:** ``alerted`` (the opportunity's ``alerted_at``) and ``followed`` (status FOLLOWED) are copied
   onto its shadow rows for the accuracy breakdowns.
3. **Resolve:** OPEN rows advance over the closed M1 bars since their ``cursor`` (one ``rates_range`` per
   symbol); ticks break SL/TP ties. The state is persisted after every pass, so a restart resumes from the
   cursor and catches up from the terminal's M1 history.

Resolution is time-boxed per cycle (``budget_seconds``); symbols left over wait for the next pass. Database
sessions are never held across broker calls.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select, update

from app.advisory.scoring import swap_per_night
from app.advisory.shadow import (
    BASE_VARIANTS,
    Flag,
    Management,
    ShadowExit,
    ShadowResult,
    ShadowState,
    ShadowStatus,
    TickRow,
    TickSource,
    Variant,
    advance,
    bars_from_frame,
    entry_fill,
    new_state,
    rollover_days,
    settle,
)
from app.advisory.statuses import OpportunityStatus
from app.broker.gateway import MarketDataGateway
from app.config import AppConfig
from app.core.clock import Clock, ensure_utc
from app.core.enums import ExitReason, Side, Timeframe
from app.core.errors import TaaError
from app.execution.fill_model import Bar
from app.learning.entry_modes import await_fill, configured, geometry
from app.market_data.candle_service import normalize_rates
from app.market_data.data_models import SymbolSpec
from app.storage.database import Database
from app.storage.models import OpportunityRow, ShadowTradeRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)

LIVE = "LIVE"


@dataclass(slots=True)
class ShadowStats:
    opened: int = 0
    closed: int = 0
    void: int = 0
    failures: int = 0
    last_duration_ms: float = 0.0
    last_error: str = ""


@dataclass(frozen=True, slots=True)
class ShadowReport:
    opened: tuple[str, ...]  # shadow ids
    closed: tuple[str, ...]
    pending_symbols: int  # left for the next pass (budget)


def shadow_id(opportunity_id: str, variant: Variant) -> str:
    return f"{opportunity_id}:{variant.value}"


def state_of(row: ShadowTradeRow) -> ShadowState:
    return ShadowState(
        side=Side(row.side),
        entry=row.entry_price,
        entry_at=ensure_utc(row.entry_at),
        initial_sl=row.initial_sl,
        sl=row.sl,
        tp=row.tp,
        deadline=ensure_utc(row.deadline),
        cursor=ensure_utc(row.cursor),
        stop_kind=ExitReason(row.stop_kind),
        mae=row.mae,
        mfe=row.mfe,
        flags={Flag(f) for f in row.flags},
    )


@dataclass(frozen=True, slots=True)
class SignalFacts:
    """What a shadow row copies from its opportunity (or, in replay, from the signal and decision)."""

    opportunity_id: str
    source: str
    server: str
    strategy: str
    symbol: str
    asset_class: str
    timeframe: str
    side: str
    session: str
    setup_strength: float
    rr: float | None
    features: dict[str, float]
    atr: float | None
    signal_at: datetime
    lot: float | None
    equity: float
    currency: str
    alerted: bool = False
    followed: bool = False


@dataclass(frozen=True, slots=True)
class EntryQuote:
    bid: float | None
    ask: float | None
    spread_points: float | None
    slippage_points: float


def new_row(
    facts: SignalFacts,
    variant: Variant,
    state: ShadowState,
    quote: EntryQuote,
    flags: Iterable[Flag],
    now: datetime,
) -> ShadowTradeRow:
    """An OPEN shadow row at its entry (VOID when the fill is already at or beyond the stop)."""
    void = state.risk <= 0
    marks = {f.value for f in flags} | ({Flag.NOT_TRADABLE.value} if facts.lot is None else set())
    return ShadowTradeRow(
        shadow_id=shadow_id(facts.opportunity_id, variant),
        opportunity_id=facts.opportunity_id,
        variant=variant.value,
        source=facts.source,
        server=facts.server,
        strategy=facts.strategy,
        symbol=facts.symbol,
        asset_class=facts.asset_class,
        timeframe=facts.timeframe,
        side=facts.side,
        session=facts.session,
        setup_strength=facts.setup_strength,
        rr=facts.rr,
        features=dict(facts.features),
        atr=facts.atr,
        alerted=facts.alerted,
        followed=facts.followed,
        status=(ShadowStatus.VOID if void else ShadowStatus.OPEN).value,
        signal_at=facts.signal_at,
        created_at=now,
        updated_at=now,
        entry_at=state.entry_at,
        entry_price=state.entry,
        bid=quote.bid,
        ask=quote.ask,
        spread_points=quote.spread_points,
        slippage_points=quote.slippage_points,
        initial_sl=state.initial_sl,
        sl=state.sl,
        tp=state.tp,
        stop_kind=state.stop_kind.value,
        deadline=state.deadline,
        cursor=state.cursor,
        lot=facts.lot,
        equity=facts.equity,
        currency=facts.currency,
        mae=0.0,
        mfe=0.0,
        swap_days=0,
        flags=sorted(marks),
        note="fill at or beyond the stop" if void else "",
    )


def apply_state(row: ShadowTradeRow, state: ShadowState, now: datetime) -> None:
    row.cursor = state.cursor
    row.sl = state.sl
    row.stop_kind = state.stop_kind.value
    row.mae = state.mae
    row.mfe = state.mfe
    row.flags = sorted({*row.flags, *(f.value for f in state.flags)})
    row.updated_at = now


def mark_missed(row: ShadowTradeRow, state: ShadowState, now: datetime) -> None:
    """A PENDING entry-mode limit that was not filled within its window: no trade (TAA-L702)."""
    row.status = ShadowStatus.MISSED.value
    row.cursor = state.cursor
    row.updated_at = now
    row.note = "limit not filled within the entry window"


def apply_close(row: ShadowTradeRow, exit_: ShadowExit, result: ShadowResult) -> None:
    row.status = ShadowStatus.CLOSED.value
    row.exit_at = exit_.at
    row.exit_price = exit_.price
    row.exit_reason = exit_.reason.value
    row.win = result.win
    row.r_multiple = result.r_multiple
    row.r_net = result.r_net
    row.mae_r = result.mae_r
    row.mfe_r = result.mfe_r
    row.gross_pnl = result.gross_pnl
    row.commission = result.commission
    row.swap = result.swap
    row.net_pnl = result.net_pnl
    row.risk_money = result.risk_money
    row.swap_days = result.swap_days
    row.flags = sorted({*row.flags, *(f.value for f in result.flags)})


def commission_per_lot(config: AppConfig, symbol: str) -> float:
    """Round turn per lot: the symbol override, else ``advisory.shadow.commission_per_lot``."""
    override = config.symbols.overrides.get(symbol)
    if override is not None and override.commission_per_lot is not None:
        return override.commission_per_lot
    return config.advisory.shadow.commission_per_lot


class ShadowTracker:
    def __init__(
        self,
        db: Database,
        gateway: MarketDataGateway,
        config: AppConfig,
        clock: Clock,
        *,
        server: str,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.config = config
        self.cfg = config.advisory.shadow
        self.clock = clock
        self.server = server
        self.stats = ShadowStats()
        self.specs: dict[str, SymbolSpec] = {}
        self._tz = ZoneInfo(gateway.server_clock.tz_name)
        self._next_poll = 0.0

    def spec(self, symbol: str) -> SymbolSpec:
        if symbol not in self.specs:
            self.specs[symbol] = self.gateway.symbol_spec(symbol)
        return self.specs[symbol]

    # --- the tick -------------------------------------------------------------------------------------------

    def tick(self, *, force: bool = False) -> ShadowReport:
        started = self.clock.monotonic()
        if not force and started < self._next_poll:
            return ShadowReport((), (), 0)
        self._next_poll = started + self.cfg.poll_seconds
        opened = self.open_new()
        self.sync_flags()
        closed, pending = self.resolve(started + self.cfg.budget_seconds)
        self.stats.last_duration_ms = (self.clock.monotonic() - started) * 1000
        return ShadowReport(tuple(opened), tuple(closed), pending)

    # --- opening --------------------------------------------------------------------------------------------

    def open_new(self) -> list[str]:
        with self.db.session() as sess:
            missing = list(
                sess.execute(
                    select(OpportunityRow)
                    .where(
                        OpportunityRow.server == self.server,
                        ~exists().where(ShadowTradeRow.opportunity_id == OpportunityRow.opportunity_id),
                    )
                    .order_by(OpportunityRow.created_at, OpportunityRow.opportunity_id)
                ).scalars()
            )
        opened: list[str] = []
        for opp in missing:
            try:
                rows = self._rows_for(opp)
            except TaaError as exc:
                self._fail(opp.symbol, exc)
                continue
            with self.db.session() as sess:
                for row in rows:
                    if sess.get(ShadowTradeRow, (LOCAL_ENGINE, row.shadow_id)) is None:
                        sess.add(row)
                        opened.append(row.shadow_id)
        self.stats.opened += len(opened)
        return opened

    def _rows_for(self, opp: OpportunityRow) -> list[ShadowTradeRow]:
        spec = self.spec(opp.symbol)
        side = Side(opp.side)
        slip = self.cfg.slippage_points * spec.point
        flags: list[Flag] = []
        if opp.bid is not None and opp.ask is not None:
            entry = entry_fill(side, opp.bid, opp.ask, slip)
            entry_at = ensure_utc(opp.quote_at or opp.created_at)
            spread = (opp.ask - opp.bid) / spec.point if spec.point > 0 else None
        else:  # rows from before quotes were recorded: the signal's entry is already the ask/bid
            entry = opp.entry + side.sign * slip
            entry_at = ensure_utc(opp.created_at)
            spread = opp.spread_points
            flags.append(Flag.ENTRY_FALLBACK)
        state = new_state(
            side=side,
            entry=entry,
            entry_at=entry_at,
            sl=opp.stop_loss,
            tp=opp.take_profit,
            time_stop=timedelta(hours=self.cfg.time_stop_hours),
        )
        facts = SignalFacts(
            opportunity_id=opp.opportunity_id,
            source=LIVE,
            server=self.server,
            strategy=opp.strategy,
            symbol=opp.symbol,
            asset_class=opp.asset_class,
            timeframe=opp.timeframe,
            side=opp.side,
            session=opp.session,
            setup_strength=opp.setup_strength,
            rr=opp.rr,
            features=dict(opp.features),
            atr=opp.atr,
            signal_at=opp.bar_close_at,
            lot=opp.lot,
            equity=opp.equity,
            currency=opp.currency,
            alerted=opp.alerted_at is not None,
            followed=opp.status == OpportunityStatus.FOLLOWED.value,
        )
        now = self.clock.now_utc()
        quote = EntryQuote(opp.bid, opp.ask, spread, self.cfg.slippage_points)
        rows = [new_row(facts, variant, state, quote, flags, now) for variant in BASE_VARIANTS]
        for variant in configured(self.cfg.entry_modes):
            geo = geometry(
                variant,
                side=side,
                fill=entry,
                plan_sl=opp.stop_loss,
                tp=opp.take_profit,
                lot=opp.lot,
                entry_at=entry_at,
                bar_seconds=Timeframe(opp.timeframe).seconds,
                cfg=self.cfg.entry_modes,
                volume_step=spec.volume_step,
                volume_min=spec.volume_min,
            )
            variant_state = new_state(
                side=side,
                entry=geo.entry,
                entry_at=entry_at,
                sl=geo.sl,
                tp=geo.tp,
                time_stop=timedelta(hours=self.cfg.time_stop_hours),
            )
            row = new_row(replace(facts, lot=geo.lot), variant, variant_state, quote, flags, now)
            if geo.window_end is not None and row.status == ShadowStatus.OPEN.value:
                row.status = ShadowStatus.PENDING.value
                row.entry_window_end = geo.window_end
            rows.append(row)
        return rows

    # --- flags ----------------------------------------------------------------------------------------------

    def sync_flags(self) -> None:
        """Copy alerted/followed from the opportunities (both only ever turn on)."""
        alerted = select(OpportunityRow.opportunity_id).where(
            OpportunityRow.server == self.server, OpportunityRow.alerted_at.is_not(None)
        )
        followed = select(OpportunityRow.opportunity_id).where(
            OpportunityRow.server == self.server,
            OpportunityRow.status == OpportunityStatus.FOLLOWED.value,
        )
        with self.db.session() as sess:
            sess.execute(
                update(ShadowTradeRow)
                .where(ShadowTradeRow.alerted.is_(False), ShadowTradeRow.opportunity_id.in_(alerted))
                .values(alerted=True)
            )
            sess.execute(
                update(ShadowTradeRow)
                .where(ShadowTradeRow.followed.is_(False), ShadowTradeRow.opportunity_id.in_(followed))
                .values(followed=True)
            )

    # --- resolution -----------------------------------------------------------------------------------------

    def resolve(self, until_monotonic: float | None = None) -> tuple[list[str], int]:
        """Advance OPEN rows over closed M1 bars; returns (closed shadow ids, symbols left for later)."""
        with self.db.session() as sess:
            rows = list(
                sess.execute(
                    select(ShadowTradeRow)
                    .where(
                        ShadowTradeRow.server == self.server,
                        ShadowTradeRow.source == LIVE,
                        ShadowTradeRow.status.in_((ShadowStatus.OPEN.value, ShadowStatus.PENDING.value)),
                    )
                    .order_by(ShadowTradeRow.cursor, ShadowTradeRow.shadow_id)
                ).scalars()
            )
        by_symbol: dict[str, list[ShadowTradeRow]] = defaultdict(list)
        for row in rows:
            by_symbol[row.symbol].append(row)
        closed: list[str] = []
        pending = 0
        for symbol, group in by_symbol.items():  # oldest cursor first
            if until_monotonic is not None and self.clock.monotonic() >= until_monotonic:
                pending += 1
                continue
            try:
                closed += self._resolve_symbol(symbol, group)
            except TaaError as exc:
                self._fail(symbol, exc)
        return closed, pending

    def _resolve_symbol(self, symbol: str, group: list[ShadowTradeRow]) -> list[str]:
        spec = self.spec(symbol)
        horizon = self.clock.now_utc() - timedelta(seconds=self.config.timeframes.candle_close_grace_seconds)
        start = min(ensure_utc(r.cursor) for r in group)
        if start >= horizon:
            return []
        bars = self._bars(spec, start, horizon)
        ticks = self._tick_source(symbol) if self.cfg.tick_tiebreak else None
        slip = self.cfg.slippage_points * spec.point
        updates: list[tuple[str, str, ShadowState, ShadowExit | None, ShadowResult | None]] = []
        for row in group:
            state = state_of(row)
            status = row.status
            exit_ = None
            if status == ShadowStatus.PENDING.value:
                window_end = ensure_utc(row.entry_window_end) if row.entry_window_end else state.entry_at
                waiting = await_fill(state, bars, window_end=window_end, slippage=slip)
                if waiting.missed:
                    status = ShadowStatus.MISSED.value
                elif waiting.filled:
                    status = ShadowStatus.OPEN.value
                    exit_ = waiting.exit
            if status == ShadowStatus.OPEN.value and exit_ is None:
                management = None
                if row.variant == Variant.MANAGED.value:
                    management = Management(
                        self.config.position_management,
                        row.atr,
                        spec.point,
                        Timeframe(row.timeframe).seconds,
                    )
                exit_ = advance(state, bars, slippage=slip, ticks=ticks, management=management)
            result = None if exit_ is None else self._settle(spec, row.lot, state, exit_)
            updates.append((row.shadow_id, status, state, exit_, result))
        closed = []
        now = self.clock.now_utc()
        with self.db.session() as sess:
            for sid, status, state, exit_, result in updates:
                stored = sess.get(ShadowTradeRow, (LOCAL_ENGINE, sid))
                if stored is None or stored.status not in (
                    ShadowStatus.OPEN.value,
                    ShadowStatus.PENDING.value,
                ):
                    continue
                if status == ShadowStatus.MISSED.value:
                    mark_missed(stored, state, now)
                    continue
                if stored.status == ShadowStatus.PENDING.value and status == ShadowStatus.OPEN.value:
                    stored.status = status
                    stored.entry_at = state.entry_at
                apply_state(stored, state, now)
                if exit_ is not None and result is not None:
                    apply_close(stored, exit_, result)
                    closed.append(sid)
        self.stats.closed += len(closed)
        for sid in closed:
            log.info("shadow %s closed", sid)
        return closed

    def _bars(self, spec: SymbolSpec, start: datetime, horizon: datetime) -> list[Bar]:
        raw = self.gateway.rates_range(spec.name, Timeframe.M1, start, horizon)
        bars = bars_from_frame(normalize_rates(raw, Timeframe.M1, self.gateway), spec.point)
        return [b for b in bars if b.close_time <= horizon]  # later bars are forming or within the grace

    def _tick_source(self, symbol: str) -> TickSource:
        def ticks(start: datetime, end: datetime) -> list[TickRow] | None:
            try:
                df = self.gateway.ticks_range(symbol, start, end)
            except TaaError as exc:
                log.warning("shadow: ticks for %s unavailable: %s", symbol, exc)
                return None
            return [
                (t.to_pydatetime(), float(b), float(a))
                for t, b, a in zip(df["time_utc"], df["bid"], df["ask"], strict=True)
            ]

        return ticks

    def _settle(
        self, spec: SymbolSpec, lot: float | None, state: ShadowState, exit_: ShadowExit
    ) -> ShadowResult:
        """Broker calls for a closed trade happen here, outside any database session."""
        side = state.side
        return settle(
            state,
            exit_,
            lot=lot,
            profit=lambda volume, price: self.gateway.calc_profit(
                side, spec.name, volume, state.entry, price
            ),
            commission_per_lot=commission_per_lot(self.config, spec.name),
            swap_per_lot_night=swap_per_night(spec, side),
            swap_days=rollover_days(
                state.entry_at, exit_.at, tz=self._tz, triple_weekday=spec.swap_rollover3days
            ),
        )

    def _fail(self, symbol: str, exc: Exception) -> None:
        self.stats.failures += 1
        self.stats.last_error = f"{symbol}: {type(exc).__name__}: {exc}"
        log.warning("shadow: %s failed: %s", symbol, exc)
