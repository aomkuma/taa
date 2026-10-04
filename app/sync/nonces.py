"""Database-backed nonce store for HMAC verification across several web processes (TAA-702)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.core.clock import ensure_utc
from app.storage.database import Database
from app.storage.models import IngestNonceRow


class SqlNonceStore:
    """Implements :class:`app.security.hmac_auth.NonceStore`; the primary key makes the check atomic."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, engine_id: str, nonce: str, now: datetime, ttl: timedelta) -> bool:
        now = ensure_utc(now)
        with self.db.session() as sess:
            sess.execute(delete(IngestNonceRow).where(IngestNonceRow.expires_at <= now))
        try:
            with self.db.session() as sess:
                sess.add(IngestNonceRow(engine_id=engine_id, nonce=nonce, expires_at=now + ttl))
        except IntegrityError:
            return False
        return True
