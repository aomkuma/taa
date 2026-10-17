"""Backtest presets for cloud jobs (PLAN §A17 "Where it runs"; TAA-807).

A user never sends a configuration. A job names a **preset** (a fixed, reviewed change to ``config.yaml``)
plus a few bounded parameters, validated by :class:`BacktestRequest`:

| Preset | Change |
|---|---|
| ``standard`` | ``config.yaml`` as it is |
| ``conservative`` | half the risk per trade and of the total open risk |
| ``high_costs`` | three times the slippage, 7 more commission per lot: does the result survive worse fills? |

Parameters: 1-5 symbols, a period of at most 366 days that has ended, optionally a subset of the strategies
listed in ``config.yaml`` (they are then run even if disabled there), a risk per trade below the hard
ceiling, and a seed. Anything else is refused (fail closed).

**Aggressive** (PLAN §A36; local CLI only, ``app.cli backtest --preset aggressive [--risk 7.5]``): the
high-risk cage (``config.yaml`` → ``high_risk``, or its defaults with the proven setups) and the preset's
limits for r = 5-10 % (:func:`aggressive_preset`), trading only the cage's setups. Cloud jobs cannot ask for
it: :class:`BacktestRequest` keeps the standard ceiling (fail closed).

"Backtest this change" (TAA-1004, a recommendation's offer) adds at most one bounded
:class:`ParameterChange` (an earlier break-even, a wider stop for one strategy, a tighter spread filter)
and/or strategies to leave out. The change exists only in the job's configuration, never in ``config.yaml``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.config import (
    AGGRESSIVE_DEFAULT_RISK_PCT,
    AGGRESSIVE_MIN_RISK_PCT,
    CEILING_RISK_PER_TRADE_PCT,
    HIGH_RISK_CEILING_RISK_PER_TRADE_PCT,
    AppConfig,
    HighRiskConfig,
    StrategiesConfig,
)
from app.core.errors import ConfigError
from app.risk.limits import aggressive_limits, effective_risk

if TYPE_CHECKING:
    from app.backtest.engine import RiskPreset

MAX_PERIOD = timedelta(days=366)
PresetName = Literal["standard", "conservative", "high_costs"]

# bounds of the testable changes (inclusive)
CHANGE_BOUNDS: dict[str, tuple[float, float]] = {
    "break_even_trigger_r": (0.3, 3.0),
    "sl_atr_multiple": (0.5, 5.0),
    "max_spread_to_sl_ratio": (0.01, 0.5),
}


class ParameterChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["break_even_trigger_r", "sl_atr_multiple", "max_spread_to_sl_ratio"]
    value: float = Field(allow_inf_nan=False)
    strategy: str | None = Field(default=None, min_length=1, max_length=64)  # sl_atr_multiple only

    @model_validator(mode="after")
    def _check(self) -> ParameterChange:
        low, high = CHANGE_BOUNDS[self.kind]
        if not low <= self.value <= high:
            raise ValueError(f"{self.kind} must be within {low}-{high}")
        if (self.kind == "sl_atr_multiple") != (self.strategy is not None):
            raise ValueError("a strategy goes with sl_atr_multiple, and only with it")
        return self


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: PresetName = "standard"
    symbols: list[str] = Field(min_length=1, max_length=5)
    start: AwareDatetime
    end: AwareDatetime
    strategies: list[str] | None = Field(default=None, min_length=1, max_length=10)
    risk_percent: float | None = Field(default=None, gt=0, le=CEILING_RISK_PER_TRADE_PCT)
    seed: int | None = Field(default=None, ge=0, lt=2**31)
    change: ParameterChange | None = None
    exclude_strategies: list[str] | None = Field(default=None, min_length=1, max_length=10)

    @model_validator(mode="after")
    def _check(self) -> BacktestRequest:
        if self.strategies is not None and self.exclude_strategies is not None:
            raise ValueError("strategies and exclude_strategies do not go together")
        for s in self.symbols:
            if not (1 <= len(s) <= 32 and all(c.isalnum() or c in "._#-" for c in s)):
                raise ValueError(f"symbol {s!r}: 1-32 letters, digits or . _ # -")
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols must be unique")
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.end - self.start > MAX_PERIOD:
            raise ValueError("the period is at most 366 days")
        return self


def _conservative(config: AppConfig) -> AppConfig:
    risk = config.risk
    return config.model_copy(
        update={
            "risk": risk.model_copy(
                update={
                    "max_risk_per_trade_percent": risk.max_risk_per_trade_percent / 2,
                    "max_total_open_risk_percent": risk.max_total_open_risk_percent / 2,
                }
            )
        }
    )


def _high_costs(config: AppConfig) -> AppConfig:
    bt = config.backtest
    return config.model_copy(
        update={
            "backtest": bt.model_copy(
                update={
                    "slippage_model": "fixed" if bt.slippage_model == "none" else bt.slippage_model,
                    "slippage_points": max(bt.slippage_points, 1.0) * 3,
                    "commission_per_lot": bt.commission_per_lot + 7.0,
                }
            )
        }
    )


PRESETS: dict[str, Callable[[AppConfig], AppConfig]] = {
    "standard": lambda c: c,
    "conservative": _conservative,
    "high_costs": _high_costs,
}


def _apply_change(config: AppConfig, request: BacktestRequest) -> AppConfig:
    """The exclusions and the parameter change of a "Backtest this change" job."""
    excluded = set(request.exclude_strategies or [])
    change = request.change
    items = [
        i.model_copy(
            update={
                "enabled": i.enabled and i.name not in excluded,
                "params": i.params | {"sl_atr_multiple": change.value}
                if change is not None and change.kind == "sl_atr_multiple" and change.strategy == i.name
                else i.params,
            }
        )
        for i in config.strategies.items
    ]
    updates: dict[str, object] = {"strategies": config.strategies.model_copy(update={"items": items})}
    if change is not None and change.kind == "break_even_trigger_r":
        updates["position_management"] = config.position_management.model_copy(
            update={"break_even_trigger_r": change.value}
        )
    if change is not None and change.kind == "max_spread_to_sl_ratio":
        updates["risk"] = config.risk.model_copy(update={"max_spread_to_sl_ratio": change.value})
    return config.model_copy(update=updates)


def apply_preset(config: AppConfig, request: BacktestRequest) -> AppConfig:
    """The job's configuration; raises :class:`ConfigError` for strategies that ``config.yaml`` lacks."""
    if request.strategies is not None:
        known = {i.name for i in config.strategies.items}
        unknown = sorted(set(request.strategies) - known)
        if unknown:
            raise ConfigError(f"strategies not in config.yaml: {unknown}")
    named = set(request.exclude_strategies or [])
    if request.change is not None and request.change.strategy is not None:
        named.add(request.change.strategy)
    missing = sorted(named - {i.name for i in config.strategies.items})
    if missing:
        raise ConfigError(f"strategies not in config.yaml: {missing}")
    out = _apply_change(PRESETS[request.preset](config), request)
    updates: dict[str, object] = {}
    if request.risk_percent is not None:
        updates["risk"] = out.risk.model_copy(update={"max_risk_per_trade_percent": request.risk_percent})
    if request.seed is not None:
        updates["backtest"] = out.backtest.model_copy(update={"seed": request.seed})
    out = out.model_copy(update=updates) if updates else out
    # model_copy skips validation: re-validate, so a preset can never produce a config the loader would refuse
    return AppConfig.model_validate(out.model_dump())


