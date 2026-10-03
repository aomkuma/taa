"""Ranking service (PLAN §A25 scheduling and persistence; TAA-6A5).

Runs inside the engine process and never affects trading. :meth:`RankingService.tick` is called every engine
cycle and does at most three things:

1. **Structural refresh** every ``structural_hours`` or when equity has moved by ``equity_change_percent``
   since the last one: the symbol catalog is refreshed (daily by itself) and every symbol's metrics are marked
   stale.
2. **Dynamic refresh:** up to ``batch_size`` stale symbols (never refreshed, or older than
   ``dynamic_minutes``) get new metrics, round-robin, so terminal load stays bounded: H1 candles (ATR, ATR
   percentile, ADX regime, median spread, liquidity profile, closes for correlations), the current tick and
   the broker facts of :func:`~app.advisory.suitability.collect_facts`.
3. **Now score** every ``now_seconds`` from the cached metrics only: the account snapshot, gates, scores,
   correlations against open positions and the ranking, written to ``suitability_snapshots``.

:meth:`RankingService.request_rescan` (the RESCAN command) makes the next tick refresh every symbol at once.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy import delete, func, select

from app.advisory.correlations import return_correlations
from app.advisory.market_sessions import (
    LiquidityProfile,
    SessionStatus,
    describe_hour,
    session_state,
    sessions_for,
)
from app.advisory.scoring import Candidate, DynamicMetrics, EdgeEstimate, RankedSymbol, rank
from app.advisory.suitability import GateStatus, SymbolFacts, assess, collect_facts
from app.advisory.universe import CatalogEntry, SymbolCatalog
from app.broker.gateway import MarketDataGateway
from app.config import AppConfig
from app.core.clock import Clock, ensure_utc
from app.core.enums import Regime, Timeframe
from app.core.errors import TaaError
from app.indicators.trend import adx
from app.indicators.volatility import atr, atr_percentile
from app.market_data.candle_service import CandleService
from app.risk.position_sizer import AccountFunds
from app.storage.database import Database
from app.storage.models import SuitabilitySnapshotRow
from app.strategy.regime_detector import classify_regime

log = logging.getLogger(__name__)

SPREAD_BARS = 100  # median spread over the last 100 bars


@dataclass(frozen=True, slots=True)
class SymbolMetrics:
    entry: CatalogEntry
    facts: SymbolFacts
    sessions: tuple[str, ...]
    profile: LiquidityProfile
    atr_percentile: float | None
    regime: Regime | None
    closes: pd.Series
    refreshed_at: datetime


@dataclass(frozen=True, slots=True)
class RankingRun:
    computed_at: datetime
    ranked: list[RankedSymbol]
    sessions: dict[str, SessionStatus]
    best_hours: dict[str, list[int]]
    universe: int
    duration_ms: float
    currency: str


@dataclass(slots=True)
class RankingStats:
    runs: int = 0
    refreshed: int = 0
    failures: int = 0
    structural: int = 0
    last_duration_ms: float = 0.0
    last_error: str = ""


def _last(series: pd.Series) -> float | None:
    clean = series.dropna()
    if clean.empty:
        return None
    value = float(clean.iloc[-1])
    return value if math.isfinite(value) else None


class RankingService:
    def __init__(
        self,
        db: Database,
        gateway: MarketDataGateway,
        catalog: SymbolCatalog,
        config: AppConfig,
        clock: Clock,
        *,
        server: str,
        edge_source: Callable[[str], EdgeEstimate | None] | None = None,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.catalog = catalog
        self.config = config
        self.advisory = config.advisory
        self.clock = clock
        self.server = server
        self.edge_source = edge_source
        self.candles = CandleService(gateway, config.timeframes, clock)
        self.cache: dict[str, SymbolMetrics] = {}
        self.universe: list[CatalogEntry] = []
        self.stats = RankingStats()
        self.last_run: RankingRun | None = None
        self._rescan = False
        self._structural_at: datetime | None = None
        self._structural_equity: float | None = None
        self._last_now: datetime | None = None
        self._last_purge: datetime | None = None
        self._correlations: pd.DataFrame | None = None
        self._correlations_dirty = True

    # --- scheduling -----------------------------------------------------------------------------------------

    def request_rescan(self) -> None:
        """RESCAN: the next tick refreshes every symbol and ranks immediately."""
        self._rescan = True

    def structural_due(self, now: datetime, equity: float) -> bool:
        cfg = self.advisory.ranking
        if self._structural_at is None or now - self._structural_at >= timedelta(hours=cfg.structural_hours):
            return True
        base = self._structural_equity
        return bool(base and abs(equity - base) / base * 100 >= cfg.equity_change_percent)

    def tick(self) -> RankingRun | None:
        now = self.clock.now_utc()
        account = self.gateway.account()
        rescan = self._rescan
        if rescan or self.structural_due(now, account.equity):
            self._structural(now, account.equity, force_catalog=rescan)
        stale = [e for e in self.universe if self._stale(e.symbol, now)]
        for entry in stale if rescan else stale[: self.advisory.ranking.batch_size]:
            self.refresh(entry, now)
        self._rescan = False
        due = self._last_now is None or now - self._last_now >= timedelta(
            seconds=self.advisory.ranking.now_seconds
        )
        return self.rank_now(now) if rescan or due else None

    def rescan(self) -> RankingRun:
        self.request_rescan()
        run = self.tick()
        if run is None:  # a rescan always ranks
            raise RuntimeError("rescan produced no ranking")
        return run

    def _stale(self, symbol: str, now: datetime) -> bool:
        cached = self.cache.get(symbol)
        horizon = timedelta(minutes=self.advisory.ranking.dynamic_minutes)
        return cached is None or now - cached.refreshed_at >= horizon

    def _structural(self, now: datetime, equity: float, *, force_catalog: bool) -> None:
        self.universe = self.catalog.refresh(force=force_catalog)
        self.universe = [e for e in self.universe if e.enabled]
        names = {e.symbol for e in self.universe}
        # metrics stay usable until refreshed; marking them stale puts every symbol back in the round-robin
        self.cache = {
            s: replace(m, refreshed_at=datetime.min.replace(tzinfo=now.tzinfo))
            for s, m in self.cache.items()
            if s in names
        }
        self._structural_at = now
        self._structural_equity = equity
        self._correlations_dirty = True
        self.stats.structural += 1
        log.info("ranking: structural refresh of %d symbols (equity %.2f)", len(self.universe), equity)

    # --- per-symbol metrics ---------------------------------------------------------------------------------

    def refresh(self, entry: CatalogEntry, now: datetime) -> SymbolMetrics | None:
        symbol = entry.symbol
        try:
            metrics = self._collect(entry, now)
        except (TaaError, KeyError, ValueError) as exc:
            self.stats.failures += 1
            self.stats.last_error = f"{symbol}: {exc}"
            log.warning("ranking: metrics for %s failed: %s", symbol, exc)
            stale = self.cache.get(symbol)
            if stale is not None:  # retry after the dynamic horizon, not every minute
                self.cache[symbol] = replace(stale, refreshed_at=now)
            return None
        self.cache[symbol] = metrics
        self.stats.refreshed += 1
        self._correlations_dirty = True
        return metrics

    def _collect(self, entry: CatalogEntry, now: datetime) -> SymbolMetrics:
        cfg = self.advisory
        spec = entry.spec
        bars = max(cfg.scoring.correlation_bars, cfg.suitability.min_candles)
        h1 = self.candles.closed_candles(spec.name, Timeframe.H1, bars, expect_live=False).df
        frame = h1
        if cfg.suitability.atr_timeframe is not Timeframe.H1:
            frame = self.candles.closed_candles(
                spec.name, cfg.suitability.atr_timeframe, bars, expect_live=False
            ).df
        atr_series = atr(frame["high"], frame["low"], frame["close"], cfg.suitability.atr_period)
        atr_now = _last(atr_series)
        pct = _last(atr_percentile(atr_series)) if atr_now is not None else None
        adx_now = _last(adx(frame["high"], frame["low"], frame["close"])["adx"]) if len(frame) else None
        regime = classify_regime(adx_now, pct, self.config.regime) if adx_now is not None else None
        spreads = frame["spread"].tail(SPREAD_BARS)
        median_spread = float(spreads.median()) * spec.point if len(spreads) else None
        sessions = sessions_for(spec.name, entry.asset_class, spec.currency_profit, cfg.sessions.overrides)
        facts = collect_facts(
            spec,
            entry.asset_class,
            self.gateway,
            cfg.suitability,
            tick=self.gateway.tick(spec.name),
            atr=atr_now,
            candles=len(frame),
            now=now,
            market_open=session_state(sessions, now).open,
            median_spread=median_spread,
        )
        closes = pd.Series(h1["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(h1["open_time"]))
        return SymbolMetrics(
            entry=entry,
            facts=facts,
            sessions=sessions,
            profile=LiquidityProfile.from_h1(h1),
            atr_percentile=pct,
            regime=regime,
            closes=closes,
            refreshed_at=now,
        )

    # --- Now score ------------------------------------------------------------------------------------------

    def correlations(self) -> pd.DataFrame | None:
        if self._correlations_dirty:
            closes = {s: m.closes for s, m in self.cache.items()}
            self._correlations = return_correlations(closes, self.advisory.scoring.correlation_min_overlap)
            self._correlations_dirty = False
        return self._correlations

    def rank_now(self, now: datetime | None = None) -> RankingRun:
        started = time.perf_counter()
        now = now or self.clock.now_utc()
        account = self.gateway.account()
        funds = AccountFunds(account.equity, account.balance, account.margin, account.margin_free)
        exposure = sorted({p.symbol for p in self.gateway.positions()})
        names = {e.symbol for e in self.universe}
        candidates: list[Candidate] = []
        sessions: dict[str, SessionStatus] = {}
        for symbol, m in sorted(self.cache.items()):
            if symbol not in names:
                continue
            state = session_state(m.sessions, now)
            sessions[symbol] = state
            facts = replace(m.facts, market_open=state.open)
            suitability = assess(
                facts,
                funds,
                self.config.risk,
                self.advisory.suitability,
                currency=account.currency,
            )
            metrics = DynamicMetrics(
                liquidity_ratio=m.profile.ratio_now(now),
                atr_percentile=m.atr_percentile,
                regime=m.regime,
                edge=self.edge_source(symbol) if self.edge_source else None,
            )
            candidates.append(Candidate(facts, suitability, metrics))
        ranked = rank(
            candidates,
            self.advisory.scoring,
            self.config.risk,
            correlations=self.correlations(),
            exposure=exposure,
        )
        run = RankingRun(
            computed_at=now,
            ranked=ranked,
            sessions=sessions,
            best_hours={s: self.cache[s].profile.best_hours() for s in sessions},
            universe=len(self.universe),
            duration_ms=(time.perf_counter() - started) * 1000,
            currency=account.currency,
        )
        self._persist(run)
        self._last_now = now
        self.last_run = run
        self.stats.runs += 1
        self.stats.last_duration_ms = run.duration_ms
        eligible = sum(r.eligible for r in ranked)
        top = ", ".join(f"{r.symbol} {r.now:.0f}" for r in ranked[:3] if r.eligible)
        log.info(
            "ranking: %d ranked of %d, %d eligible, %.0f ms; top: %s",
            len(ranked),
            run.universe,
            eligible,
            run.duration_ms,
            top or "-",
        )
        return run

    # --- persistence ----------------------------------------------------------------------------------------

    def _persist(self, run: RankingRun) -> None:
        hour = run.computed_at.replace(minute=0, second=0, microsecond=0)
        with self.db.session() as sess:
            existing = {
                row.symbol: row
                for row in sess.execute(
                    select(SuitabilitySnapshotRow).where(
                        SuitabilitySnapshotRow.server == self.server, SuitabilitySnapshotRow.hour == hour
                    )
                ).scalars()
            }
            for r in run.ranked:
                row = existing.get(r.symbol)
                if row is None:
                    row = SuitabilitySnapshotRow(server=self.server, symbol=r.symbol, hour=hour)
                    sess.add(row)
                row.computed_at = run.computed_at
                row.asset_class = r.suitability.asset_class.value
                row.rank = r.rank
                row.eligible = r.eligible
                row.overall = r.overall
                row.now_score = r.now
                row.failed_gates = [g.value for g in r.suitability.failed]
                row.payload = snapshot_payload(r, run)
            if self._last_purge is None or run.computed_at - self._last_purge >= timedelta(hours=1):
                cutoff = run.computed_at - timedelta(days=self.advisory.ranking.retention_days)
                sess.execute(
                    delete(SuitabilitySnapshotRow).where(
                        SuitabilitySnapshotRow.server == self.server, SuitabilitySnapshotRow.hour < cutoff
                    )
                )
                self._last_purge = run.computed_at

    def latest(self) -> list[SuitabilitySnapshotRow]:
        """The newest stored ranking, in rank order."""
        with self.db.session() as sess:
            newest = sess.execute(
                select(func.max(SuitabilitySnapshotRow.computed_at)).where(
                    SuitabilitySnapshotRow.server == self.server
                )
            ).scalar_one_or_none()
            if newest is None:
                return []
            rows = sess.execute(
                select(SuitabilitySnapshotRow)
                .where(
                    SuitabilitySnapshotRow.server == self.server,
                    SuitabilitySnapshotRow.computed_at == ensure_utc(newest),
                )
                .order_by(SuitabilitySnapshotRow.rank)
            ).scalars()
            return list(rows)


def _num(value: Decimal | float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def _time(value: datetime | None) -> str | None:
    return None if value is None else ensure_utc(value).isoformat()


def snapshot_payload(r: RankedSymbol, run: RankingRun) -> dict[str, Any]:
    s = r.suitability
    session = run.sessions.get(r.symbol)
    return {
        "scores": {k.value: round(v, 2) for k, v in r.scores.items()},
        "flags": list(r.flags),
        "correlation": _num(r.correlation),
        "correlated_with": r.correlated_with,
        "side": s.side.value,
        "gates": [
            {"gate": g.gate.value, "status": g.status.value, "key": g.key, "params": dict(g.params)}
            for g in s.gates
        ],
        "metrics": {
            "typical_sl": _num(s.typical_sl),
            "risk_budget": _num(s.risk_budget),
            "min_lot": _num(s.min_lot),
            "min_lot_risk": _num(s.min_lot_risk),
            "required_equity": _num(s.required_equity),
            "lot": _num(s.lot),
            "risk_money": _num(s.risk_money),
            "margin": _num(s.margin),
            "effective_leverage": _num(s.effective_leverage),
            "cost_ratio": _num(s.cost_ratio),
            "currency": run.currency,
        },
        "session": None
        if session is None
        else {
            "open": session.open,
            "active": list(session.active),
            "ends_at": _time(session.ends_at),
            "next_open": _time(session.next_open),
        },
        "best_hours_utc": [describe_hour(h) for h in run.best_hours.get(r.symbol, [])],
    }


def failed_reasons(r: RankedSymbol) -> Sequence[tuple[str, dict[str, Any]]]:
    """The explanation keys and parameters of the failed gates, in gate order."""
    return [(g.key, dict(g.params)) for g in r.suitability.gates if g.status is GateStatus.FAIL]
