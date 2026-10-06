"""Plans and entitlements (PLAN §A30 "Entitlements & plans"; TAA-8A2).

**Typed keys.** :class:`Feature` (on/off) and :class:`Limit` (a number, ``None`` = unlimited) plus two
allow-lists, asset classes and evidence families (``None`` = all). Code uses these enums, never strings.

**Resolution** (:meth:`EntitlementService.resolve`), most specific last:

1. the plan: OWNER users always get the seeded ``OWNER`` plan (unlimited); others their ACTIVE subscription's
   plan (period not ended), else ``FREE``
2. per-user overrides (``entitlement_overrides``, one key each)

**Seeded plans** (:func:`seed_plans`, idempotent, run at web and worker start): ``OWNER`` (unlimited,
active), ``FREE`` and ``PRO`` (templates, inactive: not offered while subscriptions are disabled, TAA-8A5).

**Enforcement points:** the API (watchlist counts and sizes on every preference save, backtests per month at
creation, ``GET /me/entitlements`` for locked options in the UI), the personalizer (asset classes, families,
alerts per day via :meth:`Entitlements.personalizer`), worker quotas (the backtest counter) and the engine
compute union (an engine computes only detectors its users are entitled to, ``engine_advisory_config``).
Usage is counted in ``usage_counters`` per day or month.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.advisory.personalize import Entitlements as PersonalizerEntitlements
from app.advisory.preferences import AdvisoryPreferences
from app.core.clock import Clock, ensure_utc
from app.core.errors import TaaError
from app.evidence.framework import Family
from app.storage.database import Database
from app.storage.models import EntitlementOverrideRow, PlanRow, SubscriptionRow, UsageCounterRow, UserRow


class Feature(StrEnum):
    BACKTESTS = "BACKTESTS"
    AI_NARRATIVES = "AI_NARRATIVES"  # M2
    DATA_EXPORT = "DATA_EXPORT"  # trade/CSV exports (the PDPA export of one's own data is never gated)
    API_ACCESS = "API_ACCESS"


class Limit(StrEnum):
    ALERTS_PER_DAY = "ALERTS_PER_DAY"
    WATCHLISTS = "WATCHLISTS"
    WATCHLIST_SYMBOLS = "WATCHLIST_SYMBOLS"  # per list (an AUTO_TOP_N list takes at most this many ranks)
    BACKTESTS_PER_MONTH = "BACKTESTS_PER_MONTH"
    SHADOW_HISTORY_DAYS = "SHADOW_HISTORY_DAYS"


ASSET_CLASSES_KEY = "ASSET_CLASSES"
FAMILIES_KEY = "FAMILIES"
MONTHLY = frozenset({Limit.BACKTESTS_PER_MONTH})


class PlanSpec(BaseModel):
    """A plan's typed content (stored as ``plans.spec``)."""

    model_config = ConfigDict(extra="forbid")

    features: dict[Feature, bool] = Field(default_factory=dict)
    limits: dict[Limit, int | None] = Field(default_factory=dict)
    asset_classes: list[str] | None = None  # None: all
    families: list[Family] | None = None  # None: all


UNLIMITED = PlanSpec(features=dict.fromkeys(Feature, True), limits=dict.fromkeys(Limit))
SEED: dict[str, tuple[str, str, bool, PlanSpec]] = {
    "OWNER": ("เจ้าของระบบ", "Owner", True, UNLIMITED),
    "FREE": (
        "ฟรี",
        "Free",
        False,
        PlanSpec(
            features={
                Feature.BACKTESTS: False,
                Feature.AI_NARRATIVES: False,
                Feature.DATA_EXPORT: False,
                Feature.API_ACCESS: False,
            },
            limits={
                Limit.ALERTS_PER_DAY: 5,
                Limit.WATCHLISTS: 2,
                Limit.WATCHLIST_SYMBOLS: 10,
                Limit.BACKTESTS_PER_MONTH: 0,
                Limit.SHADOW_HISTORY_DAYS: 30,
            },
            asset_classes=["FOREX_MAJOR", "METAL"],
            families=[Family.TREND, Family.LEVELS, Family.FIBONACCI, Family.CANDLESTICK],
        ),
    ),
    "PRO": (
        "โปร",
        "Pro",
        False,
        PlanSpec(
            features={
                Feature.BACKTESTS: True,
                Feature.AI_NARRATIVES: False,
                Feature.DATA_EXPORT: True,
                Feature.API_ACCESS: False,
            },
            limits={
                Limit.ALERTS_PER_DAY: 30,
                Limit.WATCHLISTS: 10,
                Limit.WATCHLIST_SYMBOLS: 60,
                Limit.BACKTESTS_PER_MONTH: 20,
                Limit.SHADOW_HISTORY_DAYS: 365,
            },
        ),
    ),
}


class EntitlementError(TaaError):
    """The plan does not allow it (API: 403 ``plan_limit``)."""

    def __init__(self, key: str, message: str) -> None:
        super().__init__(message)
        self.key = key


