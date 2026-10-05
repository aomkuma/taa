"""Backup and restore of the engine database: online copy, integrity, audit chains, restore (TAA-1403)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.clock import ManualClock
from app.storage.audit import AuditLog
from app.storage.backup import BackupError, backup, check, restore, sqlite_path
from app.storage.database import Database
from app.storage.models import AuditEvent

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


def engine_db(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'engine.db').as_posix()}"
    db = Database(url)
    db.create_all()
    log = AuditLog(db, "engine:local", ManualClock(NOW))
    for i in range(3):
        log.append("TEST", "drill", {"i": i})
    db.engine.dispose()
    return url


def test_backup_is_checked_and_restore_keeps_the_old_database(tmp_path: Path) -> None:
    url = engine_db(tmp_path)
    report = backup(url, tmp_path / "backups" / "b1.db")
    assert report.chains == {"engine:local": 3} and len(report.sha256) == 64
    with pytest.raises(BackupError, match="already exists"):
        backup(url, report.path)

    db = Database(url)  # more happens after the backup
    AuditLog(db, "engine:local", ManualClock(NOW)).append("TEST", "drill", {"i": 3})
    db.engine.dispose()
    aside = restore(url, report.path, now=NOW)
    assert aside.name == "engine.db.before-restore-20261006T090000Z" and aside.exists()
    assert check(aside).chains == {"engine:local": 4}  # nothing is lost: the newer file is kept aside
    assert check(sqlite_path(url)).chains == {"engine:local": 3}


def test_a_tampered_backup_is_refused(tmp_path: Path) -> None:
    url = engine_db(tmp_path)
    copy = backup(url, tmp_path / "b.db").path
    con = sqlite3.connect(copy)
    con.execute("UPDATE audit_events SET payload = '{\"i\": 99}' WHERE seq = 2")
    con.commit()
    con.close()
    with pytest.raises(BackupError, match="audit chain engine:local is broken"):
        check(copy)
    with pytest.raises(BackupError):
        restore(url, copy, now=NOW)
    db = Database(url)
    with db.session() as sess:  # the live database was not touched
        assert len(sess.scalars(select(AuditEvent)).all()) == 3


def test_only_sqlite_files(tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="SQLite file"):
        sqlite_path("postgresql://x")
    with pytest.raises(BackupError, match="does not exist"):
        check(tmp_path / "missing.db")
