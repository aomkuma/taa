"""Historical replay (PLAN §A27 "Historical replay"; TAA-6C2): the scanner over stored history.

For each symbol and every closed entry-timeframe bar in ``[start, end]``:

1. The context at the bar close from frames analyzed once (:func:`app.backtest.engine.bar_context`, the
   backtest's code), with the evidence engine planned for the required detectors only.
2. Every entry signal of the strategy union, without arbitration (like the live scanner).
3. The decision engine's **ADVISORY profile** at the bar-close quote (bid = close, ask = close + the bar's
   spread) for a flat account of ``equity`` (no positions, no loss state). Hard failures create nothing.
4. An accepted signal gets ``PLAN`` and ``MANAGED`` shadow trades (``source = REPLAY``) entered at that quote
   plus slippage and resolved with :func:`app.advisory.shadow.advance` on the finest stored resolution
   (M1, else M5). History has no ticks, so a bar touching both SL and TP is resolved SL first
   (``AMBIGUOUS``).

Rows use the opportunity id ``replay:<signal idempotency key>`` and are idempotent: a rerun or an
overlapping window adds only signals not stored yet. The run is deterministic (fixed slippage, no
randomness): the same data, config and equity give identical rows. Trades still open when the data ends are
not stored (``unresolved``).

Limitations, on top of the shadow ones: entries at the bar close (live enters at the decision quote), money
valued at the conversion rate of the signal time, constant equity (no compounding), news blackouts only as
configured.
"""

from __future__ import annotations

import bisect
import logging
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select

from app.advisory.asset_classes import classify
from app.advisory.confidence import Source, signal_features
from app.advisory.scoring import swap_per_night
from app.advisory.shadow import (
    Management,
    Variant,
    advance,
    bars_from_frame,
    entry_fill,
    new_state,
    rollover_days,
    settle,
)
from app.advisory.shadow_tracker import (
    EntryQuote,
    SignalFacts,
    apply_close,
    apply_state,
    commission_per_lot,
    new_row,
)
from app.backtest.conversion import SeriesRates
from app.backtest.engine import SymbolData, bar_context, bar_quote, entry_bar, float_or_none
from app.config import AppConfig
from app.core.clock import ManualClock
from app.core.enums import Timeframe, TradingMode
from app.core.errors import DataQualityError, InsufficientDataError
from app.engine.decision_engine import AccountState, Decision, DecisionEngine, DecisionRequest, Profile
from app.evidence.registry import EvidenceEngine
from app.execution.fill_model import Bar
from app.execution.simulated_broker import SimulatedBroker
from app.market_data.history_store import ParquetHistoryStore
from app.market_data.trading_sessions import TradingSessions
from app.news.calendar import ManualBlackouts, NewsFilter
from app.storage.database import Database
from app.storage.models import ShadowTradeRow
from app.strategy.context_builder import AnalyzedFrame, analyze_frame
from app.strategy.registry import StrategySet
from app.strategy.signal_models import Signal, StrategyContext

log = logging.getLogger(__name__)

RESOLUTIONS = (Timeframe.M1, Timeframe.M5)
PREFIX = "replay:"


@dataclass(frozen=True)
class Resolution:
    timeframe: Timeframe
    frame: pd.DataFrame  # normalized candles (``CANDLE_COLUMNS``), bid OHLC, spread in points


def load_resolution(
    store: ParquetHistoryStore,
    server: str,
    symbol: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    preferred: Sequence[Timeframe] = RESOLUTIONS,
) -> Resolution:
    """The finest stored resolution frame (M1, else M5); fails closed when neither is stored."""
    for tf in preferred:
        df = store.load(server, symbol, tf, start, end)
        if not df.empty:
            return Resolution(tf, df.reset_index(drop=True))
    names = "/".join(tf.value for tf in preferred)
    raise DataQualityError(f"{symbol}: no {names} history to resolve shadow trades (download it first)")


@dataclass
class ReplayReport:
    symbols: list[str]
    resolution: dict[str, str] = field(default_factory=dict)
    bars: int = 0
    signals: int = 0
    accepted: int = 0
    hidden: int = 0  # hard ADVISORY failures
    stored: int = 0  # shadow rows written
    existing: int = 0  # signals already stored by an earlier run
    unresolved: int = 0  # shadow trades still open when the data ended
    start: datetime | None = None
    end: datetime | None = None


