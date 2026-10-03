"""Typed snapshots of terminal, account, positions and deals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.broker import mt5_constants as c
from app.core.enums import Side


@dataclass(frozen=True, slots=True)
class TerminalSnapshot:
    connected: bool
    trade_allowed: bool  # "Algo Trading" button
    tradeapi_disabled: bool  # "Disable automatic trading via external Python API"
    dlls_allowed: bool
    build: int
    maxbars: int
    ping_last_us: int
    company: str
    name: str
    path: str
    data_path: str


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    login: int
    server: str
    company: str
    name: str
    currency: str
    leverage: int
    trade_mode: int  # ACCOUNT_TRADE_MODE_*
    margin_mode: int  # ACCOUNT_MARGIN_MODE_*
    trade_allowed: bool  # False when logged in with the investor password
    trade_expert: bool
    balance: float
    equity: float
    profit: float
    credit: float
    margin: float
    margin_free: float
    margin_level: float
    margin_so_call: float
    margin_so_so: float
    margin_so_mode: int
    captured_at_utc: datetime

    @property
    def trade_mode_name(self) -> str:
        return c.ACCOUNT_TRADE_MODE_NAMES.get(self.trade_mode, str(self.trade_mode))

    @property
    def margin_mode_name(self) -> str:
        return c.MARGIN_MODE_NAMES.get(self.margin_mode, str(self.margin_mode))

    @property
    def is_hedging(self) -> bool:
        return self.margin_mode == c.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING

    def identity(self) -> tuple[int, str, int, str, int]:
        """Fields that must never change during a run (account-change detection).

        Leverage is deliberately excluded: FBS adjusts Forex leverage automatically by equity tier
        (1:3000 below $200 ... 1:500 from $30k), so a leverage change is expected and is handled as a
        warning plus margin re-check, not as a different account.
        """
        return (self.login, self.server, self.trade_mode, self.currency, self.margin_mode)


@dataclass(frozen=True, slots=True)
class BrokerPosition:
    ticket: int
    symbol: str
    side: Side
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    profit: float
    swap: float
    magic: int
    comment: str
    time_utc: datetime
    identifier: int


@dataclass(frozen=True, slots=True)
class Deal:
    ticket: int
    order: int
    position_id: int
    symbol: str
    type: int  # DEAL_TYPE_*
    entry: int  # DEAL_ENTRY_*
    volume: float
    price: float
    profit: float
    commission: float
    swap: float
    fee: float
    magic: int
    comment: str
    time_utc: datetime

    @property
    def is_cash_flow(self) -> bool:
        return self.type in c.CASH_FLOW_DEAL_TYPES

    @property
    def net(self) -> float:
        return self.profit + self.commission + self.swap + self.fee
