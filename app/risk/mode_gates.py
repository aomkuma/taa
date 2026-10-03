"""Mode gates for broker orders (PLAN §A3; TAA-406). Evaluated, logged and tested in Milestone 1, but **not
wired to any order path**: Milestone 1 never sends broker orders.

The gate lives in the risk layer (not ``app/security`` as the PLAN layout sketch has it) because it reuses
the broker-layer identity check (``verify_identity``), which a lower layer may not import.

**LIVE** passes only when every condition holds:

1. ``TRADING_MODE=LIVE``
2. ``ENABLE_LIVE_TRADING=true``
3. ``LIVE_TRADING_CONFIRMATION == "I-ACCEPT-LIVE-RISK-<MT5_LOGIN>"`` (the phrase is bound to the account)
4. account, terminal and symbol validation: identity verified, account trade mode REAL, ``trade_allowed`` and
   ``trade_expert`` on the account, ``trade_allowed`` on the terminal and ``tradeapi_disabled`` off
5. the risk configuration is valid
6. the kill switch is inactive and no breaker is latched

**DEMO** mirrors it with ``ENABLE_DEMO_TRADING``, a DEMO account and no confirmation phrase. BACKTEST and
PAPER never pass (``ORDERS_NOT_ALLOWED_IN_MODE``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.broker import mt5_constants as c
from app.broker.models import AccountSnapshot, TerminalSnapshot
from app.broker.verification import verify_identity
from app.config import EnvSettings
from app.core.enums import TradingMode
from app.risk.reasons import Reason


class GateCondition(StrEnum):
    MODE = "MODE"
    ENABLE_FLAG = "ENABLE_FLAG"
    CONFIRMATION = "CONFIRMATION"
    ACCOUNT_VERIFIED = "ACCOUNT_VERIFIED"
    ACCOUNT_TRADE_MODE = "ACCOUNT_TRADE_MODE"
    ACCOUNT_PERMISSIONS = "ACCOUNT_PERMISSIONS"
    TERMINAL_PERMISSIONS = "TERMINAL_PERMISSIONS"
    RISK_CONFIG = "RISK_CONFIG"
    KILL_SWITCH = "KILL_SWITCH"
    BREAKERS = "BREAKERS"


@dataclass(frozen=True, slots=True)
class GateResult:
    mode: TradingMode
    failures: tuple[tuple[GateCondition, str], ...]

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def reason(self) -> Reason | None:
        if self.passed:
            return None
        if any(cond is GateCondition.MODE for cond, _ in self.failures):
            return Reason.ORDERS_NOT_ALLOWED_IN_MODE
        return Reason.LIVE_GATE_FAILED

    @property
    def failed_conditions(self) -> set[GateCondition]:
        return {cond for cond, _ in self.failures}


def confirmation_phrase(login: int | None) -> str:
    return f"I-ACCEPT-LIVE-RISK-{login}"


def evaluate_gate(
    mode: TradingMode,
    env: EnvSettings,
    *,
    account: AccountSnapshot | None,
    terminal: TerminalSnapshot | None,
    risk_config_ok: bool,
    kill_switch_active: bool,
    latched_breakers: Sequence[str] = (),
) -> GateResult:
    if not mode.may_send_broker_orders:
        return GateResult(mode, ((GateCondition.MODE, f"{mode.value} never sends broker orders"),))
    live = mode is TradingMode.LIVE
    failures: list[tuple[GateCondition, str]] = []

    def need(condition: GateCondition, ok: bool, detail: str) -> None:
        if not ok:
            failures.append((condition, detail))

    if env.TRADING_MODE is not mode:
        failures.append(
            (GateCondition.MODE, f"TRADING_MODE is {env.TRADING_MODE.value}, gate asked for {mode.value}")
        )
    if live:
        need(GateCondition.ENABLE_FLAG, env.ENABLE_LIVE_TRADING, "ENABLE_LIVE_TRADING is not true")
        need(
            GateCondition.CONFIRMATION,
            env.MT5_LOGIN is not None and confirmation_phrase(env.MT5_LOGIN) == env.LIVE_TRADING_CONFIRMATION,
            "LIVE_TRADING_CONFIRMATION does not match the phrase for MT5_LOGIN",
        )
    else:
        need(GateCondition.ENABLE_FLAG, env.ENABLE_DEMO_TRADING, "ENABLE_DEMO_TRADING is not true")
    if account is None or terminal is None:
        failures.append((GateCondition.ACCOUNT_VERIFIED, "no account or terminal snapshot"))
    else:
        identity = verify_identity(env, account, terminal)
        need(GateCondition.ACCOUNT_VERIFIED, not identity, "; ".join(identity))
        expected = c.ACCOUNT_TRADE_MODE_REAL if live else c.ACCOUNT_TRADE_MODE_DEMO
        needed = c.ACCOUNT_TRADE_MODE_NAMES[expected]
        need(
            GateCondition.ACCOUNT_TRADE_MODE,
            account.trade_mode == expected,
            f"account is {account.trade_mode_name}, {mode.value} needs {needed}",
        )
        need(
            GateCondition.ACCOUNT_PERMISSIONS,
            account.trade_allowed and account.trade_expert,
            "account trade_allowed / trade_expert is off (investor password or broker restriction)",
        )
        need(
            GateCondition.TERMINAL_PERMISSIONS,
            terminal.trade_allowed and not terminal.tradeapi_disabled,
            "terminal Algo Trading is off or the Python API is disabled",
        )
    need(GateCondition.RISK_CONFIG, risk_config_ok, "risk configuration is invalid")
    need(GateCondition.KILL_SWITCH, not kill_switch_active, "kill switch is active")
    need(GateCondition.BREAKERS, not latched_breakers, f"latched breakers: {', '.join(latched_breakers)}")
    return GateResult(mode, tuple(failures))
