"""The engine runtime: one loop that monitors, decides and manages (PLAN §A2, §A19; TAA-601).

**Modes:** Milestone 1 runs **PAPER only**: market data from the read-only MT5 gateway, fills on the simulated
broker. BACKTEST runs through ``app.cli backtest``; DEMO and LIVE (broker orders) are Milestone 2 and refused
here.

**Schedule** (each step is skipped until it is due; one cycle every ``engine.monitor_interval_seconds``):

- every cycle: kill switch, connection (reconnect with backoff), and per symbol a quote → breakers
  (invalid price, spread, staleness) → paper fills → position management;
- every ``candle_poll_seconds``: a newly closed entry bar per symbol (persisted watermark) → context →
  strategies → arbitration → decision → paper order;
- every ``health_interval_seconds``: loss tracking and loss breakers, time-based breaker resets, storage and
  disk checks, persisted marks;
- every ``clock_verify_minutes``: server-time verification (an idle market gives no verdict; a mismatch trips
  CLOCK).

A failure inside a cycle is logged with its traceback, trips UNHANDLED_EXCEPTION (which blocks entries) and is
announced; the loop keeps monitoring and managing positions. :meth:`Engine.stop` ends the loop after the
current cycle and shuts down cleanly.
"""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.advisory.lifecycle import OpportunityLifecycle
from app.advisory.ranking_service import RankingService
from app.advisory.requirements import ComputeRequirements, local_requirements
from app.advisory.scanner import OpportunityScanner
from app.advisory.universe import SymbolCatalog
from app.broker.execution import ExecutionGateway
from app.broker.factory import BrokerBundle
from app.broker.models import BrokerPosition
from app.config import Settings
from app.core.clock import Clock, ClockStatus, ClockVerification, ensure_utc
from app.core.enums import Side, TradingMode
from app.core.errors import SafetyViolation, SymbolUnavailable, TaaError
from app.core.ids import new_id, stable_hash
from app.engine.backends import Backend, DemoBackend, PaperBackend
from app.engine.broker_positions import BrokerPositionManager
from app.engine.decision_engine import (
    AccountState,
    Decision,
    DecisionEngine,
    DecisionRequest,
    DecisionStore,
    SystemHealth,
)
from app.engine.order_manager import OrderManager
from app.engine.paper import LiveRates, PaperExecution
from app.engine.position_manager import PositionManager
from app.engine.reconciler import Reconciler
from app.evidence.catalog import default_registry as evidence_registry
from app.evidence.registry import EvidenceEngine
from app.market_data.candle_service import CandleService, CandleWatermarks
from app.market_data.data_models import SymbolSpec
from app.market_data.quote_service import QuoteService
from app.market_data.server_time import verify_server_time_any
from app.market_data.trading_sessions import TradingSessions
from app.monitoring.alerts import EventBus, EventType
from app.monitoring.health_check import write_heartbeat
from app.news.calendar import ManualBlackouts, NewsFilter
from app.risk.breaker_monitor import BreakerMonitor
from app.risk.circuit_breaker import BreakerBoard, default_specs
from app.risk.exposure_manager import MAGIC_RANGE
from app.risk.kill_switch import KillSwitch
from app.risk.loss_tracker import LossStatus, LossTracker
from app.risk.mode_gates import GateResult, evaluate_gate
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.repositories import EngineStateRepository, RunRepository
from app.strategy.arbitration import SignalArbiter
from app.strategy.catalog import default_registry
from app.strategy.context_builder import ContextBuilder
from app.strategy.setups import EvidenceSetup

log = logging.getLogger(__name__)


@dataclass
class _Due:
    """A periodic task's next due time (monotonic seconds)."""

    every: float
    next_at: float = 0.0

    def due(self, now: float) -> bool:
        if now >= self.next_at:
            self.next_at = now + self.every
            return True
        return False


