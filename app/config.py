"""Configuration: secrets and safety flags from the environment, parameters from ``config.yaml``.

Precedence: environment variables > ``config.yaml`` > code defaults.
Risk values are expressed in **percent of equity** (``0.5`` means 0.5%) and are bounded by hard
ceilings; a value above a ceiling stops startup instead of being clamped silently.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from dotenv import dotenv_values
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import Timeframe, TradingMode
from app.core.errors import ConfigError
from app.core.ids import stable_hash

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Hard ceilings: configuration above these values is rejected at startup.
CEILING_RISK_PER_TRADE_PCT = 2.0
CEILING_DAILY_LOSS_PCT = 10.0
CEILING_WEEKLY_LOSS_PCT = 20.0
CEILING_DRAWDOWN_PCT = 50.0
CEILING_TOTAL_OPEN_RISK_PCT = 10.0


class StrictModel(BaseModel):
    """Immutable model that rejects unknown keys (typos must not be silently ignored)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _parse_hhmm(value: str) -> time:
    try:
        hours, minutes = value.split(":")
        return time(int(hours), int(minutes))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"expected HH:MM, got {value!r}") from exc


# ============================================================================ yaml sections
class SymbolOverride(StrictModel):
    max_spread_points: float | None = Field(default=None, gt=0)
    max_lot: float | None = Field(default=None, gt=0)
    commission_per_lot: float | None = Field(default=None, ge=0, description="round turn, account currency")
    daily_breaks_utc: list[str] = Field(default_factory=list, description='e.g. ["21:00-22:05"]')

    @field_validator("daily_breaks_utc")
    @classmethod
    def _check_breaks(cls, value: list[str]) -> list[str]:
        for item in value:
            start, _, end = item.partition("-")
            _parse_hhmm(start)
            _parse_hhmm(end)
        return value


