"""Shared state and FastAPI dependencies of the web service.

Dependency chain for protected routes: ``current_session`` (cookie → live session, else 401
``unauthenticated``) → ``csrf_session`` (allowed Origin + ``X-CSRF-Token``, for every mutation) →
``step_up_session`` (a fresh TOTP step-up, for control actions).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.config import WebSettings
from app.core.clock import Clock
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.web.auth import AuthService, AuthSession
from app.web.errors import ApiProblem

WEB_AUDIT_CHAIN = "web"
CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True)
class WebContext:
    settings: WebSettings
    db: Database
    clock: Clock
    audit: AuditLog
    auth: AuthService


def get_context(request: Request) -> WebContext:
    ctx: WebContext = request.app.state.ctx
    return ctx


Context = Annotated[WebContext, Depends(get_context)]


def session_cookie_name(settings: WebSettings) -> str:
    # The __Host- prefix makes browsers refuse the cookie unless it is Secure, host-only and Path=/. Local
    # development over plain http uses an unprefixed, non-Secure cookie on loopback instead.
    return "__Host-taa_session" if settings.is_production else "taa_session"


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def check_origin(request: Request, settings: WebSettings) -> None:
    """State-changing requests must come from the PWA's own origin (browsers always send Origin on POST)."""
    if request.headers.get("origin") not in settings.allowed_origins:
        raise ApiProblem(403, "origin_not_allowed", "Request origin is not allowed")


def current_session(request: Request, ctx: Context) -> AuthSession:
    session = ctx.auth.authenticate(request.cookies.get(session_cookie_name(ctx.settings)))
    if session is None:
        raise ApiProblem(401, "unauthenticated", "Sign in required")
    return session


CurrentSession = Annotated[AuthSession, Depends(current_session)]


def csrf_session(request: Request, ctx: Context, session: CurrentSession) -> AuthSession:
    check_origin(request, ctx.settings)
    if not ctx.auth.check_csrf(session, request.headers.get(CSRF_HEADER)):
        raise ApiProblem(403, "csrf_failed", "Missing or invalid CSRF token")
    return session


CsrfSession = Annotated[AuthSession, Depends(csrf_session)]


def step_up_session(ctx: Context, session: CsrfSession) -> AuthSession:
    if not ctx.auth.has_step_up(session):
        raise ApiProblem(403, "step_up_required", "Confirm with a current authenticator code")
    return session


StepUpSession = Annotated[AuthSession, Depends(step_up_session)]
