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

from pydantic import BaseModel, ConfigDict, Field

from app.config import (
    CEILING_DAILY_LOSS_PCT,
    CEILING_RISK_PER_TRADE_PCT,
    CEILING_TOTAL_OPEN_RISK_PCT,
    RiskConfig,
)
from app.core.ids import stable_hash


@dataclass(frozen=True, slots=True)
class ProfileLimits:
    """Trading-profile values that also exist in ``RiskConfig`` (``None``: the profile does not set it)."""

    risk_per_trade_percent: float | None = None
    total_open_risk_percent: float | None = None  # portfolio heat
    max_open_positions: int | None = None
    max_daily_loss_percent: float | None = None
    min_risk_reward: float | None = None

    def __post_init__(self) -> None:
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

    def to_dict(self) -> dict[str, float | int | None]:
        return asdict(self)

    def version(self) -> str:
        return stable_hash(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")), length=16)


class RiskProfileDoc(BaseModel):
    """The wire format of the owner's limits (cloud → engine). Validated again on the engine: a document the
    engine refuses is never applied (fail closed to the last good one)."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    version: str = Field(min_length=1, max_length=64)
    risk_per_trade_percent: float = Field(gt=0, le=CEILING_RISK_PER_TRADE_PCT)
    total_open_risk_percent: float = Field(gt=0, le=CEILING_TOTAL_OPEN_RISK_PCT)
    max_open_positions: int = Field(ge=1, le=20)
    max_daily_loss_percent: float = Field(gt=0, le=CEILING_DAILY_LOSS_PCT)
    min_risk_reward: float = Field(ge=1.0, le=10)
    updated_at: datetime | None = None

    @classmethod
    def of(cls, limits: ProfileLimits, updated_at: datetime | None = None) -> RiskProfileDoc:
        return cls(version=limits.version(), updated_at=updated_at, **limits.to_dict())

    def limits(self) -> ProfileLimits:
        return ProfileLimits(
            risk_per_trade_percent=self.risk_per_trade_percent,
            total_open_risk_percent=self.total_open_risk_percent,
            max_open_positions=self.max_open_positions,
            max_daily_loss_percent=self.max_daily_loss_percent,
            min_risk_reward=self.min_risk_reward,
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
    update = {
        "max_daily_loss_percent": daily,
        "max_total_open_risk_percent": total,
        "max_risk_per_trade_percent": per_trade,
        "max_open_positions": positions,
        "min_risk_reward": min_rr,
    }
    # validate the combination (bounds and coherence) exactly as a local config would be
    return RiskConfig.model_validate({**local.model_dump(), **update})
