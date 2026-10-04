"""Advisory config: the users' compute requirements from the cloud, with ETag, cache and fallback (TAA-707)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from app.advisory.preferences import local_preferences
from app.advisory.requirements import (
    AdvisoryConfig,
    advisory_config,
    compute_requirements,
    content_version,
    local_requirements,
    requirements_from_config,
)
from app.config import AppConfig
from app.core.clock import ManualClock
from app.evidence.catalog import default_registry as evidence_registry
from app.security.hmac_auth import Signer, Verifier
from app.storage.database import Database
from app.storage.repositories import EngineStateRepository
from app.strategy.catalog import default_registry
from app.sync.advisory_config import ADVISORY_CONFIG_PATH, CACHE_KEY, AdvisoryConfigClient
from app.sync.client import CloudClient

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
SECRET = "k" * 40


def remote(**over: Any) -> AdvisoryConfig:
    content: dict[str, Any] = {
        "favourites": ["XAUUSD"],
        "lists": {"0:metals": ["XAGUSD"]},
        "auto_top_n": 2,
        "detectors": ["fib.retracement", "no.such.detector"],
        "pattern_strategies": [],
        "lifetime_bars": 3,
    } | over
    return AdvisoryConfig(version=content_version(content), **content)


class Server:
    """A fake cloud: answers in order and records the If-None-Match header it saw."""

    def __init__(self, *answers: tuple[int, Any, str | None]) -> None:
        self.answers = list(answers)
        self.seen: list[str | None] = []

    def __call__(self, target: str, etag: str | None) -> tuple[int | None, Any, str | None]:
        assert target == ADVISORY_CONFIG_PATH
        self.seen.append(etag)
        return self.answers.pop(0) if self.answers else (304, None, etag)


def client(db: Database, server: Any) -> AdvisoryConfigClient:
    clock = ManualClock(NOW)
    return AdvisoryConfigClient(server, EngineStateRepository(db, clock), clock, refresh_seconds=60)


class TestRequirements:
    def test_the_engine_adds_what_only_it_knows(self) -> None:
        config = AppConfig()
        req = requirements_from_config(
            remote(),
            config,
            ranked=["GBPUSD", "USDJPY", "AUDUSD"],
            evidence=evidence_registry(),
            strategies=default_registry(),
        )
        allow = list(config.symbols.allowed)
        assert list(req.symbols) == [
            *allow,
            *[s for s in ["XAUUSD", "XAGUSD", "GBPUSD", "USDJPY"] if s not in allow],
        ]
        assert req.detectors == frozenset({"fib.retracement"})  # unknown names are skipped
        assert {i.name for i in config.strategies.items if i.enabled} <= req.strategies
        assert req.lifetime_bars == 3

    def test_unknown_setups_cannot_be_enabled(self) -> None:
        req = requirements_from_config(
            remote(pattern_strategies=["no_such_setup"]),
            AppConfig(),
            ranked=[],
            evidence=evidence_registry(),
            strategies=default_registry(),
        )
        assert "no_such_setup" not in req.strategies

    def test_one_user_through_the_cloud_equals_the_local_path(self) -> None:
        config = AppConfig()
        kwargs: dict[str, Any] = {
            "ranked": ["GBPUSD"],
            "evidence": evidence_registry(),
            "strategies": default_registry(),
        }
        wire = advisory_config(
            [local_preferences(config)], evidence=kwargs["evidence"], strategies=kwargs["strategies"]
        )
        via_cloud = requirements_from_config(
            AdvisoryConfig.model_validate(wire.model_dump(mode="json")), config, **kwargs
        )
        assert via_cloud == local_requirements(config, **kwargs)
        assert via_cloud == compute_requirements([local_preferences(config)], config, **kwargs)

    def test_the_version_follows_the_content(self) -> None:
        a, b = remote(), remote(auto_top_n=5)
        assert a.version != b.version and remote().version == a.version

    @pytest.mark.parametrize(
        "change",
        [
            {"auto_top_n": -1},
            {"lifetime_bars": 0},
            {"favourites": ["X" * 33]},
            {"lists": {"a": ["S"] * 501}},
            {"x": 1},
        ],
    )
    def test_the_wire_format_is_strict(self, change: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            AdvisoryConfig.model_validate(remote().model_dump(mode="json") | change)


class TestClient:
    def test_fallback_order_cloud_then_cache_then_local(self, db: Database) -> None:
        first = client(db, Server())
        assert first.current is None and first.source == "local"
        config = remote()
        server = Server((200, config.model_dump(mode="json"), config.version))
        live = client(db, server)
        assert live.poll_once() and live.current == config and live.source == "cloud"
        assert server.seen == [None]
        restarted = client(db, Server((None, None, None)))  # the cloud is down after a restart
        assert restarted.current == config and restarted.source == "cache"
        assert not restarted.poll_once() and restarted.current == config and restarted.failures == 1

    def test_etag_is_sent_and_304_keeps_the_config(self, db: Database) -> None:
        config = remote()
        server = Server((200, config.model_dump(mode="json"), "etag-1"), (304, None, "etag-1"))
        c = client(db, server)
        c.poll_once()
        assert c.poll_once() and c.current == config and server.seen == [None, "etag-1"]

    def test_invalid_answers_keep_the_previous_config(self, db: Database) -> None:
        config = remote()
        server = Server(
            (200, config.model_dump(mode="json"), config.version),
            (200, {"version": "v2", "auto_top_n": "lots"}, "v2"),
            (500, None, None),
        )
        c = client(db, server)
        c.poll_once()
        assert not c.poll_once() and not c.poll_once()
        assert c.current == config and c.failures == 2 and "HTTP 500" in c.last_error
        assert c.delay() == 4.0  # backing off

    def test_404_means_not_served_yet(self, db: Database) -> None:
        c = client(db, Server((404, None, None)))
        assert c.poll_once() and c.current is None and c.failures == 0 and c.delay() == 60

    def test_a_corrupt_cache_is_ignored(self, db: Database) -> None:
        EngineStateRepository(db, ManualClock(NOW)).save(CACHE_KEY, {"config": {"version": ""}, "etag": "x"})
        c = client(db, Server())
        assert c.current is None and c.source == "local" and c.etag is None

    def test_signed_conditional_get(self, db: Database) -> None:
        clock = ManualClock(NOW)
        verifier = Verifier.single("eng-1", SECRET, clock)
        config = remote()

        def handler(request: httpx.Request) -> httpx.Response:
            verifier.verify(
                request.method, request.url.raw_path.decode(), dict(request.headers), request.content
            )
            if request.headers.get("if-none-match") == f'"{config.version}"':
                return httpx.Response(304, headers={"ETag": f'"{config.version}"'})
            return httpx.Response(
                200, json=config.model_dump(mode="json"), headers={"ETag": f'W/"{config.version}"'}
            )

        cloud = CloudClient(
            "https://cloud.example",
            Signer("eng-1", SECRET.encode(), clock),
            http=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        c = AdvisoryConfigClient(cloud.get_conditional, EngineStateRepository(db, clock), clock)
        assert c.poll_once() and c.etag == config.version
        assert cloud.get_conditional(ADVISORY_CONFIG_PATH, c.etag)[0] == 304
        assert c.poll_once() and c.current == config
