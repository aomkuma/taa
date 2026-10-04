"""A user's personal data: export and erasure (PLAN §A30 "PDPA-ready export/delete"; TAA-8A1).

**Export** collects everything stored about the user, as JSON: profile (never password hashes, TOTP or
session tokens), advisory preferences, notification preferences, push devices (service host and label, never
endpoints or keys), notifications, opportunity alerts, backtest runs (requests and metrics) and engines (the
public view, never secrets).

**Erasure** removes the personal data and keeps what must stay for integrity:

- deleted: sessions, advisory and notification preferences, push subscriptions, notifications, opportunity
  alerts, backtest runs, login-throttle counters
- kept but pseudonymised: the user row (username ``deleted-<id8>``, no password, no TOTP, disabled), because
  revoked engines and the append-only audit chains refer to it; replicated trading records of a revoked engine
  stay read-only for audit (§A32)
- refused: the deployment's OWNER (409 ``owner_cannot_be_erased``) and a user with an ACTIVE engine (409
  ``engines_active``: revoke it first, so nothing keeps sending data for an erased user)

Legal review (``docs/COMPLIANCE.md``) decides the retention of the kept records before subscriptions open.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from app.core.clock import Clock
from app.core.errors import TaaError
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import (
    BacktestRunRow,
    EngineRow,
    EntitlementOverrideRow,
    LoginThrottleRow,
    NotificationPrefsRow,
    NotificationRow,
    OpportunityAlertRow,
    PushSubscriptionRow,
    SessionRow,
    UsageCounterRow,
    UserAdvisoryPrefsRow,
    UserRow,
)
from app.sync.events import json_safe
from app.sync.notifications import notification_dict
from app.web.engines import EngineRegistry
from app.worker.backtests import run_dict


class PrivacyError(TaaError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def export_user(db: Database, registry: EngineRegistry, user_id: str, now: datetime) -> dict[str, Any]:
    with db.session() as sess:
        user = sess.get(UserRow, user_id)
        if user is None:
            raise PrivacyError("user_not_found", "No such user")
        prefs = sess.get(UserAdvisoryPrefsRow, user_id)
        notif_prefs = sess.get(NotificationPrefsRow, user_id)
        devices = sess.scalars(
            select(PushSubscriptionRow).where(PushSubscriptionRow.user_id == user_id)
        ).all()
        notes = sess.scalars(
            select(NotificationRow)
            .where(NotificationRow.user_id == user_id)
            .order_by(NotificationRow.created_at)
        ).all()
        alerts = sess.scalars(
            select(OpportunityAlertRow)
            .where(OpportunityAlertRow.user_id == user_id)
            .order_by(OpportunityAlertRow.sent_at)
        ).all()
        runs = sess.scalars(
            select(BacktestRunRow)
            .where(BacktestRunRow.owner_user_id == user_id)
            .order_by(BacktestRunRow.created_at)
        ).all()
        return {
            "exported_at": json_safe(now),
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "disabled": user.disabled,
                "locale": user.locale,
                "timezone": user.timezone,
                "created_at": json_safe(user.created_at),
                "password_changed_at": json_safe(user.password_changed_at),
                "totp_enrolled_at": json_safe(user.totp_enrolled_at),
            },
            "advisory_preferences": None if prefs is None else dict(prefs.prefs),
            "notification_preferences": None if notif_prefs is None else list(notif_prefs.disabled_types),
            "push_devices": [
                {
                    "label": d.label,
                    "service": d.endpoint.split("/")[2] if "://" in d.endpoint else "",
                    "created_at": json_safe(d.created_at),
                    "active": d.disabled_at is None,
                }
                for d in devices
            ],
            "notifications": [notification_dict(n) for n in notes],
            "opportunity_alerts": [
                {
                    "engine_id": a.engine_id,
                    "opportunity_id": a.opportunity_id,
                    "symbol": a.symbol,
                    "sent_at": json_safe(a.sent_at),
                    "status": a.status,
                }
                for a in alerts
            ],
            "backtests": [run_dict(r) for r in runs],
            "engines": [i.public() for i in registry.list_engines(user_id)],
        }


def erase_user(db: Database, clock: Clock, audit: AuditLog, user_id: str, *, actor: str) -> str:
    """Erase the user's personal data (see the module docstring); returns the pseudonym."""
    with db.session() as sess:
        user = sess.get(UserRow, user_id)
        if user is None:
            raise PrivacyError("user_not_found", "No such user")
        if user.role == "OWNER":
            raise PrivacyError("owner_cannot_be_erased", "The deployment's owner cannot be erased")
        active = sess.scalar(
            select(EngineRow.engine_id)
            .where(EngineRow.owner_user_id == user_id, EngineRow.status == "ACTIVE")
            .limit(1)
        )
        if active is not None:
            raise PrivacyError("engines_active", "Revoke the user's engines first")
        old_name = user.username
        for model, col in (
            (SessionRow, SessionRow.user_id),
            (UserAdvisoryPrefsRow, UserAdvisoryPrefsRow.user_id),
            (NotificationPrefsRow, NotificationPrefsRow.user_id),
            (PushSubscriptionRow, PushSubscriptionRow.user_id),
            (NotificationRow, NotificationRow.user_id),
            (OpportunityAlertRow, OpportunityAlertRow.user_id),
            (BacktestRunRow, BacktestRunRow.owner_user_id),
            (EntitlementOverrideRow, EntitlementOverrideRow.user_id),
            (UsageCounterRow, UsageCounterRow.user_id),
        ):
            sess.execute(delete(model).where(col == user_id))
        sess.execute(delete(LoginThrottleRow).where(LoginThrottleRow.key == f"user:{old_name}"))
        pseudonym = f"deleted-{user_id[:8]}"
        user.username, user.password_hash, user.totp_secret_enc = pseudonym, "!", ""
        user.totp_pending_enc, user.disabled = None, True
    audit.append(
        "user.erased", actor, {"user_id": user_id, "pseudonym": pseudonym, "at": clock.now_utc().isoformat()}
    )
    return pseudonym
