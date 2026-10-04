"""Signed HTTP client for engine → cloud calls (PLAN §A13; TAA-701/704).

Every request is signed over the exact bytes sent (:mod:`app.security.hmac_auth`); ingest bodies are gzipped
JSON. The client never raises into the engine for HTTP failures: callers get a status (or None for a transport
error) and decide whether to back off.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.security.hmac_auth import Signer
from app.sync.outbox import SendResult

log = logging.getLogger(__name__)


class CloudClient:
    def __init__(
        self, base_url: str, signer: Signer, *, timeout: float = 15.0, http: httpx.Client | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.signer = signer
        self.http = http or httpx.Client(timeout=timeout)

    def _send(
        self,
        method: str,
        target: str,
        body: bytes = b"",
        extra: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        headers = self.signer.headers(method, target, body) | (extra or {})
        if timeout is None:
            return self.http.request(method, self.base_url + target, content=body, headers=headers)
        return self.http.request(
            method, self.base_url + target, content=body, headers=headers, timeout=timeout
        )

    def post_gzip(self, target: str, body: bytes) -> SendResult:
        """The outbox transport: POST a gzipped JSON batch."""
        try:
            resp = self._send(
                "POST",
                target,
                body,
                {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            )
        except httpx.HTTPError as exc:
            return SendResult(None, f"{type(exc).__name__}: {exc}")
        return SendResult(resp.status_code, "" if resp.is_success else f"HTTP {resp.status_code}")

    def get_json(self, target: str, timeout: float | None = None) -> tuple[int | None, Any]:
        """GET a JSON document (*timeout* overrides the default, e.g. for a long poll)."""
        try:
            resp = self._send("GET", target, timeout=timeout)
        except httpx.HTTPError as exc:
            log.warning("cloud GET %s failed: %s", target.split("?")[0], exc)
            return None, None
        try:
            return resp.status_code, resp.json() if resp.content else None
        except ValueError:
            return resp.status_code, None

    def post_json(self, target: str, body: bytes) -> int | None:
        try:
            resp = self._send("POST", target, body, {"Content-Type": "application/json"})
        except httpx.HTTPError as exc:
            log.warning("cloud POST %s failed: %s", target, exc)
            return None
        return resp.status_code

    def close(self) -> None:
        self.http.close()
