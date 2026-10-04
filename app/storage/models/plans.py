"""Plans and entitlements, structure only (PLAN §A30 "Entitlements & plans"; TAA-8A2).

Cloud only. Billing is not implemented (TAA-8A5 adds the disabled scaffolding): a subscription row today is
assigned by the owner (``provider = "manual"``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base
from app.storage.types import JSONType, UTCDateTime


class PlanRow(Base):
    """A plan: TH/EN names and its typed features and limits (``app.web.entitlements.PlanSpec``)."""

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_th: Mapped[str] = mapped_column(String(64))
    name_en: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=False)  # offered to new subscribers
    spec: Mapped[dict[str, Any]] = mapped_column(JSONType)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class SubscriptionRow(Base):
    __tablename__ = "subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_code: Mapped[str] = mapped_column(String(32), ForeignKey("plans.code"))
    status: Mapped[str] = mapped_column(String(12), index=True)  # ACTIVE / CANCELED / PAST_DUE / EXPIRED
    period_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    provider: Mapped[str] = mapped_column(String(16), default="manual")
    provider_ref: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_by: Mapped[str] = mapped_column(String(64), default="")


class EntitlementOverrideRow(Base):
    """A per-user exception to the plan: one feature or limit key with its value."""

    __tablename__ = "entitlement_overrides"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONType, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_by: Mapped[str] = mapped_column(String(64), default="")


class UsageCounterRow(Base):
    """Usage per user, key and period (``2026-10-04`` for daily, ``2026-10`` for monthly limits)."""

    __tablename__ = "usage_counters"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    period: Mapped[str] = mapped_column(String(10), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
