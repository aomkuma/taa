"""A :class:`ProfitCalculator` from symbol specs and conversion rates, without a broker (PLAN §A30 "Account
profiles"; TAA-8A3).

The cloud sizes trades for accounts it cannot reach (a user's MANUAL account profile): the replicated spec
snapshot gives contract size, currencies and calculation mode; *rate* converts a currency into the account's
currency (from the engine's latest closes, :class:`app.web.account_profiles.HistoryRates`). The formulas are
the simulated broker's, which the backtests already check against MT5's:

- profit = (close − open) × side × volume × contract size, in the profit currency, converted
- margin = FX: volume × contract size in the margin currency, converted, ÷ leverage; CFDs and metals:
  |price| × volume × contract size in the profit currency, converted, ÷ leverage

:meth:`spec_for` re-derives the tick values in the account's currency, so the sizer's tick-value
cross-check compares like with like. Any missing rate returns ``None``, which the sizer turns into a refusal
(fail closed).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping

from app.core.enums import Side
from app.market_data.data_models import SymbolSpec

RateFn = Callable[[str], float | None]  # currency → units of the account currency per unit


class SpecCalculator:
    def __init__(
        self, specs: Mapping[str, SymbolSpec], account_currency: str, leverage: float, rate: RateFn
    ) -> None:
        if leverage <= 0:
            raise ValueError("leverage must be positive")
        self.specs = specs
        self.account_currency = account_currency.upper()
        self.leverage = leverage
        self._rate_fn = rate

    def rate(self, currency: str) -> float | None:
        if currency.upper() == self.account_currency:
            return 1.0
        value = self._rate_fn(currency.upper())
        return value if value is not None and value > 0 else None

    def calc_profit(
        self, side: Side, symbol: str, volume: float, price_open: float, price_close: float
    ) -> float | None:
        spec = self.specs.get(symbol)
        rate = None if spec is None else self.rate(spec.currency_profit)
        if spec is None or rate is None:
            return None
        return (price_close - price_open) * side.sign * volume * spec.contract_size * rate

    def calc_margin(self, side: Side, symbol: str, volume: float, price: float) -> float | None:
        spec = self.specs.get(symbol)
        if spec is None:
            return None
        if spec.currency_margin != spec.currency_profit:  # FX: the base-currency notional
            rate = self.rate(spec.currency_margin)
            notional = None if rate is None else volume * spec.contract_size * rate
        else:  # CFDs and metals priced in the margin currency; a negative print is not a credit
            rate = self.rate(spec.currency_profit)
            notional = None if rate is None else volume * spec.contract_size * abs(price) * rate
        return None if notional is None else notional / self.leverage

    def spec_for(self, symbol: str) -> SymbolSpec | None:
        """The spec with tick values in the account currency (None: unknown symbol or no rate)."""
        spec = self.specs.get(symbol)
        rate = None if spec is None else self.rate(spec.currency_profit)
        if spec is None or rate is None:
            return None
        tick_value = spec.tick_size * spec.contract_size * rate
        return dataclasses.replace(
            spec, tick_value=tick_value, tick_value_profit=tick_value, tick_value_loss=tick_value
        )
