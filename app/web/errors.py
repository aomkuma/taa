"""API error shape and handlers.

Every error response has the body ``{"error": {"code": "<snake_case>", "message": "<English>"}}``
(the PWA translates by ``code``). Internals never leak: unexpected exceptions become ``internal_error`` with
the traceback in the log only, and validation errors report field locations without echoing the submitted
values.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import TaaError

log = logging.getLogger(__name__)

STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "request_too_large",
    415: "unsupported_media_type",
    422: "invalid_request",
    429: "too_many_requests",
    503: "unavailable",
}


class ApiProblem(TaaError):
    """Raised by routes and dependencies to return a well-formed error response."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        headers: Mapping[str, str] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = dict(headers or {})
        self.extra = dict(extra or {})


def error_response(
    status: int,
    code: str,
    message: str,
    *,
    headers: Mapping[str, str] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, **(extra or {})}},
        status_code=status,
        headers=dict(headers or {}),
    )


async def _api_problem(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiProblem):  # pragma: no cover - registered for ApiProblem only
        raise exc
    return error_response(exc.status, exc.code, exc.message, headers=exc.headers, extra=exc.extra)


async def _http_exception(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover
        raise exc
    code = STATUS_CODES.get(exc.status_code, "error")
    message = exc.detail if isinstance(exc.detail, str) else code
    return error_response(exc.status_code, code, message, headers=exc.headers)


async def _validation_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover
        raise exc
    fields = [
        {"loc": [str(p) for p in err.get("loc", ())], "type": err.get("type", "")} for err in exc.errors()
    ]
    return error_response(422, "invalid_request", "The request is invalid", extra={"fields": fields})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiProblem, _api_problem)
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(RequestValidationError, _validation_error)


class InternalErrorMiddleware:
    """Turns an unexpected exception into a JSON 500 *inside* the security-header middleware.

    Starlette's own server-error middleware sits outside every user middleware, so its responses would miss
    the security headers; catching here keeps every response on the same header set.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            log.exception("unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            response = error_response(500, "internal_error", "Internal error")
            await response(scope, receive, send)
