"""The engine's sync runtime: built from settings, started and stopped with the engine (TAA-701)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.core.errors import ConfigError
from app.sync.runtime import SyncRuntime
from tests.integration.test_engine_paper import harness, settings

SECRET = "k" * 40


def sync_settings(tmp_path: Path, **env: object):  # type: ignore[no-untyped-def]
    s = settings(tmp_path, sync=settings(tmp_path).config.sync.model_copy(update={"enabled": True}))
    values = {
        "CLOUD_BASE_URL": "https://cloud.example",
        "ENGINE_ID": "eng-1",
        "ENGINE_HMAC_SECRET": SecretStr(SECRET),
    }
    return dataclasses.replace(s, env=s.env.model_copy(update=values | env))


def test_from_settings_needs_cloud_settings(tmp_path: Path, db) -> None:  # type: ignore[no-untyped-def]
    h = harness(tmp_path)
    s = sync_settings(tmp_path)
    runtime = SyncRuntime.from_settings(
        s, db, h.clock, http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    )
    assert runtime.client.base_url == "https://cloud.example" and runtime.sender.engine_id == "eng-1"
    with pytest.raises(ConfigError, match="CLOUD_BASE_URL"):
        SyncRuntime.from_settings(sync_settings(tmp_path, CLOUD_BASE_URL=None), db, h.clock)
    with pytest.raises(ConfigError, match="32"):
        SyncRuntime.from_settings(sync_settings(tmp_path, ENGINE_HMAC_SECRET=SecretStr("short")), db, h.clock)


def test_the_engine_starts_reports_and_stops_sync(tmp_path: Path) -> None:
    h = harness(tmp_path)
    s = sync_settings(tmp_path)
    runtime = SyncRuntime.from_settings(
        s, h.db, h.clock, http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    )
    calls: list[str] = []
    runtime.thread.start = lambda: calls.append("start")  # type: ignore[method-assign]
    runtime.thread.stop = lambda timeout=5.0: calls.append("stop")  # type: ignore[method-assign]
    assert runtime.advisory is not None
    runtime.advisory.start = lambda: calls.append("advisory")  # type: ignore[method-assign]
    h.engine.sync = runtime
    h.engine.start()
    before = h.engine.status()["sync"]
    assert before["pending"] > 0  # the start-up snapshot queued the existing rows (TAA-703)
    runtime.outbox.emit("command_result", {"command_id": "c1"})
    status = h.engine.status()["sync"]
    assert status["pending"] == before["pending"] + 1 and status["failed_sends"] == 0
    assert status["pending_by_priority"][0] == before["pending_by_priority"].get(0, 0) + 1
    h.engine.run(max_cycles=2)
    assert calls == ["start", "advisory", "stop"]


def test_without_sync_nothing_is_built(tmp_path: Path) -> None:
    h = harness(tmp_path)
    h.engine.start()
    assert h.engine.sync is None and h.engine.status()["sync"] is None
    h.engine.shutdown()
