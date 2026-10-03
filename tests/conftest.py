from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.core.clock import ManualClock
from app.security.redaction import clear_registered_secrets
from app.storage.database import Database

BASE_ENV = {"TRADING_MODE": "BACKTEST"}


@pytest.fixture(autouse=True)
def _clean_secrets() -> Iterator[None]:
    clear_registered_secrets()
    yield
    clear_registered_secrets()


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(datetime(2026, 10, 1, 12, 0, tzinfo=UTC))  # a Thursday


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database("sqlite://")
    database.create_all()
    yield database
    database.dispose()
