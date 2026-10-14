"""Effective risk limits: min(trading profile, local ``RiskConfig``) (PLAN §A31 safety, §A13/§A20; TAA-406).

Since rev. 5 (PLAN §A33, TAA-710) the engine owner's profile reaches the engine as a :class:`RiskProfileDoc`
(``GET /api/v1/engine/risk-profile``); the local ``RiskConfig`` is the outer cage it can never exceed.

A trading profile comes from the cloud and is untrusted for raising risk. Every limit it shares with the local
configuration is combined in the conservative direction (lower risk and loss caps, fewer positions, a higher
minimum RR), so a profile can only make the owner's trading more conservative. Coherence rules of
``RiskConfig`` (risk per trade ≤ daily loss, ≤ total open risk) are restored by lowering, never by raising.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import (
    CEILING_DAILY_LOSS_PCT,
    CEILING_RISK_PER_TRADE_PCT,
    CEILING_TOTAL_OPEN_RISK_PCT,
    HIGH_RISK_CEILING_DAILY_LOSS_PCT,
    HIGH_RISK_CEILING_RISK_PER_TRADE_PCT,
    HIGH_RISK_CEILING_TOTAL_OPEN_RISK_PCT,
    HighRiskCage,
    RiskConfig,
)
from app.core.ids import stable_hash
from app.risk.position_sizer import SplitMode, WeightScheme

MAX_PLAN_PARTS = 5


class RiskMode(StrEnum):
    """The Trading profile's preset (PLAN §A36): ``STANDARD`` inside ``risk:``, ``AGGRESSIVE`` inside the
    opt-in high-risk cage (:class:`app.config.HighRiskCage`)."""

    STANDARD = "STANDARD"
    AGGRESSIVE = "AGGRESSIVE"


class HighRiskRefused(ValueError):
    """An AGGRESSIVE profile met a standard cage: it never trades (the caller falls back to STANDARD)."""


@dataclass(frozen=True, slots=True)
class EntryPlanSpec:
    """How the owner splits an entry (PLAN §A31 "แบ่งไม้"; TAA-1207): the engine's copy of the Trading
    profile's ``entry_plan``, defined here because ``app.risk`` never imports ``app.advisory``."""

    mode: SplitMode = SplitMode.SINGLE
    parts: int = 1
    weights: WeightScheme = WeightScheme.EQUAL
    spacing_atr: float = 0.5  # SCALE_IN: limit i sits i x spacing x ATR toward the stop
    lot_unit: float | None = None  # lot per tap; None: the symbol's volume step
    tp_r: tuple[float, ...] = ()  # SAME_PRICE: the take-profits (in R) of every part but the last

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", SplitMode(self.mode))
        object.__setattr__(self, "weights", WeightScheme(self.weights))
        object.__setattr__(self, "tp_r", tuple(float(r) for r in self.tp_r))
        if not 1 <= self.parts <= MAX_PLAN_PARTS:
            raise ValueError(f"an entry plan has 1 to {MAX_PLAN_PARTS} parts (got {self.parts})")
        if (self.mode is SplitMode.SINGLE) != (self.parts == 1):
            raise ValueError("a SINGLE plan has exactly one part, a split plan at least two")
        if not (math.isfinite(self.spacing_atr) and 0.1 <= self.spacing_atr <= 3.0):
            raise ValueError("spacing_atr must be within 0.1..3")
        if self.lot_unit is not None and not (math.isfinite(self.lot_unit) and 0 < self.lot_unit <= 100):
            raise ValueError("lot_unit must be within (0, 100]")
        if self.mode is SplitMode.SAME_PRICE:
            levels = list(self.tp_r)
            if len(levels) < self.parts - 1:
                raise ValueError("SAME_PRICE needs one partial take-profit (in R) per part but the last")
            if any(not math.isfinite(r) or r <= 0 for r in levels) or levels != sorted(set(levels)):
                raise ValueError("partial take-profits must be positive and increasing")

    @property
    def split(self) -> bool:
        return self.mode is not SplitMode.SINGLE

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "parts": self.parts,
            "weights": self.weights.value,
            "spacing_atr": self.spacing_atr,
            "lot_unit": self.lot_unit,
            "tp_r": list(self.tp_r),
        }


