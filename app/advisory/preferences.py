"""Advisory preferences: one user's watchlists, alert rules, theory selection, trading profile and entry plan
(PLAN §A26, §A30, §A31; TAA-6B1).

These models are shared: the cloud validates what the PWA saves, the personalizer reads them, and a local run
without a cloud uses ``config.yaml`` → ``advisory.preferences`` (:func:`local_preferences`). The engine itself
never needs a user's preferences, only the compute requirements derived from them (§A30).

Validation that needs the catalogs (detector ids, bounded detector parameters, pattern-strategy names) is in
:func:`validate_against_catalogs`, because the evidence and strategy registries live in lower layers that a
pydantic validator should not load implicitly.

**Trading profile:** a style slider 0–100 interpolates linearly between five anchors (0, 25, 50, 75, 100).
Integer fields are rounded to the defensive side (fewer positions, more supporting families); categorical
fields take the more defensive neighbouring anchor. A field set in ``overrides`` replaces the slider value
and is reported as custom. Hard ceilings (``CEILING_*``) always apply, and the win-probability threshold
never goes below break-even + 2 pp (:func:`required_win_probability`).
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, time
from enum import StrEnum
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, ValidationError, field_validator, model_validator

from app.advisory.confidence import break_even_probability
from app.config import (
    CEILING_DAILY_LOSS_PCT,
    CEILING_RISK_PER_TRADE_PCT,
    CEILING_TOTAL_OPEN_RISK_PCT,
    AppConfig,
    SessionWindow,
    StrictModel,
)
from app.core.clock import ensure_utc
from app.core.enums import Timeframe
from app.core.errors import ConfigError
from app.evidence.framework import Family
from app.evidence.registry import DetectorRegistry
from app.market_data.trading_sessions import window_end
from app.risk.limits import EntryPlanSpec, ProfileLimits
from app.risk.position_sizer import SplitMode, WeightScheme
from app.strategy.registry import StrategyRegistry
from app.strategy.setups import EvidenceSetup

# --- watchlists ---------------------------------------------------------------------------------------------


class WatchlistKind(StrEnum):
    FAVOURITES = "FAVOURITES"
    CUSTOM = "CUSTOM"
    AUTO_TOP_N = "AUTO_TOP_N"  # the top N of the suitability ranking


MAX_LIST_SYMBOLS = 200
SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9#._\-]{1,32}$")


class Watchlist(StrictModel):
    name: str = Field(min_length=1, max_length=40)
    kind: WatchlistKind = WatchlistKind.CUSTOM
    symbols: list[str] = Field(default_factory=list, max_length=MAX_LIST_SYMBOLS)
    top_n: int | None = Field(default=None, ge=1, le=60, description="AUTO_TOP_N only; None: 30")
    alerts: bool = True
    threshold: float | None = Field(default=None, ge=0, le=100, description="overrides the global x")

    @field_validator("symbols")
    @classmethod
    def _symbols(cls, value: list[str]) -> list[str]:
        bad = [s for s in value if not SYMBOL_PATTERN.match(s)]
        if bad:
            raise ValueError(f"invalid symbol names {bad}")
        return list(dict.fromkeys(value))  # de-duplicated, order kept

    @property
    def size(self) -> int | None:
        """How many ranked symbols an AUTO_TOP_N list takes."""
        if self.kind is not WatchlistKind.AUTO_TOP_N:
            return None
        return 30 if self.top_n is None else self.top_n

    @model_validator(mode="after")
    def _kind_rules(self) -> Watchlist:
        if self.kind is WatchlistKind.AUTO_TOP_N:
            if self.symbols:
                raise ValueError("an AUTO_TOP_N list takes its symbols from the ranking")
        elif self.top_n is not None:
            raise ValueError("top_n applies to AUTO_TOP_N lists only")
        return self


def default_watchlists() -> list[Watchlist]:
    return [
        Watchlist(name="Favourites", kind=WatchlistKind.FAVOURITES),
        Watchlist(name="Top 30", kind=WatchlistKind.AUTO_TOP_N, top_n=30),
    ]


# --- alerts -------------------------------------------------------------------------------------------------


class AlertMetric(StrEnum):
    WIN_PROBABILITY = "WIN_PROBABILITY"
    SETUP_STRENGTH = "SETUP_STRENGTH"


DEFAULT_THRESHOLDS = {AlertMetric.WIN_PROBABILITY: 55.0, AlertMetric.SETUP_STRENGTH: 75.0}


class UserWindow(StrictModel):
    """A time window in the user's timezone (may span midnight; ``days`` are the start days, Monday = 0)."""

    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], min_length=1)
    start: str = "00:00"
    end: str = "23:59"

    @field_validator("days")
    @classmethod
    def _days(cls, value: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in value):
            raise ValueError("days are 0 (Monday) .. 6 (Sunday)")
        return sorted(set(value))

    @field_validator("start", "end")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"expected HH:MM, got {value!r}") from exc
        return value

    def session(self, timezone: str) -> SessionWindow:
        return SessionWindow(days=self.days, start=self.start, end=self.end, timezone=timezone)


