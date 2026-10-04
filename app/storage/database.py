"""Database engine/session management for SQLite (engine, local dev) and PostgreSQL (Railway)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import StorageError

log = logging.getLogger(__name__)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _normalize_url(url: str) -> str:
    # Railway/Heroku style URLs use the legacy scheme; SQLAlchemy + psycopg3 wants postgresql+psycopg.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def create_db_engine(url: str, *, echo: bool = False) -> Engine:
    url = _normalize_url(url)
    if _is_sqlite(url):
        memory = url in ("sqlite://", "sqlite:///:memory:")
        if not memory:
            db_path = Path(url.split("///", 1)[1])
            db_path.parent.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if memory:
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, echo=echo, **kwargs)

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
            cur = dbapi_conn.cursor()
            if not memory:
                cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=FULL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

        return engine
    return create_engine(url, echo=echo, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800)


class Database:
    """Owns the engine and session factory. ``session()`` commits on success, rolls back on error."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.url = _normalize_url(url)
        self.engine = create_db_engine(self.url, echo=echo)
        self._factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    @property
    def session_factory(self) -> sessionmaker[Session]:
        """The factory behind :meth:`session` (for session event listeners such as replication)."""
        return self._factory

    @property
    def is_sqlite(self) -> bool:
        return _is_sqlite(self.url)

    @contextmanager
    def session(self) -> Iterator[Session]:
        sess = self._factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def create_all(self) -> None:
        """Create tables directly from metadata (tests). Production uses Alembic migrations."""
        from app.storage.models import Base

        Base.metadata.create_all(self.engine)

    def healthcheck(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            log.error("database healthcheck failed: %s", exc)
            return False

    def dispose(self) -> None:
        self.engine.dispose()


def upgrade_schema(url: str, revision: str = "head") -> None:
    """Apply Alembic migrations to the database at ``url``."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", _normalize_url(url).replace("%", "%%"))
    try:
        command.upgrade(cfg, revision)
    except Exception as exc:
        raise StorageError(f"schema migration failed: {exc}") from exc


def resolve_db_url(url: str) -> str:
    """Make relative SQLite paths (sqlite:///data/x.db) absolute against the repository root."""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url[len("sqlite:///") :]
        if rel and rel != ":memory:" and not Path(rel).is_absolute():
            root = Path(__file__).resolve().parent.parent.parent
            return "sqlite:///" + (root / rel).as_posix()
    return url
