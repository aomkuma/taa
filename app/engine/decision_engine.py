"""Decision engine: the deterministic A8 pipeline from a signal to ACCEPT / REJECT (PLAN §A8, §A26; TAA-405).

Every check of every group is evaluated, even after a failure, and persisted with its value and threshold,
so a rejection lists *all* its reasons. Groups: system, mode, symbol, data, session, costs, signal geometry,
portfolio, account, sizing. (The AI veto and the broker ``order_check`` precheck are Milestone 2.)

**Profiles:**

- ``EXECUTION`` (PAPER now; DEMO/LIVE in M2): any failed check rejects.
- ``ADVISORY`` (the scanner, §A26): only ``HARD`` failures reject (bad data, closed market, impossible
  geometry, RR, spread, min lot or margin infeasible, a symbol outside the universe). Failed ``ACCOUNT``
  checks (loss limits, exposure, breakers, the kill switch, configured windows, news) become **warnings** on
  the opportunity. The universe check replaces the allowlist.

Sizing feeds the exposure checks. When sizing fails, exposure is evaluated with the full risk budget as the
candidate's risk, an upper bound on what any accepted size could add.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import select

from app import __version__
from app.broker import mt5_constants as c
from app.broker.models import BrokerPosition
from app.config import AppConfig, RiskConfig
from app.core.clock import Clock
from app.core.enums import Side, TradingMode
from app.core.ids import new_id
from app.market_data.data_models import Quote, SymbolSpec
from app.market_data.trading_sessions import SessionState, TradingSessions
from app.news.calendar import NewsFilter
from app.risk.checks import Check, CheckKind
from app.risk.circuit_breaker import BreakerBoard
from app.risk.exposure_manager import Candidate, ExposureManager
from app.risk.limits import ProfileLimits, effective_risk
from app.risk.loss_tracker import LossStatus, loss_checks
from app.risk.mode_gates import GateResult
from app.risk.position_sizer import AccountFunds, PositionSizer, ProfitCalculator, SizingResult
from app.risk.reasons import Reason
from app.storage.database import Database
from app.storage.models import DecisionCheckRow, DecisionRecordRow
from app.strategy.signal_models import MarketContext, Signal

log = logging.getLogger(__name__)

HARD, ACCOUNT = CheckKind.HARD, CheckKind.ACCOUNT
INVALID_FLAGS = ("NO_DATA", "DUPLICATE_BARS", "UNORDERED_BARS", "INVALID_OHLC")
STALE_FLAGS = ("DATA_STALE", "ALIGNMENT_LAG")


class Profile(StrEnum):
    EXECUTION = "EXECUTION"
    ADVISORY = "ADVISORY"


class Decision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class SystemHealth:
    kill_switch_active: bool = False
    broker_healthy: bool = True
    storage_healthy: bool = True
    clock_verified: bool = True


@dataclass(frozen=True, slots=True)
class AccountState:
    funds: AccountFunds
    positions: Sequence[BrokerPosition] = ()
    loss: LossStatus | None = None


@dataclass(frozen=True)
class DecisionRequest:
    signal: Signal
    market: MarketContext
    spec: SymbolSpec | None
    quote: Quote | None
    account: AccountState | None
    health: SystemHealth = field(default_factory=SystemHealth)
    specs: Mapping[str, SymbolSpec] = field(default_factory=dict)  # every symbol with an open position
    gate: GateResult | None = None  # DEMO/LIVE only
    universe: frozenset[str] | None = None  # ADVISORY: the ranked universe replaces the allowlist
    pending_symbols: frozenset[str] = frozenset()  # symbols with an order intent in flight (M2)
    last_entry_at: datetime | None = None  # last accepted entry on this symbol (cooldown)
    expected_slippage_points: float | None = None
    probation: bool = False
    profile_limits: ProfileLimits | None = None


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    created_at: datetime
    profile: Profile
    decision: Decision
    signal: Signal
    market: MarketContext
    checks: tuple[Check, ...]
    sizing: SizingResult | None
    config_hash: str
    code_version: str

    @property
    def failed(self) -> tuple[Check, ...]:
        return tuple(ch for ch in self.checks if not ch.passed)

    @property
    def reason_codes(self) -> tuple[str, ...]:
        """Why it was rejected (empty when accepted)."""
        if self.decision is Decision.ACCEPT:
            return ()
        if self.decision is Decision.HOLD:
            return self.signal.reason_codes
        blocking = (
            self.failed
            if self.profile is Profile.EXECUTION
            else [ch for ch in self.failed if ch.kind is HARD]
        )
        return tuple(dict.fromkeys(ch.reason_code for ch in blocking))

    @property
    def warnings(self) -> tuple[str, ...]:
        """ADVISORY: failed account rules shown on the opportunity card."""
        if self.profile is not Profile.ADVISORY:
            return ()
        return tuple(dict.fromkeys(ch.reason_code for ch in self.failed if ch.kind is ACCOUNT))

    @property
    def volume(self) -> Decimal | None:
        return self.sizing.volume if self.sizing is not None and self.sizing.ok else None


class DecisionEngine:
    def __init__(
        self,
        config: AppConfig,
        mode: TradingMode,
        calculator: ProfitCalculator,
        clock: Clock,
        *,
        sessions: TradingSessions,
        news: NewsFilter,
        magic_base: int,
        config_hash: str,
        breakers: BreakerBoard | None = None,
        store: DecisionStore | None = None,
        spec_lookup: Callable[[str], SymbolSpec] | None = None,
    ) -> None:
        self.config = config
        self.mode = mode
        self.calculator = calculator
        self.clock = clock
        self.sessions = sessions
        self.news = news
        self.magic_base = magic_base
        self.config_hash = config_hash
        self.breakers = breakers
        self.store = store
        self.spec_lookup = spec_lookup
        self._looked_up: dict[str, SymbolSpec | None] = {}

    def position_specs(
        self, specs: Mapping[str, SymbolSpec], positions: Sequence[BrokerPosition]
    ) -> dict[str, SymbolSpec]:
        """*specs* plus the spec of every other symbol with an open position (a manual BTCUSD trade while the
        bot trades Forex), looked up once per symbol. Without a spec a position's risk to its stop cannot be
        measured and blocks new entries as unknown risk; a lookup that fails keeps it so (fail closed)."""
        out = dict(specs)
        if self.spec_lookup is None:
            return out
        for symbol in {p.symbol for p in positions} - set(out):
            if symbol not in self._looked_up:
                try:
                    self._looked_up[symbol] = self.spec_lookup(symbol)
                except Exception:  # broker boundary: an unknown spec stays unknown risk
                    log.warning("no symbol spec for the open position on %s", symbol, exc_info=True)
                    self._looked_up[symbol] = None
            found = self._looked_up[symbol]
            if found is not None:
                out[symbol] = found
        return out

    def decide(self, req: DecisionRequest, profile: Profile = Profile.EXECUTION) -> DecisionRecord:
        now = self.clock.now_utc()
        signal = req.signal
        if not signal.is_entry:
            record = self._record(now, profile, Decision.HOLD, req, (), None)
            return self._persist(record)
        risk = effective_risk(self.config.risk, req.profile_limits)
        checks: list[Check] = []
        checks += self._system(req, profile)
        checks += self._mode(req)
        checks += self._symbol(req, profile)
        checks += self._data(req, now, risk)
        checks += self._session(req, now)
        checks += self._costs(req, risk)
        checks += self._geometry(req, risk)
        sizing = self._size(req, risk)
        checks += self._sizing_checks(sizing)
        checks += self._portfolio(req, risk, sizing)
        if req.account is not None and req.account.loss is not None:
            checks += loss_checks(req.account.loss, risk)
        else:  # loss limits that cannot be verified are not assumed to be fine
            checks.append(
                Check(
                    "loss_status", Reason.DAILY_LOSS_LIMIT, False, ACCOUNT, detail="loss status unavailable"
                )
            )
        blocking = [
            ch for ch in checks if not ch.passed and (profile is Profile.EXECUTION or ch.kind is HARD)
        ]
        decision = Decision.REJECT if blocking else Decision.ACCEPT
        record = self._record(now, profile, decision, req, tuple(checks), sizing)
        log.info(
            "decision %s %s %s %s %s reasons=%s warnings=%s",
            record.decision.value,
            profile.value,
            signal.strategy,
            signal.symbol,
            signal.action.value,
            ",".join(record.reason_codes),
            ",".join(record.warnings),
        )
        return self._persist(record)

    # groups ----------------------------------------------------------------------------------------------

    def _system(self, req: DecisionRequest, profile: Profile) -> list[Check]:
        h = req.health
        out = [
            Check("kill_switch", Reason.KILL_SWITCH_ACTIVE, not h.kill_switch_active, ACCOUNT),
            Check("broker_healthy", Reason.BROKER_UNHEALTHY, h.broker_healthy, HARD),
            Check("storage_healthy", Reason.STORAGE_UNHEALTHY, h.storage_healthy, HARD),
            Check("clock_verified", Reason.CLOCK_UNVERIFIED, h.clock_verified, HARD),
        ]
        if self.breakers is not None:
            out += self.breakers.checks(req.signal.symbol)
        return out

    def _mode(self, req: DecisionRequest) -> list[Check]:
        if not self.mode.may_send_broker_orders:
            # BACKTEST and PAPER fill on the simulated broker: no broker order, no gate to pass
            return [
                Check("mode", Reason.ORDERS_NOT_ALLOWED_IN_MODE, True, ACCOUNT, self.mode.value, "simulated")
            ]
        gate = req.gate
        ok = gate is not None and gate.passed
        detail = "no gate result" if gate is None else "; ".join(f"{cond}: {d}" for cond, d in gate.failures)
        reason = Reason.LIVE_GATE_FAILED if gate is None or gate.reason is None else gate.reason
        return [Check("mode_gate", reason, ok, ACCOUNT, self.mode.value, "gate passed", detail)]

    def _symbol(self, req: DecisionRequest, profile: Profile) -> list[Check]:
        symbol, spec = req.signal.symbol, req.spec
        if profile is Profile.ADVISORY and req.universe is not None:
            allowed = Check("in_universe", Reason.SYMBOL_NOT_ALLOWED, symbol in req.universe, HARD, symbol)
        else:
            allowed = Check(
                "symbol_allowed",
                Reason.SYMBOL_NOT_ALLOWED,
                symbol in self.config.symbols.allowed,
                HARD,
                symbol,
            )
        problems = [] if spec is None else spec.validation_errors()
        side = req.signal.side
        direction_ok = (
            spec is not None and side is not None and (spec.can_buy if side is Side.BUY else spec.can_sell)
        )
        trade_mode = (
            None if spec is None else c.SYMBOL_TRADE_MODE_NAMES.get(spec.trade_mode, str(spec.trade_mode))
        )
        return [
            allowed,
            Check(
                "symbol_available",
                Reason.SYMBOL_UNAVAILABLE,
                spec is not None and not problems,
                HARD,
                detail="no symbol spec" if spec is None else "; ".join(problems),
            ),
            Check(
                "symbol_trade_enabled",
                Reason.SYMBOL_TRADE_DISABLED,
                spec is not None and spec.trading_enabled,
                HARD,
                trade_mode,
            ),
            Check(
                "direction_allowed",
                Reason.DIRECTION_NOT_ALLOWED,
                direction_ok,
                HARD,
                trade_mode,
                req.signal.action.value,
            ),
        ]

    def _data(self, req: DecisionRequest, now: datetime, risk: RiskConfig) -> list[Check]:
        flags = req.market.quality_flags
        quote = req.quote
        stale_limit = self.config.timeframes.stale_tick_seconds
        quote_ok = quote is not None and quote.valid and quote.age_seconds <= stale_limit
        stale_flags = [f for f in flags if any(s in f for s in STALE_FLAGS)]
        drift = self._drift(req)
        atr = req.market.atr
        drift_limit = None if atr is None else risk.price_drift_atr * atr
        return [
            Check(
                "data_fresh",
                Reason.DATA_STALE,
                quote_ok and not stale_flags,
                HARD,
                None if quote is None else round(quote.age_seconds, 3),
                stale_limit,
                "no valid quote" if quote is None or not quote.valid else ",".join(stale_flags),
            ),
            Check(
                "data_gaps", Reason.DATA_GAPS, not any("DATA_GAPS" in f for f in flags), HARD, ",".join(flags)
            ),
            Check(
                "data_valid",
                Reason.DATA_INVALID,
                not any(any(s in f for s in INVALID_FLAGS) for f in flags),
                HARD,
                ",".join(flags),
            ),
            Check(
                "signal_not_expired",
                Reason.SIGNAL_EXPIRED,
                not req.signal.is_expired(now),
                HARD,
                now.isoformat(),
                req.signal.expires_at_utc.isoformat(),
            ),
            Check(
                "price_drift",
                Reason.PRICE_DRIFT,
                drift is not None and drift_limit is not None and drift <= drift_limit,
                HARD,
                drift,
                drift_limit,
                "|current entry price - signal entry|",
            ),
        ]

    def _drift(self, req: DecisionRequest) -> float | None:
        quote, entry, side = req.quote, req.signal.entry_price, req.signal.side
        if quote is None or not quote.valid or entry is None or side is None:
            return None
        current = quote.ask if side is Side.BUY else quote.bid
        return abs(current - entry)

    def _session(self, req: DecisionRequest, now: datetime) -> list[Check]:
        symbol = req.signal.symbol
        verdict = self.sessions.check(symbol, now)
        currencies = () if req.spec is None else (req.spec.currency_base, req.spec.currency_profit)
        blackout = self.news.active(symbol, currencies, now)
        return [
            Check(
                "market_open",
                Reason.MARKET_CLOSED,
                verdict.state is not SessionState.MARKET_CLOSED,
                HARD,
                verdict.state.value,
                detail=verdict.detail,
            ),
            Check(
                "session_open",
                Reason.SESSION_CLOSED,
                verdict.state is not SessionState.SESSION_CLOSED,
                ACCOUNT,
                verdict.state.value,
                detail=verdict.detail,
            ),
            Check(
                "news_blackout",
                Reason.NEWS_BLACKOUT,
                blackout is None,
                ACCOUNT,
                None if blackout is None else blackout.reason,
            ),
        ]

    def _costs(self, req: DecisionRequest, risk: RiskConfig) -> list[Check]:
        symbol = req.signal.symbol
        spread_points = (
            req.quote.spread_points if req.quote is not None and req.quote.valid else req.market.spread_points
        )
        limit = self.config.spread_limit(symbol)
        sl_distance = req.signal.risk_distance
        spread_price = None if spread_points is None or req.spec is None else spread_points * req.spec.point
        ratio = None if spread_price is None or not sl_distance else spread_price / sl_distance
        slippage = (
            risk.slippage_allowance_points
            if req.expected_slippage_points is None
            else req.expected_slippage_points
        )
        return [
            Check(
                "spread",
                Reason.SPREAD_TOO_HIGH,
                spread_points is not None and spread_points <= limit,
                HARD,
                spread_points,
                limit,
            ),
            Check(
                "spread_to_sl",
                Reason.SPREAD_TO_SL_TOO_HIGH,
                ratio is not None and ratio <= risk.max_spread_to_sl_ratio,
                HARD,
                None if ratio is None else round(ratio, 4),
                risk.max_spread_to_sl_ratio,
            ),
            Check(
                "expected_slippage",
                Reason.EXPECTED_SLIPPAGE_TOO_HIGH,
                slippage <= risk.max_slippage_points,
                HARD,
                slippage,
                risk.max_slippage_points,
            ),
        ]

    def _geometry(self, req: DecisionRequest, risk: RiskConfig) -> list[Check]:
        s, spec, atr = req.signal, req.spec, req.market.atr
        side = s.side
        entry, sl, tp = s.entry_price, s.stop_loss, s.take_profit
        has_sl = sl is not None and sl > 0
        right_side = (
            sl is not None
            and has_sl
            and entry is not None
            and side is not None
            and (entry - sl) * side.sign > 0
        )
        tp_side = tp is not None and entry is not None and side is not None and (tp - entry) * side.sign > 0
        distance = s.risk_distance
        min_distance = None
        if spec is not None:
            spread = (
                req.quote.spread_points if req.quote is not None and req.quote.valid else spec.spread_points
            ) or 0
            min_distance = (spec.stops_level + spread) * spec.point
        rr = s.risk_reward
        return [
            Check("sl_present", Reason.SL_MISSING, has_sl, HARD, sl),
            Check(
                "tp_present",
                Reason.TP_MISSING,
                not risk.require_take_profit or tp_side,
                HARD,
                tp,
                "required" if risk.require_take_profit else "optional",
            ),
            Check("sl_side", Reason.SL_WRONG_SIDE, right_side, HARD, sl, entry),
            Check(
                "sl_not_too_close",
                Reason.SL_TOO_CLOSE,
                right_side and distance is not None and min_distance is not None and distance > min_distance,
                HARD,
                distance,
                min_distance,
                "stops level + spread",
            ),
            Check(
                "sl_not_too_far",
                Reason.SL_TOO_FAR,
                distance is not None and atr is not None and distance <= risk.max_sl_atr_multiple * atr,
                HARD,
                distance,
                None if atr is None else risk.max_sl_atr_multiple * atr,
            ),
            Check(
                "risk_reward",
                Reason.RR_TOO_LOW,
                rr is not None and tp_side and rr >= risk.min_risk_reward,
                HARD,
                None if rr is None else round(rr, 4),
                risk.min_risk_reward,
            ),
        ]

    def _size(self, req: DecisionRequest, risk: RiskConfig) -> SizingResult | None:
        s, spec = req.signal, req.spec
        if (
            spec is None
            or req.account is None
            or s.side is None
            or s.entry_price is None
            or s.stop_loss is None
        ):
            return None
        commission = self.config.backtest.commission_per_lot
        override = self.config.symbols.overrides.get(spec.name)
        if override is not None and override.commission_per_lot is not None:
            commission = override.commission_per_lot
        sizer = PositionSizer(risk, self.calculator, commission_per_lot=commission)
        return sizer.size(
            spec,
            s.side,
            s.entry_price,
            s.stop_loss,
            req.account.funds,
            lot_limit=self.config.lot_limit(spec.name),
            probation=req.probation,
        )

    def _sizing_checks(self, sizing: SizingResult | None) -> list[Check]:
        if sizing is None:
            return [
                Check(
                    "sizing", Reason.VOLUME_INVALID, False, HARD, detail="no spec, account or prices to size"
                )
            ]
        if sizing.ok:
            return [
                Check("sizing", Reason.VOLUME_INVALID, True, HARD, float(sizing.volume), float(sizing.budget))
            ]
        reason = sizing.reason or Reason.VOLUME_INVALID
        # margin that depends on other open positions is an account rule; everything else is infeasible
        kind = ACCOUNT if reason is Reason.MARGIN_LEVEL_TOO_LOW else HARD
        value = None if sizing.margin_level_after is None else float(sizing.margin_level_after)
        return [Check("sizing", reason, False, kind, value, float(sizing.budget), sizing.detail)]

    def _portfolio(self, req: DecisionRequest, risk: RiskConfig, sizing: SizingResult | None) -> list[Check]:
        s = req.signal
        out: list[Check] = []
        duplicate = self.store is not None and self.store.accepted_exists(s.idempotency_key)
        out.append(
            Check("duplicate_signal", Reason.DUPLICATE_SIGNAL, not duplicate, HARD, s.idempotency_key[:12])
        )
        pending = s.symbol in req.pending_symbols
        out.append(Check("pending_intent", Reason.PENDING_INTENT_EXISTS, not pending, ACCOUNT))
        cooldown_until = (
            None
            if req.last_entry_at is None
            else req.last_entry_at
            + timedelta(seconds=self.config.strategies.cooldown_bars * s.timeframe.seconds)
        )
        in_cooldown = cooldown_until is not None and s.data_timestamp_utc < cooldown_until
        out.append(
            Check(
                "symbol_cooldown",
                Reason.COOLDOWN_ACTIVE,
                not in_cooldown,
                ACCOUNT,
                None if cooldown_until is None else cooldown_until.isoformat(),
            )
        )
        if req.account is None or s.side is None or s.entry_price is None:
            out.append(
                Check("account_state", Reason.BROKER_UNHEALTHY, False, HARD, detail="no account snapshot")
            )
            return out
        manager = ExposureManager(risk, self.calculator, magic_base=self.magic_base)
        specs = self.position_specs(req.specs, req.account.positions)
        if req.spec is not None:
            specs[req.spec.name] = req.spec
        exposure = manager.snapshot(req.account.positions, req.account.funds, specs)
        if sizing is not None and sizing.ok:
            volume, risk_money = float(sizing.volume), float(sizing.risk_money)
            margin = float(sizing.margin_required or 0)
        else:
            budget = float(sizing.budget) if sizing is not None else 0.0
            volume, risk_money, margin = 0.0, budget, 0.0
        candidate = Candidate(s.symbol, s.side, volume, s.entry_price, risk_money, margin)
        out += manager.check(candidate, exposure, specs)
        return out

    # records ---------------------------------------------------------------------------------------------

    def _record(
        self,
        now: datetime,
        profile: Profile,
        decision: Decision,
        req: DecisionRequest,
        checks: tuple[Check, ...],
        sizing: SizingResult | None,
    ) -> DecisionRecord:
        return DecisionRecord(
            decision_id=new_id(),
            created_at=now,
            profile=profile,
            decision=decision,
            signal=req.signal,
            market=req.market,
            checks=checks,
            sizing=sizing,
            config_hash=self.config_hash,
            code_version=__version__,
        )

    def _persist(self, record: DecisionRecord) -> DecisionRecord:
        if self.store is not None:
            self.store.save(record)
        return record


def _plan(sizing: SizingResult | None) -> list[dict[str, Any]]:
    if sizing is None or not sizing.ok:
        return []
    return [
        {
            "entry": str(p.part.entry),
            "order_type": p.part.order_type.value,
            "take_profit": None if p.part.take_profit is None else str(p.part.take_profit),
            "volume": str(p.volume),
            "taps": p.taps,
            "risk_money": str(p.risk_money),
        }
        for p in sizing.parts
    ]


class DecisionStore:
    """Persists decision records with one row per check (``decision_records`` / ``decision_checks``)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, record: DecisionRecord) -> None:
        s = record.signal
        sizing = record.sizing
        with self.db.session() as sess:
            sess.add(
                DecisionRecordRow(
                    decision_id=record.decision_id,
                    created_at=record.created_at,
                    signal_id=s.signal_id,
                    idempotency_key=s.idempotency_key,
                    strategy=s.strategy,
                    symbol=s.symbol,
                    timeframe=s.timeframe.value,
                    action=s.action.value,
                    profile=record.profile.value,
                    decision=record.decision.value,
                    reason_codes=list(record.reason_codes),
                    warnings=list(record.warnings),
                    volume=None if record.volume is None else float(record.volume),
                    risk_money=None if sizing is None or not sizing.ok else float(sizing.risk_money),
                    entry_price=s.entry_price,
                    stop_loss=None if sizing is None or sizing.stop_loss is None else float(sizing.stop_loss),
                    take_profit=s.take_profit,
                    plan=_plan(sizing),
                    bar_times={tf.value: t.isoformat() for tf, t in s.bar_times},
                    signal=s.to_dict(),
                    market=record.market.to_dict(),
                    config_hash=record.config_hash,
                    code_version=record.code_version,
                )
            )
            for seq, ch in enumerate(record.checks):
                sess.add(
                    DecisionCheckRow(
                        decision_id=record.decision_id,
                        seq=seq,
                        name=ch.name,
                        reason=ch.reason_code,
                        passed=ch.passed,
                        kind=ch.kind.value,
                        value=ch.value,
                        threshold=ch.threshold,
                        detail=ch.detail,
                    )
                )

    def accepted_exists(self, idempotency_key: str) -> bool:
        with self.db.session() as sess:
            row = sess.execute(
                select(DecisionRecordRow.decision_id).where(
                    DecisionRecordRow.idempotency_key == idempotency_key,
                    DecisionRecordRow.decision == Decision.ACCEPT.value,
                    DecisionRecordRow.profile == Profile.EXECUTION.value,
                )
            ).first()
            return row is not None

    def checks(self, decision_id: str) -> list[DecisionCheckRow]:
        with self.db.session() as sess:
            rows = sess.execute(
                select(DecisionCheckRow)
                .where(DecisionCheckRow.decision_id == decision_id)
                .order_by(DecisionCheckRow.seq)
            ).scalars()
            out = list(rows)
            sess.expunge_all()
            return out
