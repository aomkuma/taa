"""Market opportunity scanner (PLAN §A26 "Scanner"; TAA-6B3): inside the engine; never trades or alerts.

On every new closed entry-timeframe bar of a monitored symbol (:mod:`app.advisory.requirements`):

1. Build the context with the evidence engine planned for the users' detector union only, and evaluate the
   strategy union (trading strategies plus the pattern setups users allow).
2. Run each entry signal through the decision engine's **ADVISORY profile** (the monitored symbols replace the
   allowlist). A hard failure (bad data, closed market, geometry, RR, spread, min lot, margin) records no
   opportunity; the decision record keeps the reasons. Account-rule hits become warnings.
3. Size it for the owner's broker account (lot, risk and reward money from current equity).
4. Store a market :class:`~app.storage.models.OpportunityRow`, idempotent per strategy/symbol/bar/side, with
   the full signal (conditions, evidence, confluence) and the model features of
   :func:`~app.advisory.confidence.signal_features`.

Who gets alerted is decided per user by the personalizer (§A30), not here. Work is time-boxed per engine
cycle (``advisory.scanner.budget_seconds``): new bars are queued and the queue continues in the next cycle, so
position monitoring and breakers keep priority. The scan timeframes are ``timeframes`` from ``config.yaml``.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime

from app.advisory.asset_classes import classify
from app.advisory.confidence import signal_features
from app.advisory.requirements import ComputeRequirements
from app.broker.gateway import MarketDataGateway
from app.config import AppConfig, StrategiesConfig, StrategyEntry
from app.core.clock import Clock
from app.core.errors import ConfigError, TaaError
from app.engine.decision_engine import (
    AccountState,
    Decision,
    DecisionEngine,
    DecisionRecord,
    DecisionRequest,
    Profile,
    SystemHealth,
)
from app.evidence.catalog import default_registry as evidence_registry
from app.evidence.registry import EvidenceEngine
from app.market_data.candle_service import CandleService
from app.market_data.data_models import Quote, SymbolSpec
from app.market_data.quote_service import QuoteService
from app.risk.loss_tracker import LossStatus
from app.risk.mode_gates import GateResult
from app.risk.position_sizer import AccountFunds
from app.storage.database import Database
from app.storage.models import OpportunityRow
from app.storage.models.base import LOCAL_ENGINE
from app.strategy.base_strategy import BaseStrategy
from app.strategy.catalog import default_registry as strategy_registry
from app.strategy.context_builder import ContextBuilder
from app.strategy.registry import StrategyRegistry, StrategySet
from app.strategy.signal_models import Signal, StrategyContext

log = logging.getLogger(__name__)


def strategy_set(config: AppConfig, names: Iterable[str], registry: StrategyRegistry) -> StrategySet:
    """The named strategies with their ``config.yaml`` params, enabled for advice whatever their trading flag.

    One that cannot be built (e.g. it needs a timeframe that is not enabled) is skipped with a warning, never
    guessed.
    """
    configured = {item.name: item for item in config.strategies.items}
    built: list[BaseStrategy] = []
    for name in sorted(names):
        params = configured[name].params if name in configured else {}
        one = config.strategies.model_copy(update={"items": [StrategyEntry(name=name, params=params)]})
        try:
            built += registry.from_config(
                StrategiesConfig.model_validate(one.model_dump()),
                config.timeframes,
                config.evidence.confluence,
            ).strategies
        except ConfigError as exc:
            log.warning("advisory skips strategy %s: %s", name, exc)
    return StrategySet(tuple(built), config.evidence.confluence)


@dataclass(slots=True)
class ScannerStats:
    bars: int = 0
    signals: int = 0
    opportunities: int = 0
    hidden: int = 0  # hard ADVISORY failures
    failures: int = 0
    last_duration_ms: float = 0.0
    last_error: str = ""


@dataclass(frozen=True, slots=True)
class ScanReport:
    scanned: tuple[str, ...]
    created: tuple[str, ...]  # opportunity ids
    pending: int


@dataclass
class _Plan:
    version: str
    requirements: ComputeRequirements
    builder: ContextBuilder
    strategies: StrategySet
    universe: frozenset[str] = field(default_factory=frozenset)


class OpportunityScanner:
    def __init__(
        self,
        db: Database,
        gateway: MarketDataGateway,
        config: AppConfig,
        clock: Clock,
        *,
        decisions: DecisionEngine,
        requirements: Callable[[], ComputeRequirements],
        server: str,
        health: Callable[[], SystemHealth] = SystemHealth,
        loss: Callable[[], LossStatus | None] = lambda: None,
        gate: Callable[[], GateResult | None] = lambda: None,
        strategy_catalog: StrategyRegistry | None = None,
        calibration_version: Callable[[], str | None] = lambda: None,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.config = config
        self.clock = clock
        self.decisions = decisions
        self.requirements = requirements
        self.server = server
        self.health = health
        self.loss = loss
        self.gate = gate
        self.strategy_catalog = strategy_catalog or strategy_registry()
        self.calibration_version = calibration_version
        self.candles = CandleService(gateway, config.timeframes, clock)
        self.quotes = QuoteService(gateway, clock, config.timeframes.stale_tick_seconds)
        self.stats = ScannerStats()
        self.specs: dict[str, SymbolSpec] = {}
        self.pending: deque[str] = deque()
        # symbols queued while they were monitored: their bar is scanned even if a newer plan (the ranking's
        # top N changes every minute) no longer lists them, instead of being refused as outside the universe
        self._admitted: set[str] = set()
        self._last_bar: dict[str, datetime] = {}
        self._plan: _Plan | None = None
        self._next_poll = 0.0

    # --- planning -------------------------------------------------------------------------------------------

    def plan(self) -> _Plan:
        req = self.requirements()
        if self._plan is not None and self._plan.version == req.version:
            return self._plan
        cfg = self.config
        registry = evidence_registry()
        evidence = EvidenceEngine(registry, registry.plan_from_config(cfg.evidence, only=req.detectors))
        builder = ContextBuilder(self.candles, cfg, self.clock, self.quotes, evidence)
        self._plan = _Plan(req.version, req, builder, self._strategy_set(req), frozenset(req.symbols))
        log.info(
            "scanner plan %s: %d symbols, %d detectors, strategies %s",
            req.version,
            len(req.symbols),
            len(req.detectors),
            ", ".join(self._plan.strategies.names),
        )
        return self._plan

    def _strategy_set(self, req: ComputeRequirements) -> StrategySet:
        return strategy_set(self.config, req.strategies, self.strategy_catalog)

    # --- scheduling -----------------------------------------------------------------------------------------

    def tick(self) -> ScanReport:
        """Queue symbols with a new closed entry bar, then scan the queue until the cycle budget is used."""
        plan = self.plan()
        started = self.clock.monotonic()
        if started >= self._next_poll:
            self._next_poll = started + self.config.engine.candle_poll_seconds
            self._discover(plan)
        scanned: list[str] = []
        created: list[str] = []
        budget = self.config.advisory.scanner.budget_seconds
        while self.pending and self.clock.monotonic() - started < budget:
            symbol = self.pending.popleft()
            scanned.append(symbol)
            created += self.scan_symbol(symbol, plan)
            self._admitted.discard(symbol)
        self.stats.last_duration_ms = (self.clock.monotonic() - started) * 1000
        return ScanReport(tuple(scanned), tuple(created), len(self.pending))

    def _discover(self, plan: _Plan) -> None:
        tf = self.config.timeframes.entry
        for symbol in plan.requirements.symbols:
            if symbol in self.pending:
                continue
            try:
                opened = self.candles.closed_candles(symbol, tf, 2).last_open_time
            except TaaError as exc:
                self._fail(symbol, exc)
                continue
            if opened is not None and (symbol not in self._last_bar or opened > self._last_bar[symbol]):
                self._last_bar[symbol] = opened  # each bar is queued once, even if its scan fails
                self.pending.append(symbol)
                self._admitted.add(symbol)

    def _fail(self, symbol: str, exc: Exception) -> None:
        self.stats.failures += 1
        self.stats.last_error = f"{symbol}: {type(exc).__name__}: {exc}"
        log.warning("scanner: %s failed: %s", symbol, exc)

    # --- one symbol -----------------------------------------------------------------------------------------

    def spec(self, symbol: str) -> SymbolSpec:
        if symbol not in self.specs:
            self.specs[symbol] = self.gateway.symbol_spec(symbol)
        return self.specs[symbol]

    def scan_symbol(self, symbol: str, plan: _Plan | None = None) -> list[str]:
        plan = plan or self.plan()
        try:
            spec = self.spec(symbol)
            ctx = plan.builder.build(symbol, spec)
        except TaaError as exc:
            self._fail(symbol, exc)
            return []
        self.stats.bars += 1
        created = []
        for signal in plan.strategies.evaluate(ctx):
            if not signal.is_entry:
                continue
            self.stats.signals += 1
            try:
                opportunity = self._consider(signal, ctx, spec, plan)
            except TaaError as exc:
                self._fail(symbol, exc)
                continue
            if opportunity is not None:
                created.append(opportunity)
        return created

    def _account(self) -> tuple[AccountState, str]:
        acct = self.gateway.account()
        funds = AccountFunds(acct.equity, acct.balance, acct.margin, acct.margin_free)
        return AccountState(funds, self.gateway.positions(), self.loss()), acct.currency

    def _consider(self, signal: Signal, ctx: StrategyContext, spec: SymbolSpec, plan: _Plan) -> str | None:
        universe = plan.universe | ({signal.symbol} if signal.symbol in self._admitted else set())
        with self.db.session() as sess:
            if sess.get(OpportunityRow, (LOCAL_ENGINE, signal.idempotency_key)) is not None:
                return None  # idempotent: this strategy/symbol/bar/side is already recorded
        account, currency = self._account()
        quote = self.quotes.quote(spec)
        record = self.decisions.decide(
            DecisionRequest(
                signal=signal,
                market=ctx.market,
                spec=spec,
                quote=quote,
                account=account,
                health=self.health(),
                specs=self.specs,
                gate=self.gate(),
                universe=universe,
            ),
            Profile.ADVISORY,
        )
        if record.decision is not Decision.ACCEPT:
            self.stats.hidden += 1
            return None
        row = self._row(record, ctx, spec, account, currency, plan, quote)
        with self.db.session() as sess:
            if sess.get(OpportunityRow, (LOCAL_ENGINE, row.opportunity_id)) is None:
                sess.add(row)
        self.stats.opportunities += 1
        log.info(
            "opportunity %s %s %s %s strength %.0f lot %s",
            row.strategy,
            row.symbol,
            row.side,
            row.timeframe,
            row.setup_strength,
            row.lot,
        )
        return row.opportunity_id

    def _row(
        self,
        record: DecisionRecord,
        ctx: StrategyContext,
        spec: SymbolSpec,
        account: AccountState,
        currency: str,
        plan: _Plan,
        quote: Quote,
    ) -> OpportunityRow:
        signal, market = record.signal, ctx.market
        side = signal.side
        if side is None or signal.entry_price is None or signal.stop_loss is None:
            raise TaaError(f"{signal.idempotency_key}: an accepted entry lacks its side, entry or stop")
        lot = record.volume
        reward = None
        if lot is not None and signal.take_profit is not None:
            raw = self.gateway.calc_profit(
                side, spec.name, float(lot), signal.entry_price, signal.take_profit
            )
            reward = None if raw is None else round(raw, 2)
        now = self.clock.now_utc()
        return OpportunityRow(
            opportunity_id=signal.idempotency_key,
            server=self.server,
            strategy=signal.strategy,
            symbol=signal.symbol,
            asset_class=classify(spec).value,
            timeframe=signal.timeframe.value,
            side=side.value,
            bar_close_at=market.decision_time_utc,
            created_at=now,
            signal_expires_at=signal.expires_at_utc,
            entry=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            rr=signal.risk_reward,
            setup_strength=signal.setup_strength,
            score=signal.score,
            status="CANDIDATE",
            status_reason="",
            status_at=now,
            decision_id=record.decision_id,
            warnings=list(record.warnings),
            lot=None if lot is None else float(lot),
            risk_money=None
            if record.sizing is None or lot is None
            else round(float(record.sizing.risk_money), 2),
            reward_money=reward,
            equity=account.funds.equity,
            currency=currency,
            session=market.session.value,
            regime=market.entry.regime.value,
            atr=market.atr,
            spread_points=market.spread_points,
            bid=quote.bid if quote.valid else None,  # the shadow trades enter at this quote (§A27)
            ask=quote.ask if quote.valid else None,
            quote_at=quote.time_utc if quote.valid else None,
            requirements_version=plan.version,
            calibration_version=self.calibration_version(),  # the model its win probability is read from
            features=signal_features(signal, market),
            signal=signal.to_dict(),
        )