@dataclass(frozen=True)
class Entitlements:
    plan: str
    features: Mapping[Feature, bool]
    limits: Mapping[Limit, int | None]
    asset_classes: frozenset[str] | None
    families: frozenset[Family] | None
    overrides: tuple[str, ...] = field(default=())

    def has(self, feature: Feature) -> bool:
        return bool(self.features.get(feature, False))  # unknown feature: off (fail closed)

    def limit(self, key: Limit) -> int | None:
        if key not in self.limits:
            return 0  # an unlisted limit is zero, never unlimited (fail closed)
        return self.limits[key]

    def personalizer(self) -> PersonalizerEntitlements:
        return PersonalizerEntitlements(
            asset_classes=self.asset_classes,
            families=self.families,
            alerts_per_day=self.limit(Limit.ALERTS_PER_DAY),
            ai=self.has(Feature.AI_NARRATIVES),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan,
            "features": {k.value: v for k, v in self.features.items()},
            "limits": {k.value: v for k, v in self.limits.items()},
            "asset_classes": None if self.asset_classes is None else sorted(self.asset_classes),
            "families": None if self.families is None else sorted(f.value for f in self.families),
            "overrides": list(self.overrides),
        }


def seed_plans(db: Database, now: datetime) -> None:
    """Insert the seeded plans that do not exist yet (an edited plan is never overwritten)."""
    with db.session() as sess:
        for code, (th, en, active, spec) in SEED.items():
            if sess.get(PlanRow, code) is None:
                sess.add(
                    PlanRow(
                        code=code,
                        name_th=th,
                        name_en=en,
                        active=active,
                        spec=spec.model_dump(mode="json"),
                        updated_at=now,
                    )
                )


def period_of(key: Limit, now: datetime) -> str:
    return now.strftime("%Y-%m") if key in MONTHLY else now.strftime("%Y-%m-%d")


class EntitlementService:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def plan_of(self, user: UserRow) -> str:
        if user.role == "OWNER":
            return "OWNER"
        now = self.clock.now_utc()
        with self.db.session() as sess:
            subs = sess.scalars(
                select(SubscriptionRow)
                .where(SubscriptionRow.user_id == user.id, SubscriptionRow.status == "ACTIVE")
                .order_by(SubscriptionRow.created_at.desc())
            ).all()
        for sub in subs:
            if sub.period_end is None or ensure_utc(sub.period_end) > now:
                return sub.plan_code
        return "FREE"

    def resolve(self, user_id: str) -> Entitlements:
        with self.db.session() as sess:
            user = sess.get(UserRow, user_id)
            if user is None:
                raise EntitlementError("user", "no such user")
        code = self.plan_of(user)
        with self.db.session() as sess:
            plan = sess.get(PlanRow, code)
            spec = PlanSpec.model_validate(plan.spec) if plan is not None else SEED.get(code, SEED["FREE"])[3]
            overrides = sess.scalars(
                select(EntitlementOverrideRow).where(EntitlementOverrideRow.user_id == user_id)
            ).all()
        features = {f: bool(spec.features.get(f, False)) for f in Feature}
        limits: dict[Limit, int | None] = {k: spec.limits.get(k, 0) for k in Limit}
        asset_classes = None if spec.asset_classes is None else frozenset(spec.asset_classes)
        families = None if spec.families is None else frozenset(spec.families)
        applied = []
        for o in overrides:
            if o.key in Feature.__members__:
                features[Feature(o.key)] = bool(o.value)
            elif o.key in Limit.__members__:
                limits[Limit(o.key)] = None if o.value is None else int(o.value)
            elif o.key == ASSET_CLASSES_KEY:
                asset_classes = None if o.value is None else frozenset(o.value)
            elif o.key == FAMILIES_KEY:
                families = None if o.value is None else frozenset(Family(f) for f in o.value)
            else:
                continue  # an unknown key changes nothing
            applied.append(o.key)
        return Entitlements(code, features, limits, asset_classes, families, tuple(applied))

    # --- usage ---------------------------------------------------------------------------------------------

    def usage(self, user_id: str, key: Limit) -> int:
        with self.db.session() as sess:
            row = sess.get(UsageCounterRow, (user_id, key.value, period_of(key, self.clock.now_utc())))
            return 0 if row is None else row.count

    def consume(self, user_id: str, key: Limit, amount: int = 1) -> int:
        """Count *amount* against the limit, or raise :class:`EntitlementError` when it would exceed it."""
        limit = self.resolve(user_id).limit(key)
        now = self.clock.now_utc()
        with self.db.session() as sess:
            pk = (user_id, key.value, period_of(key, now))
            row = sess.get(UsageCounterRow, pk)
            used = 0 if row is None else row.count
            if limit is not None and used + amount > limit:
                raise EntitlementError(key.value, f"your plan allows {limit} ({key.value})")
            if row is None:
                sess.add(
                    UsageCounterRow(
                        user_id=user_id, key=key.value, period=pk[2], count=amount, updated_at=now
                    )
                )
            else:
                row.count, row.updated_at = used + amount, now
            return used + amount

    # --- checks on documents --------------------------------------------------------------------------------

    @staticmethod
    def check_preferences(ent: Entitlements, prefs: AdvisoryPreferences) -> None:
        """Watchlist count and size within the plan (raises :class:`EntitlementError`)."""
        lists = ent.limit(Limit.WATCHLISTS)
        if lists is not None and len(prefs.watchlists) > lists:
            raise EntitlementError(Limit.WATCHLISTS.value, f"your plan allows {lists} watchlists")
        size = ent.limit(Limit.WATCHLIST_SYMBOLS)
        if size is not None:
            for w in prefs.watchlists:  # AUTO_TOP_N lists are capped where the ranking is used (alerter)
                if len(w.symbols) > size:
                    raise EntitlementError(
                        Limit.WATCHLIST_SYMBOLS.value, f"your plan allows {size} symbols per list"
                    )