@dataclass(frozen=True, slots=True)
class ProfileLimits:
    """Trading-profile values that also exist in ``RiskConfig`` (``None``: the profile does not set it), plus
    the owner's entry plan (TAA-1207), which the engine follows only when ``execution.entry_plans`` allows."""

    risk_per_trade_percent: float | None = None
    total_open_risk_percent: float | None = None  # portfolio heat
    max_open_positions: int | None = None
    max_daily_loss_percent: float | None = None
    min_risk_reward: float | None = None
    min_lot_fallback: bool | None = None  # open the minimum lot above the budget (needs the cage's consent)
    entry_plan: EntryPlanSpec | None = None
    risk_mode: RiskMode = RiskMode.STANDARD  # AGGRESSIVE needs the high-risk cage (PLAN §A36)

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_mode", RiskMode(self.risk_mode))
        for name in (
            "risk_per_trade_percent",
            "total_open_risk_percent",
            "max_daily_loss_percent",
            "min_risk_reward",
        ):
            value = getattr(self, name)
            if value is not None and not (math.isfinite(value) and value > 0):
                raise ValueError(f"profile {name} must be a positive number (got {value!r})")
        if self.max_open_positions is not None and self.max_open_positions < 1:
            raise ValueError("profile max_open_positions must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        """Without ``entry_plan`` when it is not set and without ``risk_mode`` when STANDARD, so profiles from
        before TAA-1207 and before the aggressive preset (PLAN §A36) keep their versions."""
        data: dict[str, Any] = {k: v for k, v in asdict(self).items() if k not in ("entry_plan", "risk_mode")}
        if self.entry_plan is not None:
            data["entry_plan"] = self.entry_plan.to_dict()
        if self.risk_mode is RiskMode.AGGRESSIVE:
            data["risk_mode"] = self.risk_mode.value
        return data

    @property
    def aggressive(self) -> bool:
        return self.risk_mode is RiskMode.AGGRESSIVE

    def version(self) -> str:
        return stable_hash(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")), length=16)


class EntryPlanDoc(BaseModel):
    """The wire format of :class:`EntryPlanSpec` (bounds as ``EntryPlanPreferences``)."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    mode: SplitMode = SplitMode.SINGLE
    parts: int = Field(default=1, ge=1, le=MAX_PLAN_PARTS)
    weights: WeightScheme = WeightScheme.EQUAL
    spacing_atr: float = Field(default=0.5, ge=0.1, le=3.0)
    lot_unit: float | None = Field(default=None, gt=0, le=100)
    tp_r: tuple[float, ...] = Field(default=(), max_length=MAX_PLAN_PARTS)

    def spec(self) -> EntryPlanSpec:
        return EntryPlanSpec(
            self.mode, self.parts, self.weights, self.spacing_atr, self.lot_unit, tuple(self.tp_r)
        )


class RiskProfileDoc(BaseModel):
    """The wire format of the owner's limits (cloud → engine). Validated again on the engine: a document the
    engine refuses is never applied (fail closed to the last good one).

    ``risk_mode`` is on the wire only when AGGRESSIVE (:meth:`wire`): standard documents stay readable by
    engines from before PLAN §A36, and those engines refuse an aggressive one (unknown field)."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    version: str = Field(min_length=1, max_length=64)
    risk_per_trade_percent: float = Field(gt=0, le=HIGH_RISK_CEILING_RISK_PER_TRADE_PCT)
    total_open_risk_percent: float = Field(gt=0, le=HIGH_RISK_CEILING_TOTAL_OPEN_RISK_PCT)
    max_open_positions: int = Field(ge=1, le=20)
    max_daily_loss_percent: float = Field(gt=0, le=HIGH_RISK_CEILING_DAILY_LOSS_PCT)
    min_risk_reward: float = Field(ge=1.0, le=10)
    min_lot_fallback: bool = False
    entry_plan: EntryPlanDoc | None = None
    risk_mode: RiskMode | None = None  # None: STANDARD
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def _standard_ceilings(self) -> RiskProfileDoc:
        if self.risk_mode is not RiskMode.AGGRESSIVE and (
            self.risk_per_trade_percent > CEILING_RISK_PER_TRADE_PCT
            or self.total_open_risk_percent > CEILING_TOTAL_OPEN_RISK_PCT
            or self.max_daily_loss_percent > CEILING_DAILY_LOSS_PCT
        ):
            raise ValueError("a standard profile stays within the standard ceilings")
        if self.risk_mode is RiskMode.AGGRESSIVE and self.min_lot_fallback:
            raise ValueError("an aggressive profile never opens the minimum lot above its budget")
        return self

    @classmethod
    def of(cls, limits: ProfileLimits, updated_at: datetime | None = None) -> RiskProfileDoc:
        data = limits.to_dict()
        data["min_lot_fallback"] = bool(data.get("min_lot_fallback"))
        return cls(version=limits.version(), updated_at=updated_at, **data)

    def wire(self) -> dict[str, Any]:
        """The JSON body for the engine: ``risk_mode`` only when it is set (see the class notes)."""
        data = self.model_dump(mode="json")
        if self.risk_mode is None:
            data.pop("risk_mode")
        return data

    def limits(self) -> ProfileLimits:
        """Raises ``ValueError`` when the entry plan is incoherent (the caller refuses the document)."""
        return ProfileLimits(
            risk_per_trade_percent=self.risk_per_trade_percent,
            total_open_risk_percent=self.total_open_risk_percent,
            max_open_positions=self.max_open_positions,
            max_daily_loss_percent=self.max_daily_loss_percent,
            min_risk_reward=self.min_risk_reward,
            min_lot_fallback=self.min_lot_fallback,
            entry_plan=None if self.entry_plan is None else self.entry_plan.spec(),
            risk_mode=self.risk_mode or RiskMode.STANDARD,
        )


def governed(risk: RiskConfig) -> dict[str, float | int]:
    """The ``RiskConfig`` values a profile can lower, keyed like :class:`ProfileLimits`."""
    return {
        "risk_per_trade_percent": risk.max_risk_per_trade_percent,
        "total_open_risk_percent": risk.max_total_open_risk_percent,
        "max_open_positions": risk.max_open_positions,
        "max_daily_loss_percent": risk.max_daily_loss_percent,
        "min_risk_reward": risk.min_risk_reward,
    }


def _lower(local: float, profile: float | None) -> float:
    return local if profile is None else min(local, profile)


def effective_risk(local: RiskConfig, profile: ProfileLimits | None) -> RiskConfig:
    """The stricter value of each governed field. The result keeps the cage's class (a
    :class:`HighRiskCage` stays one, with its own bounds). An AGGRESSIVE profile against a standard cage
    raises :class:`HighRiskRefused`: it is never clamped into a standard cage's ceiling (PLAN §A36)."""
    if profile is not None and profile.aggressive and not isinstance(local, HighRiskCage):
        raise HighRiskRefused("an aggressive profile needs the high-risk cage")
    if profile is None:
        return local
    daily = _lower(local.max_daily_loss_percent, profile.max_daily_loss_percent)
    total = _lower(local.max_total_open_risk_percent, profile.total_open_risk_percent)
    per_trade = min(_lower(local.max_risk_per_trade_percent, profile.risk_per_trade_percent), daily, total)
    positions = local.max_open_positions
    if profile.max_open_positions is not None:
        positions = min(positions, profile.max_open_positions)
    min_rr = (
        local.min_risk_reward
        if profile.min_risk_reward is None
        else max(local.min_risk_reward, profile.min_risk_reward)
    )
    update: dict[str, float | int | bool] = {
        "min_lot_fallback": local.min_lot_fallback and bool(profile.min_lot_fallback),
        "max_daily_loss_percent": daily,
        "max_total_open_risk_percent": total,
        "max_risk_per_trade_percent": per_trade,
        "max_open_positions": positions,
        "min_risk_reward": min_rr,
    }
    # validate the combination (bounds and coherence) exactly as a local config would be
    return type(local).model_validate({**local.model_dump(), **update})