class SymbolsConfig(StrictModel):
    allowed: list[str] = Field(default_factory=lambda: ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"], min_length=1)
    reference_symbol: str = Field(default="EURUSD", description="liquid symbol used to verify server time")
    clock_fallback_symbols: list[str] = Field(
        default_factory=lambda: ["BTCUSD", "ETHUSD"],
        max_length=5,
        description="24/7 symbols that verify server time while the reference symbol's market is closed",
    )
    overrides: dict[str, SymbolOverride] = Field(default_factory=dict)

    @field_validator("allowed", "clock_fallback_symbols")
    @classmethod
    def _normalize(cls, value: list[str]) -> list[str]:
        cleaned = [s.strip() for s in value if s.strip()]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("duplicate symbols in list")
        return cleaned

    @property
    def clock_symbols(self) -> list[str]:
        """Symbols to verify server time with, in order of preference."""
        return [
            self.reference_symbol,
            *(s for s in self.clock_fallback_symbols if s != self.reference_symbol),
        ]


class TimeframesConfig(StrictModel):
    higher: Timeframe = Timeframe.H1
    entry: Timeframe = Timeframe.M15
    refinement: Timeframe | None = None
    warmup_bars: int = Field(default=400, ge=50, le=20_000)
    candle_close_grace_seconds: float = Field(default=3.0, ge=0, le=60)
    stale_tick_seconds: float = Field(default=120.0, gt=0)
    max_gap_bars: int = Field(default=3, ge=0)

    @model_validator(mode="after")
    def _order(self) -> TimeframesConfig:
        if self.higher.seconds <= self.entry.seconds:
            raise ValueError("higher timeframe must be longer than the entry timeframe")
        if self.refinement and self.refinement.seconds >= self.entry.seconds:
            raise ValueError("refinement timeframe must be shorter than the entry timeframe")
        return self

    @property
    def enabled(self) -> list[Timeframe]:
        tfs = [self.higher, self.entry]
        if self.refinement:
            tfs.append(self.refinement)
        return tfs


class IndicatorParams(StrictModel):
    ema_fast: int = Field(default=20, ge=2)
    ema_mid: int = Field(default=50, ge=2)
    ema_slow: int = Field(default=200, ge=2)
    rsi_period: int = Field(default=14, ge=2)
    atr_period: int = Field(default=14, ge=2)
    adx_period: int = Field(default=14, ge=2)
    macd_fast: int = Field(default=12, ge=2)
    macd_slow: int = Field(default=26, ge=3)
    macd_signal: int = Field(default=9, ge=2)
    stoch_k: int = Field(default=14, ge=2)
    stoch_k_smooth: int = Field(default=3, ge=1)
    stoch_d: int = Field(default=3, ge=1)
    cci_period: int = Field(default=20, ge=2)
    bb_period: int = Field(default=20, ge=2)
    bb_k: float = Field(default=2.0, gt=0)
    hv_period: int = Field(default=20, ge=2)
    atr_percentile_lookback: int = Field(default=100, ge=10)
    volume_sma_period: int = Field(default=20, ge=2)
    swing_k: int = Field(default=3, ge=1, le=20)
    sr_tolerance_atr: float = Field(default=0.5, gt=0)
    breakout_buffer_atr: float = Field(default=0.1, ge=0)
    false_breakout_bars: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def _ordering(self) -> IndicatorParams:
        if not self.ema_fast < self.ema_mid < self.ema_slow:
            raise ValueError("EMA periods must satisfy ema_fast < ema_mid < ema_slow")
        if self.macd_fast >= self.macd_slow:
            raise ValueError("macd_fast must be shorter than macd_slow")
        return self


class RegimeConfig(StrictModel):
    """Regime and volatility thresholds (PLAN §A7). ADX bands leave a gap where the regime is UNCLEAR."""

    trend_adx: float = Field(default=20.0, gt=0, le=100, description="ADX at or above: TRENDING")
    range_adx: float = Field(default=18.0, gt=0, le=100, description="ADX below: RANGING")
    volatile_atr_percentile: float = Field(default=90.0, gt=0, le=100, description="above: VOLATILE")
    low_atr_percentile: float = Field(default=25.0, ge=0, lt=100, description="below: volatility LOW")
    high_atr_percentile: float = Field(default=75.0, gt=0, le=100, description="above: volatility HIGH")
    extreme_atr_percentile: float = Field(default=90.0, gt=0, le=100, description="above: EXTREME")

    @model_validator(mode="after")
    def _ordering(self) -> RegimeConfig:
        if self.range_adx > self.trend_adx:
            raise ValueError("range_adx must not exceed trend_adx")
        if not self.low_atr_percentile < self.high_atr_percentile <= self.extreme_atr_percentile:
            raise ValueError("ATR percentile bands must satisfy low < high <= extreme")
        return self


class StrategyEntry(StrictModel):
    name: str
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class StrategiesConfig(StrictModel):
    items: list[StrategyEntry] = Field(default_factory=lambda: [StrategyEntry(name="example_trend_pullback")])
    cooldown_bars: int = Field(default=4, ge=0)
    allow_single_indicator_signals: bool = False
    signal_expiry_bars: int = Field(default=1, ge=1)


class RiskConfig(StrictModel):
    max_risk_per_trade_percent: float = Field(default=0.5, gt=0, le=CEILING_RISK_PER_TRADE_PCT)
    max_risk_money_per_trade: float | None = Field(default=None, gt=0)
    max_open_positions: int = Field(default=3, ge=1, le=20)
    max_positions_per_symbol: int = Field(default=1, ge=1, le=5)
    max_total_open_risk_percent: float = Field(default=1.5, gt=0, le=CEILING_TOTAL_OPEN_RISK_PCT)
    max_daily_loss_percent: float = Field(default=2.0, gt=0, le=CEILING_DAILY_LOSS_PCT)
    max_weekly_loss_percent: float = Field(default=4.0, gt=0, le=CEILING_WEEKLY_LOSS_PCT)
    max_account_drawdown_percent: float = Field(default=10.0, gt=0, le=CEILING_DRAWDOWN_PCT)
    max_consecutive_losses: int = Field(default=4, ge=1, le=50)
    consecutive_loss_pause_hours: float = Field(default=24.0, ge=0)
    max_spread_points: float = Field(default=30.0, gt=0)
    max_spread_to_sl_ratio: float = Field(default=0.15, gt=0, le=1)
    max_slippage_points: float = Field(default=10.0, ge=0)
    slippage_allowance_points: float = Field(default=5.0, ge=0)
    min_risk_reward: float = Field(default=1.5, gt=0)
    max_lot: float = Field(default=1.0, gt=0)
    min_lot: float | None = Field(
        default=None, gt=0, description="optional floor stricter than broker minimum"
    )
    min_margin_level_percent: float = Field(default=500.0, ge=100)
    max_margin_utilization_percent: float = Field(default=30.0, gt=0, le=100)
    max_effective_leverage: float = Field(default=10.0, gt=0, le=100)
    require_take_profit: bool = True
    sizing_basis: Literal["min_equity_balance", "equity", "balance"] = "min_equity_balance"
    tick_value_tolerance: float = Field(default=0.10, gt=0, le=0.5)
    max_sl_atr_multiple: float = Field(default=3.0, gt=0)
    price_drift_atr: float = Field(default=0.5, gt=0)
    correlation_groups: dict[str, list[str]] = Field(
        default_factory=lambda: {"EUR_GBP": ["EURUSD", "GBPUSD"]}
    )
    max_same_direction_per_currency: int = Field(default=2, ge=1)
    probation_trades: int = Field(default=20, ge=0)
    probation_multiplier: float = Field(default=0.25, gt=0, le=1)
    foreign_positions_policy: Literal["count", "halt"] = "count"

    @model_validator(mode="after")
    def _coherence(self) -> RiskConfig:
        if self.max_risk_per_trade_percent > self.max_daily_loss_percent:
            raise ValueError("max_risk_per_trade_percent must not exceed max_daily_loss_percent")
        if self.max_daily_loss_percent > self.max_weekly_loss_percent:
            raise ValueError("max_daily_loss_percent must not exceed max_weekly_loss_percent")
        if self.max_total_open_risk_percent < self.max_risk_per_trade_percent:
            raise ValueError("max_total_open_risk_percent must be >= max_risk_per_trade_percent")
        if self.min_lot is not None and self.min_lot > self.max_lot:
            raise ValueError("min_lot must not exceed max_lot")
        return self


class SessionWindow(StrictModel):
    """A trading window in local time of ``timezone`` (an exchange's zone, or UTC), on local ``days``.

    ``start > end`` spans midnight (e.g. 22:00-06:00): the part after midnight belongs to the day it
    started on. DST is handled by the timezone rules, never by fixed UTC offsets (PLAN §A5, TAA-407).
    """

    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], description="0=Monday .. 6=Sunday")
    start: str = "07:00"
    end: str = "20:00"
    timezone: str = "UTC"

    @field_validator("days")
    @classmethod
    def _days(cls, value: list[int]) -> list[int]:
        if not value or any(d < 0 or d > 6 for d in value):
            raise ValueError("days must be integers 0..6")
        return value

    @field_validator("start", "end")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        _parse_hhmm(value)
        return value

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _not_empty(self) -> SessionWindow:
        if self.start == self.end:
            raise ValueError("a session window needs start != end")
        return self

    @property
    def start_time(self) -> time:
        return _parse_hhmm(self.start)

    @property
    def end_time(self) -> time:
        return _parse_hhmm(self.end)


