"""Backtest engine (PLAN §A17; TAA-502).

One event loop over the union of every symbol's entry-timeframe bar closes, running the **same** code as the
live engine: context building (``context_at`` on frames analyzed once), strategies and arbitration, the
decision engine (EXECUTION profile), the position sizer, the A11 management rules, loss tracking and the loss
breakers. Only the broker is simulated (:class:`~app.execution.simulated_broker.SimulatedBroker`).

At each bar close *t* of a symbol:

1. the broker processes the bar (fills of orders decided at the previous close, intrabar exits, marking);
2. the context at *t* is built from bars closed by *t* (higher timeframes aligned on close time);
3. open positions are managed (break-even, trailing, time stop, strategy ``should_close``): changes apply
   from the next bar;
4. the strategies run, the arbiter picks at most one signal, and the decision engine accepts or rejects it;
   accepted plans become orders that fill at the next bar's open.

After all symbols at *t*: the equity point is recorded, the loss tracker books the new deals and the loss
breakers are evaluated. Progress events are emitted every ``progress_every`` steps.

**Entry lanes** (TAA-507, PLAN §A7): more entry timeframes in the same run, as the live engine trades them
(owner, 2026-10-17: one account, every setup). Each lane (:class:`BacktestLane`) has its own config
view (:meth:`AppConfig.for_lane`), strategies, arbiter, evidence and market maps; the account, risk
budget, decision engine, loss breakers and per-symbol position limit are shared. The timeline is the union
of every lane's entry-bar closes. The broker steps each symbol on the finest entry timeframe that trades it
(fills, stops and targets on M1 when an M1 lane trades the symbol), once per bar, before the lanes evaluate
in order (the main lane first). Positions are managed by their strategy's lane, with bars held counted on
that lane's timeframe. Without extra lanes the run is exactly the single-timeframe run above.

A :class:`RiskPreset` (the aggressive Trading-profile preset, PLAN §A36) makes every decision combine its
profile limits with its cage, as the live engine's risk-limit selector does, and the loss breakers trip on the
combined limits.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from app.config import AppConfig, RiskConfig
from app.core.clock import ManualClock
from app.core.enums import ExitReason, Side, Timeframe, TradingMode
from app.core.errors import DataQualityError, InsufficientDataError
from app.engine.decision_engine import (
    AccountState,
    Decision,
    DecisionEngine,
    DecisionRequest,
    SystemHealth,
)
from app.evidence.framework import EvidenceContext
from app.evidence.registry import EvidenceEngine
from app.execution.fill_model import Bar, mark_price
from app.execution.management import PositionView, from_advice, manage, with_advice
from app.execution.simulated_broker import ClosedTrade, EquityPoint, OrderRequest, RateSource, SimulatedBroker
from app.indicators.market_map import MarketMap
from app.market_data.data_models import Quote, SymbolSpec
from app.market_data.trading_sessions import TradingSessions
from app.news.calendar import ManualBlackouts, NewsFilter
from app.risk.breaker_monitor import BreakerMonitor
from app.risk.circuit_breaker import BreakerBoard, default_specs
from app.risk.limits import ProfileLimits, effective_risk
from app.risk.loss_tracker import LossStatus, LossTracker
from app.storage.database import Database
from app.strategy.arbitration import SignalArbiter
from app.strategy.base_strategy import BaseStrategy
from app.strategy.context_builder import AnalyzedFrame, analyze_frame, context_at
from app.strategy.market_maps import MapBook
from app.strategy.registry import StrategySet
from app.strategy.signal_models import OpenPosition, StrategyContext

log = logging.getLogger(__name__)

MAGIC_BASE = 7_310_000  # same default as MAGIC_NUMBER_BASE; position i of the strategy list gets base + i
MAIN = "main"  # the run's own entry timeframe (app.engine.lanes.MAIN)


@dataclass(frozen=True)
class SymbolData:
    spec: SymbolSpec
    frames: Mapping[Timeframe, pd.DataFrame]  # closed candles (``CANDLE_COLUMNS``) per enabled timeframe


@dataclass(frozen=True)
class BacktestLane:
    """One more entry timeframe in a run (TAA-507): the lane's config view (:meth:`AppConfig.for_lane`), its
    strategies, the symbols it trades and the evidence its strategies need."""

    name: str
    config: AppConfig
    strategies: StrategySet
    symbols: frozenset[str]
    evidence: EvidenceEngine | None = None


@dataclass
class _Lane:
    name: str
    config: AppConfig
    strategies: StrategySet
    symbols: frozenset[str] | None  # None: every symbol of the run
    evidence: EvidenceEngine | None
    maps: MapBook | None
    arbiter: SignalArbiter
    by_name: dict[str, BaseStrategy]

    @property
    def entry_tf(self) -> Timeframe:
        return self.config.timeframes.entry

    def trades(self, symbol: str) -> bool:
        return self.symbols is None or symbol in self.symbols


@dataclass(frozen=True)
class RiskPreset:
    """A cage and the profile limits combined with it for every decision (PLAN §A36)."""

    name: str
    cage: RiskConfig
    limits: ProfileLimits

    @property
    def effective(self) -> RiskConfig:
        return effective_risk(self.cage, self.limits)


@dataclass(frozen=True, slots=True)
class Progress:
    step: int
    total: int
    at: datetime
    equity: float
    open_positions: int

    @property
    def fraction(self) -> float:
        return self.step / self.total if self.total else 1.0


@dataclass
class BacktestResult:
    trades: list[ClosedTrade]
    equity_curve: list[EquityPoint]
    initial_balance: float
    start: datetime | None
    end: datetime | None
    symbols: list[str]
    signals: int = 0
    decisions: Counter[str] = field(default_factory=Counter)
    rejections: Counter[str] = field(default_factory=Counter)

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1].equity if self.equity_curve else self.initial_balance


class BacktestEngine:
    def __init__(
        self,
        config: AppConfig,
        data: Mapping[str, SymbolData],
        strategies: StrategySet,
        rates: RateSource,
        *,
        evidence: EvidenceEngine | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        on_progress: Callable[[Progress], None] | None = None,
        progress_every: int = 500,
        config_hash: str = "",
        context: Mapping[str, Mapping[Timeframe, pd.DataFrame]] | None = None,
        risk_preset: RiskPreset | None = None,
        lanes: Sequence[BacktestLane] = (),
        main_symbols: Collection[str] | None = None,
    ) -> None:
        """*lanes*: more entry timeframes sharing the account (TAA-507); *config* then is the full config (its
        ``lanes`` give each lane strategy its spread ratio, cooldown and management). *main_symbols*: the
        symbols the main lane trades (None: all of *data*)."""
        self.config = config
        self.risk_preset = risk_preset
        self.data = dict(data)
        # TAA-L809: the higher-timeframe market map (MarketContext.htf), as in live and replay, when the
        # context timeframes' candles are given (app.backtest.runner.load_context)
        self.context = {s: dict(frames) for s, frames in (context or {}).items()}
        self.strategies = strategies
        self.evidence = evidence
        main = None if main_symbols is None else frozenset(main_symbols)
        if lanes and not strategies.strategies:
            main = frozenset()  # e.g. only a lane's strategies selected: the main lane steps nothing
        specs = [(MAIN, config, strategies, main, evidence)]
        specs += [(x.name, x.config, x.strategies, x.symbols, x.evidence) for x in lanes]
        self.lanes = [
            _Lane(
                name,
                cfg,
                sset,
                syms,
                ev,
                MapBook.from_config(cfg) if self.context else None,
                SignalArbiter(cfg.strategies.cooldown_bars),
                {s.name: s for s in sset.strategies},
            )
            for name, cfg, sset, syms, ev in specs
            if sset.strategies or name == MAIN
        ]
        self.maps = self.lanes[0].maps
        self.start, self.end = start, end
        self.on_progress = on_progress
        self.progress_every = max(1, progress_every)
        self.entry_tf = config.timeframes.entry
        self.clock = ManualClock(datetime(2000, 1, 1, tzinfo=UTC))
        bt = config.backtest
        commissions = {
            sym: o.commission_per_lot
            for sym, o in config.symbols.overrides.items()
            if o.commission_per_lot is not None
        }
        self.broker = SimulatedBroker(
            {s: d.spec for s, d in self.data.items()},
            bt,
            rates,
            account_currency=bt.account_currency,
            leverage=bt.leverage,
            commission_overrides=commissions,
        )
        self.db = Database("sqlite://")
        self.db.create_all()
        tz = "Europe/Athens"
        self.losses = LossTracker(self.db, "backtest", tz, self.clock)
        self.board = BreakerBoard(
            self.db,
            default_specs(config.breakers, consecutive_pause_hours=config.risk.consecutive_loss_pause_hours),
            self.clock,
            mode=TradingMode.BACKTEST,
            tz_name=tz,
        )
        loss_limits = config.risk if risk_preset is None else risk_preset.effective
        self.monitor = BreakerMonitor(self.board, config.breakers, loss_limits, self.clock)
        self.decisions = DecisionEngine(
            config,
            TradingMode.BACKTEST,
            self.broker,
            self.clock,
            sessions=TradingSessions(config.sessions, config.symbols),
            news=NewsFilter(ManualBlackouts(config.sessions.news_blackouts)),
            magic_base=MAGIC_BASE,
            config_hash=config_hash,
            breakers=self.board,
        )
        self.arbiter = self.lanes[0].arbiter
        everything = [s for lane in self.lanes for s in lane.strategies.strategies]
        self._magic = {s.name: MAGIC_BASE + i for i, s in enumerate(everything)}
        self._by_magic = {m: n for n, m in self._magic.items()}
        self._lane_of = {s: lane.name for lane in self.lanes for s in lane.by_name}
        self._last_entry: dict[str, datetime] = {}
        self._booked_deals = 0
        self._feed: dict[str, Timeframe] = {}  # per symbol: the timeframe the broker steps it on

    # --- preparation --------------------------------------------------------------------------------------

    def _analyze(self) -> dict[str, dict[str, dict[Timeframe, AnalyzedFrame]]]:
        """Per lane, per symbol it trades: its enabled timeframes, each frame analyzed once for the run."""
        cache: dict[tuple[str, Timeframe], AnalyzedFrame] = {}
        out: dict[str, dict[str, dict[Timeframe, AnalyzedFrame]]] = {}
        for lane in self.lanes:
            cfg = lane.config
            per: dict[str, dict[Timeframe, AnalyzedFrame]] = {}
            for symbol, d in self.data.items():
                if not lane.trades(symbol):
                    continue
                missing = [tf for tf in cfg.timeframes.enabled if tf not in d.frames]
                if missing:
                    where = "" if lane.name == MAIN else f" (lane {lane.name})"
                    raise DataQualityError(f"{symbol}: no history for {missing}{where}")
                for tf in cfg.timeframes.enabled:
                    if (symbol, tf) not in cache:
                        cache[symbol, tf] = analyze_frame(d.frames[tf], tf, cfg.indicators, cfg.regime)
                per[symbol] = {tf: cache[symbol, tf] for tf in cfg.timeframes.enabled}
            out[lane.name] = per
        for symbol in self.data:
            tfs = [lane.entry_tf for lane in self.lanes if symbol in out[lane.name]]
            if tfs:
                self._feed[symbol] = min(tfs, key=lambda tf: tf.seconds)
        return out

    def _timeline(
        self, analyzed: Mapping[str, Mapping[str, Mapping[Timeframe, AnalyzedFrame]]]
    ) -> list[pd.Timestamp]:
        times: set[pd.Timestamp] = set()
        for lane in self.lanes:
            for frames in analyzed[lane.name].values():
                idx = frames[lane.entry_tf].df.index
                if self.start is not None:
                    idx = idx[idx >= pd.Timestamp(self.start)]
                if self.end is not None:
                    idx = idx[idx <= pd.Timestamp(self.end)]
                times.update(idx)
        return sorted(times)

    # --- loop ---------------------------------------------------------------------------------------------

    def run(self) -> BacktestResult:
        analyzed = self._analyze()
        timeline = self._timeline(analyzed)
        result = BacktestResult([], [], self.config.backtest.initial_balance, None, None, sorted(self.data))
        if not timeline:
            return result
        result.start, result.end = timeline[0].to_pydatetime(), timeline[-1].to_pydatetime()
        for step, ts in enumerate(timeline, start=1):
            t = ts.to_pydatetime()
            self.clock.set(t)
            for symbol, feed_tf in self._feed.items():
                feed = self._frame_at(analyzed, symbol, feed_tf, ts)
                if feed is not None:
                    self.broker.on_bar(symbol, self._bar(symbol, feed[0].df.iloc[feed[1]], t))
                for lane in self.lanes:
                    frames = analyzed[lane.name].get(symbol)
                    if frames is None:
                        continue
                    index = frames[lane.entry_tf].df.index
                    pos = int(index.searchsorted(ts))
                    if pos < len(index) and index[pos] == ts:
                        self._step_symbol(symbol, frames, pos, t, result, lane)
            self.broker.record_equity(t)
            self._book_losses()
            if self.on_progress is not None and (step % self.progress_every == 0 or step == len(timeline)):
                self.on_progress(
                    Progress(step, len(timeline), t, self.broker.equity, len(self.broker.positions))
                )
        self.broker.close_all(timeline[-1].to_pydatetime(), ExitReason.END_OF_DATA)
        self.broker.record_equity(timeline[-1].to_pydatetime())
        result.trades = list(self.broker.trades)
        result.equity_curve = list(self.broker.equity_curve)
        return result

    def _frame_at(
        self,
        analyzed: Mapping[str, Mapping[str, Mapping[Timeframe, AnalyzedFrame]]],
        symbol: str,
        tf: Timeframe,
        ts: pd.Timestamp,
    ) -> tuple[AnalyzedFrame, int] | None:
        """The *tf* frame of *symbol* (the first lane's with it) and the row of its bar closing at *ts*."""
        for lane in self.lanes:
            frames = analyzed[lane.name].get(symbol)
            if frames is not None and tf in frames:
                index = frames[tf].df.index
                pos = int(index.searchsorted(ts))
                return (frames[tf], pos) if pos < len(index) and index[pos] == ts else None
        return None

    def _bar(self, symbol: str, row: pd.Series, t: datetime) -> Bar:
        return entry_bar(row, t, self.broker.spread_price(symbol, float_or_none(row["spread"])))

    def _step_symbol(
        self,
        symbol: str,
        frames: Mapping[Timeframe, AnalyzedFrame],
        pos: int,
        t: datetime,
        result: BacktestResult,
        lane: _Lane,
    ) -> None:
        """One lane at the close *t* of its entry bar (the broker has already stepped the symbol)."""
        bar = self._bar(symbol, frames[lane.entry_tf].df.iloc[pos], t)
        try:
            ctx = self._context(symbol, frames, t, bar, lane)
        except (InsufficientDataError, DataQualityError):
            return
        self._manage(symbol, ctx, bar, lane, frames[lane.entry_tf], t)
        signals = lane.strategies.evaluate(ctx)
        result.signals += sum(1 for s in signals if s.is_entry)
        selected = lane.arbiter.arbitrate(signals).selected
        if selected is None:
            return
        spec = self.broker.spec_at(symbol)
        quote = bar_quote(symbol, bar, spec, t)
        account = AccountState(self.broker.funds(), self.broker.broker_positions(), self._loss_status())
        record = self.decisions.decide(
            DecisionRequest(
                signal=selected,
                market=ctx.market,
                spec=spec,
                quote=quote,
                account=account,
                health=SystemHealth(),
                specs={s: d.spec for s, d in self.data.items()},
                last_entry_at=self._last_entry.get(symbol),
                profile_limits=None if self.risk_preset is None else self.risk_preset.limits,
                cage=None if self.risk_preset is None else self.risk_preset.cage,
                risk_source=None if self.risk_preset is None else f"preset:{self.risk_preset.name}",
            )
        )
        result.decisions[record.decision.value] += 1
        for code in record.reason_codes:
            result.rejections[code] += 1
        if record.decision is not Decision.ACCEPT or record.sizing is None:
            return
        self._last_entry[symbol] = t
        side = selected.side
        if side is None:
            return
        for part in record.sizing.parts:
            self.broker.submit(
                OrderRequest(
                    symbol=symbol,
                    side=side,
                    volume=float(part.volume),
                    sl=float(record.sizing.stop_loss) if record.sizing.stop_loss is not None else None,
                    tp=selected.take_profit,
                    magic=self._magic.get(selected.strategy, MAGIC_BASE),
                    comment=selected.strategy[:25],
                    strategy=selected.strategy,
                    signal_id=selected.signal_id,
                    risk_money=float(part.risk_money),
                ),
                t,
            )

    def _context(
        self, symbol: str, frames: Mapping[Timeframe, AnalyzedFrame], t: datetime, bar: Bar, lane: _Lane
    ) -> StrategyContext:
        spec = self.broker.spec_at(symbol)
        htf = None if lane.maps is None else lane.maps.at(symbol, self.context.get(symbol, {}), t, spec.point)
        return bar_context(lane.config, frames, symbol, t, bar, spec, lane.evidence, htf)

    def _manage(
        self, symbol: str, ctx: StrategyContext, bar: Bar, lane: _Lane, entry: AnalyzedFrame, t: datetime
    ) -> None:
        """The positions of *lane*'s strategies on *symbol* (an unknown strategy's: the main lane's)."""
        cfg = self.config.management
        spec = self.data[symbol].spec
        own_feed = self._feed.get(symbol) is lane.entry_tf
        for p in [p for p in self.broker.positions.values() if p.symbol == symbol]:
            name = self._by_magic.get(p.request.magic, "")
            if self._lane_of.get(name, MAIN) != lane.name:
                continue
            strategy = lane.by_name.get(name)
            if strategy is not None and strategy.should_close(ctx, p.side):
                self.broker.request_close(p.ticket, ExitReason.SIGNAL)
                continue
            if p.request.sl is None or p.sl is None:
                continue
            mark = mark_price(p.side, bar.close, bar.spread)
            own = None
            if strategy is not None:
                view = OpenPosition(
                    p.side, p.entry_price, p.request.sl, p.sl, p.request.tp, p.entry_time, p.request.signal_id
                )
                own = from_advice(strategy.manage_position(ctx, view), p.side, mark=mark, sl=p.sl)
            # bars held on the lane's own timeframe (the broker may step the symbol on a finer one)
            held = p.bars_held if own_feed else entry.count_upto(t) - entry.count_upto(p.entry_time)
            adj = manage(
                PositionView(p.side, p.entry_price, p.request.sl, p.sl, held, p.request.tp),
                mark=mark,
                atr=ctx.market.atr,
                point=spec.point,
                cfg=cfg.for_strategy(name),
                reach=bar.high if p.side is Side.BUY else bar.low + bar.spread,
            )
            adj = with_advice(p.side, adj, own)
            if adj.close is not None:
                self.broker.request_close(p.ticket, adj.close)
            elif adj.new_sl is not None:
                self.broker.modify(p.ticket, sl=adj.new_sl, stop_kind=adj.stop_kind)

    def _loss_status(self) -> LossStatus:
        return self.losses.observe(self.broker.equity)

    def _book_losses(self) -> None:
        new = self.broker.deals[self._booked_deals :]
        self._booked_deals = len(self.broker.deals)
        status = self.losses.observe(self.broker.equity, new, is_bot=lambda d: d.magic in self._by_magic)
        self.monitor.observe_losses(status)
        self.board.tick()


def bar_quote(symbol: str, bar: Bar, spec: SymbolSpec, t: datetime) -> Quote:
    """The quote at a bar's close: bid = close, ask = close + the bar's spread."""
    return Quote(symbol, bar.close, bar.close + bar.spread, bar.spread / spec.point, t, 0.0, True)


def bar_context(
    config: AppConfig,
    frames: Mapping[Timeframe, AnalyzedFrame],
    symbol: str,
    t: datetime,
    bar: Bar,
    spec: SymbolSpec,
    evidence_engine: EvidenceEngine | None,
    htf: MarketMap | None = None,
) -> StrategyContext:
    """The strategy context at the close *t* of *bar* from frames analyzed once (shared with replay)."""
    evidence = None
    if evidence_engine is not None:
        evidence = {}
        for tf, frame in frames.items():
            n = frame.count_upto(t)
            window = frame.df.iloc[max(0, n - config.timeframes.warmup_bars) : n].reset_index(
                names="close_time"
            )
            if len(window):
                evidence[tf] = evidence_engine.evaluate(EvidenceContext(symbol, tf, window, config.evidence))
    return context_at(
        frames,
        symbol=symbol,
        entry_timeframe=config.timeframes.entry,
        higher_timeframe=config.timeframes.higher,
        decision_time=t,
        now_utc=t,
        params=config.indicators,
        quote=bar_quote(symbol, bar, spec, t),
        spec=spec,
        evidence=evidence,
        window=config.timeframes.warmup_bars,
        htf=htf,
    )


def entry_bar(row: pd.Series, t: datetime, spread: float) -> Bar:
    """An analyzed entry-timeframe row as a :class:`Bar` closing at *t*."""
    return Bar(
        pd.Timestamp(row["open_time"]).to_pydatetime(),
        t,
        float(row["open"]),
        float(row["high"]),
        float(row["low"]),
        float(row["close"]),
        spread,
    )


def float_or_none(value: object) -> float | None:
    """A bar's spread field (NaN or missing in some histories) as a float, or None."""
    try:
        f = float(str(value))
    except ValueError:
        return None
    return f if math.isfinite(f) else None
