from __future__ import annotations

import dataclasses
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from app.broker import mt5_constants as c
from app.config import AppConfig, BlackoutWindow
from app.core.clock import ManualClock
from app.core.enums import Action, Side, Timeframe, TradingMode
from app.engine.decision_engine import (
    AccountState,
    Decision,
    DecisionEngine,
    DecisionRequest,
    DecisionStore,
    Profile,
    SystemHealth,
)
from app.market_data.data_models import Quote
from app.market_data.trading_sessions import TradingSessions
from app.news.calendar import ManualBlackouts, NewsFilter
from app.risk.checks import CheckKind
from app.risk.circuit_breaker import BreakerBoard, BreakerName, default_specs
from app.risk.mode_gates import GateCondition, GateResult
from app.risk.reasons import Reason
from app.storage.database import Database
from tests.risk_data import TickCalculator, funds
from tests.strategy_data import EURUSD_SPEC
from tests.unit.test_exposure_manager import BASE, GBPUSD_SPEC, USDJPY_SPEC, pos
from tests.unit.test_loss_tracker import status
from tests.unit.test_strategy_models import BAR, make_context, make_signal, state

NOW = BAR + timedelta(seconds=5)  # Wednesday 10:15:05 UTC
SPECS = {s.name: s for s in (EURUSD_SPEC, GBPUSD_SPEC, USDJPY_SPEC)}


def quote(**kw: object) -> Quote:
    base: dict[str, object] = {
        "symbol": "EURUSD",
        "bid": 1.09992,
        "ask": 1.10000,
        "spread_points": 8.0,
        "time_utc": NOW,
        "age_seconds": 1.0,
        "valid": True,
    }
    base.update(kw)
    return Quote(**base)  # type: ignore[arg-type]


def request(**kw: Any) -> DecisionRequest:
    base: dict[str, Any] = {
        "signal": make_signal(evidence=()),
        "market": make_context(quality_flags=()),
        "spec": EURUSD_SPEC,
        "quote": quote(),
        "account": AccountState(funds(), (), status()),
        "specs": SPECS,
    }
    base.update(kw)
    return DecisionRequest(**base)


@dataclasses.dataclass
class Setup:
    config: dict[str, Any] = dataclasses.field(default_factory=dict)
    mode: TradingMode = TradingMode.PAPER
    calc: TickCalculator | None = None
    blackouts: list[BlackoutWindow] = dataclasses.field(default_factory=list)
    trip: BreakerName | None = None


def engine(db: Database, setup: Setup | None = None, clock: ManualClock | None = None) -> DecisionEngine:
    s = setup or Setup()
    config = AppConfig.model_validate(s.config)
    clk = clock or ManualClock(NOW)
    board = BreakerBoard(
        db,
        default_specs(config.breakers, consecutive_pause_hours=24),
        clk,
        mode=s.mode,
        tz_name="Europe/Athens",
    )
    if s.trip is not None:
        board.trip(s.trip, "test")
    return DecisionEngine(
        config,
        s.mode,
        s.calc or TickCalculator(*SPECS.values()),
        clk,
        sessions=TradingSessions(config.sessions, config.symbols),
        news=NewsFilter(ManualBlackouts(s.blackouts)),
        magic_base=BASE,
        config_hash="cfg",
        breakers=board,
        store=DecisionStore(db),
    )


def risk(**kw: Any) -> dict[str, Any]:
    return {"risk": kw}


def signal(**kw: Any) -> dict[str, Any]:
    return {"signal": make_signal(evidence=(), **kw)}


def spec(**kw: Any) -> dict[str, Any]:
    return {"spec": dataclasses.replace(EURUSD_SPEC, **kw)}


def account(*positions: Any, loss: Any = None, **fund_kw: float) -> dict[str, Any]:
    return {"account": AccountState(funds(**fund_kw), positions, status() if loss is None else loss)}


BLACKOUT = BlackoutWindow(
    start_utc=BAR - timedelta(minutes=5),
    end_utc=BAR + timedelta(minutes=30),
    currencies=["USD"],
    reason="CPI",
)
PAPER_GATE = GateResult(TradingMode.LIVE, ((GateCondition.MODE, "x"),))

