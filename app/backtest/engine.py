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
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from app.config import AppConfig
from app.core.clock import ManualClock
from app.core.enums import ExitReason, Timeframe, TradingMode
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
from app.execution.management import PositionView, manage
from app.execution.simulated_broker import ClosedTrade, EquityPoint, OrderRequest, RateSource, SimulatedBroker
from app.market_data.data_models import Quote, SymbolSpec
from app.market_data.trading_sessions import TradingSessions
from app.news.calendar import ManualBlackouts, NewsFilter
from app.risk.breaker_monitor import BreakerMonitor
from app.risk.circuit_breaker import BreakerBoard, default_specs
from app.risk.loss_tracker import LossStatus, LossTracker
from app.storage.database import Database
from app.strategy.arbitration import SignalArbiter
from app.strategy.context_builder import AnalyzedFrame, analyze_frame, context_at
from app.strategy.registry import StrategySet
from app.strategy.signal_models import StrategyContext

log = logging.getLogger(__name__)

MAGIC_BASE = 7_310_000  # same default as MAGIC_NUMBER_BASE; position i of the strategy list gets base + i


@dataclass(frozen=True)
class SymbolData:
    spec: SymbolSpec
    frames: Mapping[Timeframe, pd.DataFrame]  # closed candles (``CANDLE_COLUMNS``) per enabled timeframe


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
    ) -> None:
        self.config = config
        self.data = dict(data)
        self.strategies = strategies
        self.evidence = evidence
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
        self.monitor = BreakerMonitor(self.board, config.breakers, config.risk, self.clock)
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
        self.arbiter = SignalArbiter(config.strategies.cooldown_bars)
        self._magic = {s.name: MAGIC_BASE + i for i, s in enumerate(strategies.strategies)}
        self._by_magic = {m: n for n, m in self._magic.items()}
        self._last_entry: dict[str, datetime] = {}
        self._booked_deals = 0

    # --- preparation --------------------------------------------------------------------------------------

    def _analyze(self) -> dict[str, dict[Timeframe, AnalyzedFrame]]:
        cfg = self.config
        out = {}
        for symbol, d in self.data.items():
            missing = [tf for tf in cfg.timeframes.enabled if tf not in d.frames]
            if missing:
                raise DataQualityError(f"{symbol}: no history for {missing}")
            out[symbol] = {
                tf: analyze_frame(d.frames[tf], tf, cfg.indicators, cfg.regime)
                for tf in cfg.timeframes.enabled
            }
        return out

    def _timeline(self, analyzed: Mapping[str, Mapping[Timeframe, AnalyzedFrame]]) -> list[pd.Timestamp]:
        times: set[pd.Timestamp] = set()
        for frames in analyzed.values():
            idx = frames[self.entry_tf].df.index
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
            for symbol, frames in analyzed.items():
                index = frames[self.entry_tf].df.index
                pos = int(index.searchsorted(ts))
                if pos < len(index) and index[pos] == ts:
                    self._step_symbol(symbol, frames, pos, t, result)
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

    def _step_symbol(
        self,
        symbol: str,
        frames: Mapping[Timeframe, AnalyzedFrame],
        pos: int,
        t: datetime,
        result: BacktestResult,
    ) -> None:
        row = frames[self.entry_tf].df.iloc[pos]
        spread = self.broker.spread_price(symbol, _float_or_none(row["spread"]))
        bar = Bar(
            pd.Timestamp(row["open_time"]).to_pydatetime(),
            t,
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            spread,
        )
        self.broker.on_bar(symbol, bar)
        try:
            ctx = self._context(symbol, frames, t, bar)
        except (InsufficientDataError, DataQualityError):
            return
        self._manage(symbol, ctx, bar)
        signals = self.strategies.evaluate(ctx)
        result.signals += sum(1 for s in signals if s.is_entry)
        selected = self.arbiter.arbitrate(signals).selected
        if selected is None:
            return
        spec = self.broker.spec_at(symbol)
        quote = Quote(symbol, bar.close, bar.close + spread, spread / spec.point, t, 0.0, True)
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
        self, symbol: str, frames: Mapping[Timeframe, AnalyzedFrame], t: datetime, bar: Bar
    ) -> StrategyContext:
        cfg = self.config
        evidence = None
        if self.evidence is not None:
            evidence = {}
            for tf, frame in frames.items():
                n = frame.count_upto(t)
                window = frame.df.iloc[max(0, n - cfg.timeframes.warmup_bars) : n].reset_index(
                    names="close_time"
                )
                if len(window):
                    evidence[tf] = self.evidence.evaluate(EvidenceContext(symbol, tf, window, cfg.evidence))
        spec = self.broker.spec_at(symbol)
        quote = Quote(symbol, bar.close, bar.close + bar.spread, bar.spread / spec.point, t, 0.0, True)
        return context_at(
            frames,
            symbol=symbol,
            entry_timeframe=self.entry_tf,
            higher_timeframe=cfg.timeframes.higher,
            decision_time=t,
            now_utc=t,
            params=cfg.indicators,
            quote=quote,
            spec=spec,
            evidence=evidence,
            window=cfg.timeframes.warmup_bars,
        )

    def _manage(self, symbol: str, ctx: StrategyContext, bar: Bar) -> None:
        cfg = self.config.position_management
        by_name = {s.name: s for s in self.strategies.strategies}
        spec = self.data[symbol].spec
        for p in [p for p in self.broker.positions.values() if p.symbol == symbol]:
            strategy = by_name.get(self._by_magic.get(p.request.magic, ""))
            if strategy is not None and strategy.should_close(ctx, p.side):
                self.broker.request_close(p.ticket, ExitReason.SIGNAL)
                continue
            if p.request.sl is None or p.sl is None:
                continue
            adj = manage(
                PositionView(p.side, p.entry_price, p.request.sl, p.sl, p.bars_held),
                mark=mark_price(p.side, bar.close, bar.spread),
                atr=ctx.market.atr,
                point=spec.point,
                cfg=cfg,
            )
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


def _float_or_none(value: object) -> float | None:
    """A bar's spread field (NaN or missing in some histories) as a float, or None."""
    try:
        f = float(str(value))
    except ValueError:
        return None
    return f if math.isfinite(f) else None
