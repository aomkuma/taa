"""Which risk limits the engine trades with (PLAN §A33; TAA-710).

The local ``config.yaml`` → ``risk`` is the outer cage. Inside it the engine owner's trading profile decides,
combined through :func:`app.risk.limits.effective_risk` (the stricter value of each field wins):

1. the profile the cloud sent (:class:`app.sync.risk_profile.RiskProfileClient`, this run or its cache);
2. otherwise the local profile, ``config.yaml`` → ``advisory.preferences.trading_profile``.

There is no third step: the bare cage is never used on its own, so losing the cloud cannot make the engine
less conservative than the owner chose. A cloud document the engine cannot combine with its cage (it fails
``RiskConfig`` validation) is refused, audited once per version (``RISK_PROFILE_REJECTED``) and the local
profile applies. Every change of the applied limits is audited (``RISK_PROFILE_APPLIED``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.advisory.preferences import TradingProfile, local_preferences
from app.config import AppConfig, RiskConfig
from app.core.clock import Clock
from app.core.errors import ConfigError
from app.risk.limits import ProfileLimits, effective_risk, governed
from app.storage.audit import AuditLog
from app.sync.risk_profile import RiskProfileClient

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AppliedRisk:
    limits: ProfileLimits  # the profile's values, before the cage
    origin: str  # cloud | cache | local
    version: str
    effective: RiskConfig

    @property
    def source(self) -> str:
        return f"{self.origin}:{self.version}"


class RiskLimitSelector:
    def __init__(
        self, config: AppConfig, client: RiskProfileClient | None, audit: AuditLog | None, clock: Clock
    ) -> None:
        self.cage = config.risk
        self.client = client
        self.audit = audit
        self.clock = clock
        try:
            self.local = local_preferences(config).engine_limits()
        except ConfigError:
            log.warning("advisory.preferences is invalid; the local risk profile uses the defaults")
            self.local = TradingProfile().resolve().limits()
        self._applied: AppliedRisk | None = None
        self._refused: set[str] = set()

    def current(self) -> AppliedRisk:
        """The limits for this decision; audits when they change. Called on the engine loop only."""
        chosen = self._from_cloud() or AppliedRisk(
            self.local, "local", self.local.version(), effective_risk(self.cage, self.local)
        )
        previous = self._applied
        if previous is None or (
            chosen.version,
            governed(chosen.effective),
            chosen.effective.min_lot_fallback,
        ) != (previous.version, governed(previous.effective), previous.effective.min_lot_fallback):
            self._record(chosen, previous)
        self._applied = chosen
        return chosen

    def _from_cloud(self) -> AppliedRisk | None:
        doc = None if self.client is None else self.client.current
        if self.client is None or doc is None:
            return None
        try:
            limits = doc.limits()
            effective = effective_risk(self.cage, limits)
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
        return AppliedRisk(limits, self.client.source, doc.version, effective)

    def _record(self, chosen: AppliedRisk, previous: AppliedRisk | None) -> None:
        effective = governed(chosen.effective)
        log.info("risk limits from %s: %s (cage %s)", chosen.source, effective, governed(self.cage))
        if self.audit is not None:
            self.audit.append(
                "RISK_PROFILE_APPLIED",
                "engine",
                {
                    "source": chosen.source,
                    "profile": chosen.limits.to_dict(),
                    "cage": governed(self.cage),
                    "effective": effective,
                    "min_lot_fallback": chosen.effective.min_lot_fallback,
                    "previous": None if previous is None else governed(previous.effective),
                },
            )

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
            "cage": governed(self.cage),
            "profile": {
                k: v
                for k, v in applied.limits.to_dict().items()
                if k not in ("min_lot_fallback", "entry_plan")
            },
            "effective": governed(applied.effective),
            "min_lot_fallback": applied.effective.min_lot_fallback,
        }
