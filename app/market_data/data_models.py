"""Typed market-data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.broker import mt5_constants as c
from app.core.enums import Timeframe

CANDLE_COLUMNS = [
    "open_time",
    "close_time",
    "time_server",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
]


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    """Broker specification of one instrument, validated at runtime (never assumed)."""

    name: str
    description: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    tick_value_profit: float
    tick_value_loss: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    volume_limit: float
    stops_level: int  # points
    freeze_level: int  # points
    filling_mode: int  # SYMBOL_FILLING_* bitmask
    trade_mode: int  # SYMBOL_TRADE_MODE_*
    execution_mode: int  # SYMBOL_TRADE_EXECUTION_*
    chart_mode: int
    currency_base: str
    currency_profit: str
    currency_margin: str
    spread_points: int
    spread_float: bool
    swap_long: float
    swap_short: float
    swap_rollover3days: int
    calc_mode: int
    path: str = ""

    @property
    def can_buy(self) -> bool:
        return self.trade_mode in (c.SYMBOL_TRADE_MODE_FULL, c.SYMBOL_TRADE_MODE_LONGONLY)

    @property
    def can_sell(self) -> bool:
        return self.trade_mode in (c.SYMBOL_TRADE_MODE_FULL, c.SYMBOL_TRADE_MODE_SHORTONLY)

    @property
    def trading_enabled(self) -> bool:
        return self.trade_mode != c.SYMBOL_TRADE_MODE_DISABLED

    def validation_errors(self) -> list[str]:
        """Inconsistent or missing broker data means the symbol must not be traded."""
        errors: list[str] = []
        positives = {
            "point": self.point,
            "tick_size": self.tick_size,
            "tick_value": self.tick_value,
            "contract_size": self.contract_size,
            "volume_min": self.volume_min,
            "volume_max": self.volume_max,
            "volume_step": self.volume_step,
        }
        errors += [f"{k} must be > 0 (got {v})" for k, v in positives.items() if not v or v <= 0]
        if self.digits < 0 or self.digits > 10:
            errors.append(f"implausible digits {self.digits}")
        if self.volume_min and self.volume_max and self.volume_min > self.volume_max:
            errors.append("volume_min > volume_max")
        if self.tick_value_loss is not None and self.tick_value_loss < 0:
            errors.append("negative tick_value_loss")
        if self.stops_level < 0 or self.freeze_level < 0:
            errors.append("negative stops/freeze level")
        if self.chart_mode != c.SYMBOL_CHART_MODE_BID:
            errors.append("chart_mode is not BID; bar prices would not be bid-based")
        if not self.currency_profit:
            errors.append("missing profit currency")
        return errors


@dataclass(frozen=True, slots=True)
class Tick:
    symbol: str
    time_server_msc: int
    time_utc: datetime
    bid: float
    ask: float
    last: float = 0.0


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    spread_points: float
    time_utc: datetime
    age_seconds: float
    valid: bool
    problem: str = ""

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass(slots=True)
class QualityReport:
    ok: bool = True
    flags: list[str] = field(default_factory=list)
    missing_bars: int = 0
    unexpected_gaps: list[tuple[datetime, datetime, int]] = field(default_factory=list)
    invalid_rows: int = 0
    stale: bool = False

    def add(self, flag: str) -> None:
        self.flags.append(flag)
        self.ok = False


@dataclass(slots=True)
class CandleFrame:
    """Closed candles for one symbol/timeframe. ``df`` columns: :data:`CANDLE_COLUMNS`."""

    symbol: str
    timeframe: Timeframe
    df: pd.DataFrame
    quality: QualityReport
    fetched_at_utc: datetime

    @property
    def last_close_time(self) -> datetime | None:
        if self.df.empty:
            return None
        return pd.Timestamp(self.df["close_time"].iloc[-1]).to_pydatetime()

    @property
    def last_open_time(self) -> datetime | None:
        if self.df.empty:
            return None
        return pd.Timestamp(self.df["open_time"].iloc[-1]).to_pydatetime()

    def __len__(self) -> int:
        return len(self.df)
