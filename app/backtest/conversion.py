"""Currency conversion series for backtests (PLAN §A17 "Currency conversion"; TAA-503).

A P/L or margin in a currency other than the account currency is converted with the **last close at or
before** the time of the price that produced it (no look-ahead). A currency is priced by a conversion symbol:

- direct: ``<CUR><ACCOUNT>`` (EURUSD prices EUR in USD);
- inverse: ``<ACCOUNT><CUR>`` (USDJPY prices JPY as 1 / close);
- cross: through one intermediate currency with both legs available (CHF via EURCHF and EURUSD).

A currency that no available series can price has no rate: the simulated broker then refuses to value the
trade, and :func:`missing_currencies` lets the CLI say which history to download first.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from app.core.clock import ensure_utc
from app.market_data.data_models import SymbolSpec


@dataclass(frozen=True)
class _Series:
    times: np.ndarray  # close times, int64 nanoseconds UTC, ascending
    closes: np.ndarray

    def at(self, when: datetime) -> float | None:
        key = pd.Timestamp(ensure_utc(when)).as_unit("ns").value
        pos = int(np.searchsorted(self.times, key, side="right")) - 1
        if pos < 0:
            return None
        value = float(self.closes[pos])
        return value if np.isfinite(value) and value > 0 else None


class SeriesRates:
    """A :class:`~app.execution.simulated_broker.RateSource` backed by close series of conversion symbols."""

    def __init__(self, account_currency: str, pairs: Mapping[str, tuple[str, str, pd.DataFrame]]) -> None:
        """*pairs*: symbol -> (base currency, quote currency, candles with ``close_time`` and ``close``)."""
        self.account = account_currency
        self._legs: dict[tuple[str, str], _Series] = {}
        for base, quote, candles in pairs.values():
            index = pd.DatetimeIndex(pd.to_datetime(candles["close_time"], utc=True)).as_unit("ns")
            times = index.to_numpy(dtype="datetime64[ns]").astype(np.int64)
            order = np.argsort(times, kind="stable")
            self._legs[(base, quote)] = _Series(times[order], candles["close"].to_numpy(dtype=float)[order])

    @classmethod
    def from_specs(
        cls, account_currency: str, specs: Mapping[str, SymbolSpec], candles: Mapping[str, pd.DataFrame]
    ) -> SeriesRates:
        pairs = {
            name: (specs[name].currency_base, specs[name].currency_profit, df)
            for name, df in candles.items()
            if name in specs
        }
        return cls(account_currency, pairs)

    def _direct(self, cur: str, to: str, at: datetime) -> float | None:
        if cur == to:
            return 1.0
        series = self._legs.get((cur, to))
        if series is not None:
            return series.at(at)
        inverse = self._legs.get((to, cur))
        if inverse is not None:
            value = inverse.at(at)
            return None if value is None else 1.0 / value
        return None

    def rate(self, currency: str, at: datetime) -> float | None:
        direct = self._direct(currency, self.account, at)
        if direct is not None:
            return direct
        for mid in self.currencies():
            if mid in (currency, self.account):
                continue
            first = self._direct(currency, mid, at)
            second = None if first is None else self._direct(mid, self.account, at)
            if first is not None and second is not None:
                return first * second
        return None

    def currencies(self) -> list[str]:
        return sorted({c for pair in self._legs for c in pair})

    def _linked(self, a: str, b: str) -> bool:
        return a == b or (a, b) in self._legs or (b, a) in self._legs

    def can_price(self, currency: str) -> bool:
        """Whether a direct or one-hop path to the account currency exists (whatever the time)."""
        if self._linked(currency, self.account):
            return True
        return any(
            self._linked(currency, mid) and self._linked(mid, self.account) for mid in self.currencies()
        )


def needed_currencies(specs: Iterable[SymbolSpec], account_currency: str) -> set[str]:
    """Profit and margin currencies of the traded symbols that are not the account currency."""
    out: set[str] = set()
    for spec in specs:
        out |= {spec.currency_profit, spec.currency_margin}
    out.discard(account_currency)
    return out


def missing_currencies(
    specs: Iterable[SymbolSpec], rates: SeriesRates, traded: Iterable[SymbolSpec] = ()
) -> list[str]:
    """Currencies that neither a traded symbol nor a conversion series can price."""
    traded_pairs = {(s.currency_base, s.currency_profit) for s in traded}
    return [
        cur
        for cur in sorted(needed_currencies(specs, rates.account))
        if (cur, rates.account) not in traded_pairs
        and (rates.account, cur) not in traded_pairs
        and not rates.can_price(cur)
    ]
