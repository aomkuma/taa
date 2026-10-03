"""Post-connection verification: the terminal/account must match configuration and the mode's rules.

``initialize()`` silently uses the terminal's *last* account when no login is passed, and this
machine's terminal has used both FBS-Demo and FBS-Real. Verifying identity after every (re)connect
is what prevents trading the wrong account.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.broker import mt5_constants as c
from app.broker.models import AccountSnapshot, TerminalSnapshot
from app.config import EnvSettings
from app.core.enums import TradingMode
from app.security.redaction import mask_login


@dataclass
class VerificationResult:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _same_server(a: str | None, b: str | None) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def verify_connection(
    mode: TradingMode, env: EnvSettings, account: AccountSnapshot, terminal: TerminalSnapshot
) -> VerificationResult:
    r = VerificationResult()
    if not terminal.connected:
        r.problems.append("terminal is not connected to the trade server")
    if env.MT5_LOGIN is not None and account.login != env.MT5_LOGIN:
        r.problems.append(
            f"connected account {mask_login(account.login)} does not match "
            f"MT5_LOGIN {mask_login(env.MT5_LOGIN)}"
        )
    if env.MT5_SERVER and not _same_server(account.server, env.MT5_SERVER):
        r.problems.append(f"connected server {account.server!r} does not match MT5_SERVER {env.MT5_SERVER!r}")
    if not account.is_hedging:
        r.problems.append(
            f"account margin mode is {account.margin_mode_name}; only HEDGING accounts are supported"
        )
    if not account.currency:
        r.problems.append("account currency is empty")

    if mode is TradingMode.PAPER:
        if account.trade_allowed:
            msg = (
                "PAPER mode is connected with a trading-capable (master) password; use the investor "
                "password for least privilege"
            )
            (r.warnings if env.PAPER_ALLOW_MASTER_PASSWORD else r.problems).append(
                msg + ("" if env.PAPER_ALLOW_MASTER_PASSWORD else " or set PAPER_ALLOW_MASTER_PASSWORD=true")
            )
    elif mode in (TradingMode.DEMO, TradingMode.LIVE):
        required = c.ACCOUNT_TRADE_MODE_DEMO if mode is TradingMode.DEMO else c.ACCOUNT_TRADE_MODE_REAL
        if account.trade_mode != required:
            r.problems.append(
                f"{mode} mode requires a {c.ACCOUNT_TRADE_MODE_NAMES[required]} account, "
                f"but the connected account is {account.trade_mode_name}"
            )
        if mode is TradingMode.DEMO and not env.ENABLE_DEMO_TRADING:
            r.problems.append("DEMO mode requires ENABLE_DEMO_TRADING=true")
        if not account.trade_allowed:
            r.problems.append("trading is not allowed for this login (investor password?)")
        if not account.trade_expert:
            r.problems.append("expert/algorithmic trading is disabled for this account")
        if not terminal.trade_allowed:
            r.problems.append("'Algo Trading' is disabled in the terminal")
        if terminal.tradeapi_disabled:
            r.problems.append("trading via the external Python API is disabled in terminal options")

    if account.leverage >= 1000:
        r.warnings.append(
            f"account leverage is 1:{account.leverage}; position sizing is risk-based, not leverage-based"
        )
    return r