# reason -> (engine setup, request overrides)
CASES: dict[str, tuple[Setup, dict[str, Any]]] = {
    "KILL_SWITCH_ACTIVE": (Setup(), {"health": SystemHealth(kill_switch_active=True)}),
    "BREAKER_OPEN:DAILY_LOSS": (Setup(trip=BreakerName.DAILY_LOSS), {}),
    "BROKER_UNHEALTHY": (Setup(), {"health": SystemHealth(broker_healthy=False)}),
    "STORAGE_UNHEALTHY": (Setup(), {"health": SystemHealth(storage_healthy=False)}),
    "CLOCK_UNVERIFIED": (Setup(), {"health": SystemHealth(clock_verified=False)}),
    "ORDERS_NOT_ALLOWED_IN_MODE": (Setup(mode=TradingMode.LIVE), {"gate": PAPER_GATE}),
    "LIVE_GATE_FAILED": (Setup(mode=TradingMode.LIVE), {}),
    "SYMBOL_NOT_ALLOWED": (Setup(config={"symbols": {"allowed": ["GBPUSD"]}}), {}),
    "SYMBOL_UNAVAILABLE": (Setup(), {"spec": None}),
    "SYMBOL_TRADE_DISABLED": (Setup(), spec(trade_mode=c.SYMBOL_TRADE_MODE_DISABLED)),
    "DIRECTION_NOT_ALLOWED": (Setup(), spec(trade_mode=c.SYMBOL_TRADE_MODE_SHORTONLY)),
    "DATA_STALE": (Setup(), {"quote": quote(age_seconds=500.0)}),
    "DATA_GAPS": (Setup(), {"market": make_context(quality_flags=("M15:DATA_GAPS",))}),
    "DATA_INVALID": (Setup(), {"market": make_context(quality_flags=("H1:INVALID_OHLC",))}),
    "SIGNAL_EXPIRED": (Setup(), signal(expires_at_utc=BAR + timedelta(seconds=3))),
    "PRICE_DRIFT": (Setup(), {"quote": quote(bid=1.10092, ask=1.10100)}),
    "SESSION_CLOSED": (Setup(config={"sessions": {"default": [{"start": "12:00", "end": "20:00"}]}}), {}),
    "MARKET_CLOSED": (
        Setup(config={"symbols": {"overrides": {"EURUSD": {"daily_breaks_utc": ["10:00-10:30"]}}}}),
        {},
    ),
    "NEWS_BLACKOUT": (Setup(blackouts=[BLACKOUT]), {}),
    "SPREAD_TOO_HIGH": (Setup(), {"quote": quote(spread_points=40.0)}),
    "SPREAD_TO_SL_TOO_HIGH": (Setup(), signal(stop_loss=1.0995)),
    "EXPECTED_SLIPPAGE_TOO_HIGH": (Setup(), {"expected_slippage_points": 20.0}),
    "SL_MISSING": (Setup(), signal(stop_loss=None)),
    "TP_MISSING": (Setup(), signal(take_profit=None)),
    "SL_WRONG_SIDE": (Setup(), signal(stop_loss=1.1020)),
    "SL_TOO_CLOSE": (Setup(), spec(stops_level=300)),
    "SL_TOO_FAR": (
        Setup(),
        {
            "market": make_context(
                quality_flags=(), states=(state(Timeframe.M15, BAR, atr=0.0005), state(Timeframe.H1, BAR))
            )
        },
    ),
    "RR_TOO_LOW": (Setup(), signal(take_profit=1.1020)),
    "MAX_OPEN_POSITIONS": (
        Setup(config=risk(max_open_positions=1)),
        account(pos("USDJPY", price=150.0, sl=149.9)),
    ),
    "MAX_POSITIONS_PER_SYMBOL": (Setup(), account(pos())),
    "CONFLICTING_POSITION": (
        Setup(config=risk(max_positions_per_symbol=2)),
        account(pos(side=Side.SELL, sl=1.102)),
    ),
    "DUPLICATE_SIGNAL": (Setup(), {}),  # decided twice below
    "PENDING_INTENT_EXISTS": (Setup(), {"pending_symbols": frozenset({"EURUSD"})}),
    "CORRELATION_LIMIT": (Setup(), account(pos("GBPUSD", price=1.3, sl=1.298))),
    "CURRENCY_EXPOSURE_LIMIT": (
        Setup(config=risk(max_same_direction_per_currency=1, correlation_groups={})),
        account(pos("GBPUSD", price=1.3, sl=1.298)),
    ),
    "MAX_TOTAL_OPEN_RISK": (Setup(), account(pos("GBPUSD", side=Side.SELL, volume=0.3, price=1.3, sl=1.304))),
    "UNKNOWN_POSITION_RISK": (Setup(), account(pos("USDJPY", price=150.0, sl=0.0))),
    "FOREIGN_POSITIONS": (
        Setup(config=risk(foreign_positions_policy="halt")),
        account(pos("USDJPY", price=150.0, sl=149.9, magic=0)),
    ),
    "COOLDOWN_ACTIVE": (Setup(), {"last_entry_at": BAR - timedelta(minutes=15)}),
    "DAILY_LOSS_LIMIT": (Setup(), account(loss=status(equity=9_780.0, adjusted_equity=9_780.0))),
    "WEEKLY_LOSS_LIMIT": (Setup(), account(loss=status(equity=9_850.0, week_start=10_300.0))),
    "MAX_DRAWDOWN": (Setup(), account(loss=status(hwm=11_200.0))),
    "CONSECUTIVE_LOSSES": (Setup(), account(loss=status(consecutive_losses=4, last_loss_at=BAR))),
    "MARGIN_INSUFFICIENT": (Setup(), account(margin=9_500.0)),
    "MARGIN_LEVEL_TOO_LOW": (Setup(), account(margin=1_900.0)),
    "LEVERAGE_LIMIT": (
        Setup(config=risk(max_effective_leverage=10)),  # off by default (margin decides)
        account(pos("USDJPY", volume=1.0, price=150.0, sl=149.95)),
    ),
    "SYMBOL_SPEC_INCONSISTENT": (Setup(calc=TickCalculator(*SPECS.values(), skew=1.5)), {}),
    "RISK_BELOW_MIN_LOT": (Setup(), account(equity=300.0)),
    "VOLUME_INVALID": (Setup(), {"account": None}),
}
M2_ONLY = {"AI_DISAGREES", "AI_LOW_CONFIDENCE", "AI_UNAVAILABLE", "ORDER_CHECK_FAILED"}


