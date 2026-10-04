"""Advisory-config pull client: the users' compute requirements from the cloud (PLAN §A26, §A30; TAA-707).

``GET /api/v1/engine/advisory-config`` (HMAC-signed, conditional on ``If-None-Match``) returns an
:class:`app.advisory.requirements.AdvisoryConfig`. The client polls it on its own thread every
``sync.advisory_config_seconds``; the engine loop only reads :attr:`AdvisoryConfigClient.current`, so a
slow or offline cloud never delays a cycle.

Fallback order: the last config received in this run → the cached one (``engine_state`` key
``advisory_config``, survives restarts) → the local ``config.yaml`` preferences (``current`` is None). The
config only decides what the advisory scanner computes and which symbols it watches; it never touches the
bot's trading universe, strategies or risk.

Answers: 200 (validated, cached), 304 (unchanged), 404 (the cloud does not serve it yet: keep the fallback,
not an error); anything else counts a failure and backs off (2 s doubling to ``backoff_max_seconds``).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.advisory.requirements import AdvisoryConfig
from app.core.clock import Clock
from app.storage.repositories import EngineStateRepository

log = logging.getLogger(__name__)

ADVISORY_CONFIG_PATH = "/api/v1/engine/advisory-config"
CACHE_KEY = "advisory_config"

# (target, etag) -> (HTTP status or None for a transport error, JSON body, ETag header)
ConditionalGet = Callable[[str, str | None], tuple[int | None, Any, str | None]]


class AdvisoryConfigClient:
    def __init__(
        self,
        get: ConditionalGet,
        state: EngineStateRepository,
        clock: Clock,
        *,
        refresh_seconds: float = 300.0,
        backoff_max_seconds: float = 300.0,
    ) -> None:
        self.get = get
        self.state = state
        self.clock = clock
        self.refresh_seconds = refresh_seconds
        self.backoff_max_seconds = backoff_max_seconds
        self.current: AdvisoryConfig | None = None
        self.etag: str | None = None
        self.source = "local"  # local | cache | cloud
        self.failures = 0
        self.last_error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._load_cache()

    def _load_cache(self) -> None:
        cached = self.state.load(CACHE_KEY)
        if not cached:
            return
        try:
            self.current = AdvisoryConfig.model_validate(cached.get("config"))
        except ValidationError:
            log.warning(
                "cached advisory config is invalid; using the local preferences until the cloud answers"
            )
            return
        etag = cached.get("etag")
        self.etag = etag if isinstance(etag, str) and etag else None
        self.source = "cache"

    def poll_once(self) -> bool:
        """One conditional GET. True when the cloud answered usefully (200, 304 or 404)."""
        status, data, etag = self.get(ADVISORY_CONFIG_PATH, self.etag)
        if status == 304:
            self.failures = 0
            return True
        if status == 404:  # not served (yet): the fallback stays in force
            self.failures = 0
            return True
        if status != 200:
            return self._failed(f"HTTP {status}" if status is not None else "transport error")
        try:
            config = AdvisoryConfig.model_validate(data)
        except ValidationError as exc:
            return self._failed(f"invalid advisory config: {exc.error_count()} errors")
        self.etag = etag or config.version
        if self.current is None or config.version != self.current.version:
            log.info("advisory config %s received from the cloud", config.version)
        self.current = config
        self.source = "cloud"
        self.failures = 0
        self.state.save(
            CACHE_KEY,
            {
                "etag": self.etag,
                "config": config.model_dump(mode="json"),
                "fetched_at": self.clock.now_utc().isoformat(),
            },
        )
        return True

    def _failed(self, error: str) -> bool:
        self.failures += 1
        self.last_error = error
        log.warning("advisory config pull failed (%s); keeping the %s config", error, self.source)
        return False

    def delay(self) -> float:
        if self.failures == 0:
            return self.refresh_seconds
        return min(self.backoff_max_seconds, 2.0 ** min(self.failures, 8))

    def status(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "version": None if self.current is None else self.current.version,
            "failures": self.failures,
            "last_error": self.last_error,
        }

    def start(self) -> None:
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="advisory-config", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:  # thread boundary: the fallback config stays in force
                log.exception("advisory config pull failed")
                self.failures += 1
            self._stop.wait(self.delay())

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
