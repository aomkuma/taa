"""Cloud-sync tables (PLAN §A13): the cloud's ingest nonce store and, on the engine, the event outbox."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base
from app.storage.types import UTCDateTime


class IngestNonceRow(Base):
    """A request nonce seen by the cloud, kept until it expires (replay protection, TAA-702)."""

    __tablename__ = "ingest_nonces"

    engine_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
