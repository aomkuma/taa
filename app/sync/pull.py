"""A document the engine pulls from the cloud on its own thread (TAA-707 advisory config, TAA-710 risk).

One conditional ``GET`` (HMAC-signed, ``If-None-Match``) every ``refresh_seconds``; the engine loop only
reads :attr:`PulledDocument.current`, so a slow or offline cloud never delays a cycle.

Fallback order: the last document received in this run → the cached one (``engine_state`` key, survives
restarts) → ``current`` is None and the caller uses its local fallback.

Answers: 200 (validated, cached), 304 (unchanged), 404 (the cloud does not serve it: keep the fallback, not an
error); anything else counts a failure and backs off (2 s doubling to ``backoff_max_seconds``). A 200 whose
body fails validation is a failure too: the previous document stays in force.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.clock import Clock
from app.storage.repositories import EngineStateRepository

log = logging.getLogger(__name__)

# (target, etag) -> (HTTP status or None for a transport error, JSON body, ETag header)
ConditionalGet = Callable[[str, str | None], tuple[int | None, Any, str | None]]

D = TypeVar("D", bound=BaseModel)


class PulledDocument(Generic[D]):
    """Subclasses set :attr:`path`, :attr:`cache_key`, :attr:`name` and :attr:`model` (with a ``version``)."""

    path: ClassVar[str]
    cache_key: ClassVar[str]
    name: ClassVar[str]
    model: type[D]

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
        self.current: D | None = None
        self.etag: str | None = None
        self.fetched_at: datetime | None = (
            None  # when the cloud last sent (or confirmed) the current document
        )
        self.source = "local"  # local | cache | cloud
        self.failures = 0
        self.last_error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._load_cache()

    def _load_cache(self) -> None:
        cached = self.state.load(self.cache_key)
        if not cached:
            return
        try:
            self.current = self.model.model_validate(cached.get("config"))
        except ValidationError:
            log.warning("cached %s is invalid; using the local fallback until the cloud answers", self.name)
            return
        etag = cached.get("etag")
        self.etag = etag if isinstance(etag, str) and etag else None
        fetched = cached.get("fetched_at")
        try:
            self.fetched_at = datetime.fromisoformat(fetched) if isinstance(fetched, str) else None
        except ValueError:
            self.fetched_at = None
        self.source = "cache"

    def poll_once(self) -> bool:
        """One conditional GET. True when the cloud answered usefully (200, 304 or 404)."""
        status, data, etag = self.get(self.path, self.etag)
        if status == 304:
            self.failures = 0
            if self.current is not None:
                self.fetched_at = self.clock.now_utc()
            return True
        if status == 404:  # not served (yet): the fallback stays in force
            self.failures = 0
            return True
        if status != 200:
            return self._failed(f"HTTP {status}" if status is not None else "transport error")
        try:
            doc = self.model.model_validate(data)
        except ValidationError as exc:
            errors = exc.errors()
            where = ".".join(str(x) for x in errors[0]["loc"]) if errors else ""
            detail = f"{where}: {errors[0]['msg']}" if errors else ""
            return self._failed(f"invalid {self.name}: {exc.error_count()} errors ({detail})")
        version = getattr(doc, "version", "")
        self.etag = etag or version
        if self.current is None or version != getattr(self.current, "version", None):
            log.info("%s %s received from the cloud", self.name, version)
        self.current = doc
        self.source = "cloud"
        self.failures = 0
        self.fetched_at = self.clock.now_utc()
        self.state.save(
            self.cache_key,
            {
                "etag": self.etag,
                "config": doc.model_dump(mode="json"),
                "fetched_at": self.fetched_at.isoformat(),
            },
        )
        return True

    def _failed(self, error: str) -> bool:
        self.failures += 1
        self.last_error = error
        log.warning("%s pull failed (%s); keeping the %s one", self.name, error, self.source)
        return False

    def delay(self) -> float:
        if self.failures == 0:
            return self.refresh_seconds
        return min(self.backoff_max_seconds, 2.0 ** min(self.failures, 8))

    def status(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "version": None if self.current is None else getattr(self.current, "version", None),
            "failures": self.failures,
            "last_error": self.last_error,
        }

    def start(self) -> None:
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name=self.cache_key, daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:  # thread boundary: the fallback stays in force
                log.exception("%s pull failed", self.name)
                self.failures += 1
            self._stop.wait(self.delay())

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