class Engine:
    def __init__(
        self,
        settings: Settings,
        bundle: BrokerBundle,
        db: Database,
        clock: Clock,
        *,
        bus: EventBus,
        sleep: Callable[[float], None] = time.sleep,
        process: str = "engine",
    ) -> None:
        if settings.mode is TradingMode.DEMO:
            if not (settings.env.ENABLE_DEMO_TRADING and bundle.client.allow_trading):
                raise SafetyViolation(
                    "DEMO needs ENABLE_DEMO_TRADING=true and a trading client (build_trading)"
                )
        elif settings.mode is not TradingMode.PAPER:
            raise SafetyViolation(
                f"the engine runs PAPER or DEMO (TRADING_MODE={settings.mode.value}); LIVE waits for "
                "Phase 14 and backtests run with `python -m app.cli backtest`"
            )
        self.settings = settings
        self.config = settings.config
        self.bundle = bundle
        self.gateway = bundle.gateway
        self.db = db
        self.clock = clock
        self.bus = bus
        self.sleep = sleep
        self.process = process
        self.run_id = new_id()
        self.running = False
        self.cycles = 0
        self.symbols: dict[str, SymbolSpec] = {}
        self.last_error: str = ""
        self._clock_ok = False
        self._kill_active = False
        self._connected = True
        self._atr: dict[str, float] = {}
        self._last_entry: dict[str, datetime] = {}
        self._booked_deals = 0
        self.ranking: RankingService | None = None
        self.scanner: OpportunityScanner | None = None
        self.lifecycle: OpportunityLifecycle | None = None
        self._requirements_cache: tuple[datetime | None, ComputeRequirements] | None = None
        loop = self.config.engine
        self._candles_due = _Due(loop.candle_poll_seconds)
        self._health_due = _Due(loop.health_interval_seconds)
        self._clock_due = _Due(loop.clock_verify_minutes * 60)
        self.audit = AuditLog(db, f"engine:{settings.env.ENGINE_ID or 'local'}", clock)
        self.heartbeat_path = settings.path(loop.heartbeat_file)
        self.runs = RunRepository(db, clock)

    # --- startup ----------------------------------------------------------------------------------------

    def start(self) -> None:
        cfg, env = self.config, self.settings.env
        report = self.bundle.client.connect()
        account = report.account
        self.account_key = stable_hash(account.login, account.server, length=16)
        self._verify_clock(initial=True)
        for symbol in cfg.symbols.allowed:
            try:
                self.symbols[symbol] = self.gateway.symbol_spec(symbol)
            except SymbolUnavailable as exc:
                log.error("symbol %s is unavailable and will not be traded: %s", symbol, exc)
        if not self.symbols:
            raise SymbolUnavailable("none of symbols.allowed is available on this server")
        self.board = BreakerBoard(
            self.db,
            default_specs(
                cfg.breakers,
                consecutive_pause_hours=cfg.risk.consecutive_loss_pause_hours,
                symbol_pause_minutes=cfg.execution.symbol_pause_minutes,
            ),
            self.clock,
            mode=self.settings.mode,
            tz_name=env.BROKER_TIMEZONE,
            audit=self.audit,
            notify=self.bus.breaker_notifier(),
        )
        self.monitor = BreakerMonitor(self.board, cfg.breakers, cfg.risk, self.clock)
        self.kill_switch = KillSwitch(
            self.settings.path(env.KILL_SWITCH_FILE),
            self.db,
            self.audit,
            self.clock,
            flatten_allowed=env.KILL_SWITCH_FLATTEN_ALLOWED,
        )
        self.losses = LossTracker(self.db, self.account_key, env.BROKER_TIMEZONE, self.clock)
        self.watermarks = CandleWatermarks(self.db, self.clock)
        self.candles = CandleService(self.gateway, cfg.timeframes, self.clock)
        self.quotes = QuoteService(self.gateway, self.clock, cfg.timeframes.stale_tick_seconds)
        self.strategies = default_registry().from_config(
            cfg.strategies, cfg.timeframes, cfg.evidence.confluence
        )
        self.magic = {s.name: env.MAGIC_NUMBER_BASE + i for i, s in enumerate(self.strategies.strategies)}
        self.arbiter = SignalArbiter(cfg.strategies.cooldown_bars)
        needs_evidence = any(isinstance(s, EvidenceSetup) for s in self.strategies.strategies)
        evidence = None
        if needs_evidence or cfg.evidence.default_enabled:
            registry = evidence_registry()
            evidence = EvidenceEngine(registry, registry.plan_from_config(cfg.evidence))
        self.builder = ContextBuilder(self.candles, cfg, self.clock, self.quotes, evidence)
        self.sessions = TradingSessions(cfg.sessions, cfg.symbols)
        self.news = NewsFilter(ManualBlackouts(cfg.sessions.news_blackouts))
        self.decisions = DecisionEngine(
            cfg,
            self.settings.mode,
            self.gateway,  # broker-computed P/L and margin for sizing
            self.clock,
            sessions=self.sessions,
            news=self.news,
            magic_base=env.MAGIC_NUMBER_BASE,
            config_hash=self.settings.config_hash,
            breakers=self.board,
            store=DecisionStore(self.db),
        )
        if cfg.advisory.ranking.enabled:  # advice about the broker account; never changes what the bot trades
            catalog = SymbolCatalog(
                self.db, self.gateway, cfg.advisory.universe, self.clock, server=account.server
            )
            self.ranking = RankingService(
                self.db, self.gateway, catalog, cfg, self.clock, server=account.server
            )
        if cfg.advisory.scanner.enabled:
            self.requirements()  # invalid advisory preferences fail at startup (ConfigError)
            self.scanner = OpportunityScanner(
                self.db,
                self.gateway,
                cfg,
                self.clock,
                decisions=self.decisions,
                requirements=self.requirements,
                server=account.server,
                health=self.health_snapshot,
                loss=self._loss_status,
                gate=self.gate,
            )
            self.lifecycle = OpportunityLifecycle(
                self.db,
                self.gateway,
                cfg,
                self.clock,
                server=account.server,
                lifetime_bars=lambda: self.requirements().lifetime_bars,
                news=self.news,
            )
            expired = self.lifecycle.catch_up()
            if expired:
                log.info("expired %d opportunity windows that passed while the engine was down", len(expired))
        by_magic = {self.magic[s.name]: s for s in self.strategies.strategies}
        restored = self._build_backend(account, by_magic)
        self.on_started(restored)
        self.runs.start(self.run_id, self.process, self.settings.mode.value, self.settings.config_hash)
        self.runs.save_config_snapshot(self.settings.config_hash, self.settings.summary())
        self.audit.append(
            "ENGINE_START",
            self.process,
            {"run_id": self.run_id, "mode": self.settings.mode.value, "symbols": sorted(self.symbols)},
        )
        self.bus.emit(
            EventType.ENGINE_STARTED,
            mode=self.settings.mode.value,
            symbols=sorted(self.symbols),
            strategies=self.strategies.names,
            restored_positions=restored,
        )
        self.running = True

    def _build_backend(self, account: Any, by_magic: dict[int, Any]) -> int:
        """PAPER: the persisted paper book. DEMO: orders, reconciliation and management on the demo
        account."""
        cfg, env = self.config, self.settings.env
        if self.settings.mode is TradingMode.PAPER:
            self.paper = PaperExecution(
                self.db,
                self.account_key,
                self.symbols,
                LiveRates(self.gateway, account.currency),
                self.clock,
                paper=cfg.paper,
                backtest=cfg.backtest,
                account_currency=account.currency,
                leverage=float(account.leverage or cfg.backtest.leverage),
                starting_equity=account.equity,
                bus=self.bus,
            )
            restored = self.paper.restore()
            self.positions = PositionManager(
                self.paper,
                cfg.position_management,
                self.symbols,
                self.clock,
                strategies_by_magic=by_magic,
                bus=self.bus,
            )
            self.backend: Backend = PaperBackend(self.paper, self.positions, self.gateway)
            return restored
        deviation = cfg.execution.deviation_points
        self.orders = OrderManager(
            self.db,
            ExecutionGateway(self.bundle.client),
            self.gateway,
            self.monitor,
            self.kill_switch,
            self.clock,
            cfg.execution,
            deviation_points=int(cfg.risk.max_slippage_points if deviation is None else deviation),
            presend=self._presend,
            bus=self.bus,
        )
        self.reconciler = Reconciler(
            self.db,
            self.orders,
            self.gateway,
            self.monitor,
            self.clock,
            cfg.execution,
            self.symbols,
            magic_base=env.MAGIC_NUMBER_BASE,
            bus=self.bus,
        )
        self.broker_positions = BrokerPositionManager(
            self.orders,
            cfg.position_management,
            self.symbols,
            self.clock,
            entry_timeframe=cfg.timeframes.entry,
            magic_base=env.MAGIC_NUMBER_BASE,
            strategies_by_magic=by_magic,
            flatten_allowed=env.KILL_SWITCH_FLATTEN_ALLOWED,
            bus=self.bus,
        )
        self.backend = DemoBackend(
            self.orders, self.reconciler, self.broker_positions, self.gateway, self.kill_switch, self.clock
        )
        report = self.reconciler.run()
        log.warning("DEMO mode: broker orders go to the demo account (%s)", report)
        return len(self.broker_positions.bot_positions())

    def gate(self) -> GateResult | None:
        """The DEMO gate (PLAN §A3), evaluated on fresh account and terminal snapshots."""
        if self.settings.mode is not TradingMode.DEMO:
            return None
        try:
            account, terminal = self.gateway.account(), self.gateway.terminal()
        except TaaError:
            account, terminal = None, None
        latched = [s.name.value for s in self.board.statuses() if s.latched]
        return evaluate_gate(
            self.settings.mode,
            self.settings.env,
            account=account,
            terminal=terminal,
            risk_config_ok=True,  # settings were validated at startup
            kill_switch_active=self.kill_switch.is_active(),
            latched_breakers=latched,
        )

    def _presend(self, symbol: str, side: Side, price: float, expires_at: datetime) -> list[str]:
        """Time-of-use checks right before ``order_send`` (PLAN §A12 write-ahead)."""
        problems = []
        gate = self.gate()
        if gate is not None and not gate.passed:
            problems.append("gate: " + ", ".join(sorted(c.value for c in gate.failed_conditions)))
        if self.kill_switch.is_active():
            problems.append("kill switch active")
        blocking = self.board.blocking(symbol)
        if blocking:
            problems.append("breakers: " + ", ".join(b.name.value for b in blocking))
        if not self.bundle.client.is_healthy():
            problems.append("terminal not connected")
        quote = self.quotes.quote(self.symbols[symbol])
        if not quote.valid:
            problems.append(f"quote: {quote.problem}")
        elif quote.spread_points > self.config.spread_limit(symbol):
            problems.append(f"spread {quote.spread_points:g} > {self.config.spread_limit(symbol):g}")
        if self.clock.now_utc() >= expires_at:
            problems.append("signal expired")
        return problems

    def on_started(self, restored_positions: int) -> None:
        """Startup reconciliation (TAA-604).

        - Arbiter cooldowns and the last entry per symbol come back from ``engine_state``; watermarks and
          breakers are persisted by their own services, and the paper book by :meth:`PaperExecution.restore`.
        - A real account position carrying the bot's magic cannot exist in Milestone 1 (no broker orders):
          it trips ACCOUNT_CHANGE and raises a CRITICAL event.
        """
        self.state = EngineStateRepository(self.db, self.clock)
        cooldowns = self.state.load("arbiter_cooldowns") or {}
        self.arbiter.restore_cooldowns({k: str(v) for k, v in cooldowns.items()})
        entries = self.state.load("last_entry") or {}
        self._last_entry = {sym: ensure_utc(datetime.fromisoformat(str(at))) for sym, at in entries.items()}
        base = self.settings.env.MAGIC_NUMBER_BASE
        try:
            real = self.gateway.positions()
        except TaaError:
            log.warning("could not read account positions during reconciliation")
            real = []
        for pos in real:
            # in PAPER no broker order is ever sent, so a bot-magic position is an anomaly; in DEMO the
            # reconciler has already matched positions to intents
            if self.settings.mode is TradingMode.PAPER and base <= pos.magic < base + MAGIC_RANGE:
                detail = f"position #{pos.ticket} {pos.symbol} carries the bot's magic {pos.magic}"
                self.monitor.account_changed(detail)
                self.bus.emit(
                    EventType.UNKNOWN_POSITION, symbol=pos.symbol, ticket=pos.ticket, magic=pos.magic
                )
        log.info(
            "reconciled (%s): %d bot position(s), %d real position(s), %d cooldown(s)",
            self.backend.name,
            restored_positions,
            len(real),
            len(cooldowns),
        )

    # --- loop -------------------------------------------------------------------------------------------

    def run(self, max_cycles: int | None = None) -> None:
        interval = self.config.engine.monitor_interval_seconds
        try:
            while self.running and (max_cycles is None or self.cycles < max_cycles):
                self.cycle()
                self.sleep(interval)
        finally:
            self.shutdown()

    def stop(self) -> None:
        self.running = False

    def cycle(self) -> None:
        self.cycles += 1
        now = self.clock.monotonic()
        try:
            self._check_kill_switch()
            connected = self.bundle.client.ensure_connected()
            self._connection_changed(connected)
            self.monitor.observe_connection(connected)
            if connected:
                for symbol in self.symbols:
                    self._monitor_symbol(symbol)
                if self._candles_due.due(now):
                    for symbol in self.symbols:
                        self._check_new_bar(symbol)
            if self._health_due.due(now):
                self._health()
            if connected and self._clock_due.due(now):
                self._verify_clock()
            if connected and self.ranking is not None:
                self._advisory(self.ranking)
            if connected and self.scanner is not None:
                self._scan(self.scanner)
        except Exception as exc:  # process boundary: keep monitoring, block entries, tell the operator
            log.exception("engine cycle %s failed", self.cycles)
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.monitor.record_exception("cycle", exc)
            self.bus.emit(
                EventType.ENGINE_ERROR, error=self.last_error, dedupe_key=f"error:{type(exc).__name__}"
            )

    # --- steps ------------------------------------------------------------------------------------------

    def _advisory(self, ranking: RankingService) -> None:
        try:
            ranking.tick()
        except Exception as exc:  # advisory boundary: a ranking failure never touches trading
            log.exception("advisory ranking failed")
            ranking.stats.failures += 1
            ranking.stats.last_error = f"{type(exc).__name__}: {exc}"

    def _scan(self, scanner: OpportunityScanner) -> None:
        try:
            scanner.tick()
            if self.lifecycle is not None:
                self.lifecycle.tick()
        except Exception as exc:  # advisory boundary: a scanner failure never touches trading
            log.exception("opportunity scanner failed")
            scanner.stats.failures += 1
            scanner.stats.last_error = f"{type(exc).__name__}: {exc}"

    def requirements(self) -> ComputeRequirements:
        """What the scanner computes: from the local preferences until the cloud sends them (Phase 7).

        Recomputed when a new ranking arrives (its top N is part of the monitored set)."""
        run = None if self.ranking is None else self.ranking.last_run
        key = None if run is None else run.computed_at
        if self._requirements_cache is None or self._requirements_cache[0] != key:
            ranked = [] if run is None else [r.symbol for r in run.ranked if r.eligible]
            universe = [] if self.ranking is None else [e.symbol for e in self.ranking.universe]
            req = local_requirements(
                self.config,
                ranked=ranked,
                evidence=evidence_registry(),
                strategies=default_registry(),
                available=universe or None,
            )
            self._requirements_cache = (key, req)
        return self._requirements_cache[1]

    def request_rescan(self) -> bool:
        """The RESCAN_SUITABILITY command: the next cycle refreshes every symbol's ranking metrics."""
        if self.ranking is None:
            return False
        self.ranking.request_rescan()
        return True

    def _check_kill_switch(self) -> None:
        active = self.kill_switch.is_active()
        if active != self._kill_active:
            self._kill_active = active
            self.bus.emit(EventType.KILL_SWITCH_ACTIVATED if active else EventType.KILL_SWITCH_RELEASED)

    def _connection_changed(self, connected: bool) -> None:
        if connected != self._connected:
            self._connected = connected
            self.bus.emit(
                EventType.CONNECTION_RESTORED if connected else EventType.CONNECTION_LOST,
                dedupe_key="connection",
            )

    def _monitor_symbol(self, symbol: str) -> None:
        spec = self.symbols[symbol]
        quote = self.quotes.quote(spec)
        now = self.clock.now_utc()
        atr = self._atr.get(symbol)
        if not quote.valid and quote.problem == "no tick available":
            return
        self.monitor.observe_quote(
            symbol,
            bid=quote.bid,
            ask=quote.ask,
            spread_points=quote.spread_points,
            spread_limit=self.config.spread_limit(symbol),
            tick_age_seconds=quote.age_seconds,
            in_session=self.sessions.check(symbol, now).is_open,
            previous_mid=None,
            atr=atr,
            median_spread=self.quotes.median_spread(symbol),
        )
        if quote.valid:
            self.backend.on_quote(symbol, quote.bid, quote.ask, atr, now)

    def _check_new_bar(self, symbol: str) -> None:
        tf = self.config.timeframes.entry
        frame = self.candles.closed_candles(symbol, tf, 2)
        opened = frame.last_open_time
        if opened is None or not self.watermarks.is_new(symbol, tf, opened):
            return
        try:
            self._evaluate(symbol)
        finally:
            # a bar is evaluated at most once, even when the evaluation failed (fail closed: no retry storm)
            self.watermarks.mark(symbol, tf, opened)

    def _evaluate(self, symbol: str) -> None:
        spec = self.symbols[symbol]
        try:
            ctx = self.builder.build(symbol, spec)
        except TaaError as exc:
            log.warning("no context for %s: %s", symbol, exc)
            return
        if ctx.market.atr is not None:
            self._atr[symbol] = ctx.market.atr
        self.backend.on_bar(symbol, ctx)
        signals = self.strategies.evaluate(ctx)
        selected = self.arbiter.arbitrate(signals).selected
        self.on_arbitrated()
        if selected is None:
            return
        record = self.decisions.decide(
            DecisionRequest(
                signal=selected,
                market=ctx.market,
                spec=spec,
                quote=self.quotes.quote(spec),
                account=AccountState(self.backend.funds(), self._book(), self._loss_status()),
                health=self.health_snapshot(),
                specs=self.symbols,
                gate=self.gate(),
                last_entry_at=self._last_entry.get(symbol),
            )
        )
        if record.decision is Decision.ACCEPT:
            magic = self.magic.get(selected.strategy, self.settings.env.MAGIC_NUMBER_BASE)
            if self.backend.place(record, spec, magic):
                self._last_entry[symbol] = ctx.decision_time_utc
                self.on_entry(symbol, ctx.decision_time_utc)
                self.bus.emit(
                    EventType.SIGNAL_ACCEPTED,
                    symbol=symbol,
                    strategy=selected.strategy,
                    side=selected.action.value,
                    volume=str(record.volume),
                    decision_id=record.decision_id,
                    paper=self.settings.mode is TradingMode.PAPER,
                )

    def on_arbitrated(self) -> None:
        self.state.save("arbiter_cooldowns", self.arbiter.cooldown_state())

    def on_entry(self, symbol: str, at: datetime) -> None:
        self.state.save("last_entry", {sym: t.isoformat() for sym, t in self._last_entry.items()})

    def _book(self) -> list[BrokerPosition]:
        try:
            return self.backend.book()
        except TaaError:
            log.warning("could not read positions for exposure")
            return []

    def _loss_status(self) -> LossStatus:
        magics = set(self.magic.values())
        return self.losses.observe(
            self.backend.equity(), self.backend.new_deals(), is_bot=lambda d: d.magic in magics
        )

    def _health(self) -> None:
        status = self._loss_status()
        self.monitor.observe_losses(status)
        self.board.tick()
        write_ok = self.db.healthcheck()
        data_dir = self.settings.path("data")
        free_gb = shutil.disk_usage(data_dir).free / 1e9 if data_dir.exists() else None
        self.monitor.observe_storage(write_ok, free_gb)
        self.backend.maintain()
        self.heartbeat()

    def heartbeat(self, state: str = "running") -> None:
        write_heartbeat(self.heartbeat_path, self.clock.now_utc(), self.status(), state=state)

    def _verify_clock(self, *, initial: bool = False) -> None:
        cfg = self.config
        symbol, result = verify_server_time_any(
            self.gateway, cfg.symbols.clock_symbols, wait_seconds=10.0 if initial else 5.0, sleep=self.sleep
        )
        self._apply_clock(result, symbol)

    def _apply_clock(self, result: ClockVerification, symbol: str | None) -> None:
        if result.status is ClockStatus.UNVERIFIED_MARKET_IDLE:
            log.info("server time not verifiable now (idle markets); keeping the previous state")
            return  # no verdict: the previous verification stands, and without one entries stay blocked
        self._clock_ok = result.ok
        if hasattr(self, "monitor"):
            self.monitor.observe_clock(result.ok, result.detail)
        if not result.ok:
            self.bus.emit(EventType.CLOCK_UNVERIFIED, detail=result.detail, symbol=symbol, dedupe_key="clock")

    def health_snapshot(self) -> SystemHealth:
        return SystemHealth(
            kill_switch_active=self._kill_active,
            broker_healthy=self._connected,
            storage_healthy=True,
            clock_verified=self._clock_ok,
        )

    def status(self) -> dict[str, Any]:
        """For the health endpoint and the heartbeat (TAA-605)."""
        backend = getattr(self, "backend", None)
        try:
            funds = None if backend is None else backend.funds()
        except TaaError:
            funds = None
        return {
            "run_id": self.run_id,
            "mode": self.settings.mode.value,
            "running": self.running,
            "cycles": self.cycles,
            "connected": self._connected,
            "clock_verified": self._clock_ok,
            "kill_switch": self._kill_active,
            "symbols": sorted(self.symbols),
            "backend": None if backend is None else backend.name,
            "open_positions": 0 if backend is None else backend.open_positions(),
            "equity": None if funds is None else round(funds.equity, 2),
            "breakers": [
                {"name": s.name.value, "scope": s.scope_key, "state": s.state.value}
                for s in (self.board.blocking() if hasattr(self, "board") else [])
            ],
            "last_error": self.last_error,
            "scanner": None
            if self.scanner is None
            else {
                "bars": self.scanner.stats.bars,
                "opportunities": self.scanner.stats.opportunities,
                "hidden": self.scanner.stats.hidden,
                "pending": len(self.scanner.pending),
                "failures": self.scanner.stats.failures,
                "last_duration_ms": round(self.scanner.stats.last_duration_ms),
                "last_error": self.scanner.stats.last_error,
            },
            "ranking": None
            if self.ranking is None
            else {
                "runs": self.ranking.stats.runs,
                "symbols": len(self.ranking.cache),
                "refreshed": self.ranking.stats.refreshed,
                "failures": self.ranking.stats.failures,
                "last_duration_ms": round(self.ranking.stats.last_duration_ms),
                "last_error": self.ranking.stats.last_error,
            },
        }

    # --- shutdown ---------------------------------------------------------------------------------------

    def shutdown(self) -> None:
        self.running = False
        try:
            if hasattr(self, "backend") and isinstance(self.backend, PaperBackend):
                self.backend.maintain()
            self.heartbeat("stopped")  # a deliberate stop: the watchdog does not restart it
            self.runs.finish(self.run_id, "STOPPED", self.last_error)
            self.audit.append("ENGINE_STOP", self.process, {"run_id": self.run_id, "cycles": self.cycles})
            self.bus.emit(EventType.ENGINE_STOPPED, cycles=self.cycles)
        finally:
            self.bundle.client.shutdown()
