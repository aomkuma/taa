"""Backup and restore of the engine's SQLite database (TAA-1403 drills; PLAN §A18).

The engine's local database is authoritative for trading state, so a restore must bring back a database
that is whole and untampered:

- :func:`backup` uses SQLite's online backup API (consistent with a running engine in WAL mode) and then
  checks the copy.
- :func:`check` runs ``PRAGMA integrity_check`` and verifies every audit hash chain in the file.
- :func:`restore` refuses a file that fails :func:`check`, moves the current database (with its ``-wal`` and
  ``-shm`` files) aside as ``<name>.before-restore-<UTC time>`` and copies the backup into place. The engine
  must be stopped (the CLI checks its health port first).
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.errors import TaaError
from app.storage.audit import verify_chain
from app.storage.database import Database
from app.storage.models import AuditEvent


class BackupError(TaaError):
    pass


@dataclass(frozen=True, slots=True)
class BackupReport:
    path: Path
    size: int
    sha256: str
    chains: dict[str, int]  # chain → verified events


def sqlite_path(url: str) -> Path:
    if not url.startswith("sqlite:///") or url.endswith(":memory:"):
        raise BackupError(f"backup and restore need a SQLite file database (got {url.split(':', 1)[0]})")
    return Path(url[len("sqlite:///") :])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check(path: Path) -> BackupReport:
    """Integrity and every audit chain of the database file *path*; raises :class:`BackupError`."""
    if not path.is_file():
        raise BackupError(f"{path} does not exist")
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        result = con.execute("PRAGMA integrity_check").fetchone()
    finally:
        con.close()
    if result is None or result[0] != "ok":
        raise BackupError(f"{path}: integrity check failed ({result})")
    db = Database(f"sqlite:///{path.as_posix()}")
    chains: dict[str, int] = {}
    try:
        with db.session() as sess:
            names = sorted(set(sess.scalars(select(AuditEvent.chain))))
        for name in names:
            report = verify_chain(db, name)
            if not report.ok:
                raise BackupError(
                    f"{path}: audit chain {name} is broken at {report.first_bad_seq}: {report.detail}"
                )
            chains[name] = report.events_checked
    finally:
        db.engine.dispose()
    return BackupReport(path, path.stat().st_size, _sha256(path), chains)


def backup(url: str, out: Path) -> BackupReport:
    """Copy the live database at *url* to *out* (online, consistent) and check the copy."""
    src = sqlite_path(url)
    if not src.is_file():
        raise BackupError(f"{src} does not exist")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise BackupError(f"{out} already exists")
    source, target = sqlite3.connect(src), sqlite3.connect(out)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return check(out)


def restore(url: str, backup_file: Path, *, now: datetime) -> Path:
    """Replace the database at *url* with *backup_file* (checked first); returns where the old one went."""
    report = check(backup_file)
    dst = sqlite_path(url)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    aside = dst.with_name(f"{dst.name}.before-restore-{stamp}")
    if dst.exists():
        dst.replace(aside)
    for suffix in ("-wal", "-shm"):
        extra = dst.with_name(dst.name + suffix)
        if extra.exists():
            extra.replace(aside.with_name(aside.name + suffix))
    shutil.copyfile(report.path, dst)
    return aside