class RateLimits(StrictModel):
    max_alerts_per_hour: int = Field(default=6, ge=1, le=60)
    symbol_cooldown_minutes: int = Field(default=30, ge=0, le=1440)


class RiskFullPolicy(StrEnum):
    """What an opportunity alert does when taking it would exceed the user's risk budget (portfolio heat
    after it, or the number of open positions)."""

    # no push; the opportunity stays visible in the app with the reason (default, fail closed)
    PAUSE = "PAUSE"
    WARN = "WARN"  # push anyway, with a warning line


class AlertPreferences(StrictModel):
    metric: AlertMetric = AlertMetric.WIN_PROBABILITY
    threshold: float | None = Field(default=None, ge=0, le=100, description="global x; None: metric default")
    signal_lifetime_bars: int = Field(default=2, ge=1, le=20)
    respect_market_sessions: bool = True
    timezone: str = "Asia/Bangkok"
    windows: list[UserWindow] = Field(default_factory=list, max_length=14, description="empty: any time")
    rate_limits: RateLimits = Field(default_factory=RateLimits)
    expiry_updates: bool = True  # silent same-tag replacement on expiry/invalidation (R26)
    when_risk_full: RiskFullPolicy = RiskFullPolicy.PAUSE
    language: Literal["th", "en"] = "th"
    # (TAA-1305) alert only what the engine's AI agrees with; applies only while the filter is offered (it
    # beat the baseline on the engine's shadow outcomes, app.web.ai.filter_evaluation) and the plan has AI
    ai_filter: bool = False

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {value!r}") from exc
        return value

    def effective_threshold(self, watchlist: Watchlist | None = None) -> float:
        if watchlist is not None and watchlist.threshold is not None:
            return watchlist.threshold
        return self.threshold if self.threshold is not None else DEFAULT_THRESHOLDS[self.metric]

    def window_end(self, at: datetime) -> datetime | None:
        """The end of the user window containing *at*; ``None`` when *at* is outside every window.

        With no windows configured the user is always reachable, which is reported as ``datetime.max``.
        """
        if not self.windows:
            return datetime.max.replace(tzinfo=ensure_utc(at).tzinfo)
        ends = [e for w in self.windows if (e := window_end(w.session(self.timezone), at)) is not None]
        return max(ends) if ends else None


# --- theories -----------------------------------------------------------------------------------------------


class ConflictPolicy(StrEnum):
    IGNORE = "IGNORE"
    PENALIZE = "PENALIZE"
    BLOCK = "BLOCK"