class TestBaseline:
    def test_clean_request_is_accepted(self, db: Database) -> None:
        record = engine(db).decide(request())
        assert record.decision is Decision.ACCEPT, [c.reason_code for c in record.failed]
        assert record.volume == Decimal("0.24")
        assert record.reason_codes == ()
        assert all(ch.passed for ch in record.checks)
        assert len(record.checks) >= 35

    def test_a_tight_stop_is_sized_down_to_a_configured_leverage_cap(self, db: Database) -> None:
        """2026-10-06 on FBS: 1.5 % of a 1,080 USD account on a 9-pip GBPUSD stop was 0.16 lot (~20x) and the
        whole trade was rejected for leverage. With a cap configured, the lot is cut to what it allows."""
        tight = make_signal(evidence=(), stop_loss=1.0991, take_profit=1.1020)  # 9 pips
        config = risk(
            max_risk_per_trade_percent=2.0, max_total_open_risk_percent=4.0, max_effective_leverage=10
        )
        record = engine(db, Setup(config=config)).decide(request(signal=tight))
        assert record.decision is Decision.ACCEPT, [c.reason_code for c in record.failed]
        lever = next(ch for ch in record.checks if ch.name == "effective_leverage")
        assert lever.passed and float(lever.value) <= 10.0
        assert record.volume == Decimal("0.9")  # 10x of 10,000 USD at 1.10 = 0.909 lot, floored
        assert record.sizing is not None and float(record.sizing.risk_money) < 200.0  # below the 2 % budget

    def test_margin_decides_by_default_and_the_lot_shrinks_to_fit_it(self, db: Database) -> None:
        tight = make_signal(evidence=(), stop_loss=1.0991, take_profit=1.1020)
        config = risk(max_risk_per_trade_percent=2.0, max_total_open_risk_percent=4.0)
        other = Database("sqlite://")  # each decision on its own store: the same signal is not a duplicate
        other.create_all()
        record = engine(other, Setup(config=config)).decide(request(signal=tight))
        assert record.decision is Decision.ACCEPT
        assert record.volume == Decimal("1.0")  # no leverage cap: the risk-sized lot, within max_lot
        config["risk"]["max_margin_utilization_percent"] = 5.0  # 500 USD of margin at 1,100 USD per lot
        record = engine(db, Setup(config=config)).decide(request(signal=tight))
        assert record.decision is Decision.ACCEPT, [c.reason_code for c in record.failed]
        assert record.volume == Decimal("0.45")
        margin = next(ch for ch in record.checks if ch.name == "margin_utilization")
        assert margin.passed and float(margin.value) <= 5.0

    def test_missing_loss_status_fails_closed(self, db: Database) -> None:
        record = engine(db).decide(request(account=AccountState(funds())))
        assert record.reason_codes == ("DAILY_LOSS_LIMIT",)
        assert any(ch.name == "loss_status" and not ch.passed for ch in record.checks)

    def test_hold_signal_is_recorded_as_hold(self, db: Database) -> None:
        hold = make_signal(
            evidence=(),
            action=Action.HOLD,
            entry_price=None,
            stop_loss=None,
            take_profit=None,
            reason_codes=("NO_BIAS",),
        )
        record = engine(db).decide(request(signal=hold))
        assert record.decision is Decision.HOLD
        assert record.reason_codes == ("NO_BIAS",)
        assert record.checks == ()


