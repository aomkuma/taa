"""Thin repository helpers on top of SQLAlchemy sessions."""

from __future__ import annotations

import platform
from collections.abc import Sequence
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import Select, func, select

from app import __version__
from app.core.clock import Clock, SystemClock
from app.storage.database import Database
from app.storage.models import Base, ConfigSnapshot, Run

T = TypeVar("T", bound=Base)


class Repository:
    """Generic CRUD and pagination helpers shared by concrete repositories."""

    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self.db = db
        self.clock = clock or SystemClock()

    def add(self, obj: T) -> T:
        with self.db.session() as sess:
            sess.add(obj)
            sess.flush()
            return obj

    def add_all(self, objs: Sequence[Base]) -> None:
        with self.db.session() as sess:
            sess.add_all(list(objs))

    def get(self, model: type[T], key: Any) -> T | None:
        with self.db.session() as sess:
            return sess.get(model, key)

    def page(self, stmt: Select[Any], *, limit: int = 100, offset: int = 0) -> tuple[list[Any], int]:
        """Return one page of results and the total count for ``stmt``."""
        limit = max(1, min(limit, 1000))
        with self.db.session() as sess:
            total = sess.execute(
                select(func.count()).select_from(stmt.order_by(None).subquery())
            ).scalar_one()
            rows = list(sess.execute(stmt.limit(limit).offset(max(0, offset))).scalars())
        return rows, int(total)


class RunRepository(Repository):
    def start(self, run_id: str, process: str, mode: str, config_hash: str) -> Run:
        return self.add(
            Run(
                run_id=run_id,
                process=process,
                mode=mode,
                version=__version__,
                config_hash=config_hash,
                host=platform.node()[:128],
                started_at=self.clock.now_utc(),
                status="RUNNING",
            )
        )

    def finish(self, run_id: str, status: str = "STOPPED", detail: str = "") -> None:
        with self.db.session() as sess:
            run = sess.get(Run, run_id)
            if run is not None:
                run.ended_at = self.clock.now_utc()
                run.status = status
                run.detail = detail[:2000]

    def save_config_snapshot(self, config_hash: str, payload: dict[str, Any]) -> None:
        with self.db.session() as sess:
            if sess.get(ConfigSnapshot, config_hash) is None:
                sess.add(
                    ConfigSnapshot(config_hash=config_hash, created_at=self.clock.now_utc(), payload=payload)
                )

    def latest(self, process: str) -> Run | None:
        with self.db.session() as sess:
            return sess.execute(
                select(Run).where(Run.process == process).order_by(Run.started_at.desc()).limit(1)
            ).scalar_one_or_none()


def utc_range_filter(column: Any, start: datetime | None, end: datetime | None) -> list[Any]:
    conditions = []
    if start is not None:
        conditions.append(column >= start)
    if end is not None:
        conditions.append(column < end)
    return conditions