F = Family
PRESETS: dict[str, frozenset[Family]] = {
    "ALL": frozenset(Family),
    "CLASSIC_TA": frozenset(
        {F.LEVELS, F.TREND, F.CHART_PATTERN, F.CANDLESTICK, F.MOMENTUM, F.VOLATILITY_VOLUME}
    ),
    "PRICE_ACTION": frozenset({F.LEVELS, F.CHART_PATTERN, F.CANDLESTICK, F.SMART_MONEY, F.SESSIONS}),
    "FIB_HARMONICS": frozenset({F.FIBONACCI, F.HARMONIC, F.ELLIOTT, F.LEVELS}),
    "TREND_FOLLOWING": frozenset({F.TREND, F.MOMENTUM, F.ICHIMOKU, F.VOLATILITY_VOLUME}),
}


class TheoryPreferences(StrictModel):
    preset: str | None = Field(default="ALL", description="sets the family toggles; None: custom")
    families: dict[str, bool] = Field(default_factory=dict, description="overrides on top of the preset")
    detectors: dict[str, bool] = Field(default_factory=dict, description="per-detector overrides")
    params: dict[str, dict[str, Any]] = Field(default_factory=dict, description="bounded detector params")
    pattern_strategies: dict[str, bool] = Field(default_factory=dict, description="may these setups alert")
    min_supporting_families: int = Field(default=2, ge=1, le=len(Family))
    conflict_policy: ConflictPolicy = ConflictPolicy.PENALIZE

    @field_validator("preset")
    @classmethod
    def _preset(cls, value: str | None) -> str | None:
        if value is not None and value not in PRESETS:
            raise ValueError(f"unknown preset {value!r}; known: {sorted(PRESETS)}")
        return value

    @field_validator("families")
    @classmethod
    def _families(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = sorted(set(value) - {f.value for f in Family})
        if unknown:
            raise ValueError(f"unknown detector families {unknown}")
        return value

    def enabled_families(self) -> frozenset[Family]:
        base = PRESETS[self.preset] if self.preset is not None else frozenset()
        on = {f for f in base}
        for name, enabled in self.families.items():
            (on.add if enabled else on.discard)(Family(name))
        return frozenset(on)

    def enabled_detectors(self, registry: DetectorRegistry) -> set[str]:
        """Detectors whose evidence the user wants (prerequisites are added by the run plan, not here)."""
        ids = registry.ids_in_families(self.enabled_families())
        for det_id, enabled in self.detectors.items():
            (ids.add if enabled else ids.discard)(det_id)
        return ids


# --- trading profile ----------------------------------------------------------------------------------------

ANCHORS = (0, 25, 50, 75, 100)
PROFILE_ANCHORS: dict[str, tuple[Any, ...]] = {
    "risk_per_signal_percent": (0.25, 0.5, 0.75, 1.0, 1.5),
    "portfolio_heat_percent": (0.5, 1.0, 2.0, 3.0, 4.0),
    "max_positions": (1, 2, 3, 4, 5),
    "max_daily_loss_percent": (1.0, 1.5, 2.0, 3.0, 4.0),
    "min_rr": (2.5, 2.0, 1.5, 1.3, 1.2),
    "min_win_probability": (62.0, 58.0, 55.0, 52.0, 50.0),
    "min_supporting_families": (4, 3, 2, 2, 1),
    "conflict_policy": (
        ConflictPolicy.BLOCK,
        ConflictPolicy.BLOCK,
        ConflictPolicy.PENALIZE,
        ConflictPolicy.PENALIZE,
        ConflictPolicy.IGNORE,
    ),
    "require_htf_alignment": (True, True, True, False, False),
}
INT_DEFENSIVE = {"max_positions": math.floor, "min_supporting_families": math.ceil}
WIN_PROBABILITY_MARGIN = 2.0  # percentage points above break-even


class HoldingStyle(StrEnum):
    SCALP = "SCALP"
    DAY = "DAY"
    SWING = "SWING"


HOLDING_TIMEFRAMES: dict[HoldingStyle, tuple[Timeframe, Timeframe]] = {  # (entry, higher)
    HoldingStyle.SCALP: (Timeframe.M5, Timeframe.M15),
    HoldingStyle.DAY: (Timeframe.M15, Timeframe.H1),
    HoldingStyle.SWING: (Timeframe.H1, Timeframe.H4),
}


class StopPlacement(StrEnum):
    STRUCTURE = "STRUCTURE"
    ATR = "ATR"


class ProfileOverrides(StrictModel):
    """Fields the user set explicitly; each replaces the slider's value."""

    risk_per_signal_percent: float | None = Field(default=None, gt=0, le=CEILING_RISK_PER_TRADE_PCT)
    portfolio_heat_percent: float | None = Field(default=None, gt=0, le=CEILING_TOTAL_OPEN_RISK_PCT)
    max_positions: int | None = Field(default=None, ge=1, le=20)
    max_daily_loss_percent: float | None = Field(default=None, gt=0, le=CEILING_DAILY_LOSS_PCT)
    min_rr: float | None = Field(default=None, ge=1.0, le=10)
    min_win_probability: float | None = Field(default=None, ge=0, le=100)
    min_supporting_families: int | None = Field(default=None, ge=1, le=len(Family))
    conflict_policy: ConflictPolicy | None = None
    require_htf_alignment: bool | None = None


@dataclass(frozen=True, slots=True)
class ResolvedProfile:
    style: int
    risk_per_signal_percent: float
    portfolio_heat_percent: float
    max_positions: int
    max_daily_loss_percent: float
    min_rr: float
    min_win_probability: float
    min_supporting_families: int
    conflict_policy: ConflictPolicy
    require_htf_alignment: bool
    holding_style: HoldingStyle
    max_signals_per_day: int
    avoid_news: bool
    hold_over_weekend: bool
    stop_placement: StopPlacement
    custom: frozenset[str]  # fields that came from overrides
    min_lot_fallback: bool = False

    @property
    def timeframes(self) -> tuple[Timeframe, Timeframe]:
        return HOLDING_TIMEFRAMES[self.holding_style]

    def limits(self) -> ProfileLimits:
        """The values the engine trades with when this is its owner's profile (PLAN §A33)."""
        return ProfileLimits(
            risk_per_trade_percent=self.risk_per_signal_percent,
            total_open_risk_percent=self.portfolio_heat_percent,
            max_open_positions=self.max_positions,
            max_daily_loss_percent=self.max_daily_loss_percent,
            min_risk_reward=self.min_rr,
            min_lot_fallback=self.min_lot_fallback,
        )


def interpolate(field: str, style: float) -> Any:
    values = PROFILE_ANCHORS[field]
    style = max(0.0, min(100.0, style))
    i = min(int(style // 25), len(ANCHORS) - 2)
    lo, hi = values[i], values[i + 1]
    t = (style - ANCHORS[i]) / 25
    if isinstance(lo, (bool, ConflictPolicy)):
        return hi if t >= 1 else lo  # the more defensive neighbour until the next anchor is reached
    value = lo + (hi - lo) * t
    if field in INT_DEFENSIVE:
        return int(INT_DEFENSIVE[field](round(value, 9)))
    return round(value, 4)


class TradingProfile(StrictModel):
    style: int = Field(default=50, ge=0, le=100, description="0 very defensive .. 100 very offensive")
    overrides: ProfileOverrides = Field(default_factory=ProfileOverrides)
    holding_style: HoldingStyle = HoldingStyle.DAY
    max_signals_per_day: int = Field(default=10, ge=1, le=100)
    avoid_news: bool = True
    hold_over_weekend: bool = False
    stop_placement: StopPlacement = StopPlacement.STRUCTURE
    # when the risk budget buys less than the minimum lot: open the minimum lot if margin allows (its risk is
    # then above the budget); the engine also needs risk.min_lot_fallback in its config.yaml cage
    min_lot_fallback: bool = False

    def resolve(self) -> ResolvedProfile:
        values: dict[str, Any] = {}
        custom: set[str] = set()
        for name in PROFILE_ANCHORS:
            override = getattr(self.overrides, name)
            if override is not None:
                values[name] = override
                custom.add(name)
            else:
                values[name] = interpolate(name, self.style)
        # ceilings bound the slider too (they already bound the overrides through the field limits)
        values["risk_per_signal_percent"] = min(values["risk_per_signal_percent"], CEILING_RISK_PER_TRADE_PCT)
        values["portfolio_heat_percent"] = min(values["portfolio_heat_percent"], CEILING_TOTAL_OPEN_RISK_PCT)
        values["max_daily_loss_percent"] = min(values["max_daily_loss_percent"], CEILING_DAILY_LOSS_PCT)
        return ResolvedProfile(
            style=self.style,
            holding_style=self.holding_style,
            max_signals_per_day=self.max_signals_per_day,
            avoid_news=self.avoid_news,
            hold_over_weekend=self.hold_over_weekend,
            stop_placement=self.stop_placement,
            custom=frozenset(custom),
            min_lot_fallback=self.min_lot_fallback,
            **values,
        )


def required_win_probability(profile: ResolvedProfile, rr: float, cost_r: float = 0.0) -> float:
    """The profile's minimum, never below break-even + 2 pp, so an alert always has EV > 0."""
    return max(profile.min_win_probability, break_even_probability(rr, cost_r) + WIN_PROBABILITY_MARGIN)


# --- entry plan ---------------------------------------------------------------------------------------------


class EntryPlanPreferences(StrictModel):
    lot_unit: float | None = Field(default=None, gt=0, le=100, description="lot per tap; None: volume step")
    mode: SplitMode = SplitMode.SINGLE
    parts: int = Field(default=1, ge=1, le=5)
    weights: WeightScheme = WeightScheme.EQUAL
    spacing_atr: float = Field(default=0.5, ge=0.1, le=3.0, description="SCALE_IN limit spacing")
    partial_tp_r: list[float] = Field(default_factory=lambda: [1.0, 2.0], description="SAME_PRICE TPs")

    @model_validator(mode="after")
    def _coherent(self) -> EntryPlanPreferences:
        if self.mode is SplitMode.SINGLE and self.parts != 1:
            raise ValueError("a SINGLE plan has exactly one part")
        if self.mode is not SplitMode.SINGLE and self.parts < 2:
            raise ValueError(f"a {self.mode.value} plan needs at least two parts")
        if self.mode is SplitMode.SAME_PRICE:
            levels = self.partial_tp_r
            if len(levels) < self.parts - 1:
                raise ValueError("SAME_PRICE needs one partial take-profit (in R) per part except the last")
            if any(r <= 0 for r in levels) or levels != sorted(set(levels)):
                raise ValueError("partial take-profits must be positive and increasing")
        return self

    @property
    def take_profits_r(self) -> list[float]:
        """The partial take-profits a SAME_PRICE plan uses (the last part runs to the setup's target)."""
        return self.partial_tp_r[: self.parts - 1] if self.mode is SplitMode.SAME_PRICE else []

    def spec(self) -> EntryPlanSpec:
        """The engine's copy of this plan (TAA-1207)."""
        return EntryPlanSpec(
            self.mode, self.parts, self.weights, self.spacing_atr, self.lot_unit, tuple(self.take_profits_r)
        )


# --- the whole set ------------------------------------------------------------------------------------------


class AdvisoryPreferences(StrictModel):
    version: int = Field(default=1, ge=1)
    watchlists: list[Watchlist] = Field(default_factory=default_watchlists, max_length=20)
    alerts: AlertPreferences = Field(default_factory=AlertPreferences)
    theories: TheoryPreferences = Field(default_factory=TheoryPreferences)
    trading_profile: TradingProfile = Field(default_factory=TradingProfile)
    entry_plan: EntryPlanPreferences = Field(default_factory=EntryPlanPreferences)

    @model_validator(mode="after")
    def _lists(self) -> AdvisoryPreferences:
        names = [w.name.casefold() for w in self.watchlists]
        if len(names) != len(set(names)):
            raise ValueError("watchlist names must be unique")
        for kind in (WatchlistKind.FAVOURITES, WatchlistKind.AUTO_TOP_N):
            if sum(w.kind is kind for w in self.watchlists) > 1:
                raise ValueError(f"at most one {kind.value} list")
        return self

    def watchlist(self, name: str) -> Watchlist | None:
        return next((w for w in self.watchlists if w.name.casefold() == name.casefold()), None)

    def listed_symbols(self) -> list[str]:
        """Symbols named in FAVOURITES and CUSTOM lists, in list order (AUTO_TOP_N comes from the ranking)."""
        out: dict[str, None] = {}
        for w in self.watchlists:
            out.update(dict.fromkeys(w.symbols))
        return list(out)

    def engine_limits(self) -> ProfileLimits:
        """What the engine owner's preferences govern on the engine (PLAN §A33, TAA-1207): the Trading
        profile's limits plus the entry plan (None for SINGLE, which is the engine's default)."""
        plan = self.entry_plan.spec()
        return replace(self.trading_profile.resolve().limits(), entry_plan=plan if plan.split else None)


def validate_against_catalogs(
    prefs: AdvisoryPreferences, evidence: DetectorRegistry, strategies: StrategyRegistry
) -> list[str]:
    """Problems with ids and parameters the models cannot check alone (empty list: valid)."""
    problems: list[str] = []
    known = set(evidence.ids)
    theories = prefs.theories
    for det_id in sorted(set(theories.detectors) | set(theories.params)):
        if det_id not in known:
            problems.append(f"unknown detector {det_id!r}")
    for det_id, raw in sorted(theories.params.items()):
        if det_id in known:
            try:
                evidence.parse_params(det_id, raw)
            except (ConfigError, ValidationError, ValueError) as exc:
                problems.append(f"{det_id}: {exc}")
    for name in sorted(theories.pattern_strategies):
        if name not in strategies.names:
            problems.append(f"unknown strategy {name!r}")
        elif not issubclass(strategies.get(name), EvidenceSetup):
            problems.append(f"{name!r} is not a pattern strategy")
    return problems


def parse_preferences(
    raw: Mapping[str, Any],
    *,
    evidence: DetectorRegistry | None = None,
    strategies: StrategyRegistry | None = None,
) -> AdvisoryPreferences:
    """Validate a stored or submitted preference document; any problem is a :class:`ConfigError`."""
    try:
        prefs = AdvisoryPreferences.model_validate(dict(raw))
    except ValidationError as exc:
        raise ConfigError(f"invalid advisory preferences: {exc}") from exc
    if evidence is not None and strategies is not None:
        problems = validate_against_catalogs(prefs, evidence, strategies)
        if problems:
            raise ConfigError("invalid advisory preferences: " + "; ".join(problems))
    return prefs


def local_preferences(config: AppConfig) -> AdvisoryPreferences:
    """The ``config.yaml`` fallback for local runs without a cloud, checked against the catalogs."""
    from app.evidence.catalog import default_registry as evidence_registry
    from app.strategy.catalog import default_registry as strategy_registry

    return parse_preferences(
        config.advisory.preferences, evidence=evidence_registry(), strategies=strategy_registry()
    )


def symbols_union(prefs: Iterable[AdvisoryPreferences]) -> list[str]:
    out: dict[str, None] = {}
    for p in prefs:
        out.update(dict.fromkeys(p.listed_symbols()))
    return list(out)