class BlackoutWindow(StrictModel):
    start_utc: datetime
    end_utc: datetime
    currencies: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    reason: str = "manual blackout"

    @model_validator(mode="after")
    def _aware(self) -> BlackoutWindow:
        if self.start_utc.tzinfo is None or self.end_utc.tzinfo is None:
            raise ValueError("blackout times must include a timezone (use Z for UTC)")
        if self.end_utc <= self.start_utc:
            raise ValueError("blackout end must be after start")
        return self


class SessionsConfig(StrictModel):
    default: list[SessionWindow] = Field(default_factory=lambda: [SessionWindow()])
    by_symbol: dict[str, list[SessionWindow]] = Field(default_factory=dict)
    friday_cutoff_utc: str | None = "20:00"
    news_blackouts: list[BlackoutWindow] = Field(default_factory=list)

    @field_validator("friday_cutoff_utc")
    @classmethod
    def _cutoff(cls, value: str | None) -> str | None:
        if value is not None:
            _parse_hhmm(value)
        return value


class PositionManagementConfig(StrictModel):
    break_even_trigger_r: float = Field(default=1.0, gt=0)
    break_even_buffer_points: float = Field(default=2.0, ge=0)
    trailing_start_r: float = Field(default=1.5, gt=0)
    trailing_atr_multiple: float = Field(default=2.0, gt=0)
    time_stop_bars: int | None = Field(default=None, ge=1)
    min_sl_step_points: float = Field(default=5.0, ge=0)
    modify_min_interval_seconds: float = Field(default=10.0, ge=0)


