"""Which risk limits the engine trades with (PLAN §A33, §A36; TAA-710).

The local ``config.yaml`` → ``risk`` is the outer cage. Inside it the engine owner's trading profile decides,
combined through :func:`app.risk.limits.effective_risk` (the stricter value of each field wins):

1. the profile the cloud sent (:class:`app.sync.risk_profile.RiskProfileClient`, this run or its cache);
2. otherwise the local profile, ``config.yaml`` → ``advisory.preferences.trading_profile``.

There is no third step: the bare cage is never used on its own, so losing the cloud cannot make the engine
less conservative than the owner chose. A cloud document the engine cannot combine with its cage (it fails
``RiskConfig`` validation) is refused, audited once per version (``RISK_PROFILE_REJECTED``) and the local
profile applies. Every change of the applied limits is audited (``RISK_PROFILE_APPLIED``).

**Aggressive preset (PLAN §A36).** A profile with ``risk_mode: AGGRESSIVE`` trades inside the high-risk cage
(:meth:`app.config.Settings.high_risk_cage`) only when this machine opted in (env flag + account-bound
confirmation + a ``high_risk:`` section) and the trading mode is allowed. Otherwise it is refused, audited
once per version (``HIGH_RISK_REFUSED`` with ``HIGH_RISK_NOT_ENABLED`` / ``HIGH_RISK_MODE_NOT_ALLOWED``) and
the STANDARD local profile applies: a refusal can only make the engine more conservative.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.advisory.preferences import TradingProfile, local_preferences
from app.config import AppConfig, HighRiskCage, RiskConfig
from app.core.clock import Clock
from app.core.errors import ConfigError
from app.risk.limits import ProfileLimits, RiskMode, effective_risk, governed
from app.risk.reasons import Reason
from app.storage.audit import AuditLog
from app.sync.risk_profile import RiskProfileClient

log = logging.getLogger(__name__)

REFUSALS = {
    "NOT_ENABLED": Reason.HIGH_RISK_NOT_ENABLED,
    "MODE_NOT_ALLOWED": Reason.HIGH_RISK_MODE_NOT_ALLOWED,
}


@dataclass(frozen=True, slots=True)
class AppliedRisk:
    limits: ProfileLimits  # the profile's values, before the cage
    origin: str  # cloud | cache | local
    version: str
    effective: RiskConfig
    cage: RiskConfig  # the cage the limits were combined with (a HighRiskCage in AGGRESSIVE)
    refused: Reason | None = None  # an AGGRESSIVE profile this engine refused (the STANDARD one applies)

    @property
    def source(self) -> str:
        return f"{self.origin}:{self.version}"

    @property
    def risk_mode(self) -> RiskMode:
        return self.limits.risk_mode

    @property
    def aggressive(self) -> bool:
        return isinstance(self.cage, HighRiskCage) and self.limits.aggressive


class RiskLimitSelector:
    def __init__(
        self,
        config: AppConfig,
        client: RiskProfileClient | None,
        audit: AuditLog | None,
        clock: Clock,
        *,
        high_risk: HighRiskCage | None = None,
        high_risk_refusal: str | None = "NOT_ENABLED",
    ) -> None:
        self.cage = config.risk
        self.high_risk = high_risk
        # why an AGGRESSIVE profile is refused here (None: the cage is available)
        self.high_risk_refusal: Reason | None = (
            None
            if high_risk is not None
            else REFUSALS.get(high_risk_refusal or "NOT_ENABLED", Reason.HIGH_RISK_NOT_ENABLED)
        )
        self.plans_enabled = config.execution.entry_plans
        self.client = client
        self.audit = audit
        self.clock = clock
        try:
            local = local_preferences(config).engine_limits()
        except ConfigError:
            log.warning("advisory.preferences is invalid; the local risk profile uses the defaults")
            local = TradingProfile().resolve().limits()
        self.local = local
        # what applies when an aggressive profile is refused: the local profile, never aggressive itself
        self.standard = local if not local.aggressive else TradingProfile().resolve().limits()
        self._applied: AppliedRisk | None = None
        self._refused: set[str] = set()

    def current(self) -> AppliedRisk:
        """The limits for this decision; audits when they change. Called on the engine loop only."""
        chosen = self._from_cloud() or self._combine(self.local, "local", self.local.version())
        previous = self._applied
        if previous is None or self._key(chosen) != self._key(previous):
            self._record(chosen, previous)
        self._applied = chosen
        return chosen

    @staticmethod
    def _key(applied: AppliedRisk) -> tuple[Any, ...]:
        eff = applied.effective
        return (
            applied.version,
            governed(eff),
            eff.min_lot_fallback,
            applied.aggressive,
            applied.refused,
            eff.max_weekly_loss_percent,
            eff.max_account_drawdown_percent,
        )

    def _combine(self, limits: ProfileLimits, origin: str, version: str) -> AppliedRisk:
        """*limits* inside their cage; an AGGRESSIVE profile without the high-risk cage is refused."""
        if limits.aggressive:
            if self.high_risk is not None:
                return AppliedRisk(
                    limits, origin, version, effective_risk(self.high_risk, limits), self.high_risk
                )
            reason = self.high_risk_refusal or Reason.HIGH_RISK_NOT_ENABLED
            self._refuse_aggressive(version, reason)
            standard = self.standard
            return AppliedRisk(
                standard, origin, version, effective_risk(self.cage, standard), self.cage, refused=reason
            )
        return AppliedRisk(limits, origin, version, effective_risk(self.cage, limits), self.cage)

    def _refuse_aggressive(self, version: str, reason: Reason) -> None:
        key = f"high-risk:{version}"
        if key in self._refused:
            return
        self._refused.add(key)
        log.warning("aggressive risk profile %s refused (%s); the standard profile applies", version, reason)
        if self.audit is not None:
            self.audit.append("HIGH_RISK_REFUSED", "engine", {"version": version, "reason": reason.value})

    def _from_cloud(self) -> AppliedRisk | None:
        doc = None if self.client is None else self.client.current
        if self.client is None or doc is None:
            return None
        try:
            limits = doc.limits()
            return self._combine(limits, self.client.source, doc.version)
        except (ValidationError, ValueError) as exc:
            if doc.version not in self._refused:
                self._refused.add(doc.version)
                log.warning("risk profile %s refused: %s; the local profile applies", doc.version, exc)
                if self.audit is not None:
                    profile = doc.model_dump(mode="json", exclude={"version", "updated_at"})
                    self.audit.append(
                        "RISK_PROFILE_REJECTED",
                        "engine",
                        {"version": doc.version, "profile": profile, "error": str(exc)[:500]},
                    )
            return None

    def _record(self, chosen: AppliedRisk, previous: AppliedRisk | None) -> None:
        effective = governed(chosen.effective)
        log.info(
            "risk limits from %s (%s): %s (cage %s)",
            chosen.source,
            "AGGRESSIVE" if chosen.aggressive else "STANDARD",
            effective,
            governed(chosen.cage),
        )
        if self.audit is not None:
            self.audit.append(
                "RISK_PROFILE_APPLIED",
                "engine",
                {
                    "source": chosen.source,
                    "profile": chosen.limits.to_dict(),
                    "cage": governed(chosen.cage),
                    "effective": effective,
                    "min_lot_fallback": chosen.effective.min_lot_fallback,
                    "risk_mode": RiskMode.AGGRESSIVE.value if chosen.aggressive else RiskMode.STANDARD.value,
                    "refused": None if chosen.refused is None else chosen.refused.value,
                    "weekly_loss_percent": chosen.effective.max_weekly_loss_percent,
                    "drawdown_percent": chosen.effective.max_account_drawdown_percent,
                    "previous": None if previous is None else governed(previous.effective),
                },
            )

    def scan_limits(self) -> ProfileLimits:
        """The owner's limits for the scanner's ADVISORY decisions, always STANDARD: the advisory path sizes
        inside ``risk:`` and never inside the high-risk cage (PLAN §A36)."""
        limits = self.current().limits
        return limits if not limits.aggressive else self.standard

    def config_ok(self) -> bool:
        """For the mode gate's RISK_CONFIG condition: the applied limits validate again inside their cage."""
        applied = self._applied
        if applied is None:
            return False
        try:
            type(applied.effective).model_validate(applied.effective.model_dump())
        except ValidationError:
            return False
        return not applied.limits.aggressive or isinstance(applied.cage, HighRiskCage)

    def high_risk_snapshot(self) -> dict[str, Any]:
        """Whether the aggressive preset can apply on this engine (the PWA enables the choice from this)."""
        cage = self.high_risk
        return {
            "available": cage is not None,
            "reason": None if self.high_risk_refusal is None else self.high_risk_refusal.value,
            "max_risk_percent": None if cage is None else cage.max_risk_per_trade_percent,
            "drawdown_kill_percent": None if cage is None else cage.max_account_drawdown_percent,
            "weekly_loss_percent": None if cage is None else cage.max_weekly_loss_percent,
            "setups": [] if cage is None else list(cage.setups),
            "fade_risk_factor": None if cage is None else cage.fade_risk_factor,
        }

    def snapshot(self) -> dict[str, Any] | None:
        """For the heartbeat: what the engine uses now and where it came from."""
        applied = self._applied
        if applied is None:
            return None
        fetched: datetime | None = None
        if self.client is not None and applied.origin != "local":
            fetched = self.client.fetched_at
        age = None if fetched is None else max(0.0, (self.clock.now_utc() - fetched).total_seconds())
        return {
            "source": applied.origin,
            "version": applied.version,
            "age_seconds": None if age is None else round(age),
            "cage": governed(applied.cage),
            "profile": {
                k: v
                for k, v in applied.limits.to_dict().items()
                if k not in ("min_lot_fallback", "entry_plan", "risk_mode")
            },
            "effective": governed(applied.effective),
            "min_lot_fallback": applied.effective.min_lot_fallback,
            "entry_plan": None if applied.limits.entry_plan is None else applied.limits.entry_plan.to_dict(),
            "entry_plans_enabled": self.plans_enabled,
            "risk_mode": RiskMode.AGGRESSIVE.value if applied.aggressive else RiskMode.STANDARD.value,
            "refused": None if applied.refused is None else applied.refused.value,
            "high_risk": self.high_risk_snapshot(),
        }