class TestEveryReasonCode:
    @pytest.mark.parametrize("code", sorted(CASES))
    def test_rejects_with_the_exact_code(self, db: Database, code: str) -> None:
        setup, overrides = CASES[code]
        eng = engine(db, setup)
        if code == "DUPLICATE_SIGNAL":
            assert eng.decide(request()).decision is Decision.ACCEPT
        record = eng.decide(request(**overrides))
        assert record.decision is Decision.REJECT
        assert code in record.reason_codes, record.reason_codes

    def test_every_milestone_1_reason_is_covered(self) -> None:
        covered = {code.split(":")[0] for code in CASES}
        assert covered == {r.value for r in Reason} - M2_ONLY

    def test_all_checks_are_evaluated_after_a_failure(self, db: Database) -> None:
        record = engine(db).decide(
            request(health=SystemHealth(kill_switch_active=True), quote=quote(spread_points=40.0))
        )
        assert {"KILL_SWITCH_ACTIVE", "SPREAD_TOO_HIGH"} <= set(record.reason_codes)
        baseline = engine(db).decide(request())
        assert len(record.checks) == len(baseline.checks)


class TestAdvisoryProfile:
    def test_account_rules_become_warnings(self, db: Database) -> None:
        loss = account(loss=status(equity=9_780.0, adjusted_equity=9_780.0))
        record = engine(db, Setup(trip=BreakerName.DAILY_LOSS)).decide(
            request(**loss, health=SystemHealth(kill_switch_active=True)), Profile.ADVISORY
        )
        assert record.decision is Decision.ACCEPT
        assert set(record.warnings) == {"DAILY_LOSS_LIMIT", "KILL_SWITCH_ACTIVE", "BREAKER_OPEN:DAILY_LOSS"}
        assert record.reason_codes == ()

    @pytest.mark.parametrize(
        "code",
        [
            "SPREAD_TOO_HIGH",
            "RR_TOO_LOW",
            "DATA_STALE",
            "MARKET_CLOSED",
            "RISK_BELOW_MIN_LOT",
            "SL_WRONG_SIDE",
        ],
    )
    def test_hard_failures_still_reject(self, db: Database, code: str) -> None:
        setup, overrides = CASES[code]
        record = engine(db, setup).decide(request(**overrides), Profile.ADVISORY)
        assert record.decision is Decision.REJECT
        assert code in record.reason_codes

    def test_universe_replaces_the_allowlist(self, db: Database) -> None:
        eng = engine(db, Setup(config={"symbols": {"allowed": ["GBPUSD"]}}))
        assert (
            eng.decide(request(universe=frozenset({"EURUSD"})), Profile.ADVISORY).decision is Decision.ACCEPT
        )
        out = eng.decide(request(universe=frozenset({"XAUUSD"})), Profile.ADVISORY)
        assert out.reason_codes == ("SYMBOL_NOT_ALLOWED",)

    def test_kinds(self, db: Database) -> None:
        kinds = {ch.name: ch.kind for ch in engine(db).decide(request()).checks}
        assert kinds["daily_loss"] is CheckKind.ACCOUNT
        assert kinds["spread"] is CheckKind.HARD
        assert kinds["session_open"] is CheckKind.ACCOUNT
        assert kinds["market_open"] is CheckKind.HARD


