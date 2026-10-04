"""Security headers and request-size limits for every response (PLAN §A14).

The CSP allows only same-origin resources: no inline scripts or styles, no ``eval``, no CDNs, no framing. The
PWA build is made to run under it (frontend/README.md). ``img-src data:`` is needed for the TOTP QR code.
"""

from __future__ import annotations

from collections.abc import Mapping

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.web.errors import error_response

CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "manifest-src 'self'",
        "worker-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
)

BASE_HEADERS: dict[str, str] = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
# Two years; only sent in production, where the service is reachable over HTTPS only.
HSTS = "max-age=63072000; includeSubDomains"

DEFAULT_MAX_BODY_BYTES = 64 * 1024


class SecurityHeadersMiddleware:
    """Adds the security headers to every HTTP response; API responses are never cached."""

    def __init__(self, app: ASGIApp, *, production: bool) -> None:
        self.app = app
        self.headers = {**BASE_HEADERS, **({"Strict-Transport-Security": HSTS} if production else {})}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = str(scope.get("path", "")).startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self.headers.items():
                    headers[name] = value
                if is_api:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Rejects request bodies above *max_bytes*, by ``Content-Length`` up front or while streaming.

    *path_limits* raises the limit for exact paths (the engine's gzipped ingest batches)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_bytes: int = DEFAULT_MAX_BODY_BYTES,
        path_limits: Mapping[str, int] | None = None,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.path_limits = dict(path_limits or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.path_limits.get(str(scope.get("path", "")), self.max_bytes)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = limit + 1
                if declared > limit:
                    response = error_response(413, "request_too_large", "The request body is too large")
                    await response(scope, receive, send)
                    return
        received = 0
        too_large = False
        started = False

        # A streamed body that grows past the limit is cut off with a disconnect; whatever the app answers to
        # the truncated body is dropped and replaced by a 413.
        async def limited_receive() -> Message:
            nonlocal received, too_large
            if too_large:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_large = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if too_large and not started:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not too_large or started:
                raise
        if too_large and not started:
            response = error_response(413, "request_too_large", "The request body is too large")
            await response(scope, receive, send)
