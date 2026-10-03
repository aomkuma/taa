"""Domain enumerations shared by every layer."""

from __future__ import annotations

from enum import StrEnum


class TradingMode(StrEnum):
    """Runtime mode. Selected only from configuration; never inferred."""

    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    DEMO = "DEMO"
    LIVE = "LIVE"

    @property
    def uses_live_market_data(self) -> bool:
        return self is not TradingMode.BACKTEST

    @property
    def may_send_broker_orders(self) -> bool:
        """Only DEMO and LIVE can ever reach a broker order path (Milestone 2)."""
        return self in (TradingMode.DEMO, TradingMode.LIVE)


class Action(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"
    MODIFY = "MODIFY"

    @property
    def is_entry(self) -> bool:
        return self in (Action.BUY, Action.SELL)


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def sign(self) -> int:
        return 1 if self is Side.BUY else -1

    @property
    def opposite(self) -> Side:
        return Side.SELL if self is Side.BUY else Side.BUY

    @classmethod
    def from_action(cls, action: Action) -> Side:
        if action is Action.BUY:
            return cls.BUY
        if action is Action.SELL:
            return cls.SELL
        raise ValueError(f"action {action} has no side")


class EntryType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class Trend(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Regime(StrEnum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    UNCLEAR = "UNCLEAR"


class VolatilityState(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Timeframe(StrEnum):
    """Supported bar timeframes. Values match MetaTrader 5 naming."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    @property
    def seconds(self) -> int:
        return _TF_SECONDS[self]

    @property
    def minutes(self) -> int:
        return self.seconds // 60

    @property
    def bars_per_year(self) -> float:
        """Approximate bars per year for a 24x5 market (260 trading days)."""
        return 260 * 86_400 / self.seconds


_TF_SECONDS: dict[Timeframe, int] = {
    Timeframe.M1: 60,
    Timeframe.M5: 300,
    Timeframe.M15: 900,
    Timeframe.M30: 1800,
    Timeframe.H1: 3600,
    Timeframe.H4: 14_400,
    Timeframe.D1: 86_400,
}


class ExitReason(StrEnum):
    TAKE_PROFIT = "TP"
    STOP_LOSS = "SL"
    BREAK_EVEN = "BE"
    TRAILING_STOP = "TRAIL"
    TIME_STOP = "TIME"
    SIGNAL = "SIGNAL"
    KILL_SWITCH = "KILL_SWITCH"
    MANUAL = "MANUAL"
    STOP_OUT = "STOP_OUT"
    END_OF_DATA = "END_OF_DATA"


class Session(StrEnum):
    ASIA = "ASIA"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    LONDON_NY_OVERLAP = "LONDON_NY_OVERLAP"
    OFF = "OFF"
