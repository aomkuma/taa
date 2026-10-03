"""Effective risk limits: min(trading profile, local ``RiskConfig``) (PLAN §A31 safety, §A13/§A20; TAA-406).

A trading profile comes from the cloud and is untrusted for raising risk. Every limit it shares with the local
configuration is combined in the conservative direction (lower risk and loss caps, fewer positions, a higher
minimum RR), so a profile can only make the owner's trading more conservative. Coherence rules of
``RiskConfig`` (risk per trade ≤ daily loss, ≤ total open risk) are restored by lowering, never by raising.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.config import RiskConfig


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
