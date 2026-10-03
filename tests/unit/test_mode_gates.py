from __future__ import annotations

import dataclasses
import itertools
from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.broker import mt5_constants as c
from app.broker.models import AccountSnapshot, TerminalSnapshot
from app.config import EnvSettings, RiskConfig
from app.core.enums import TradingMode
from app.risk.limits import ProfileLimits, effective_risk
from app.risk.mode_gates import GateCondition, confirmation_phrase, evaluate_gate
from app.risk.reasons import Reason

LOGIN = 12345678
G = GateCondition


def env(mode: TradingMode, **kw: object) -> EnvSettings:
    base: dict[str, object] = {
        "TRADING_MODE": mode,
        "MT5_LOGIN": LOGIN,
        "MT5_SERVER": "FBS-Real" if mode is TradingMode.LIVE else "FBS-Demo",
    }
    base.update(kw)
    return EnvSettings.model_validate(base)


def account(mode: TradingMode, **kw: object) -> AccountSnapshot:
    base: dict[str, object] = {
        "login": LOGIN,
        "server": "FBS-Real" if mode is TradingMode.LIVE else "FBS-Demo",
        "company": "FBS",
        "name": "x",
        "currency": "USD",
        "leverage": 200,
        "trade_mode": c.ACCOUNT_TRADE_MODE_REAL if mode is TradingMode.LIVE else c.ACCOUNT_TRADE_MODE_DEMO,
        "margin_mode": c.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
        "trade_allowed": True,
        "trade_expert": True,
        "balance": 1000.0,
        "equity": 1000.0,
        "profit": 0.0,
        "credit": 0.0,
        "margin": 0.0,
        "margin_free": 1000.0,
        "margin_level": 0.0,
        "margin_so_call": 40.0,
        "margin_so_so": 20.0,
        "margin_so_mode": 0,
        "captured_at_utc": datetime(2026, 9, 30, 10, 0, tzinfo=UTC),
    }
    base.update(kw)
    return AccountSnapshot(**base)  # type: ignore[arg-type]


TERMINAL = TerminalSnapshot(True, True, False, False, 5000, 100_000, 1000, "FBS", "MT5", "x", "y")

LIVE_INPUTS = {
    G.ENABLE_FLAG: ("env", {"ENABLE_LIVE_TRADING": False}),
    G.CONFIRMATION: ("env", {"LIVE_TRADING_CONFIRMATION": "I-ACCEPT-LIVE-RISK-999"}),
    G.ACCOUNT_VERIFIED: ("account", {"server": "Other-Server"}),
    G.ACCOUNT_TRADE_MODE: ("account", {"trade_mode": c.ACCOUNT_TRADE_MODE_DEMO}),
    G.ACCOUNT_PERMISSIONS: ("account", {"trade_allowed": False}),
    G.TERMINAL_PERMISSIONS: ("terminal", {"trade_allowed": False}),
    G.RISK_CONFIG: ("risk_config_ok", False),
    G.KILL_SWITCH: ("kill_switch_active", True),
    G.BREAKERS: ("latched_breakers", ["MAX_DRAWDOWN"]),
}


def run(mode: TradingMode, broken: set[GateCondition]):  # type: ignore[no-untyped-def]
    live = mode is TradingMode.LIVE
    env_kw: dict[str, object] = {}
    if live:
        env_kw = {"ENABLE_LIVE_TRADING": True, "LIVE_TRADING_CONFIRMATION": confirmation_phrase(LOGIN)}
    else:
        env_kw = {"ENABLE_DEMO_TRADING": True}
    acct_kw: dict[str, object] = {}
    term = TERMINAL
    kw: dict[str, object] = {"risk_config_ok": True, "kill_switch_active": False, "latched_breakers": []}
    for cond in broken:
        where, value = LIVE_INPUTS[cond]
        if cond is G.ENABLE_FLAG and not live:
            value = {"ENABLE_DEMO_TRADING": False}
        if cond is G.ACCOUNT_TRADE_MODE and not live:
            value = {"trade_mode": c.ACCOUNT_TRADE_MODE_REAL}
        if where == "env":
            env_kw.update(value)  # type: ignore[arg-type]
        elif where == "account":
            acct_kw.update(value)  # type: ignore[arg-type]
        elif where == "terminal":
            term = dataclasses.replace(TERMINAL, **value)  # type: ignore[arg-type]
        else:
            kw[where] = value
    return evaluate_gate(mode, env(mode, **env_kw), account=account(mode, **acct_kw), terminal=term, **kw)  # type: ignore[arg-type]


