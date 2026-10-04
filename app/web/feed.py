"""Who reads which engine's market facts (PLAN §A30 "compute once, personalize per user"; TAA-8A4).

- A user with an ACTIVE engine of their own reads that engine (their own account, their own facts).
- Otherwise a SUBSCRIBER reads the **market feed**: the ACTIVE engine of the deployment's OWNER (the oldest,
  when there are several). The owner's account stays private: subscribers get the market facts
  (ranking, opportunities, evidence, shadow outcomes in R), never the owner's lots, money, equity, plans,
  positions, decisions or trades (:data:`OWNER_ONLY_FIELDS`).
- ADMIN (support) reads no feed.

``engine_users`` is the reverse: the users an engine computes and alerts for (its owner, plus, for the
market feed, every active SUBSCRIBER without an engine of their own).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select

from app.storage.database import Database
from app.storage.models import EngineRow, UserRow

# Columns of opportunity and shadow rows that describe the engine owner's account, not the market.
OWNER_ONLY_FIELDS = frozenset(
    {
        "lot",
        "risk_money",
        "reward_money",
        "equity",
        "decision_id",
        "plan",
        "heat_after",
        "net_pnl",
        "gross_pnl",
        "commission",
        "swap",
        "pnl",
        "mae_money",
        "mfe_money",
        "followed",
        "warnings",  # the owner's account rules (loss limits, breakers, exposure)
    }
)


def own_engine(db: Database, user_id: str) -> str | None:
    with db.session() as sess:
        return sess.scalar(
            select(EngineRow.engine_id)
            .where(EngineRow.owner_user_id == user_id, EngineRow.status == "ACTIVE")
            .order_by(EngineRow.created_at)
            .limit(1)
        )


def market_feed(db: Database) -> str | None:
    """The deployment owner's oldest ACTIVE engine."""
    with db.session() as sess:
        return sess.scalar(
            select(EngineRow.engine_id)
            .join(UserRow, UserRow.id == EngineRow.owner_user_id)
            .where(UserRow.role == "OWNER", EngineRow.status == "ACTIVE")
            .order_by(EngineRow.created_at)
            .limit(1)
        )


def feed_engine(db: Database, user_id: str, role: str) -> str | None:
    """The engine whose market facts *user* reads (None: none available)."""
    own = own_engine(db, user_id)
    if own is not None:
        return own
    if role != "SUBSCRIBER":
        return None
    return market_feed(db)


def engine_users(db: Database, engine_id: str) -> list[str]:
    """The users *engine_id* alerts for: its owner first, then the subscribers it feeds."""
    with db.session() as sess:
        engine = sess.get(EngineRow, engine_id)
        if engine is None or engine.status != "ACTIVE":
            return []
        users = [engine.owner_user_id]
        if engine_id != market_feed(db):
            return users
        with_engines = set(
            sess.scalars(select(EngineRow.owner_user_id).where(EngineRow.status == "ACTIVE")).all()
        )
        subscribers = sess.scalars(
            select(UserRow.id)
            .where(UserRow.role == "SUBSCRIBER", UserRow.disabled.is_(False))
            .order_by(UserRow.created_at)
        ).all()
        return users + [u for u in subscribers if u not in with_engines]


def redact(item: Mapping[str, Any]) -> dict[str, Any]:
    """An opportunity or shadow row without the engine owner's account details."""
    return {k: v for k, v in item.items() if k not in OWNER_ONLY_FIELDS}
