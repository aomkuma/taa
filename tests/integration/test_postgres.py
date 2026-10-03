"""Runs only in CI (or locally) when DATABASE_URL points to PostgreSQL."""

from __future__ import annotations

import os

import pytest

from app.storage.audit import AuditLog
from app.storage.database import Database

pytestmark = pytest.mark.postgres

URL = os.environ.get("DATABASE_URL", "")


@pytest.mark.skipif(
    not URL.startswith(("postgres://", "postgresql")), reason="DATABASE_URL is not PostgreSQL"
)
def test_audit_chain_on_postgres() -> None:
    db = Database(URL)
    audit = AuditLog(db, "ci:postgres")
    for i in range(3):
        audit.append("ci.event", "ci", {"i": i, "nested": {"x": [1, 2]}})
    assert audit.verify().ok
    db.dispose()
