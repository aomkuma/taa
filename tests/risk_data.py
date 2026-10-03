"""Test doubles for the risk layer: a tick-value profit calculator and account funds."""

from __future__ import annotations

import dataclasses

from app.core.enums import Side
from app.market_data.data_models import SymbolSpec
from app.risk.position_sizer import AccountFunds
from tests.strategy_data import EURUSD_SPEC

XAUUSD_SPEC = dataclasses.replace(
    EURUSD_SPEC,
    name="XAUUSD",
    description="Gold",
    digits=2,
    point=0.01,
    tick_size=0.01,
    tick_value=1.0,
    tick_value_profit=1.0,
    tick_value_loss=1.0,
    contract_size=100,
    volume_max=50.0,
    currency_base="XAU",
    currency_margin="XAU",
)


class TickCalculator:
    """``calc_profit`` from tick value (what MT5 does for a USD-quoted symbol); ``skew`` breaks it on purpose."""

    def __init__(self, *specs: SymbolSpec, leverage: float = 100.0, skew: float = 1.0) -> None:
        self.specs = {s.name: s for s in (specs or (EURUSD_SPEC, XAUUSD_SPEC))}
        self.leverage = leverage
        self.skew = skew
        self.profit_none = False
        self.margin_none = False

    def calc_profit(
        self, side: Side, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None:
        if self.profit_none:
            return None
        spec = self.specs[symbol]
        ticks = (price_close - price_open) / spec.tick_size
        return ticks * spec.tick_value * side.sign * volume * self.skew

    def calc_margin(self, side: Side, symbol: str, volume: float, price: float) -> float | None:
        if self.margin_none:
            return None
        spec = self.specs[symbol]
        return volume * spec.contract_size * price / self.leverage


def funds(equity: float = 10_000.0, balance: float | None = None, margin: float = 0.0) -> AccountFunds:
    bal = equity if balance is None else balance
    return AccountFunds(equity=equity, balance=bal, margin=margin, margin_free=equity - margin)