class HistoricalReplay:
    def __init__(
        self,
        config: AppConfig,
        data: Mapping[str, SymbolData],
        resolution: Mapping[str, Resolution],
        rates: SeriesRates,
        strategies: StrategySet,
        *,
        server: str,
        evidence: EvidenceEngine | None = None,
        equity: float | None = None,
        currency: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        broker_tz: str = "Europe/Athens",
        config_hash: str = "",
        on_symbol: Callable[[str, int, int], None] | None = None,
    ) -> None:
        missing = sorted(set(data) - set(resolution))
        if missing:
            raise DataQualityError(f"no resolution history for {missing}")
        self.config = config
        self.data = dict(data)
        self.resolution = dict(resolution)
        self.strategies = strategies
        self.server = server
        self.evidence = evidence
        bt = config.backtest
        self.equity = equity if equity is not None else bt.initial_balance
        self.currency = currency or bt.account_currency
        self.start, self.end = start, end
        self.tz = ZoneInfo(broker_tz)
        self.on_symbol = on_symbol
        self.entry_tf = config.timeframes.entry
        self.clock = ManualClock(datetime(2000, 1, 1, tzinfo=UTC))
        # the simulated broker only prices: P/L, margin and tick values at each bar's conversion rate
        self.broker = SimulatedBroker(
            {s: d.spec for s, d in self.data.items()},
            bt.model_copy(update={"initial_balance": self.equity}),
            rates,
            account_currency=self.currency,
            leverage=bt.leverage,
            broker_tz=broker_tz,
        )
        self.decisions = DecisionEngine(
            config,
            TradingMode.BACKTEST,
            self.broker,
            self.clock,
            sessions=TradingSessions(config.sessions, config.symbols),
            news=NewsFilter(ManualBlackouts(config.sessions.news_blackouts)),
            magic_base=0,
            config_hash=config_hash,
        )
        self.universe = frozenset(self.data)

    # --- run ------------------------------------------------------------------------------------------------

    def run(self, db: Database) -> ReplayReport:
        report = ReplayReport(sorted(self.data))
        with db.session() as sess:
            existing = set(
                sess.execute(
                    select(ShadowTradeRow.opportunity_id).where(
                        ShadowTradeRow.source == Source.REPLAY.value, ShadowTradeRow.server == self.server
                    )
                ).scalars()
            )
        for symbol in sorted(self.data):
            rows = self._symbol(symbol, existing, report)
            with db.session() as sess:
                for row in rows:
                    if sess.get(ShadowTradeRow, row.shadow_id) is None:
                        sess.add(row)
                        report.stored += 1
            log.info("replay %s: %d shadow rows", symbol, len(rows))
        return report

    def _analyze(self, symbol: str) -> dict[Timeframe, AnalyzedFrame]:
        cfg = self.config
        frames = self.data[symbol].frames
        missing = [tf for tf in cfg.timeframes.enabled if tf not in frames]
        if missing:
            raise DataQualityError(f"{symbol}: no history for {missing}")
        return {
            tf: analyze_frame(frames[tf], tf, cfg.indicators, cfg.regime) for tf in cfg.timeframes.enabled
        }

    def _symbol(self, symbol: str, existing: Collection[str], report: ReplayReport) -> list[ShadowTradeRow]:
        analyzed = self._analyze(symbol)
        res = self.resolution[symbol]
        report.resolution[symbol] = res.timeframe.value
        spec0 = self.data[symbol].spec
        bars = bars_from_frame(res.frame, spec0.point)
        opens = [b.open_time for b in bars]
        index = analyzed[self.entry_tf].df.index
        positions = [
            i
            for i, ts in enumerate(index)
            if (self.start is None or ts >= pd.Timestamp(self.start))
            and (self.end is None or ts <= pd.Timestamp(self.end))
        ]
        out: list[ShadowTradeRow] = []
        for n, pos in enumerate(positions, start=1):
            ts = index[pos]
            t = ts.to_pydatetime()
            self.clock.set(t)
            row = analyzed[self.entry_tf].df.iloc[pos]
            bar = entry_bar(row, t, self.broker.spread_price(symbol, float_or_none(row["spread"])))
            self.broker.on_bar(symbol, bar)  # conversion rates and tick values at t
            spec = self.broker.spec_at(symbol)
            try:
                ctx = bar_context(self.config, analyzed, symbol, t, bar, spec, self.evidence)
            except (InsufficientDataError, DataQualityError):
                continue
            report.bars += 1
            report.start = report.start or t
            report.end = t
            for signal in self.strategies.evaluate(ctx):
                if not signal.is_entry:
                    continue
                report.signals += 1
                oid = PREFIX + signal.idempotency_key
                if oid in existing:
                    report.existing += 1
                    continue
                out += self._consider(signal, ctx, bar, t, bars, opens, report)
            if self.on_symbol is not None and n % 500 == 0:
                self.on_symbol(symbol, n, len(positions))
        return out

    def _consider(
        self,
        signal: Signal,
        ctx: StrategyContext,
        bar: Bar,
        t: datetime,
        bars: Sequence[Bar],
        opens: Sequence[datetime],
        report: ReplayReport,
    ) -> list[ShadowTradeRow]:
        symbol = signal.symbol
        spec = self.broker.spec_at(symbol)
        quote = bar_quote(symbol, bar, spec, t)
        record = self.decisions.decide(
            DecisionRequest(
                signal=signal,
                market=ctx.market,
                spec=spec,
                quote=quote,
                account=AccountState(self.broker.funds(), [], None),
                specs={symbol: spec},
                universe=self.universe,
            ),
            Profile.ADVISORY,
        )
        side = signal.side
        if record.decision is not Decision.ACCEPT or side is None or signal.stop_loss is None:
            report.hidden += 1
            return []
        report.accepted += 1
        cfg = self.config.advisory.shadow
        slip = cfg.slippage_points * spec.point
        lot = None if record.volume is None else float(record.volume)
        facts = SignalFacts(
            opportunity_id=PREFIX + signal.idempotency_key,
            source=Source.REPLAY.value,
            server=self.server,
            strategy=signal.strategy,
            symbol=symbol,
            asset_class=classify(spec).value,
            timeframe=signal.timeframe.value,
            side=side.value,
            session=ctx.market.session.value,
            setup_strength=signal.setup_strength,
            rr=signal.risk_reward,
            features=signal_features(signal, ctx.market),
            atr=ctx.market.atr,
            signal_at=t,
            lot=lot,
            equity=self.equity,
            currency=self.currency,
        )
        entry_quote = EntryQuote(quote.bid, quote.ask, quote.spread_points, cfg.slippage_points)
        first = bisect.bisect_left(opens, t)
        rows = []
        for variant in Variant:
            state = new_state(
                side=side,
                entry=entry_fill(side, quote.bid, quote.ask, slip),
                entry_at=t,
                sl=signal.stop_loss,
                tp=signal.take_profit,
                time_stop=timedelta(hours=cfg.time_stop_hours),
            )
            row = new_row(facts, variant, state, entry_quote, (), t)
            if state.risk <= 0:
                rows.append(row)  # VOID
                continue
            management = None
            if variant is Variant.MANAGED:
                management = Management(
                    self.config.position_management, ctx.market.atr, spec.point, self.entry_tf.seconds
                )
            later = (bars[i] for i in range(first, len(bars)))  # lazy: stops at the exit
            exit_ = advance(state, later, slippage=slip, management=management)
            if exit_ is None:
                report.unresolved += 1
                continue
            entry = state.entry

            def profit(volume: float, price: float, entry: float = entry) -> float | None:
                return self.broker.calc_profit(side, symbol, volume, entry, price)

            result = settle(
                state,
                exit_,
                lot=lot,
                profit=profit,
                commission_per_lot=commission_per_lot(self.config, symbol),
                swap_per_lot_night=swap_per_night(spec, side),
                swap_days=rollover_days(t, exit_.at, tz=self.tz, triple_weekday=spec.swap_rollover3days),
            )
            apply_state(row, state, t)
            apply_close(row, exit_, result)
            rows.append(row)
        return rows