class BreakerConfig(StrictModel):
    connection_grace_seconds: float = Field(default=15.0, gt=0)
    healthy_checks_to_recover: int = Field(default=3, ge=1)
    invalid_price_jump_atr: float = Field(default=5.0, gt=0)
    invalid_price_recovery_seconds: float = Field(default=30.0, ge=0)
    spread_spike_multiple: float = Field(default=3.0, gt=1)
    spread_persist_seconds: float = Field(default=30.0, ge=0)
    spread_recovery_seconds: float = Field(default=60.0, ge=0)
    stale_data_seconds: float = Field(default=120.0, gt=0)
    slippage_cooldown_minutes: float = Field(default=60.0, ge=0)
    exception_cooldown_minutes: float = Field(default=10.0, ge=0)
    exception_max_trips_per_day: int = Field(default=3, ge=1)
    order_failures_max: int = Field(default=3, ge=1)
    order_failures_window_minutes: float = Field(default=15.0, gt=0)
    order_failures_cooldown_minutes: float = Field(default=30.0, ge=0)
    clock_max_drift_seconds: float = Field(default=120.0, gt=0)
    disk_min_free_gb: float = Field(default=1.0, ge=0)


class BacktestConfig(StrictModel):
    initial_balance: float = Field(default=10_000.0, gt=0)
    account_currency: str = "USD"
    commission_per_lot: float = Field(default=0.0, ge=0, description="round turn")
    spread_model: Literal["bar", "fixed"] = "bar"
    fixed_spread_points: float = Field(default=15.0, ge=0)
    min_spread_points: float = Field(default=0.0, ge=0)
    slippage_model: Literal["none", "fixed", "random"] = "fixed"
    slippage_points: float = Field(default=1.0, ge=0)
    swap_enabled: bool = False
    leverage: float = Field(default=100.0, gt=0, le=3000, description="account leverage for simulated margin")
    seed: int = 42


ASSET_CLASSES = (
    "FOREX_MAJOR",
    "FOREX_MINOR",
    "FOREX_EXOTIC",
    "METAL",
    "INDEX",
    "ENERGY",
    "CRYPTO",
    "STOCK",
    "OTHER",
)


