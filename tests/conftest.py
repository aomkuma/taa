from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.core.clock import ManualClock
from app.security.redaction import clear_registered_secrets
from app.storage.database import Database

BASE_ENV = {"TRADING_MODE": "BACKTEST"}

# Settings that belong to THIS machine, not to the project: a developer's .env must never change what
# the suite does. On 2026-10-27 `SYNC_ENABLED=true` was added to .env to pair the engine with the local
# web; tests that call `load_settings()` without `env_file=None` then started the cloud pull threads,
# which piled up until Python died with a Windows access violation about 1 % into the run - a crash that
# looked like flakiness and was reproducible. Clearing them for the session fixes the cause; a test that
# wants one sets it explicitly (tests/integration/test_engine_commands.py writes its own .env).
MACHINE_ONLY_ENV = (
    "SYNC_ENABLED",
    "CLOUD_BASE_URL",
    "ENGINE_ID",
    "ENGINE_HMAC_SECRET",
    "WEB_REQUIRE_TOTP",
)


@pytest.fixture(autouse=True, scope="session")
def _no_machine_env() -> Iterator[None]:
    saved = {k: os.environ.pop(k, None) for k in MACHINE_ONLY_ENV}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


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
