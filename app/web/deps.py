"""Shared state and FastAPI dependencies of the web service.

Dependency chain for protected routes: ``current_session`` (cookie → live session, else 401
``unauthenticated``) → ``csrf_session`` (allowed Origin + ``X-CSRF-Token``, for every mutation) →
``step_up_session`` (a fresh TOTP step-up, for control actions). Engine-scoped routes add ``owned_engine``.

Engine routes (ingest, command long poll) use ``signed_engine`` instead: the paired engine's HMAC signature
over method, path and query, timestamp, nonce and body (PLAN §A13). They never see a web session.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from starlette.concurrency import run_in_threadpool

from app.config import WebSettings
from app.core.clock import Clock
from app.security.hmac_auth import AuthError, Verified, Verifier
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.sync.command_queue import CommandQueue
from app.sync.ingest import IngestService
from app.web.auth import AuthService, AuthSession
from app.web.engines import ENGINE_ID_RE, EngineInfo, EngineRegistry
from app.web.errors import ApiProblem

log = logging.getLogger(__name__)

WEB_AUDIT_CHAIN = "web"
CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True)
class EngineLink:
    """Engine-facing services: the registry (keys and owners), signature verifier, ingest and the command
    queue engines poll."""

    registry: EngineRegistry
    verifier: Verifier
    ingest: IngestService
    commands: CommandQueue


@dataclass(frozen=True)
class WebContext:
    settings: WebSettings
    db: Database
    clock: Clock
    audit: AuditLog
    auth: AuthService
    engine: EngineLink


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


@dataclass(frozen=True)
class EngineRequest:
    link: EngineLink
    verified: Verified
    owner_user_id: str
    body: bytes

    @property
    def engine_id(self) -> str:
        return self.verified.engine_id


async def signed_engine(request: Request, ctx: Context) -> EngineRequest:
    """A request signed by an ACTIVE registered engine (unknown, revoked or forged: 401)."""
    link = ctx.engine
    body = await request.body()
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    try:  # the nonce store may hit the database
        verified = await run_in_threadpool(
            link.verifier.verify, request.method, target, request.headers, body
        )
    except AuthError as exc:
        log.warning("engine request %s %s refused: %s", request.method, request.url.path, exc)
        raise ApiProblem(401, "signature_invalid", "Request signature rejected") from exc
    owner = link.registry.owner_of(verified.engine_id)
    if owner is None:  # revoked between the key lookup and now
        raise ApiProblem(401, "signature_invalid", "Request signature rejected")
    await run_in_threadpool(link.registry.seen, verified.engine_id, previous_secret=verified.previous_secret)
    return EngineRequest(link, verified, owner, body)


SignedEngine = Annotated[EngineRequest, Depends(signed_engine)]


def owned_engine(engine_id: str, ctx: Context, session: CurrentSession) -> EngineInfo:
    """An engine of the session user (PLAN §A32). Anyone else's, or an unknown id, is 404 ``engine_not_found``
    (never 403), so ids cannot be probed. The OWNER role administers engines but reads only its own data."""
    info = ctx.engine.registry.get(engine_id) if ENGINE_ID_RE.fullmatch(engine_id) else None
    if info is None or info.owner_user_id != session.user_id:
        raise ApiProblem(404, "engine_not_found", "No such engine")
    return info


OwnedEngine = Annotated[EngineInfo, Depends(owned_engine)]
