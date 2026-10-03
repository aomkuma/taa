"""Account snapshots, identity baseline and unexpected-change detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from app.broker.gateway import MarketDataGateway
from app.broker.models import AccountSnapshot, Deal

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccountChange:
    field: str
    before: object
    after: object
    critical: bool  # True: identity changed (halt + manual review); False: monitored (warn + re-check)


CRITICAL_FIELDS = ("login", "server", "trade_mode", "currency", "margin_mode")
# Expected to change during a run (FBS equity-tier leverage): reported as warnings, never as identity changes.
MONITORED_FIELDS = ("leverage",)


class AccountService:
    def __init__(self, gateway: MarketDataGateway) -> None:
        self.gateway = gateway
        self.baseline: AccountSnapshot | None = None
        self.last: AccountSnapshot | None = None

    def snapshot(self) -> AccountSnapshot:
        snap = self.gateway.account()
        if self.baseline is None:
            self.baseline = snap
        self.last = snap
        return snap

    def identity_changes(self, snap: AccountSnapshot) -> list[AccountChange]:
        """Differences from the baseline: critical identity fields plus monitored fields such as leverage."""
        if self.baseline is None:
            return []
        changes = [
            AccountChange(name, getattr(self.baseline, name), getattr(snap, name), name in CRITICAL_FIELDS)
            for name in (*CRITICAL_FIELDS, *MONITORED_FIELDS)
            if getattr(self.baseline, name) != getattr(snap, name)
        ]
        for change in changes:
            if not change.critical:
                log.warning(
                    "account %s changed %s -> %s (expected with FBS leverage tiers; margin re-check)",
                    change.field,
                    change.before,
                    change.after,
                )
        return changes

    def acknowledge_monitored(self, snap: AccountSnapshot) -> None:
        """Adopt the new values of monitored fields as the baseline once they were handled."""
        if self.baseline is None:
            return
        if all(getattr(self.baseline, name) == getattr(snap, name) for name in CRITICAL_FIELDS):
            self.baseline = snap

    def cash_flows(self, since_utc: datetime, until_utc: datetime) -> list[Deal]:
        """Deposits, withdrawals, credits and corrections (they adjust loss baselines)."""
        return [d for d in self.gateway.deals(since_utc, until_utc) if d.is_cash_flow]

    @staticmethod
    def stop_out_summary(snap: AccountSnapshot) -> str:
        unit = "%" if snap.margin_so_mode == 0 else snap.currency
        return f"margin call {snap.margin_so_call:g}{unit}, stop-out {snap.margin_so_so:g}{unit}"