class TestGateTruthTable:
    LIVE_CONDS = sorted(LIVE_INPUTS)
    DEMO_CONDS = sorted(set(LIVE_INPUTS) - {G.CONFIRMATION})

    @pytest.mark.parametrize("mask", range(2 ** len(LIVE_INPUTS)))
    def test_live_passes_only_when_every_condition_holds(self, mask: int) -> None:
        broken = {cond for i, cond in enumerate(self.LIVE_CONDS) if mask >> i & 1}
        result = run(TradingMode.LIVE, broken)
        assert result.failed_conditions == broken
        assert result.passed is (not broken)
        assert result.reason is (None if not broken else Reason.LIVE_GATE_FAILED)

    def test_demo_truth_table(self) -> None:
        for bits in itertools.product([False, True], repeat=len(self.DEMO_CONDS)):
            broken = {cond for cond, b in zip(self.DEMO_CONDS, bits, strict=True) if b}
            result = run(TradingMode.DEMO, broken)
            assert result.failed_conditions == broken, broken
            assert result.passed is (not broken)

    @pytest.mark.parametrize("mode", [TradingMode.BACKTEST, TradingMode.PAPER])
    def test_paper_and_backtest_never_pass(self, mode: TradingMode) -> None:
        result = evaluate_gate(
            mode,
            env(mode, ENABLE_LIVE_TRADING=True, ENABLE_DEMO_TRADING=True),
            account=account(TradingMode.LIVE),
            terminal=TERMINAL,
            risk_config_ok=True,
            kill_switch_active=False,
        )
        assert not result.passed
        assert result.reason is Reason.ORDERS_NOT_ALLOWED_IN_MODE

    def test_confirmation_is_bound_to_the_login(self) -> None:
        other = run(TradingMode.LIVE, set())
        assert other.passed
        moved = evaluate_gate(
            TradingMode.LIVE,
            env(
                TradingMode.LIVE,
                MT5_LOGIN=LOGIN + 1,
                ENABLE_LIVE_TRADING=True,
                LIVE_TRADING_CONFIRMATION=confirmation_phrase(LOGIN),
            ),
            account=account(TradingMode.LIVE, login=LOGIN + 1),
            terminal=TERMINAL,
            risk_config_ok=True,
            kill_switch_active=False,
        )
        assert moved.failed_conditions == {G.CONFIRMATION}

    def test_missing_snapshots_fail_closed(self) -> None:
        result = evaluate_gate(
            TradingMode.LIVE,
            env(
                TradingMode.LIVE,
                ENABLE_LIVE_TRADING=True,
                LIVE_TRADING_CONFIRMATION=confirmation_phrase(LOGIN),
            ),
            account=None,
            terminal=None,
            risk_config_ok=True,
            kill_switch_active=False,
        )
        assert result.failed_conditions == {G.ACCOUNT_VERIFIED}

    def test_env_mode_must_match(self) -> None:
        result = evaluate_gate(
            TradingMode.LIVE,
            env(
                TradingMode.DEMO,
                ENABLE_LIVE_TRADING=True,
                LIVE_TRADING_CONFIRMATION=confirmation_phrase(LOGIN),
            ),
            account=account(TradingMode.LIVE),
            terminal=TERMINAL,
            risk_config_ok=True,
            kill_switch_active=False,
        )
        assert G.MODE in result.failed_conditions


LOCAL = RiskConfig()


class TestEffectiveLimits:
    def test_no_profile_is_the_local_config(self) -> None:
        assert effective_risk(LOCAL, None) is LOCAL

    def test_profile_can_only_tighten(self) -> None:
        offensive = ProfileLimits(
            risk_per_trade_percent=1.5,
            total_open_risk_percent=4.0,
            max_open_positions=5,
            max_daily_loss_percent=4.0,
            min_risk_reward=1.2,
        )
        eff = effective_risk(LOCAL, offensive)
        assert eff.max_risk_per_trade_percent == LOCAL.max_risk_per_trade_percent
        assert eff.max_total_open_risk_percent == LOCAL.max_total_open_risk_percent
        assert eff.max_open_positions == LOCAL.max_open_positions
        assert eff.max_daily_loss_percent == LOCAL.max_daily_loss_percent
        assert eff.min_risk_reward == LOCAL.min_risk_reward

    def test_defensive_profile_applies(self) -> None:
        defensive = ProfileLimits(0.25, 0.5, 1, 1.0, 2.5)
        eff = effective_risk(LOCAL, defensive)
        assert (eff.max_risk_per_trade_percent, eff.max_total_open_risk_percent) == (0.25, 0.5)
        assert (eff.max_open_positions, eff.max_daily_loss_percent, eff.min_risk_reward) == (1, 1.0, 2.5)

    def test_coherence_is_restored_by_lowering(self) -> None:
        eff = effective_risk(LOCAL, ProfileLimits(max_daily_loss_percent=0.3))
        assert eff.max_risk_per_trade_percent == 0.3  # lowered to the daily cap, never the cap raised

    @pytest.mark.parametrize(
        "bad", [{"risk_per_trade_percent": 0.0}, {"min_risk_reward": float("nan")}, {"max_open_positions": 0}]
    )
    def test_malformed_profiles_are_rejected(self, bad: dict[str, float]) -> None:
        with pytest.raises(ValueError):
            ProfileLimits(**bad)  # type: ignore[arg-type]

    @settings(max_examples=200, deadline=None)
    @given(
        risk=st.one_of(st.none(), st.floats(0.01, 50)),
        heat=st.one_of(st.none(), st.floats(0.01, 50)),
        positions=st.one_of(st.none(), st.integers(1, 100)),
        daily=st.one_of(st.none(), st.floats(0.01, 50)),
        rr=st.one_of(st.none(), st.floats(0.1, 10)),
    )
    def test_never_raises_a_local_limit(
        self,
        risk: float | None,
        heat: float | None,
        positions: int | None,
        daily: float | None,
        rr: float | None,
    ) -> None:
        eff = effective_risk(LOCAL, ProfileLimits(risk, heat, positions, daily, rr))
        assert eff.max_risk_per_trade_percent <= LOCAL.max_risk_per_trade_percent
        assert eff.max_total_open_risk_percent <= LOCAL.max_total_open_risk_percent
        assert eff.max_open_positions <= LOCAL.max_open_positions
        assert eff.max_daily_loss_percent <= LOCAL.max_daily_loss_percent
        assert eff.min_risk_reward >= LOCAL.min_risk_reward
        unchanged = {
            "max_lot",
            "max_weekly_loss_percent",
            "max_account_drawdown_percent",
            "max_spread_points",
        }
        assert all(getattr(eff, f) == getattr(LOCAL, f) for f in unchanged)
