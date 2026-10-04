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
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.config import CEILING_RISK_PER_TRADE_PCT, AppConfig
from app.core.errors import ConfigError

MAX_PERIOD = timedelta(days=366)
PresetName = Literal["standard", "conservative", "high_costs"]


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: PresetName = "standard"
    symbols: list[str] = Field(min_length=1, max_length=5)
    start: AwareDatetime
    end: AwareDatetime
    strategies: list[str] | None = Field(default=None, min_length=1, max_length=10)
    risk_percent: float | None = Field(default=None, gt=0, le=CEILING_RISK_PER_TRADE_PCT)
    seed: int | None = Field(default=None, ge=0, lt=2**31)

    @model_validator(mode="after")
    def _check(self) -> BacktestRequest:
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


def apply_preset(config: AppConfig, request: BacktestRequest) -> AppConfig:
    """The job's configuration; raises :class:`ConfigError` for strategies that ``config.yaml`` lacks."""
    if request.strategies is not None:
        known = {i.name for i in config.strategies.items}
        unknown = sorted(set(request.strategies) - known)
        if unknown:
            raise ConfigError(f"strategies not in config.yaml: {unknown}")
    out = PRESETS[request.preset](config)
    updates: dict[str, object] = {}
    if request.risk_percent is not None:
        updates["risk"] = out.risk.model_copy(update={"max_risk_per_trade_percent": request.risk_percent})
    if request.seed is not None:
        updates["backtest"] = out.backtest.model_copy(update={"seed": request.seed})
    out = out.model_copy(update=updates) if updates else out
    # model_copy skips validation: re-validate, so a preset can never produce a config the loader would refuse
    return AppConfig.model_validate(out.model_dump())
