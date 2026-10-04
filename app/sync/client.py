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


def _rejected(resp: httpx.Response) -> dict[str, str]:
    try:
        doc = resp.json() if resp.content else {}
    except ValueError:
        return {}
    items = doc.get("rejected") if isinstance(doc, dict) else None
    out: dict[str, str] = {}
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and isinstance(item.get("event_id"), str) and item["event_id"]:
            out[item["event_id"]] = f"{item.get('code', '')}: {item.get('detail', '')}"[:500]
    return out


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
        """The outbox transport: POST a gzipped JSON batch.

        A 2xx answer lists the events the cloud refused for good (TAA-703); they come back in
        ``SendResult.rejected`` so the sender parks them instead of resending."""
        try:
            resp = self._send(
                "POST",
                target,
                body,
                {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            )
        except httpx.HTTPError as exc:
            return SendResult(None, f"{type(exc).__name__}: {exc}")
        if not resp.is_success:
            return SendResult(resp.status_code, f"HTTP {resp.status_code}")
        return SendResult(resp.status_code, "", _rejected(resp))

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

    def get_conditional(self, target: str, etag: str | None) -> tuple[int | None, Any, str | None]:
        """GET with ``If-None-Match``: (status, JSON body or None, ETag header).

        The status is None for a transport error."""
        try:
            resp = self._send("GET", target, extra={"If-None-Match": f'"{etag}"'} if etag else None)
        except httpx.HTTPError as exc:
            log.warning("cloud GET %s failed: %s", target, exc)
            return None, None, None
        header = resp.headers.get("etag")
        tag = header.removeprefix("W/").strip('"') if header else None
        if resp.status_code != 200 or not resp.content:
            return resp.status_code, None, tag
        try:
            return resp.status_code, resp.json(), tag
        except ValueError:
            return resp.status_code, None, tag

    def post_json(self, target: str, body: bytes) -> int | None:
        try:
            resp = self._send("POST", target, body, {"Content-Type": "application/json"})
        except httpx.HTTPError as exc:
            log.warning("cloud POST %s failed: %s", target, exc)
            return None
        return resp.status_code

    def close(self) -> None:
        self.http.close()