class UniverseConfig(StrictModel):
    """Which broker symbols the advisory ranking considers (PLAN §A25). Never the bot's trading allowlist."""

    include: list[str] = Field(default_factory=lambda: ["*"], min_length=1, description="MT5 group patterns")
    exclude: list[str] = Field(default_factory=list)
    classes: dict[str, bool] = Field(
        default_factory=lambda: {c: c not in ("FOREX_EXOTIC", "OTHER") for c in ASSET_CLASSES},
        description="per asset class; exotics and unclassified symbols are opt-in",
    )
    symbols: dict[str, bool] = Field(default_factory=dict, description="per-symbol overrides")
    auto_top_n: int = Field(default=30, ge=0, le=60)
    monitored_cap: int = Field(default=60, ge=1, le=200)
    refresh_hours: float = Field(default=24.0, gt=0, le=168)

    @field_validator("classes")
    @classmethod
    def _known_classes(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = sorted(set(value) - set(ASSET_CLASSES))
        if unknown:
            raise ValueError(f"unknown asset classes {unknown}")
        return {c: value.get(c, c not in ("FOREX_EXOTIC", "OTHER")) for c in ASSET_CLASSES}

    @field_validator("include", "exclude")
    @classmethod
    def _patterns(cls, value: list[str]) -> list[str]:
        if any("," in p or p.startswith("!") for p in value):
            raise ValueError("one pattern per entry, without commas or '!' (use exclude for exclusions)")
        return [p.strip() for p in value if p.strip()]

    @property
    def group(self) -> str:
        """The MT5 ``symbols_get(group=...)`` filter: inclusions first, then exclusions (R22)."""
        return ",".join([*self.include, *(f"!{p}" for p in self.exclude)])


class AdvisorySessionsConfig(StrictModel):
    """Per-symbol session overrides for the ranking (names from ``app.advisory.market_sessions``)."""

    overrides: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("overrides")
    @classmethod
    def _names(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        known = {"SYDNEY", "TOKYO", "LONDON", "NEW_YORK", "EUROPE_EQUITIES", "US_EQUITIES", "CRYPTO"}
        for symbol, names in value.items():
            unknown = sorted(set(names) - known)
            if not names or unknown:
                raise ValueError(f"{symbol}: unknown or empty sessions {unknown}")
        return value


class SuitabilityConfig(StrictModel):
    """Suitability metrics and hard gates G1–G6 (PLAN §A25)."""

    sl_atr_multiple: float = Field(default=1.5, gt=0, le=10, description="typical SL = k x ATR + spread")
    atr_timeframe: Timeframe = Timeframe.H1
    atr_period: int = Field(default=14, ge=2, le=200)
    margin_buffer: float = Field(default=2.0, ge=1, le=10, description="headroom for margin hikes (R24)")
    stops_level_max_fraction: float = Field(default=0.5, gt=0, le=1, description="G5: of the typical SL")
    min_candles: int = Field(default=200, ge=20)
    max_quote_age_seconds: float = Field(default=300.0, gt=0)


class AdvisoryConfig(StrictModel):
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    sessions: AdvisorySessionsConfig = Field(default_factory=AdvisorySessionsConfig)
    suitability: SuitabilityConfig = Field(default_factory=SuitabilityConfig)


class ExecutionConfig(StrictModel):
    """Broker order execution (DEMO in Phase 12; PLAN §A12)."""

    deviation_points: int | None = Field(
        default=None, ge=0, le=1000, description="order_send deviation; None: risk.max_slippage_points"
    )
    max_send_attempts: int = Field(default=2, ge=1, le=2, description="1 + at most one requote retry (§A12)")
    reconcile_after_seconds: float = Field(default=30.0, gt=0, le=600)
    reconcile_window_hours: float = Field(default=24.0, gt=0, le=72, description="history search widening")
    realized_risk_tolerance: float = Field(
        default=0.2, ge=0, le=1, description="fill risk above plan x (1+t)"
    )
    excess_risk_policy: Literal["reduce", "close"] = "reduce"
    unprotected_grace_seconds: float = Field(default=5.0, gt=0, le=60)
    symbol_pause_minutes: float = Field(default=60.0, gt=0)


class PaperConfig(StrictModel):
    """PAPER mode's simulated account (fills on live quotes; never a broker order)."""

    initial_balance: float | None = Field(
        default=None, gt=0, description="None: the real account's equity at the first PAPER start"
    )
    slippage_points: float = Field(
        default=1.0, ge=0, description="adverse, on market orders, closes and stops"
    )
    swap_enabled: bool = True


class EngineLoopConfig(StrictModel):
    monitor_interval_seconds: float = Field(default=1.0, gt=0, le=10)
    health_interval_seconds: float = Field(default=5.0, gt=0)
    candle_poll_seconds: float = Field(default=2.0, gt=0)
    clock_verify_minutes: float = Field(default=10.0, gt=0)
    health_host: str = "127.0.0.1"
    health_port: int = Field(default=8765, ge=1024, le=65535)
    heartbeat_file: str = "data/heartbeat.json"

    @field_validator("health_host")
    @classmethod
    def _loopback_only(cls, value: str) -> str:
        if value not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("the engine health endpoint must bind to loopback only")
        return value


class SyncConfig(StrictModel):
    enabled: bool = False
    batch_size: int = Field(default=500, ge=1, le=5000)
    flush_interval_seconds: float = Field(default=2.0, gt=0)
    command_poll_seconds: float = Field(default=25.0, gt=0, le=60)
    heartbeat_seconds: float = Field(default=10.0, gt=0)
    request_timeout_seconds: float = Field(default=15.0, gt=0)
    max_backlog_events: int = Field(default=200_000, ge=1000)


class DetectorSettings(StrictModel):
    """Per-detector overrides. ``params`` are checked against the detector's own parameter model when the
    evidence registry is configured (config cannot import the detectors: they live in a higher layer)."""

    enabled: bool | None = None  # None: follow evidence.default_enabled
    params: dict[str, Any] = Field(default_factory=dict)


class ConfluenceConfig(StrictModel):
    """Setup-strength weights (PLAN §A29, docs/PATTERNS.md "Confluence score"). Points out of 100.

    Family names are checked against the evidence families when the score is computed (config cannot import
    the evidence package: it lives in a higher layer).
    """

    core_weight: float = Field(default=40.0, ge=0, le=100, description="points for a full strategy checklist")
    conflict_penalty: float = Field(default=0.75, ge=0, le=3, description="conflict points per support point")
    family_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "TREND": 15.0,
            "FIBONACCI": 12.0,
            "LEVELS": 12.0,
            "CHART_PATTERN": 12.0,
            "CANDLESTICK": 8.0,
            "MOMENTUM": 8.0,
            "SMART_MONEY": 8.0,
            "HARMONIC": 8.0,
            "VOLATILITY_VOLUME": 6.0,
            "ICHIMOKU": 6.0,
            "SESSIONS": 5.0,
            "ELLIOTT": 4.0,
        }
    )
    tier_weights: dict[str, float] = Field(default_factory=lambda: {"T1": 1.0, "T2": 0.9, "T3": 0.6})

    @field_validator("family_weights", "tier_weights")
    @classmethod
    def _bounded(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not (0 <= w <= 100) for w in value.values()):
            raise ValueError("weights must be in [0, 100]")
        return value

    @field_validator("tier_weights")
    @classmethod
    def _tiers(cls, value: dict[str, float]) -> dict[str, float]:
        if any(w > 1 for w in value.values()):
            raise ValueError("tier weights scale quality and must be <= 1")
        return value