# the setups proven by backtest (SETUP_REVIEW §15.3 harmonic V1, §16 breakout F1): the preset's default list
PROVEN_SETUPS = ("setup_harmonic_prz", "setup_breakout")


def aggressive_preset(
    config: AppConfig, risk_percent: float = AGGRESSIVE_DEFAULT_RISK_PCT
) -> tuple[AppConfig, RiskPreset]:
    """The aggressive preset for a local backtest (PLAN §A36): only the cage's setups enabled (in every
    lane), the high-risk cage from ``config.yaml`` → ``high_risk`` (or its defaults with
    :data:`PROVEN_SETUPS`), and the preset's limits for *risk_percent*. The profile's minimum RR is left
    to ``risk:`` (as the standard backtests run). Raises :class:`ConfigError` for a risk outside 5-10 % or
    setups that ``config.yaml`` lacks."""
    if not AGGRESSIVE_MIN_RISK_PCT <= risk_percent <= HIGH_RISK_CEILING_RISK_PER_TRADE_PCT:
        raise ConfigError(
            f"the aggressive preset risks {AGGRESSIVE_MIN_RISK_PCT:g}-"
            f"{HIGH_RISK_CEILING_RISK_PER_TRADE_PCT:g} % a trade (got {risk_percent:g})"
        )
    known = {i.name for i in config.strategies.items}
    section = config.high_risk
    if section is None:
        setups = [s for s in PROVEN_SETUPS if s in known]
        if not setups:
            raise ConfigError(f"config.yaml lists none of the proven setups {list(PROVEN_SETUPS)}")
        section = HighRiskConfig(setups=setups)

    def caged(strategies: StrategiesConfig) -> StrategiesConfig:
        items = [i.model_copy(update={"enabled": i.name in section.setups}) for i in strategies.items]
        return strategies.model_copy(update={"items": items})

    lanes = [lane.model_copy(update={"strategies": caged(lane.strategies)}) for lane in config.lanes]
    out = config.model_copy(update={"strategies": caged(config.strategies), "lanes": lanes})
    out = AppConfig.model_validate(out.model_dump())
    from app.backtest.engine import RiskPreset  # local: the web imports this module, not the engine

    preset = RiskPreset(
        name=f"aggressive-{risk_percent:g}",
        cage=section.cage(out.risk),
        limits=aggressive_limits(risk_percent),
    )
    effective_risk(preset.cage, preset.limits)  # an incoherent combination fails here, not mid-run
    return out, preset
