"""Declarative base and shared column helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names keep Alembic migrations stable across SQLite and PostgreSQL.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# (rev. 4, TAA-709) Replicated rows belong to an engine. The engine's own database holds one engine and writes
# LOCAL_ENGINE; the cloud stores the verified signer's id and never trusts the payload. Rows the cloud writes
# itself (its ``web`` audit chain) also carry LOCAL_ENGINE.
LOCAL_ENGINE = "local"


class EngineKeyed:
    """Mixin: ``engine_id`` is the first part of the primary key (natural or engine-chosen keys)."""

    engine_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=LOCAL_ENGINE, server_default=LOCAL_ENGINE, sort_order=-1
    )


class EngineTagged:
    """Mixin: ``engine_id`` as an indexed column, for tables with a local autoincrement id."""

    engine_id: Mapped[str] = mapped_column(
        String(64), index=True, default=LOCAL_ENGINE, server_default=LOCAL_ENGINE, sort_order=-1
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