class EvidenceConfig(StrictModel):
    default_enabled: bool = True
    atr_period: int = Field(default=14, ge=2)
    # zigzag reversal thresholds in ATR multiples, one per degree (minor < intermediate < major)
    zigzag_degrees: dict[str, float] = Field(
        default_factory=lambda: {"minor": 1.5, "intermediate": 3.0, "major": 6.0}, min_length=1
    )
    # whose midnight starts a trading day for daily/weekly levels; FBS server time is EET/EEST
    session_timezone: str = "Europe/Athens"
    detectors: dict[str, DetectorSettings] = Field(default_factory=dict)
    confluence: ConfluenceConfig = Field(default_factory=ConfluenceConfig)

    @field_validator("session_timezone")
    @classmethod
    def _tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {value!r}") from exc
        return value

    @field_validator("zigzag_degrees")
    @classmethod
    def _degrees(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not (0 < m <= 50) for m in value.values()):
            raise ValueError("zigzag multiples must be in (0, 50]")
        return value


class AppConfig(StrictModel):
    symbols: SymbolsConfig = Field(default_factory=SymbolsConfig)
    timeframes: TimeframesConfig = Field(default_factory=TimeframesConfig)
    indicators: IndicatorParams = Field(default_factory=IndicatorParams)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    strategies: StrategiesConfig = Field(default_factory=StrategiesConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    sessions: SessionsConfig = Field(default_factory=SessionsConfig)
    position_management: PositionManagementConfig = Field(default_factory=PositionManagementConfig)
    breakers: BreakerConfig = Field(default_factory=BreakerConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    engine: EngineLoopConfig = Field(default_factory=EngineLoopConfig)
    paper: PaperConfig = Field(default_factory=PaperConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    advisory: AdvisoryConfig = Field(default_factory=AdvisoryConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    evidence: EvidenceConfig = Field(default_factory=EvidenceConfig)

    def spread_limit(self, symbol: str) -> float:
        override = self.symbols.overrides.get(symbol)
        if override and override.max_spread_points is not None:
            return override.max_spread_points
        return self.risk.max_spread_points

    def lot_limit(self, symbol: str) -> float:
        override = self.symbols.overrides.get(symbol)
        if override and override.max_lot is not None:
            return min(override.max_lot, self.risk.max_lot)
        return self.risk.max_lot


# ============================================================================== env settings
class EnvSettings(BaseSettings):
    """Secrets and safety flags. Loaded from the process environment and ``.env``."""

    # env_ignore_empty: a blank line copied from .env.example (``CLOUD_BASE_URL=``) means "not set", not ""
    model_config = SettingsConfigDict(
        env_file=None, extra="ignore", case_sensitive=True, env_ignore_empty=True
    )

    TRADING_MODE: TradingMode

    MT5_LOGIN: int | None = None
    MT5_PASSWORD: SecretStr | None = None
    MT5_SERVER: str | None = None
    MT5_TERMINAL_PATH: str | None = None
    MT5_PORTABLE: bool = True
    MT5_TIMEOUT_MS: int = Field(default=60_000, ge=1_000, le=300_000)
    BROKER_TIMEZONE: str = "Europe/Athens"
    PAPER_ALLOW_MASTER_PASSWORD: bool = False

    ENABLE_DEMO_TRADING: bool = False
    ENABLE_LIVE_TRADING: bool = False
    LIVE_TRADING_CONFIRMATION: str | None = None
    MAGIC_NUMBER_BASE: int = Field(default=7_310_000, ge=1, le=2_000_000_000)

    KILL_SWITCH_FILE: str = "data/KILL_SWITCH"
    KILL_SWITCH_FLATTEN_ALLOWED: bool = False

    ENGINE_DB_URL: str = "sqlite:///data/taa_engine.db"
    CONFIG_FILE: str = "config.yaml"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_DIR: str = "logs"

    AI_PROVIDER: Literal["none", "anthropic"] = "none"
    AI_API_KEY: SecretStr | None = None
    AI_MODEL: str = "claude-opus-5-5"
    AI_MODE: Literal["off", "advisory", "veto"] = "veto"

    CLOUD_BASE_URL: str | None = None
    ENGINE_ID: str | None = None
    ENGINE_HMAC_SECRET: SecretStr | None = None
    CONTROL_TOTP_SECRET: SecretStr | None = None

    # Spec-mandated variables that override config.yaml values when set.
    ALLOWED_SYMBOLS: str | None = None
    MAX_RISK_PER_TRADE: float | None = None
    MAX_DAILY_LOSS_PERCENT: float | None = None
    MAX_ACCOUNT_DRAWDOWN_PERCENT: float | None = None
    MAX_OPEN_POSITIONS: int | None = None
    MAX_SPREAD_POINTS: float | None = None

    @field_validator("CLOUD_BASE_URL")
    @classmethod
    def _https_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.rstrip("/")
        local = value.startswith(("http://127.0.0.1", "http://localhost"))
        if not (value.startswith("https://") or local):
            raise ValueError("CLOUD_BASE_URL must use https:// (plain http is allowed only for localhost)")
        return value


ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "MAX_RISK_PER_TRADE": ("risk", "max_risk_per_trade_percent"),
    "MAX_DAILY_LOSS_PERCENT": ("risk", "max_daily_loss_percent"),
    "MAX_ACCOUNT_DRAWDOWN_PERCENT": ("risk", "max_account_drawdown_percent"),
    "MAX_OPEN_POSITIONS": ("risk", "max_open_positions"),
    "MAX_SPREAD_POINTS": ("risk", "max_spread_points"),
}

KNOWN_ENV_KEYS = frozenset(EnvSettings.model_fields)
# Keys that may legitimately appear in a shared .env (web/worker/tooling) without being engine settings.
EXTERNAL_ENV_KEYS = frozenset(
    {
        "DATABASE_URL",
        "WEB_SESSION_SECRET",
        "VAPID_PRIVATE_KEY",
        "VAPID_PUBLIC_KEY",
        "VAPID_SUBJECT",
        "WEB_IP_ALLOWLIST",
        "WEB_STATIC_DIR",
        "WEB_ENV",
        "PORT",
        "ENGINE_HMAC_SECRET_PREVIOUS",
        "WEB_PUBLIC_ORIGIN",
        "WORKER_CONCURRENCY",
    }
)


# ================================================================================= loading
@dataclass(frozen=True)
class Settings:
    env: EnvSettings
    config: AppConfig
    config_hash: str
    env_file: Path | None
    config_file: Path | None

    @property
    def mode(self) -> TradingMode:
        return self.env.TRADING_MODE

    def path(self, value: str) -> Path:
        """Resolve a configured relative path against the repository root."""
        p = Path(value)
        return p if p.is_absolute() else REPO_ROOT / p

    def summary(self) -> dict[str, Any]:
        """Effective configuration safe for logs: secrets masked, login partially hidden."""
        from app.security.redaction import mask_login  # local import avoids a cycle

        env = self.env.model_dump()
        for key, value in list(env.items()):
            if isinstance(getattr(self.env, key), SecretStr):
                env[key] = "***set***" if value is not None else None
        if env.get("MT5_LOGIN") is not None:
            env["MT5_LOGIN"] = mask_login(env["MT5_LOGIN"])
        if env.get("LIVE_TRADING_CONFIRMATION"):
            env["LIVE_TRADING_CONFIRMATION"] = "***set***"
        return {
            "env": json.loads(json.dumps(env, default=str)),
            "config": self.config.model_dump(mode="json"),
            "config_hash": self.config_hash,
        }


def _read_yaml(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        if path is not None:
            log.warning("config file %s not found; using built-in defaults", path)
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return data


def _apply_env_overrides(data: dict[str, Any], env: EnvSettings) -> dict[str, Any]:
    merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in data.items()}
    for env_key, (section, field) in ENV_OVERRIDES.items():
        value = getattr(env, env_key)
        if value is not None:
            merged.setdefault(section, {})
            merged[section][field] = value
    if env.ALLOWED_SYMBOLS:
        merged.setdefault("symbols", {})
        merged["symbols"]["allowed"] = [s.strip() for s in env.ALLOWED_SYMBOLS.split(",") if s.strip()]
    return merged


def unknown_env_file_keys(env_file: Path) -> list[str]:
    """Keys in a .env file that no component reads (likely typos)."""
    if not env_file.exists():
        return []
    keys = dotenv_values(env_file).keys()
    return sorted(k for k in keys if k not in KNOWN_ENV_KEYS and k not in EXTERNAL_ENV_KEYS)


def _format_validation_error(prefix: str, exc: ValidationError) -> str:
    lines = [f"{prefix}:"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"  - {loc}: {err['msg']}")
    return "\n".join(lines)


def _require_mode_fields(env: EnvSettings, config: AppConfig) -> None:
    missing: list[str] = []
    if env.TRADING_MODE is not TradingMode.BACKTEST:
        for key in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER", "MT5_TERMINAL_PATH"):
            if getattr(env, key) in (None, ""):
                missing.append(key)
    if env.AI_PROVIDER != "none" and env.AI_API_KEY is None:
        missing.append("AI_API_KEY (required when AI_PROVIDER is set)")
    if config.sync.enabled:
        for key in ("CLOUD_BASE_URL", "ENGINE_ID", "ENGINE_HMAC_SECRET"):
            if getattr(env, key) in (None, ""):
                missing.append(f"{key} (required when sync.enabled is true)")
    if missing:
        raise ConfigError("missing required configuration: " + ", ".join(missing))


def load_settings(
    env_file: str | Path | None = ".env",
    config_file: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Load, merge and validate configuration. Raises :class:`ConfigError` on any problem."""
    env_path = Path(env_file) if env_file else None
    if env_path is not None and not env_path.is_absolute():
        env_path = REPO_ROOT / env_path
    try:
        if environ is not None:
            # Explicit mapping (tests / tooling): do not read the process environment.
            values = {k: v for k, v in environ.items() if k in KNOWN_ENV_KEYS and v != ""}
            env = EnvSettings.model_validate(values)
        else:
            env = EnvSettings(_env_file=env_path if env_path and env_path.exists() else None)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error("invalid environment settings", exc)) from exc

    if env_path is not None:
        for key in unknown_env_file_keys(env_path):
            log.warning("unknown key %s in %s (typo?)", key, env_path.name)

    cfg_path = Path(config_file) if config_file else Path(env.CONFIG_FILE)
    if not cfg_path.is_absolute():
        cfg_path = REPO_ROOT / cfg_path
    raw = _apply_env_overrides(_read_yaml(cfg_path), env)
    try:
        config = AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(f"invalid configuration in {cfg_path.name}", exc)) from exc

    _require_mode_fields(env, config)

    from app.security.secrets import resolve_env_secrets  # local import avoids a cycle

    env = resolve_env_secrets(env)
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return Settings(
        env=env,
        config=config,
        config_hash=stable_hash(canonical, length=16),
        env_file=env_path if env_path and env_path.exists() else None,
        config_file=cfg_path if cfg_path.exists() else None,
    )