class TestPersistence:
    def test_record_and_every_check_are_stored(self, db: Database) -> None:
        store = DecisionStore(db)
        record = engine(db).decide(request(quote=quote(spread_points=40.0)))
        rows = store.checks(record.decision_id)
        assert len(rows) == len(record.checks)
        spread = next(r for r in rows if r.name == "spread")
        assert (spread.passed, spread.value, spread.threshold) == (False, 40.0, 30.0)
        assert not store.accepted_exists(record.signal.idempotency_key)  # rejected decisions don't block

    def test_profile_limits_tighten_the_decision(self, db: Database) -> None:
        from app.risk.limits import ProfileLimits

        record = engine(db).decide(request(profile_limits=ProfileLimits(min_risk_reward=2.5)))
        assert record.reason_codes == ("RR_TOO_LOW",)
        sized = engine(db).decide(request(profile_limits=ProfileLimits(risk_per_trade_percent=0.25)))
        assert sized.volume == Decimal("0.12")


def test_mutations_are_all_rejections_in_isolation(db: Database) -> None:
    """Each case must fail on its own code; any extra code flags a test that breaks more than intended."""
    noisy: dict[str, list[str]] = {}
    allowed_extra: dict[str, set[str]] = {
        "SPREAD_TOO_HIGH": {"SPREAD_TO_SL_TOO_HIGH"},
        "SYMBOL_UNAVAILABLE": {
            "DIRECTION_NOT_ALLOWED",
            "SYMBOL_TRADE_DISABLED",
            "VOLUME_INVALID",
            "SPREAD_TO_SL_TOO_HIGH",
            "SL_TOO_CLOSE",
        },
        "SYMBOL_TRADE_DISABLED": {"DIRECTION_NOT_ALLOWED"},
        "SL_MISSING": {
            "SL_WRONG_SIDE",
            "SL_TOO_CLOSE",
            "SL_TOO_FAR",
            "RR_TOO_LOW",
            "SPREAD_TO_SL_TOO_HIGH",
            "VOLUME_INVALID",
        },
        "TP_MISSING": {"RR_TOO_LOW"},
        "SL_WRONG_SIDE": {"SL_TOO_CLOSE", "SL_WRONG_SIDE"},
        "MARGIN_INSUFFICIENT": {"MARGIN_INSUFFICIENT"},
        "LEVERAGE_LIMIT": {"MARGIN_INSUFFICIENT"},
        "VOLUME_INVALID": {"BROKER_UNHEALTHY", "DAILY_LOSS_LIMIT"},  # no account: no loss status either
        "ORDERS_NOT_ALLOWED_IN_MODE": set(),
        "DUPLICATE_SIGNAL": set(),
        "CONSECUTIVE_LOSSES": set(),
    }
    for code, (setup, overrides) in CASES.items():
        if code == "DUPLICATE_SIGNAL":
            continue
        fresh = Database("sqlite://")
        fresh.create_all()
        record = engine(fresh, setup).decide(request(**overrides))
        extra = set(record.reason_codes) - {code} - allowed_extra.get(code, set())
        if extra:
            noisy[code] = sorted(extra)
    assert not noisy, noisy


class TestPositionsOnOtherSymbols:
    """A manual trade (magic 0) with a stop on a symbol the bot does not trade, e.g. BTCUSD next to Forex: the
    request carries only the traded symbols' specs (2026-10-05: every entry was refused as unknown risk)."""

    def manual(self) -> dict[str, Any]:
        return account(pos("GBPUSD", price=1.3, sl=1.298, magic=0, ticket=7))

    def unknown(self, record: Any) -> bool:
        return any(ch.name == "unknown_position_risk" and not ch.passed for ch in record.checks)

    def test_its_spec_is_looked_up_once_and_its_risk_measured(self, db: Database) -> None:
        eng = engine(db)
        calls: list[str] = []

        def lookup(symbol: str) -> Any:
            calls.append(symbol)
            return GBPUSD_SPEC

        eng.spec_lookup = lookup
        only_traded = {"EURUSD": EURUSD_SPEC}
        assert not self.unknown(eng.decide(request(specs=only_traded, **self.manual())))
        assert not self.unknown(eng.decide(request(specs=only_traded, **self.manual())))
        assert calls == ["GBPUSD"]

    def test_without_a_spec_it_stays_unknown_risk(self, db: Database) -> None:
        eng = engine(db)
        assert self.unknown(eng.decide(request(specs={"EURUSD": EURUSD_SPEC}, **self.manual())))

        def broken(symbol: str) -> Any:
            raise RuntimeError("symbol_info failed")

        eng.spec_lookup = broken
        assert self.unknown(
            eng.decide(request(specs={"EURUSD": EURUSD_SPEC}, **self.manual()))
        )  # fail closed
